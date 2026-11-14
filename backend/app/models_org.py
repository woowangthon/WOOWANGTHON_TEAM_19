"""계정·연결·학원·강의실·씨앗·상점·알림함 테이블 12개(명세 4.12, 설계 1112 §2·§10).

- 기존 학습 테이블 7개에는 열을 더하지 않는다(create_all은 새 테이블만 만든다).
- 모든 행에 created_at·trial_id(체험 세상이면 세트 id, 아니면 None) — 72시간 정리 대상.
- 비밀번호는 scrypt, 토큰·이메일은 sha256 해시만 저장한다(원문 없음).
- 학생 계정 id = 그 students 행 id(같은 값). 씨앗 기록·꾸미기의 학생 키도 이 id.
- 화면 시각(at, appliedAt)은 저장하지 않고 created_at 등에서 서울 시간으로 만든다(accounts.stamp_label).
"""

import datetime as dt
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
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
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(dt.UTC)


class _Stamped:
    """created_at·trial_id 공통 열."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    trial_id: Mapped[str | None] = mapped_column(String(20), index=True)


class Account(_Stamped, Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)  # a-<16> 또는 {t}-{key}
    login_id: Mapped[str] = mapped_column(String(40), unique=True)  # 전역 유일(체험은 _xxxx 접미사)
    pw_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(10))  # student / guardian / teacher / operator
    name: Mapped[str] = mapped_column(String(40))
    grade: Mapped[int | None] = mapped_column(Integer)
    email_hash: Mapped[str | None] = mapped_column(String(64), index=True)  # sha256(정규화 이메일)
    link_code: Mapped[str | None] = mapped_column(String(10), unique=True)
    academy_id: Mapped[str | None] = mapped_column(String(40))
    teacher_status: Mapped[str | None] = mapped_column(String(10))  # 승인 대기 / 승인됨
    application_id: Mapped[str | None] = mapped_column(String(40))
    outfit: Mapped[str | None] = mapped_column(String(20))  # 학생이 입은 옷(꾸미기 id)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    marketing: Mapped[bool] = mapped_column(Boolean, default=False)
    agreed_at: Mapped[date | None] = mapped_column(Date)
    student_id: Mapped[str | None] = mapped_column(String(40))  # 학생이면 students.id(= id)


class AuthToken(_Stamped, Base):
    __tablename__ = "auth_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)  # sha256(토큰)
    account_id: Mapped[str] = mapped_column(String(40), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Link(_Stamped, Base):
    __tablename__ = "links"

    student_account_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    guardian_account_id: Mapped[str] = mapped_column(String(40), primary_key=True, index=True)
    status: Mapped[str] = mapped_column(String(10))  # 대기 / 연결됨
    consent_at: Mapped[date | None] = mapped_column(Date)


class Academy(_Stamped, Base):
    __tablename__ = "academies"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    org_type: Mapped[str] = mapped_column(String(10))  # 학원 / 학교
    serial: Mapped[str] = mapped_column(String(20), unique=True)  # XXXX-XXXX
    owner_id: Mapped[str] = mapped_column(String(40), index=True)
    entry_code: Mapped[str | None] = mapped_column(String(10))
    entry_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 수업 타이머 알림 시점(분 전, 큰 것부터 쉼표로). 원장만 바꾼다(11-12, 결정 「강의실 수업 타이머」)
    timer_alerts: Mapped[str] = mapped_column(String(20), default="10,5")


class AcademyApplication(_Stamped, Base):
    __tablename__ = "academy_applications"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(40), index=True)
    owner_name: Mapped[str] = mapped_column(String(40))
    org_type: Mapped[str] = mapped_column(String(10))
    academy_name: Mapped[str] = mapped_column(String(60))
    # 심사 화면에 보여야 해서 원문(화면에 「예시 값」 안내, 설계 §7)
    biz_no: Mapped[str] = mapped_column(String(20), default="")
    ceo: Mapped[str] = mapped_column(String(40), default="")
    phone: Mapped[str] = mapped_column(String(30), default="")
    address: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(10))  # 심사 중 / 승인 / 반려
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    serial: Mapped[str | None] = mapped_column(String(20))
    reject_reason: Mapped[str | None] = mapped_column(Text)


class Room(_Stamped, Base):
    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    academy_id: Mapped[str] = mapped_column(String(40), index=True)
    teacher_id: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(60))
    plan: Mapped[str] = mapped_column(String(120), default="")


class RoomPerson(_Stamped, Base):
    __tablename__ = "room_people"

    room_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    student_account_id: Mapped[str] = mapped_column(String(40), primary_key=True, index=True)
    state: Mapped[str] = mapped_column(String(10))  # member / invited / requested


class SeedLedger(_Stamped, Base):
    __tablename__ = "seed_ledger"
    __table_args__ = (Index("ix_ledger_student_date", "student_account_id", "date"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=_uuid)
    student_account_id: Mapped[str] = mapped_column(String(40))  # = students.id
    date: Mapped[dt.date] = mapped_column(Date)  # 서울 날짜(하루 1번 규칙용)
    amount: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(
        String(20)
    )  # 학습 완료 / 보호자 도장 / 학습지도자 칭찬 / 상점 구매 / 꾸미기 구매
    note: Mapped[str] = mapped_column(String(60), default="")
    by: Mapped[str] = mapped_column(String(40))  # system 또는 계정 id
    # 두 재화(결정 11-11): seed = 씨앗(학원 상점), stamp = 칭찬 도장(캐릭터 옷). 잔액은 재화별 합
    currency: Mapped[str] = mapped_column(String(5), default="seed")
    # 하루 1번 출처(학습 완료·보호자 도장)만 "{학생}:{출처}:{서울 날짜}", 나머지 None.
    # 유일 제약이 동시 요청의 두 번째 줄을 DB에서 막는다(보안 검토 11-12, seeds.add_seed).
    once_key: Mapped[str | None] = mapped_column(String(100), unique=True)


class ShopItem(_Stamped, Base):
    __tablename__ = "shop_items"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    teacher_id: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(60))
    price: Mapped[int] = mapped_column(Integer)
    stock: Mapped[int | None] = mapped_column(Integer)  # None = 무제한
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str] = mapped_column(String(120), default="")


class Order(_Stamped, Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    student_account_id: Mapped[str] = mapped_column(String(40), index=True)
    teacher_id: Mapped[str] = mapped_column(String(40), index=True)
    item_name: Mapped[str] = mapped_column(String(60))
    price: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10))  # 교환 요청 / 전달 완료


class CosmeticOwned(_Stamped, Base):
    __tablename__ = "cosmetics_owned"

    student_account_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    cosmetic_id: Mapped[str] = mapped_column(String(20), primary_key=True)


class Notice(_Stamped, Base):
    __tablename__ = "notices"
    __table_args__ = (Index("ix_notice_account_created", "account_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=_uuid)
    account_id: Mapped[str] = mapped_column(String(40))
    text: Mapped[str] = mapped_column(Text)
    to_path: Mapped[str | None] = mapped_column(String(60))
    read: Mapped[bool] = mapped_column(Boolean, default=False)


class SessionProblem(_Stamped, Base):
    """한 세션에 잇는 문제 순서(SESSION_PROBLEMS > 1일 때만 행이 생긴다, 11-12).

    sessions 열은 늘리지 않는다: 지금 문제는 sessions.problem_id, 지금 힌트는 sessions.hint_level.
    이 표는 순서와 끝난 문제의 결과만 적는다.
    """

    __tablename__ = "session_problems"
    __table_args__ = (UniqueConstraint("session_id", "idx", name="uq_session_problem_idx"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    idx: Mapped[int] = mapped_column(Integer)  # 0부터
    problem_id: Mapped[str] = mapped_column(String(40))
    # 이 문제를 시작할 때 세션의 마지막 메시지 순번. 정답 판정은 이보다 큰 순번만 본다
    start_seq: Mapped[int] = mapped_column(Integer, default=0)
    hint_level: Mapped[int] = mapped_column(Integer, default=0)  # 끝낼 때의 힌트 단계
    finished: Mapped[bool] = mapped_column(Boolean, default=False)
    assisted: Mapped[bool] = mapped_column(Boolean, default=False)  # 정답 없이 풀이 보기로 끝냄


# --- 강의실 수업 진행·공지/숙제(명세 4.12 5-4, 재하 시나리오 11-13) ------------------------
# 시각은 화면과 같은 epoch 밀리초(BigInteger). 학생 목록은 저장하지 않고 room_people에서 그때그때 읽는다.


class ClassLive(_Stamped, Base):
    """강의실마다 지금(또는 마지막) 수업 한 줄. 새 수업을 시작하면 같은 행을 덮어쓴다."""

    __tablename__ = "class_live"

    class_id: Mapped[str] = mapped_column(String(40), primary_key=True)  # rooms.id
    academy_id: Mapped[str] = mapped_column(String(40), index=True)
    phase: Mapped[str] = mapped_column(String(10))  # class / break
    start_at: Mapped[int] = mapped_column(BigInteger)
    end_at: Mapped[int] = mapped_column(BigInteger)
    closed_at: Mapped[int | None] = mapped_column(BigInteger)
    joined: Mapped[list[Any]] = mapped_column(JSON, default=list)  # [{id, at}]
    removed: Mapped[list[Any]] = mapped_column(JSON, default=list)  # [학생 id]


class ClassLiveSetting(_Stamped, Base):
    """학원별 수업 기본값과 강의실 장소."""

    __tablename__ = "class_live_settings"

    academy_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    defaults: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    places: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # {class_id: 장소}


class ClassPost(_Stamped, Base):
    """강의실 공지·숙제. 댓글·1:1 채팅은 없다(아이 안전)."""

    __tablename__ = "class_posts"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    class_id: Mapped[str] = mapped_column(String(40), index=True)
    academy_id: Mapped[str] = mapped_column(String(40), index=True)
    kind: Mapped[str] = mapped_column(String(10))  # notice / homework
    title: Mapped[str] = mapped_column(String(40))
    body: Mapped[str] = mapped_column(Text, default="")
    due: Mapped[str | None] = mapped_column(String(10))  # YYYY-MM-DD
    at: Mapped[int] = mapped_column(BigInteger)
    done: Mapped[list[Any]] = mapped_column(JSON, default=list)  # 「다 했어」 누른 학생 id
