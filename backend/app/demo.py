"""API 1번 POST /demo/reset — 시드 day3 하나(명세 4.4·4.8-3·부록 E).

- 헤더 X-Demo-Token이 환경변수 DEMO_TOKEN과 같아야 한다. 토큰은 로그·응답에 싣지 않는다.
- 한 트랜잭션: 시드 문제 적재 → 데모 아이의 세션·메시지·알림·오개념·강사 노트 삭제 →
  학생 행을 day3 상태로 다시 만든다. 데모 배우가 아닌 행은 건드리지 않는다. 여러 번 불러도 같은 상태.
- timer_scale은 테이블 칸이 없어 프로세스 메모리(config.set_timer_scale)에 둔다.
"""

import hmac
import logging
from datetime import date, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import config
from app.actors import DEMO_CHILD_ID, DEMO_GUARDIAN_ID, DEMO_INSTRUCTOR_ID
from app.db import get_db
from app.errors import ApiError
from app.models import Alert, InstructorNote, Message, Misconception, Problem, Session, Student
from app.seed import load_seed
from app.timeutil import get_now, seoul_date

log = logging.getLogger(__name__)

router = APIRouter(prefix="/demo")

Db = Annotated[AsyncSession, Depends(get_db)]
Now = Annotated[datetime, Depends(get_now)]

ACTORS = [
    {"role": "child", "id": DEMO_CHILD_ID, "label": "지우"},
    {"role": "guardian", "id": DEMO_GUARDIAN_ID, "label": "지우 보호자"},
    {"role": "instructor", "id": DEMO_INSTRUCTOR_ID, "label": "강사"},
]

# day3 오개념: (태그, 상태, 처음 틀린 날 = 오늘 - n일). 태그는 시드 4태그 중에서.
DAY3_MISCONCEPTIONS = [
    ("frac-div-nat", "open", 2),
    ("frac-div-frac-diff", "open", 1),
    ("nat-div-nat", "resolved", 2),
]
TODAY_TASK_EXPR = "3/4 / 2"  # 명세 3.2의 "3/4 ÷ 2"


async def require_demo_token(x_demo_token: Annotated[str | None, Header()] = None) -> None:
    expected = config.demo_token()
    if not expected or not x_demo_token:
        raise ApiError(403, "forbidden", "시연자만 쓸 수 있어요.")
    if not hmac.compare_digest(x_demo_token.encode(), expected.encode()):
        raise ApiError(403, "forbidden", "시연자만 쓸 수 있어요.")


class ResetBody(BaseModel):
    scenario: Literal["day3"] = "day3"
    style: Literal["EBSP", "EQLC", "DQSC"] = "EBSP"
    honorific: Literal["hyung", "unni", "friend"] = "hyung"
    polite: bool = False
    # 생략하면 리셋이 정한 배율을 지우고 환경변수 TIMER_SCALE(없으면 1)로 돌아간다
    timer_scale: float | None = Field(default=None, gt=0, allow_inf_nan=False)


async def _wipe_demo_child(db: AsyncSession, *, keep_notes: bool = False) -> None:
    """keep_notes=True면 강사 노트(메모·코멘트)는 남긴다(compat /demo/restart, 11-11)."""
    sessions = select(Session.id).where(Session.student_id == DEMO_CHILD_ID)
    await db.execute(delete(Message).where(Message.session_id.in_(sessions)))
    await db.execute(delete(Alert).where(Alert.student_id == DEMO_CHILD_ID))
    await db.execute(delete(Session).where(Session.student_id == DEMO_CHILD_ID))
    await db.execute(delete(Misconception).where(Misconception.student_id == DEMO_CHILD_ID))
    if not keep_notes:
        await db.execute(delete(InstructorNote).where(InstructorNote.student_id == DEMO_CHILD_ID))


async def _today_task_problem(db: AsyncSession) -> str | None:
    pid = await db.scalar(select(Problem.id).where(Problem.expr == TODAY_TASK_EXPR).limit(1))
    if pid is not None:
        return pid
    # 시드가 바뀌어 3/4 ÷ 2가 없으면 첫 미해결 태그의 첫 문제
    first_open = next(tag for tag, status, _ in DAY3_MISCONCEPTIONS if status == "open")
    return await db.scalar(
        select(Problem.id).where(Problem.tag == first_open).order_by(Problem.id).limit(1)
    )


async def _write_day3_student(
    db: AsyncSession,
    body: ResetBody,
    today: date,
    student_id: str = DEMO_CHILD_ID,
    consent: bool = True,
    nickname: str = "지우",
) -> None:
    """student_id 학생을 day3로. 체험 세트(명세 4.11)는 consent=False로 약속 화면부터.
    새로 가입한 학생(명세 4.12-5)은 nickname = 가입 이름(프롬프트에는 안 넣는다)."""
    values: dict[str, Any] = {
        "nickname": nickname,  # 기본은 합성 배우(프론트 체험 계정 jiwoo와 같은 이름, 11-11)
        "grade_band": "초5-6",
        "style": body.style,
        "honorific": body.honorific,
        "polite": body.polite,
        "streak_days": 3,
        "last_streak_date": today - timedelta(days=1),
        "freezes": 2,
        "fence_codes": [],
        "guardian_contact_enc": None,
        "consent": consent,  # 데모 day3 = 약속 화면을 이미 지난 아이
        "today_task_problem_id": await _today_task_problem(db),
        "today_task_date": today,
    }
    student = await db.get(Student, student_id)
    if student is None:
        db.add(Student(id=student_id, **values))
    else:
        for key, value in values.items():
            setattr(student, key, value)
    await db.flush()
    for tag, status, days_ago in DAY3_MISCONCEPTIONS:
        db.add(
            Misconception(
                student_id=student_id,
                tag=tag,
                status=status,
                first_wrong_date=today - timedelta(days=days_ago),
            )
        )
    await db.flush()


async def ensure_demo_actors(db: AsyncSession, now: datetime) -> bool:
    """기동 시: 데모 아이 행이 없을 때만 리셋과 같은 day3 상태를 만든다(있으면 아무것도 안 함).

    배포 DB가 휘발성이라(재시작·재배포·슬립 뒤 빈 DB) /demo/reset 전에도 배우가 있어야 한다.
    커밋은 호출하는 쪽이 한다. timer_scale은 건드리지 않는다.
    """
    if await db.get(Student, DEMO_CHILD_ID) is not None:
        return False
    await _wipe_demo_child(db)  # 학생 행 없이 남은 고아 행이 있으면 정리
    await _write_day3_student(db, ResetBody(), seoul_date(now))
    return True


@router.post("/reset", dependencies=[Depends(require_demo_token)])
async def reset(
    db: Db, now: Now, body: Annotated[ResetBody | None, Body()] = None
) -> dict[str, Any]:
    body = body or ResetBody()
    today = seoul_date(now)
    await load_seed(db)
    await _wipe_demo_child(db)
    await _write_day3_student(db, body, today)
    await db.commit()
    if body.timer_scale is None:
        config.clear_timer_scale()
    else:
        config.set_timer_scale(body.timer_scale)
    log.info("demo reset scenario=%s style=%s", body.scenario, body.style)
    return {"ok": True, "actors": ACTORS, "date": today.isoformat()}
