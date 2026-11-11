"""테이블 7개 (명세 4.2). PK는 UUID 문자열, 시드 문제만 고정 ID.

- 학생에 실명 칸 없음. 스타일은 동물명이 아니라 스타일 코드(EBSP/EQLC/DQSC).
- 메시지는 PII 치환본만, 생성 + 72시간 만료. 알림은 생성 + 90일 만료.
- 삭제는 만료 시각 방식(`DELETE WHERE expires_at < now()`), 11-15는 열만 둔다.
"""

import datetime as dt
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

MESSAGE_TTL = timedelta(hours=72)
ALERT_TTL = timedelta(days=90)
EXCERPT_MAX = 300


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[str]: JSON}


class Student(Base):
    __tablename__ = "students"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    nickname: Mapped[str] = mapped_column(String(40))  # 프롬프트에는 넣지 않는다
    grade_band: Mapped[str] = mapped_column(String(20))
    style: Mapped[str] = mapped_column(String(4), default="EBSP")  # EBSP / EQLC / DQSC
    honorific: Mapped[str] = mapped_column(String(10), default="friend")  # hyung/unni/friend
    polite: Mapped[bool] = mapped_column(Boolean, default=False)  # True = 존댓말
    streak_days: Mapped[int] = mapped_column(Integer, default=0)
    last_streak_date: Mapped[date | None] = mapped_column(Date)
    freezes: Mapped[int] = mapped_column(Integer, default=2)
    fence_codes: Mapped[list[str]] = mapped_column(default=list)  # 울타리 코드 4항목
    guardian_contact_enc: Mapped[str | None] = mapped_column(Text)  # 암호화된 값만
    consent: Mapped[bool] = mapped_column(Boolean, default=False)
    today_task_problem_id: Mapped[str | None] = mapped_column(ForeignKey("problems.id"))
    today_task_date: Mapped[date | None] = mapped_column(Date)
    # 체험 세트 발급 상한을 DB에서 세는 데 쓴다(명세 4.11-5). 기존 행은 비어 있을 수 있다
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(dt.UTC)
    )


class Problem(Base):
    __tablename__ = "problems"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)  # frac-div-nat-01 식
    tag: Mapped[str] = mapped_column(String(40), index=True)
    standard: Mapped[dict[str, Any]] = mapped_column()
    grade: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    expr: Mapped[str] = mapped_column(String(100))
    answer: Mapped[dict[str, Any]] = mapped_column()  # 서버 판정 전용, 프롬프트 금지
    hint1: Mapped[str] = mapped_column(Text)
    hint2: Mapped[str] = mapped_column(Text)
    solution: Mapped[str] = mapped_column(Text)
    forbidden: Mapped[list[str]] = mapped_column(default=list)


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (UniqueConstraint("student_id", "date", name="uq_session_student_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)  # 토큰 겸용
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    date: Mapped[dt.date] = mapped_column(Date)  # Asia/Seoul 날짜
    state: Mapped[str] = mapped_column(String(10), default="study")
    hint_level: Mapped[int] = mapped_column(Integer, default=0)
    problem_id: Mapped[str | None] = mapped_column(ForeignKey("problems.id"))
    phase_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    flag: Mapped[str] = mapped_column(String(10), default="green")  # green / red
    study_summary: Mapped[list[str] | None] = mapped_column()
    guardian_line: Mapped[str | None] = mapped_column(Text)
    quiz_problem_id: Mapped[str | None] = mapped_column(ForeignKey("problems.id"))
    streak_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    chat_only: Mapped[bool] = mapped_column(Boolean, default=False)
    end_reason: Mapped[str | None] = mapped_column(String(10))  # normal / crisis
    prompt_version: Mapped[str | None] = mapped_column(String(20))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 멘토 답(LLM) 생성 중 표시. 지나면 무효(죽은 요청 대비). 그 사이 온 조각은 흡수(11-11)
    replying_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    study_sec: Mapped[int | None] = mapped_column(Integer)  # study를 떠날 때 쓴 초(표시용)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("session_id", "seq", name="uq_message_session_seq"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(10))  # child / mentor
    text_redacted: Mapped[str] = mapped_column(Text)  # PII 치환본만. 원문 저장 금지
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    # 한 번의 멘토 답이 다룬 아이 조각들과 그 답이 공유한다. 멘토 행과 같은 turn_id = 답 받은 조각
    turn_id: Mapped[str | None] = mapped_column(String(36), index=True)
    judge: Mapped[str | None] = mapped_column(String(10))  # 아이 study 조각만 correct / wrong

    @classmethod
    def new(
        cls,
        *,
        session_id: str,
        seq: int,
        role: str,
        text_redacted: str,
        now: datetime,
        turn_id: str | None = None,
        judge: str | None = None,
    ):
        return cls(
            session_id=session_id,
            seq=seq,
            role=role,
            text_redacted=text_redacted,
            expires_at=now + MESSAGE_TTL,
            turn_id=turn_id,
            judge=judge,
        )


class Misconception(Base):
    __tablename__ = "misconceptions"
    __table_args__ = (UniqueConstraint("student_id", "tag", name="uq_misconception_student_tag"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    tag: Mapped[str] = mapped_column(String(40))
    first_wrong_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), default="open")  # open / resolved


class InstructorNote(Base):
    __tablename__ = "instructor_notes"
    __table_args__ = (Index("ix_note_student_date", "student_id", "date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    date: Mapped[dt.date] = mapped_column(Date)
    covered: Mapped[str] = mapped_column(Text, default="")
    stuck: Mapped[str] = mapped_column(Text, default="")
    homework: Mapped[str] = mapped_column(Text, default="")
    memo_redacted: Mapped[str] = mapped_column(Text, default="")  # 치환본
    draft_body: Mapped[str | None] = mapped_column(Text)
    facts: Mapped[dict[str, Any] | None] = mapped_column()
    final_body: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="draft")  # draft/published/skipped
    prompt_version: Mapped[str | None] = mapped_column(String(20))


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alert_student_created", "student_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    level: Mapped[str] = mapped_column(String(10), default="red")
    trigger: Mapped[str] = mapped_column(String(20))  # 키워드 id (R1 등)
    excerpt: Mapped[str] = mapped_column(String(EXCERPT_MAX))  # ±2턴 치환본, 300자
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    guardian_seen: Mapped[bool] = mapped_column(Boolean, default=False)

    @classmethod
    def new(cls, *, session_id: str, student_id: str, trigger: str, excerpt: str, now: datetime):
        return cls(
            session_id=session_id,
            student_id=student_id,
            trigger=trigger,
            excerpt=excerpt[:EXCERPT_MAX],
            created_at=now,
            expires_at=now + ALERT_TTL,
        )
