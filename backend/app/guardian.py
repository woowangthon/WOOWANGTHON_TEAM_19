"""API 11번 GET /guardian/today — 보호자 「오늘」 카드 하나(명세 3.3·4.4).

- 신원은 X-Demo-Role: guardian / X-Demo-Actor: 보호자 id → resolve_actor가 학생으로 푼다.
- 키는 항상 4개(빈 값도 같은 모양, 명세 4.8-4). 대화 내용은 싣지 않는다(명세 3.3).
- 읽기만 한다. 세션 마감 전이·보호자 확인 표시는 여기서 하지 않는다.
"""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts import CurrentAccount, token_sent
from app.actors import actor_from_request
from app.api import HOTLINES
from app.db import get_db
from app.models import Alert, InstructorNote, Problem, Session, Student
from app.pii import unredact_name
from app.timeutil import as_utc, get_now, seoul_date

router = APIRouter(prefix="/guardian")

Db = Annotated[AsyncSession, Depends(get_db)]
Now = Annotated[datetime, Depends(get_now)]


async def current_guardian_child(
    request: Request,
    db: Db,
    account: CurrentAccount,
    x_demo_role: Annotated[str | None, Header()] = None,
    x_demo_actor: Annotated[str | None, Header()] = None,
) -> Student:
    """보호자 계정(연결된 첫 아이) 또는 보호자 헤더를 확인하고 그 보호자의 학생을 돌려준다."""
    actor = await actor_from_request(
        db, "guardian", x_demo_role, x_demo_actor, account=account, token_sent=token_sent(request)
    )
    student = actor.student
    assert student is not None  # guardian 역할은 학생이 없으면 resolve_actor가 404
    return student


GuardianChild = Annotated[Student, Depends(current_guardian_child)]


async def _today_alert(db: AsyncSession, student: Student, now: datetime) -> dict[str, Any] | None:
    """오늘(서울 날짜) 가장 최근 알림. SQLite가 시간대를 버려서 날짜 비교는 파이썬에서 한다.
    발췌는 싣지 않는다(11-12 결정: 보호자에게는 분류·긴급도·행동 안내만, 동의 문구와 일치)."""
    today = seoul_date(now)
    alerts = await db.scalars(
        select(Alert).where(Alert.student_id == student.id).order_by(Alert.created_at.desc())
    )
    for alert in alerts:
        created = as_utc(alert.created_at)
        assert created is not None
        if seoul_date(created) == today:
            return {
                "created_at": created.isoformat(),
                "hotlines": list(HOTLINES),
            }
    return None


@router.get("/today")
async def guardian_today(db: Db, now: Now, student: GuardianChild) -> dict[str, Any]:
    today = seoul_date(now)
    session = await db.scalar(
        select(Session).where(Session.student_id == student.id, Session.date == today)
    )
    child_line = None
    quiz = None
    if session is not None:
        if session.state == "ended":
            child_line = session.guardian_line
        if session.quiz_problem_id:
            problem = await db.get(Problem, session.quiz_problem_id)
            quiz = {"text": problem.text} if problem is not None else None
    comment = await db.scalar(
        select(InstructorNote.final_body)
        .where(
            InstructorNote.student_id == student.id,
            InstructorNote.date == today,
            InstructorNote.status == "published",
        )
        .limit(1)
    )
    return {
        "alert": await _today_alert(db, student, now),
        "child_line": child_line,
        "quiz": quiz,
        # 저장본은 치환본. 보호자 화면에 보이기 직전에만 별명으로 되돌린다(11-11 A6)
        "instructor_comment": unredact_name(comment, student.nickname),
    }
