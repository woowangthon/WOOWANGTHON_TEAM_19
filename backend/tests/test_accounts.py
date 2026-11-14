"""명세 4.12 계정(설계 1112 §10): 가입·로그인·쿠키·Me·로그아웃·비밀번호·탈퇴, 체험 세상, 신원 분기.

이름·아이디·이메일은 모두 합성 값. 시계는 테스트가 고정한다.
"""

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select

from app import config
from app.accounts import sha256
from app.api import get_llm
from app.db import get_db
from app.instructor import get_draft_adapter
from app.llm import ScriptedAdapter
from app.main import create_app
from app.models import Student
from app.models_org import Account, AuthToken, Link, Room, RoomPerson
from app.seed import load_seed
from app.timeutil import get_now
from app.trial import TRIAL_HOURLY_MAX

NOW = datetime(2026, 11, 9, 21, 0, tzinfo=UTC)  # 서울 11-10 06:00
BASE = "/api/v1/compat"
PW = "abcd1234"


class Clock:
    def __init__(self) -> None:
        self.now = NOW


@pytest_asyncio.fixture
async def clock() -> Clock:
    return Clock()


@pytest_asyncio.fixture
async def client(db_session, clock, monkeypatch):
    monkeypatch.setattr(config, "_timer_scale_override", None)
    await load_seed(db_session)
    await db_session.flush()
    app = create_app()

    async def _db():
        yield db_session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_now] = lambda: clock.now
    app.dependency_overrides[get_llm] = ScriptedAdapter.from_file
    app.dependency_overrides[get_draft_adapter] = ScriptedAdapter.from_file
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _token_of(client, r) -> str:
    """응답이 준 쿠키 토큰. 이후 요청은 Bearer로만(쿠키 저장소는 비운다)."""
    assert r.status_code == 200, r.text
    token = r.cookies.get("cm_session")
    assert token
    client.cookies.clear()
    return token


async def _signup(client, role="student", login="kid_one", **extra) -> tuple[str, dict]:
    body = {
        "role": role,
        "loginId": login,
        "password": PW,
        "name": extra.pop("name", "새싹"),
        "agreements": {"terms": True, "privacy": True, "marketing": False},
        **extra,
    }
    if role == "student":
        body.setdefault("grade", 5)
    else:
        body.setdefault("email", f"{login}@example.com")
    r = await client.post(f"{BASE}/auth/signup", json=body)
    token = await _token_of(client, r)
    return token, r.json()


async def _trial(client) -> str:
    r = await client.post(f"{BASE}/trial")
    assert r.status_code == 200
    return r.json()["trialId"]


async def _demo_login(client, trial_id: str, user_id: str) -> tuple[str, dict]:
    r = await client.post(
        f"{BASE}/demo/login", json={"userId": user_id}, headers={"X-Trial-Id": trial_id}
    )
    return await _token_of(client, r), r.json()


# --- 가입·로그인·Me ---------------------------------------------------------------------


async def test_me_is_null_before_login(client):
    r = await client.get(f"{BASE}/me")
    assert r.status_code == 200 and r.json() is None
    r = await client.get(f"{BASE}/me", headers=_bearer("nope"))
    assert r.status_code == 200 and r.json() is None


async def test_signup_student_creates_day3_like_row(client, db_session):
    token, me = await _signup(client)
    assert me["role"] == "student" and me["loginId"] == "kid_one" and me["grade"] == 5
    assert me["id"].startswith("a-") and len(me["id"]) == 18
    assert me["restricted"] is True and me["linked"] == [] and me["email"] is None
    assert len(me["linkCode"]) == 6
    assert me["settings"]["studyReminder"] == "17:00"
    student = await db_session.get(Student, me["id"])
    assert student is not None
    assert student.nickname == "새싹" and student.streak_days == 0 and student.consent is False
    assert student.today_task_problem_id is not None
    # 홈: 계정 학생은 restricted 계산값
    home = await client.get(f"{BASE}/student/home", headers=_bearer(token))
    assert home.status_code == 200
    assert home.json()["restricted"] is True and home.json()["needsOnboarding"] is True
    # 비밀번호는 scrypt, 토큰은 sha256만
    acc = await db_session.get(Account, me["id"])
    assert acc is not None and acc.pw_hash.startswith("scrypt$") and PW not in acc.pw_hash
    assert await db_session.get(AuthToken, sha256(token)) is not None


async def test_signup_rules(client):
    await _signup(client, login="kid_one")
    r = await client.get(f"{BASE}/auth/check-id", params={"loginId": "kid_one"})
    assert r.json() is False
    r = await client.get(f"{BASE}/auth/check-id", params={"loginId": "kid_two"})
    assert r.json() is True
    r = await client.get(f"{BASE}/auth/check-id", params={"loginId": "1bad"})
    assert r.status_code == 422 and "영문 소문자" in r.json()["detail"]
    # 체험 아이디 형식은 예약
    r = await client.get(f"{BASE}/auth/check-id", params={"loginId": "jiwoo_ab12"})
    assert r.json() is False
    base = {
        "role": "guardian",
        "loginId": "mom_one",
        "password": PW,
        "name": "보호",
        "email": "bad",
        "agreements": {"terms": True, "privacy": True, "marketing": False},
    }
    r = await client.post(f"{BASE}/auth/signup", json=base)
    assert r.status_code == 422 and r.json()["detail"].startswith("이메일을 바르게")
    r = await client.post(f"{BASE}/auth/signup", json={**base, "loginId": "kid_one"})
    assert r.status_code == 409 and r.json()["detail"] == "이미 쓰는 아이디예요."
    r = await client.post(f"{BASE}/auth/signup", json={**base, "password": "short"})
    assert r.status_code == 422


async def test_login_cookie_me_logout(client):
    await _signup(client, role="guardian", login="mom_one")
    r = await client.post(
        f"{BASE}/auth/login", json={"loginId": "mom_one", "password": "wrong123", "remember": True}
    )
    assert r.status_code == 401 and r.json()["detail"] == "아이디 또는 비밀번호가 맞지 않아요."
    r = await client.post(
        f"{BASE}/auth/login", json={"loginId": " MOM_ONE ", "password": PW, "remember": False}
    )
    assert r.status_code == 200
    set_cookie = r.headers["set-cookie"]
    assert "cm_session=" in set_cookie and "HttpOnly" in set_cookie
    assert "samesite=lax" in set_cookie.lower() and "Max-Age" not in set_cookie
    token = await _token_of(client, r)
    # 쿠키로도 Bearer로도
    me = await client.get(f"{BASE}/me", headers={"Cookie": f"cm_session={token}"})
    assert me.json()["loginId"] == "mom_one"
    assert (await client.get(f"{BASE}/me", headers=_bearer(token))).json()["role"] == "guardian"
    r = await client.post(f"{BASE}/auth/logout", headers=_bearer(token))
    assert r.status_code == 204
    assert (await client.get(f"{BASE}/me", headers=_bearer(token))).json() is None
    # 멱등
    assert (await client.post(f"{BASE}/auth/logout")).status_code == 204
    # 로그아웃한 토큰으로 학습 API → 401 not_logged_in
    r = await client.get(f"{BASE}/guardian/today", headers=_bearer(token))
    assert r.status_code == 401 and r.json()["code"] == "not_logged_in"


async def test_expired_token(client, clock):
    _, _ = await _signup(client, role="teacher", login="teach_one")
    r = await client.post(
        f"{BASE}/auth/login", json={"loginId": "teach_one", "password": PW, "remember": False}
    )
    token = await _token_of(client, r)
    clock.now += timedelta(days=2)
    assert (await client.get(f"{BASE}/me", headers=_bearer(token))).json() is None


async def test_profile_password_settings_delete(client, db_session):
    token, me = await _signup(client, role="guardian", login="mom_one")
    h = _bearer(token)
    r = await client.put(f"{BASE}/me", json={"name": "새이름"}, headers=h)
    assert r.json()["name"] == "새이름"
    r = await client.put(f"{BASE}/me", json={"name": ""}, headers=h)
    assert r.status_code == 422
    r = await client.put(
        f"{BASE}/me/password", json={"current": "x", "next": "new12345"}, headers=h
    )
    assert r.json()["detail"] == "지금 비밀번호가 맞지 않아요."
    r = await client.put(f"{BASE}/me/password", json={"current": PW, "next": "new12345"}, headers=h)
    assert r.status_code == 204
    settings = {"studyReminder": None, "learnDone": False, "activity": True, "marketing": True}
    r = await client.put(f"{BASE}/me/settings", json=settings, headers=h)
    assert r.json()["settings"] == settings
    # 이메일로 아이디 찾기·비밀번호 재설정 안내
    r = await client.post(f"{BASE}/auth/find-id", json={"email": " MOM_ONE@example.com"})
    assert r.json() == ["mom****"]
    r = await client.post(
        f"{BASE}/auth/reset-password", json={"loginId": "mom_one", "email": "mom_one@example.com"}
    )
    assert r.json() == "sent"
    r = await client.post(f"{BASE}/me/delete", json={"password": PW}, headers=h)
    assert r.json()["detail"] == "비밀번호가 맞지 않아요."
    r = await client.post(f"{BASE}/me/delete", json={"password": "new12345"}, headers=h)
    assert r.status_code == 204
    assert await db_session.get(Account, me["id"]) is None
    assert (await client.get(f"{BASE}/me", headers=h)).json() is None


async def test_student_reset_password_asks_guardian(client):
    await _signup(client, login="kid_one")
    r = await client.post(
        f"{BASE}/auth/reset-password", json={"loginId": "kid_one", "email": "x@example.com"}
    )
    assert r.json() == "ask-guardian"


# --- 체험 세상 -------------------------------------------------------------------------


async def test_demo_world_is_per_trial(client, db_session):
    t1, t2 = await _trial(client), await _trial(client)
    a = (await client.get(f"{BASE}/demo/accounts", headers={"X-Trial-Id": t1})).json()
    b = (await client.get(f"{BASE}/demo/accounts", headers={"X-Trial-Id": t2})).json()
    assert [x["id"] for x in a][:3] == [f"{t1}-child", f"{t1}-guardian", f"{t1}-instructor"]
    assert len(a) == 8 and a[3]["note"] == "원장"
    assert a[0]["loginId"].startswith("jiwoo_") and len(a[0]["loginId"]) == 14
    assert {x["loginId"] for x in a}.isdisjoint({x["loginId"] for x in b})
    # 두 번 불러도 한 번만 만든다
    again = (await client.get(f"{BASE}/demo/accounts", headers={"X-Trial-Id": t1})).json()
    assert again == a
    n = await db_session.scalar(
        select(func.count()).select_from(Account).where(Account.trial_id == t1)
    )
    assert n == 11
    # s2~s4 학생 행이 생겨도 체험 상한은 -child만 센다
    assert await db_session.get(Student, f"{t1}-s2") is not None


async def test_demo_accounts_unknown_trial(client):
    r = await client.get(f"{BASE}/demo/accounts", headers={"X-Trial-Id": "t-" + "z" * 16})
    assert r.status_code == 404 and r.json()["code"] == "trial_not_found"
    r = await client.get(f"{BASE}/demo/accounts")
    assert r.status_code == 400


async def test_demo_login_maps_foreign_id_to_current_world(client):
    old, new = await _trial(client), await _trial(client)
    token, me = await _demo_login(client, new, f"{old}-child")
    assert me["id"] == f"{new}-child" and me["restricted"] is False
    assert me["linked"] == [{"id": f"{new}-guardian", "name": "지우 보호자", "role": "guardian"}]
    assert me["academy"]["id"] == f"{new}-a1"
    _, me = await _demo_login(client, new, "own2")
    assert me["application"]["status"] == "심사 중" and me["membership"] is None
    _, me = await _demo_login(client, new, "own1")
    assert me["membership"]["isOwner"] is True
    # 학생 홈은 그 세트 day3 아이
    home = await client.get(f"{BASE}/student/home", headers=_bearer(token))
    assert home.json()["name"] == "지우" and home.json()["restricted"] is False
    r = await client.post(
        f"{BASE}/demo/login", json={"userId": "nobody"}, headers={"X-Trial-Id": new}
    )
    assert r.status_code == 404


async def test_login_with_trial_header_builds_world(client):
    t = await _trial(client)
    accounts = (await client.get(f"{BASE}/demo/accounts", headers={"X-Trial-Id": t})).json()
    login_id = accounts[1]["loginId"]  # 보호자
    r = await client.post(
        f"{BASE}/auth/login",
        json={"loginId": login_id, "password": "demo1234", "remember": True},
    )
    token = await _token_of(client, r)
    r = await client.get(f"{BASE}/guardian/today", headers=_bearer(token))
    assert r.status_code == 200 and r.json()["childName"] == "지우"


async def test_notices(client):
    t = await _trial(client)
    token, _ = await _demo_login(client, t, "g1")
    h = _bearer(token)
    notices = (await client.get(f"{BASE}/notices", headers=h)).json()
    assert len(notices) == 1 and notices[0]["read"] is False
    assert notices[0]["at"] == "11월 10일 · 09:00"
    assert (await client.post(f"{BASE}/notices/read", headers=h)).status_code == 204
    assert (await client.get(f"{BASE}/notices", headers=h)).json()[0]["read"] is True


async def test_reset_child_password(client):
    t = await _trial(client)
    token, _ = await _demo_login(client, t, "g1")
    r = await client.put(
        f"{BASE}/guardian/children/{t}-s2/password",
        json={"next": "kid12345"},
        headers=_bearer(token),
    )
    assert r.status_code == 403
    r = await client.put(
        f"{BASE}/guardian/children/{t}-child/password",
        json={"next": "kid12345"},
        headers=_bearer(token),
    )
    assert r.status_code == 204
    kid, _ = await _demo_login(client, t, "s1")
    texts = [n["text"] for n in (await client.get(f"{BASE}/notices", headers=_bearer(kid))).json()]
    assert "보호자가 비밀번호를 새로 정해 줬어." in texts


# --- 신원 분기 -------------------------------------------------------------------------


async def test_guardian_not_linked(client):
    token, _ = await _signup(client, role="guardian", login="mom_one")
    r = await client.get(f"{BASE}/guardian/today", headers=_bearer(token))
    assert r.status_code == 404 and r.json()["code"] == "not_linked"


async def test_operator_forbidden_on_learning_api(client):
    t = await _trial(client)
    token, me = await _demo_login(client, t, "op")
    assert me["role"] == "operator"
    for path in ("/student/home", "/guardian/today", "/teacher/today"):
        r = await client.get(f"{BASE}{path}", headers=_bearer(token))
        assert r.status_code == 403, path


async def test_account_wins_over_demo_headers(client):
    t = await _trial(client)
    token, _ = await _demo_login(client, t, "g1")
    # 보호자 계정 + 아이 헤더 → 계정이 이긴다(아이 API는 403)
    r = await client.get(
        f"{BASE}/student/home",
        headers={**_bearer(token), "X-Demo-Role": "child", "X-Demo-Actor": f"{t}-child"},
    )
    assert r.status_code == 403


async def test_instructor_sees_room_members(client, db_session):
    t = await _trial(client)
    token, _ = await _demo_login(client, t, "t1")
    h = _bearer(token)
    r = await client.get(f"{BASE}/teacher/today", headers=h)
    assert r.status_code == 200
    ids = [s["id"] for s in r.json()["students"]]
    assert sorted(ids) == sorted([f"{t}-child", f"{t}-s2", f"{t}-s3"])  # s4는 요청만
    assert (await client.get(f"{BASE}/teacher/students/{t}-s4/memo", headers=h)).status_code == 404
    assert (await client.get(f"{BASE}/teacher/students/{t}-s2/memo", headers=h)).status_code == 200
    # 다른 세트 아이는 못 본다
    other = await _trial(client)
    r = await client.get(f"{BASE}/teacher/students/{other}-child/memo", headers=h)
    assert r.status_code == 404
    # 강의실 없는 강사(t3)는 아무도 못 본다
    t3, _ = await _demo_login(client, t, "t3")
    assert (await client.get(f"{BASE}/teacher/today", headers=_bearer(t3))).json()["students"] == []
    # 체험 헤더 학습지도자는 그대로 같은 세트 아이 하나
    r = await client.get(
        f"{BASE}/teacher/today",
        headers={"X-Demo-Role": "instructor", "X-Demo-Actor": f"{t}-instructor"},
    )
    assert [s["id"] for s in r.json()["students"]] == [f"{t}-child"]


async def test_room_membership_query(db_session):
    """room_members는 member만(초대·요청 제외)."""
    from app.actors import room_members

    db_session.add_all(
        [
            Room(id="r1", academy_id="a", teacher_id="tt", name="반"),
            RoomPerson(room_id="r1", student_account_id="x1", state="member"),
            RoomPerson(room_id="r1", student_account_id="x2", state="invited"),
        ]
    )
    await db_session.flush()
    assert await room_members(db_session, "tt") == frozenset({"x1"})


async def test_linked_student_not_restricted(client, db_session):
    token, me = await _signup(client, login="kid_one")
    _, mom = await _signup(client, role="guardian", login="mom_one")
    db_session.add(
        Link(
            student_account_id=me["id"],
            guardian_account_id=mom["id"],
            status="연결됨",
            consent_at=NOW.date(),
        )
    )
    await db_session.flush()
    home = await client.get(f"{BASE}/student/home", headers=_bearer(token))
    assert home.json()["restricted"] is False


async def test_trial_cap_counts_child_rows_only(client, db_session, make_student, clock):
    for i in range(TRIAL_HOURLY_MAX - 1):
        db_session.add(
            make_student(id=f"t-{i:016d}-child", created_at=clock.now - timedelta(minutes=5))
        )
    # 세트 세상 학생 행(-s2 등)은 세지 않는다
    for i in range(5):
        db_session.add(
            make_student(id=f"t-{i:016d}-s2", created_at=clock.now - timedelta(minutes=5))
        )
    await db_session.flush()
    assert (await client.post(f"{BASE}/trial")).status_code == 200
    assert (await client.post(f"{BASE}/trial")).status_code == 429


# --- 비밀번호가 바뀌면 다른 기기의 로그인을 끊는다(11-12 보안 점검) ------------------------


async def test_password_change_ends_other_sessions(client):
    a, _ = await _signup(client, login="kid_two")
    r = await client.post(
        f"{BASE}/auth/login", json={"loginId": "kid_two", "password": PW, "remember": True}
    )
    b = await _token_of(client, r)
    r = await client.put(
        f"{BASE}/me/password", json={"current": PW, "next": "newpw1234"}, headers=_bearer(a)
    )
    assert r.status_code == 204
    assert (await client.get(f"{BASE}/me", headers=_bearer(a))).json()["loginId"] == "kid_two"
    assert (await client.get(f"{BASE}/me", headers=_bearer(b))).json() is None


async def test_reset_child_password_ends_child_sessions(client):
    t = await _trial(client)
    kid, _ = await _demo_login(client, t, "s1")
    mom, _ = await _demo_login(client, t, "g1")
    r = await client.put(
        f"{BASE}/guardian/children/{t}-child/password",
        json={"next": "kid12345"},
        headers=_bearer(mom),
    )
    assert r.status_code == 204
    assert (await client.get(f"{BASE}/me", headers=_bearer(kid))).json() is None


# --- 11-12 보안 점검: 체험 아이디 추측·데모 헤더로 계정 학생 접근 -------------------------


async def test_demo_login_ids_are_hard_to_guess(client):
    t = await _trial(client)
    rows = (await client.get(f"{BASE}/demo/accounts", headers={"X-Trial-Id": t})).json()
    for a in rows:
        suffix = a["loginId"].rsplit("_", 1)[1]
        assert len(suffix) == 8, a["loginId"]


async def test_trial_only_blocks_headers_to_account_students(client, monkeypatch):
    """공개 배포(TRIAL_ONLY)에서는 데모 헤더로 가입 학생(a-…)·체험 세상 다른 학생(…-s2)에 못 닿는다."""
    _, me = await _signup(client, login="kid_three")
    t = await _trial(client)
    await client.get(f"{BASE}/demo/accounts", headers={"X-Trial-Id": t})  # 세상 만들기
    monkeypatch.setenv("TRIAL_ONLY", "1")
    for actor in (me["id"], f"{t}-s2"):
        r = await client.get(
            f"{BASE}/student/home", headers={"X-Demo-Role": "child", "X-Demo-Actor": actor}
        )
        assert r.status_code == 403, (actor, r.text)


# --- 11-12 점검 수정(1112_fix_list A1~A4) ------------------------------------------------


async def test_trial_account_cannot_delete(client):
    """A1: 체험 계정은 탈퇴 409(세상이 반쯤 지워지지 않게)."""
    t = await _trial(client)
    token, _ = await _demo_login(client, t, "g1")
    r = await client.post(
        f"{BASE}/me/delete", json={"password": "demo1234"}, headers=_bearer(token)
    )
    assert r.status_code == 409 and r.json()["detail"] == "체험 계정은 탈퇴할 수 없어요."


async def test_world_exists_by_academy_row(client, db_session):
    """A1: 보호자 행이 사라져도(예전 탈퇴) 같은 세트 시트·로그인은 500이 아니라 200."""
    from app.demo_world import world_exists

    t = await _trial(client)
    await client.get(f"{BASE}/demo/accounts", headers={"X-Trial-Id": t})
    guardian = await db_session.get(Account, f"{t}-guardian")
    assert guardian is not None
    await db_session.execute(delete(Link).where(Link.guardian_account_id == guardian.id))
    await db_session.delete(guardian)
    await db_session.flush()
    assert await world_exists(db_session, t) is True
    r = await client.get(f"{BASE}/demo/accounts", headers={"X-Trial-Id": t})
    assert r.status_code == 200 and len(r.json()) == 7
    r = await client.post(f"{BASE}/demo/login", json={"userId": "s1"}, headers={"X-Trial-Id": t})
    assert r.status_code == 200


async def test_ensure_world_race_returns_false(client, db_session, monkeypatch):
    """A2: exists 확인 뒤 다른 요청이 먼저 만들면 IntegrityError → False, 요청은 200."""
    from app import demo_world

    t = await _trial(client)
    assert (await client.get(f"{BASE}/demo/accounts", headers={"X-Trial-Id": t})).status_code == 200

    async def _never(db, trial_id):
        return False

    monkeypatch.setattr(demo_world, "world_exists", _never)
    db_session.expunge_all()  # 다른 요청(다른 세션)처럼 식별 맵을 비운다
    assert await demo_world.ensure_world(db_session, t, NOW) is False
    db_session.expunge_all()
    r = await client.get(f"{BASE}/demo/accounts", headers={"X-Trial-Id": t})
    assert r.status_code == 200 and len(r.json()) == 8
    db_session.expunge_all()
    r = await client.post(f"{BASE}/demo/login", json={"userId": "g1"}, headers={"X-Trial-Id": t})
    assert r.status_code == 200 and r.json()["id"] == f"{t}-guardian"


async def test_header_paths_never_reach_signed_up_students(client):
    """A3: TRIAL_ONLY가 꺼져 있어도 데모 헤더로 가입 학생(a-…)을 보거나 그 아이로 행동하지 못한다."""
    _, me = await _signup(client, login="kid_hidden")
    r = await client.get(
        f"{BASE}/student/home", headers={"X-Demo-Role": "child", "X-Demo-Actor": me["id"]}
    )
    assert r.status_code == 403 and r.json()["code"] == "trial_only"
    head = {"X-Demo-Role": "instructor", "X-Demo-Actor": "anyone"}
    rows = (await client.get(f"{BASE}/teacher/today", headers=head)).json()["students"]
    assert me["id"] not in {s["id"] for s in rows}
    rows = (await client.get(f"{BASE}/teacher/results", headers=head)).json()
    assert me["id"] not in {s["id"] for s in rows}
    r = await client.get("/api/v1/instructor/notes", params={"student_id": me["id"]}, headers=head)
    assert r.status_code == 404
    # 데모 아이는 그대로
    r = await client.get(
        f"{BASE}/student/home",
        headers={"X-Demo-Role": "child", "X-Demo-Actor": "demo-child-minsu"},
    )
    assert r.status_code != 403


async def test_trial_account_accepts_demo_password_after_change(client):
    """A4: 체험 계정은 비밀번호를 바꿔도 공개 비밀번호(demo1234)로 로그인된다. 가입 계정은 아니다."""
    t = await _trial(client)
    rows = (await client.get(f"{BASE}/demo/accounts", headers={"X-Trial-Id": t})).json()
    token, _ = await _demo_login(client, t, "g1")
    r = await client.put(
        f"{BASE}/me/password",
        json={"current": "demo1234", "next": "newpass99"},
        headers=_bearer(token),
    )
    assert r.status_code == 204
    r = await client.post(
        f"{BASE}/auth/login",
        json={"loginId": rows[1]["loginId"], "password": "demo1234", "remember": True},
    )
    assert r.status_code == 200
    client.cookies.clear()
    await _signup(client, login="real_mom", role="guardian")
    r = await client.post(
        f"{BASE}/auth/login",
        json={"loginId": "real_mom", "password": "demo1234", "remember": True},
    )
    assert r.status_code == 401


# --- TK-107 학생 탈퇴 시 학습·대화 기록 삭제(명세 「탈퇴 시 삭제」) ---------------------------


async def _add_day(db, student_id: str, now: datetime) -> None:
    """세션 1·메시지 2·🔴 알림 1·강사 메모 1을 직접 만든다(합성 문장)."""
    from app.models import Alert, InstructorNote, Message, Session

    s = Session(student_id=student_id, date=now.date(), state="ended")
    db.add(s)
    await db.flush()
    db.add(Message.new(session_id=s.id, seq=1, role="child", text_redacted="줄넘기 했어", now=now))
    db.add(Message.new(session_id=s.id, seq=2, role="mentor", text_redacted="좋다", now=now))
    db.add(Alert.new(session_id=s.id, student_id=student_id, trigger="K01", excerpt="-", now=now))
    db.add(InstructorNote(student_id=student_id, date=now.date()))
    # 씨앗·칭찬 도장·옷·교환 요청·알림(학원·앱 재화, 결정 11-12 성호: 탈퇴하면 같이 사라진다)
    from app.models_org import CosmeticOwned, Notice, Order, SeedLedger

    for cur in ("seed", "stamp"):
        db.add(
            SeedLedger(
                student_account_id=student_id,
                date=now.date(),
                amount=3,
                source="학습 완료",
                by="system",
                currency=cur,
            )
        )
    db.add(CosmeticOwned(student_account_id=student_id, cosmetic_id="hat-1"))
    db.add(
        Order(
            id=f"o-{student_id}",
            student_account_id=student_id,
            teacher_id="t-x",
            item_name="연필",
            price=3,
            status="교환 요청",
        )
    )
    db.add(Notice(account_id=student_id, text="합성 알림"))
    await db.flush()


async def _rows_of(db, student_id: str) -> dict[str, int]:
    from app.models import Alert, InstructorNote, Message, Misconception, Session
    from app.models_org import CosmeticOwned, Notice, Order, SeedLedger

    sids = select(Session.id).where(Session.student_id == student_id)
    counts = {
        "students": select(func.count()).select_from(Student).where(Student.id == student_id),
        "sessions": select(func.count())
        .select_from(Session)
        .where(Session.student_id == student_id),
        "messages": select(func.count()).select_from(Message).where(Message.session_id.in_(sids)),
        "alerts": select(func.count()).select_from(Alert).where(Alert.student_id == student_id),
        "misconceptions": select(func.count())
        .select_from(Misconception)
        .where(Misconception.student_id == student_id),
        "instructor_notes": select(func.count())
        .select_from(InstructorNote)
        .where(InstructorNote.student_id == student_id),
        "seed_ledger": select(func.count())
        .select_from(SeedLedger)
        .where(SeedLedger.student_account_id == student_id),
        "cosmetics_owned": select(func.count())
        .select_from(CosmeticOwned)
        .where(CosmeticOwned.student_account_id == student_id),
        "orders": select(func.count())
        .select_from(Order)
        .where(Order.student_account_id == student_id),
        "notices": select(func.count()).select_from(Notice).where(Notice.account_id == student_id),
    }
    return {k: await db.scalar(q) for k, q in counts.items()}


async def test_student_delete_removes_learning_and_chat_records(client, db_session):
    token, me = await _signup(client, login="kid_one")
    _, other = await _signup(client, login="kid_two")
    await _add_day(db_session, me["id"], NOW)
    await _add_day(db_session, other["id"], NOW)
    before = await _rows_of(db_session, me["id"])
    assert before["students"] == 1 and before["messages"] == 2 and before["alerts"] == 1
    assert before["seed_ledger"] >= 2 and before["cosmetics_owned"] == 1 and before["orders"] == 1
    other_before = await _rows_of(db_session, other["id"])

    r = await client.post(f"{BASE}/me/delete", json={"password": PW}, headers=_bearer(token))
    assert r.status_code == 204
    db_session.expire_all()
    assert await _rows_of(db_session, me["id"]) == dict.fromkeys(before, 0)
    assert await _rows_of(db_session, other["id"]) == other_before  # 다른 학생은 그대로


async def test_guardian_delete_keeps_child_records(client, db_session):
    _, kid = await _signup(client, login="kid_one")
    token, _ = await _signup(client, role="guardian", login="mom_one")
    await _add_day(db_session, kid["id"], NOW)
    before = await _rows_of(db_session, kid["id"])
    r = await client.post(f"{BASE}/me/delete", json={"password": PW}, headers=_bearer(token))
    assert r.status_code == 204
    db_session.expire_all()
    assert await _rows_of(db_session, kid["id"]) == before


async def test_signup_student_starts_without_trial_misconceptions(client, db_session):
    # 수정 명세 B30(성호 승인 11-14, 명세 4.12-5): 공부한 적 없는 아이에게 체험용 미해결 오개념이
    # 다리 놓기 요약·강사 화면에 실제 기록처럼 나왔다 → 오개념 0·freezes 0. 오늘 과제는 있다
    from sqlalchemy import func, select

    from app.models import Misconception

    _, me = await _signup(client)
    student = await db_session.get(Student, me["id"])
    assert student is not None
    count = await db_session.scalar(
        select(func.count()).select_from(Misconception).where(Misconception.student_id == me["id"])
    )
    assert count == 0
    assert student.freezes == 0 and student.streak_days == 0
    assert student.today_task_problem_id is not None


@pytest.mark.parametrize(
    ("grade", "band"),
    [(1, "초1-2"), (4, "초3-4"), (6, "초5-6"), (8, "중1-3"), (11, "고1-3")],
)
async def test_signup_grade_sets_grade_band(client, db_session, grade, band):
    # 11-14 B11(명세 부록 D 「학년대 말투」): 가입 학년이 서버 말투에 안 갔다 → 늘 초5-6
    _, me = await _signup(client, grade=grade)
    student = await db_session.get(Student, me["id"])
    assert student is not None and student.grade_band == band


async def test_me_grade_rolls_over_after_school_year(client, db_session):
    # 명세 4.12-5 UG1: 가입 학년도가 지나면 학년이 계산으로 올라간다(6 → 중1 = 7)
    from datetime import UTC, datetime

    from app.models_org import Account

    token, me = await _signup(client, grade=6)
    acc = await db_session.get(Account, me["id"])
    assert acc is not None
    acc.created_at = datetime(2020, 11, 14, tzinfo=UTC)  # 오래전 가입 → 고3에서 멈춤
    await db_session.commit()
    r = await client.get(f"{BASE}/me", headers={"Authorization": f"Bearer {token}"})
    assert r.json()["grade"] == 12


def test_grade_band_now_uses_rolled_grade():
    from datetime import UTC, datetime

    from app.prompts import grade_band_now

    signup = datetime(2026, 11, 14, tzinfo=UTC)
    assert grade_band_now(6, signup, datetime(2027, 3, 2, tzinfo=UTC), "초5-6") == "중1-3"
    assert grade_band_now(None, signup, datetime(2027, 3, 2, tzinfo=UTC), "초5-6") == "초5-6"
