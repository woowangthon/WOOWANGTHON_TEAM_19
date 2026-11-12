"""데모 배우 대응표와 신원 해석 함수 하나(명세 4.4 공통 헤더, 부록 E 역할 선택).

실서비스는 학원·계정·보호자–학생 연결(N:M, 동의 기록)·강사–학생 배정 테이블로 바꾼다 — 명세 4.2 후속(작성 예정). 이 함수 속만 바꾸면 된다.

- 아이·보호자·강사 인증은 전부 actor_from_request(헤더 없음 401 → 역할 다름 403 → resolve_actor)를
  거친다. 역할별 의존성(current_child·current_guardian_child·current_instructor)은 껍데기다(B6).
  로그인을 넣을 때는 이 함수 안에서 갈린다(지금은 데모 헤더 한 갈래).
- 아이: 학생 행 id를 그대로 받는다(데모 아이 id도 학생 행 id다).
- 보호자: 대응표에 있는 id만 받는다. 없으면 404 guardian_not_found.
- 강사: 강사 테이블이 없어 11-15는 비어 있지 않은 actor면 받는다.
- 공개 체험 세트(명세 4.11): 보호자 `t-…-guardian`은 같은 세트 `t-…-child`로, 학습지도자
  `t-…-instructor`는 scope = 같은 세트 아이 id(그 아이만 본다). 다른 강사는 scope None(전체).
- 계정(명세 4.12, 설계 §10): 유효한 쿠키/Bearer가 있으면 데모 헤더보다 먼저. 학생 = 자기 students 행,
  보호자 = 연결된 첫 아이(없으면 404 not_linked), 학습지도자 = allowed(내 강의실 member 학생),
  운영자 = 학습 API 403. 토큰이 왔는데 만료·로그아웃이고 데모 헤더도 없으면 401 not_logged_in.
- 학습지도자 범위 판단은 `instructor_allows(actor, student_id)` 한 곳.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import config
from app.accounts import first_child_id
from app.errors import ApiError
from app.models import Student
from app.models_org import Account, Room, RoomPerson
from app.trial import instructor_can_see, is_trial_actor, trial_child_of

DEMO_CHILD_ID = "demo-child-minsu"
DEMO_GUARDIAN_ID = "demo-guardian-minsu"
DEMO_INSTRUCTOR_ID = "demo-instructor"

# 보호자 id → 학생 id (데모 배우만)
GUARDIAN_TO_CHILD = {DEMO_GUARDIAN_ID: DEMO_CHILD_ID}


@dataclass(frozen=True)
class Actor:
    role: str  # child / guardian / instructor
    id: str
    student: Student | None  # 아이·보호자는 해당 학생, 강사는 None
    scope: str | None = None  # 체험 학습지도자만: 볼 수 있는 아이 id 하나. None = 전체
    # 계정 학습지도자만: 내 강의실 member 학생 id. None = 체험 헤더 규칙(scope)
    allowed: frozenset[str] | None = None


def instructor_allows(actor: Actor, student_id: str) -> bool:
    """학습지도자가 이 학생을 볼 수 있는지. 계정이면 내 강의실 member, 아니면 체험 헤더 규칙."""
    if actor.allowed is not None:
        return student_id in actor.allowed
    return instructor_can_see(actor.id, student_id)


def instructor_scope(actor_id: str) -> str | None:
    """체험 학습지도자면 같은 세트 아이 id, 아니면 None(전체)."""
    return trial_child_of(actor_id, "instructor")


async def _student_or_404(db: AsyncSession, student_id: str) -> Student:
    student = await db.get(Student, student_id)
    if student is None:
        raise ApiError(404, "student_not_found", "학생을 찾을 수 없어요.")
    return student


async def resolve_actor(db: AsyncSession, role: str, actor_id: str) -> Actor:
    if role == "child":
        # 실제 가입 학생(체험 아닌 계정)은 데모 헤더로 못 쓴다 — TRIAL_ONLY가 꺼져 있어도(11-12 A3)
        acc = await db.get(Account, actor_id)
        if acc is not None and acc.trial_id is None:
            raise ApiError(
                403, "trial_only", "체험 계정으로만 쓸 수 있어요. 처음부터 다시 시작해 주세요."
            )
        return Actor(role, actor_id, await _student_or_404(db, actor_id))
    if role == "guardian":
        child_id = GUARDIAN_TO_CHILD.get(actor_id) or trial_child_of(actor_id, "guardian")
        if child_id is None:
            raise ApiError(404, "guardian_not_found", "보호자를 찾을 수 없어요.")
        return Actor(role, actor_id, await _student_or_404(db, child_id))
    if role == "instructor":
        scope = instructor_scope(actor_id)
        # 체험 세트가 DB에 없으면(재배포·만료) 404 → 프론트가 새 세트를 받는다
        if scope is not None and await db.get(Student, scope) is None:
            raise ApiError(404, "trial_not_found", "체험이 끝났어요. 처음부터 다시 시작해 주세요.")
        return Actor(role, actor_id, None, scope)
    raise ApiError(403, "forbidden", "알 수 없는 역할이에요.")


# 역할별 403 문구(전과 같게)
_FORBIDDEN = {
    "child": "아이 화면에서만 쓸 수 있어요.",
    "guardian": "보호자 화면에서만 쓸 수 있어요.",
    "instructor": "강사 화면에서만 쓸 수 있어요.",
}


# 계정 역할 → 학습 역할
_ACCOUNT_ROLE = {"student": "child", "guardian": "guardian", "teacher": "instructor"}


async def room_members(db: AsyncSession, teacher_id: str) -> frozenset[str]:
    """학습지도자의 강의실 member 학생 id(= students.id)."""
    rows = await db.scalars(
        select(RoomPerson.student_account_id)
        .join(Room, Room.id == RoomPerson.room_id)
        .where(Room.teacher_id == teacher_id, RoomPerson.state == "member")
    )
    return frozenset(rows)


async def actor_from_account(db: AsyncSession, want_role: str, account: Account) -> Actor:
    """로그인 계정 → 기존 학습 신원(설계 §10)."""
    if account.role == "operator":
        raise ApiError(403, "forbidden", "운영자 계정은 학습 화면을 쓸 수 없어요.")
    if _ACCOUNT_ROLE.get(account.role) != want_role:
        raise ApiError(403, "forbidden", _FORBIDDEN[want_role])
    if want_role == "child":
        return Actor("child", account.id, await _student_or_404(db, account.student_id or ""))
    if want_role == "guardian":
        child_id = await first_child_id(db, account.id)
        if child_id is None:
            raise ApiError(404, "not_linked", "먼저 아이와 연결해 주세요.")
        return Actor("guardian", account.id, await _student_or_404(db, child_id))
    return Actor("instructor", account.id, None, None, await room_members(db, account.id))


async def actor_from_request(
    db: AsyncSession,
    want_role: str,
    x_demo_role: str | None,
    x_demo_actor: str | None,
    *,
    account: Account | None = None,
    token_sent: bool = False,
) -> Actor:
    """계정이 먼저. 없으면 데모 헤더 → Actor.

    데모 헤더: 헤더 없음 401 no_actor → 역할 다름 403 forbidden → resolve_actor.
    토큰은 왔는데 계정이 없고(만료·로그아웃) 데모 헤더도 없으면 401 not_logged_in.
    """
    if account is not None:
        return await actor_from_account(db, want_role, account)
    if token_sent and not (x_demo_role and x_demo_actor):
        raise ApiError(401, "not_logged_in", "로그인이 필요해요.")
    # 강사는 학생 행이 없어 공백 actor도 헤더 없음으로 본다(아이·보호자는 resolve_actor가 404)
    blank = not x_demo_actor or (want_role == "instructor" and not x_demo_actor.strip())
    if not x_demo_role or blank:
        raise ApiError(401, "no_actor", "데모 역할·행위자 헤더가 없어요.")
    if x_demo_role != want_role:
        raise ApiError(403, "forbidden", _FORBIDDEN[want_role])
    assert x_demo_actor is not None
    # 공개 배포는 체험 세트만(11-11). 공용 데모 아이·보호자·임의 강사 id는 막는다
    if config.trial_only() and not is_trial_actor(x_demo_actor, want_role):
        raise ApiError(
            403, "trial_only", "체험 계정으로만 쓸 수 있어요. 처음부터 다시 시작해 주세요."
        )
    return await resolve_actor(db, want_role, x_demo_actor)
