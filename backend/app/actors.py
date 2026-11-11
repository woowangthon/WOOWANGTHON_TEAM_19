"""데모 배우 대응표와 신원 해석 함수 하나(명세 4.4 공통 헤더, 부록 E 역할 선택).

실서비스는 학원·계정·보호자–학생 연결(N:M, 동의 기록)·강사–학생 배정 테이블로 바꾼다 — 명세 4.2 후속(작성 예정). 이 함수 속만 바꾸면 된다.

- 아이·보호자·강사 인증은 전부 actor_from_request(헤더 없음 401 → 역할 다름 403 → resolve_actor)를
  거친다. 역할별 의존성(current_child·current_guardian_child·current_instructor)은 껍데기다(B6).
  로그인을 넣을 때는 이 함수 안에서 갈린다(지금은 데모 헤더 한 갈래).
- 아이: 학생 행 id를 그대로 받는다(데모 아이 id도 학생 행 id다).
- 보호자: 대응표에 있는 id만 받는다. 없으면 404 guardian_not_found.
- 강사: 강사 테이블이 없어 11-15는 비어 있지 않은 actor면 받는다.
"""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.models import Student

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


async def _student_or_404(db: AsyncSession, student_id: str) -> Student:
    student = await db.get(Student, student_id)
    if student is None:
        raise ApiError(404, "student_not_found", "학생을 찾을 수 없어요.")
    return student


async def resolve_actor(db: AsyncSession, role: str, actor_id: str) -> Actor:
    if role == "child":
        return Actor(role, actor_id, await _student_or_404(db, actor_id))
    if role == "guardian":
        child_id = GUARDIAN_TO_CHILD.get(actor_id)
        if child_id is None:
            raise ApiError(404, "guardian_not_found", "보호자를 찾을 수 없어요.")
        return Actor(role, actor_id, await _student_or_404(db, child_id))
    if role == "instructor":
        return Actor(role, actor_id, None)
    raise ApiError(403, "forbidden", "알 수 없는 역할이에요.")


# 역할별 403 문구(전과 같게)
_FORBIDDEN = {
    "child": "아이 화면에서만 쓸 수 있어요.",
    "guardian": "보호자 화면에서만 쓸 수 있어요.",
    "instructor": "강사 화면에서만 쓸 수 있어요.",
}


async def actor_from_request(
    db: AsyncSession, want_role: str, x_demo_role: str | None, x_demo_actor: str | None
) -> Actor:
    """데모 헤더 → Actor. 헤더 없음 401 no_actor → 역할 다름 403 forbidden → resolve_actor."""
    # 강사는 학생 행이 없어 공백 actor도 헤더 없음으로 본다(아이·보호자는 resolve_actor가 404)
    blank = not x_demo_actor or (want_role == "instructor" and not x_demo_actor.strip())
    if not x_demo_role or blank:
        raise ApiError(401, "no_actor", "데모 역할·행위자 헤더가 없어요.")
    if x_demo_role != want_role:
        raise ApiError(403, "forbidden", _FORBIDDEN[want_role])
    assert x_demo_actor is not None
    return await resolve_actor(db, want_role, x_demo_actor)
