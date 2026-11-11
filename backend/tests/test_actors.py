"""actors.resolve_actor — 데모 배우 대응표로 신원을 푼다(명세 부록 E 역할 선택). 합성 값만."""

import pytest

from app.actors import (
    DEMO_CHILD_ID,
    DEMO_GUARDIAN_ID,
    DEMO_INSTRUCTOR_ID,
    actor_from_request,
    resolve_actor,
)
from app.errors import ApiError


async def test_fixed_demo_ids():
    assert DEMO_CHILD_ID == "demo-child-minsu"
    assert DEMO_GUARDIAN_ID == "demo-guardian-minsu"
    assert DEMO_INSTRUCTOR_ID == "demo-instructor"


async def test_child_resolves_any_student_row(db_session, make_student):
    s = make_student()
    db_session.add(s)
    await db_session.flush()
    actor = await resolve_actor(db_session, "child", s.id)
    assert actor.role == "child"
    assert actor.id == s.id
    assert actor.student is s


async def test_child_unknown_student_is_404(db_session):
    with pytest.raises(ApiError) as e:
        await resolve_actor(db_session, "child", "nope")
    assert (e.value.status, e.value.code) == (404, "student_not_found")


async def test_guardian_maps_to_demo_child(db_session, make_student):
    db_session.add(make_student(id=DEMO_CHILD_ID))
    await db_session.flush()
    actor = await resolve_actor(db_session, "guardian", DEMO_GUARDIAN_ID)
    assert actor.role == "guardian"
    assert actor.student is not None and actor.student.id == DEMO_CHILD_ID


async def test_guardian_unknown_id_is_404(db_session, make_student):
    s = make_student()
    db_session.add(s)
    await db_session.flush()
    # 학생 id를 보호자 id로 넣어도 대응표에 없으면 404
    for actor_id in ("nope", s.id):
        with pytest.raises(ApiError) as e:
            await resolve_actor(db_session, "guardian", actor_id)
        assert (e.value.status, e.value.code) == (404, "guardian_not_found")


async def test_guardian_before_reset_child_missing_is_404(db_session):
    with pytest.raises(ApiError) as e:
        await resolve_actor(db_session, "guardian", DEMO_GUARDIAN_ID)
    assert (e.value.status, e.value.code) == (404, "student_not_found")


async def test_instructor_any_nonempty_actor(db_session):
    for actor_id in (DEMO_INSTRUCTOR_ID, "teacher-demo"):
        actor = await resolve_actor(db_session, "instructor", actor_id)
        assert actor.role == "instructor"
        assert actor.id == actor_id
        assert actor.student is None


async def test_unknown_role_is_forbidden(db_session):
    with pytest.raises(ApiError) as e:
        await resolve_actor(db_session, "admin", "x")
    assert (e.value.status, e.value.code) == (403, "forbidden")


# --- B6: 헤더 확인을 한곳에(401 → 403 → resolve_actor). 오류 코드·문구는 전과 같다 ---


@pytest.mark.parametrize(
    ("role", "actor"), [(None, "x"), ("child", None), ("child", ""), (None, None)]
)
async def test_actor_from_request_missing_header_is_401(db_session, role, actor):
    with pytest.raises(ApiError) as e:
        await actor_from_request(db_session, "child", role, actor)
    assert (e.value.status, e.value.code) == (401, "no_actor")
    assert e.value.message == "데모 역할·행위자 헤더가 없어요."


@pytest.mark.parametrize(
    ("want", "message"),
    [
        ("child", "아이 화면에서만 쓸 수 있어요."),
        ("guardian", "보호자 화면에서만 쓸 수 있어요."),
        ("instructor", "강사 화면에서만 쓸 수 있어요."),
    ],
)
async def test_actor_from_request_wrong_role_is_403(db_session, want, message):
    other = "guardian" if want == "child" else "child"
    with pytest.raises(ApiError) as e:
        await actor_from_request(db_session, want, other, "x")
    assert (e.value.status, e.value.code, e.value.message) == (403, "forbidden", message)


async def test_actor_from_request_blank_instructor_is_401(db_session):
    with pytest.raises(ApiError) as e:
        await actor_from_request(db_session, "instructor", "instructor", "   ")
    assert (e.value.status, e.value.code) == (401, "no_actor")


async def test_actor_from_request_resolves(db_session, make_student):
    s = make_student()
    db_session.add(s)
    await db_session.flush()
    actor = await actor_from_request(db_session, "child", "child", s.id)
    assert actor.role == "child" and actor.student is s
    actor = await actor_from_request(db_session, "instructor", "instructor", DEMO_INSTRUCTOR_ID)
    assert actor.id == DEMO_INSTRUCTOR_ID and actor.student is None
