"""API 2·3·12번 (/me/today, /sessions, /healthz). 명세 4.4."""

from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db import get_db
from app.main import create_app
from app.models import Misconception, Session
from app.prompts import PROMPT_VERSION
from app.seed import load_seed
from app.timeutil import get_now

# UTC 11-09 21:00 = 서울 11-10 06:00. 세션 날짜는 서울 기준이어야 한다.
NOW = datetime(2026, 11, 9, 21, 0, tzinfo=UTC)
SEOUL_TODAY = date(2026, 11, 10)


@pytest_asyncio.fixture
async def client(db_session, monkeypatch):
    monkeypatch.delenv("LLM_MODE", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    await load_seed(db_session)
    app = create_app()

    async def _db():
        yield db_session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_now] = lambda: NOW
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def student(db_session, make_student):
    s = make_student(today_task_problem_id="frac-div-nat-01", today_task_date=SEOUL_TODAY)
    db_session.add(s)
    await db_session.flush()
    return s


def _child(student) -> dict[str, str]:
    return {"X-Demo-Role": "child", "X-Demo-Actor": student.id}


async def test_healthz_reports_db_mode_and_tz(client):
    for path in ("/healthz", "/api/v1/healthz"):
        r = await client.get(path)
        assert r.status_code == 200
        assert r.json() == {
            "db": "ok",
            "llm_key": False,
            "llm_mode": "scripted",
            "tz": "Asia/Seoul",
        }


@pytest.mark.parametrize(("key", "mode"), [(None, "scripted"), ("synthetic-key", "live")])
async def test_healthz_llm_mode_reflects_adapter_in_use(client, monkeypatch, key, mode):
    """LLM_MODE=live여도 키가 없으면 실제로는 scripted라 그대로 답한다."""
    monkeypatch.setenv("LLM_MODE", "live")
    if key:
        monkeypatch.setenv("LLM_API_KEY", key)
    body = (await client.get("/healthz")).json()
    assert body["llm_mode"] == mode
    assert body["llm_key"] is bool(key)


async def test_missing_actor_returns_error_shape(client):
    r = await client.get("/api/v1/me/today")
    assert r.status_code == 401
    body = r.json()
    assert body["code"] == "no_actor"
    assert body["message"] and body["request_id"]


async def test_wrong_role_is_forbidden(client, student):
    r = await client.get(
        "/api/v1/me/today", headers={"X-Demo-Role": "guardian", "X-Demo-Actor": student.id}
    )
    assert r.status_code == 403


async def test_today_prefers_instructor_task(client, student):
    r = await client.get("/api/v1/me/today", headers=_child(student))
    assert r.status_code == 200
    body = r.json()
    assert body["today_task"] == {"problem_id": "frac-div-nat-01", "source": "instructor"}
    assert body["session"] is None
    assert body["greeting"] and body["streak_text"]


async def test_today_falls_back_to_open_misconception(client, db_session, make_student):
    s = make_student()
    db_session.add(s)
    await db_session.flush()
    db_session.add(Misconception(student_id=s.id, tag="frac-div-nat", first_wrong_date=SEOUL_TODAY))
    await db_session.flush()
    body = (await client.get("/api/v1/me/today", headers=_child(s))).json()
    assert body["today_task"]["source"] == "misconception"
    assert body["today_task"]["problem_id"].startswith("frac-div-nat-")


async def test_start_session_uses_seoul_date_and_consumes_task(client, db_session, student):
    r = await client.post("/api/v1/sessions", headers=_child(student))
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "study" and body["hint_level"] == 0
    assert body["problem"]["id"] == "frac-div-nat-01"
    assert set(body["problem"]) == {"id", "text"}  # 정답·힌트는 내보내지 않는다
    row = await db_session.get(Session, body["session_id"])
    assert row is not None and row.date == SEOUL_TODAY
    await db_session.refresh(student)
    assert student.today_task_problem_id is None


async def test_start_session_records_prompt_version(client, db_session, student):
    """새 세션에 그때의 프롬프트 버전을 적는다(평가·회귀 비교용, 부록 D)."""
    body = (await client.post("/api/v1/sessions", headers=_child(student))).json()
    row = await db_session.get(Session, body["session_id"])
    assert row is not None and row.prompt_version == PROMPT_VERSION


async def test_start_session_twice_returns_same_session(client, student):
    first = (await client.post("/api/v1/sessions", headers=_child(student))).json()
    second = (await client.post("/api/v1/sessions", headers=_child(student))).json()
    assert first["session_id"] == second["session_id"]


async def test_start_session_race_returns_existing_session(
    client, db_session, student, monkeypatch
):
    """첫 조회 뒤 다른 요청이 같은 날 세션을 먼저 넣으면 500이 아니라 그 세션을 돌려준다."""
    from app import api

    real = api._today_session
    other = Session(student_id=student.id, date=SEOUL_TODAY, state="study", hint_level=0)
    calls = 0

    async def racing(db, s, now):
        nonlocal calls
        calls += 1
        if calls == 1:
            db_session.add(other)
            await db_session.flush()
            return None
        return await real(db, s, now)

    monkeypatch.setattr(api, "_today_session", racing)
    r = await client.post("/api/v1/sessions", headers=_child(student))
    assert r.status_code == 200
    assert r.json()["session_id"] == other.id
    # 바깥 트랜잭션은 살아 있어 이어서 쓸 수 있다
    assert await db_session.get(Session, other.id) is not None


@pytest.mark.parametrize("state", ["ended", "crisis"])
async def test_start_after_finished_session_is_conflict(client, db_session, student, state):
    db_session.add(Session(student_id=student.id, date=SEOUL_TODAY, state=state))
    await db_session.flush()
    r = await client.post("/api/v1/sessions", headers=_child(student))
    assert r.status_code == 409
    assert r.json()["code"] == "session_finished"


async def test_start_without_task_is_conflict(client, db_session, make_student):
    s = make_student()
    db_session.add(s)
    await db_session.flush()
    r = await client.post("/api/v1/sessions", headers=_child(s))
    assert r.status_code == 409
    assert r.json()["code"] == "no_task"


async def test_today_expires_chat_past_deadline(client, db_session, student):
    db_session.add(
        Session(
            student_id=student.id,
            date=SEOUL_TODAY,
            state="chat",
            problem_id="frac-div-nat-01",
            streak_applied=True,
            deadline_at=NOW - timedelta(seconds=1),
        )
    )
    await db_session.flush()
    body = (await client.get("/api/v1/me/today", headers=_child(student))).json()
    assert body["session"]["state"] == "bridge"


async def test_today_after_ended_says_see_you_tomorrow(client, db_session, student):
    db_session.add(Session(student_id=student.id, date=SEOUL_TODAY, state="ended"))
    await db_session.flush()
    body = (await client.get("/api/v1/me/today", headers=_child(student))).json()
    assert body["session"]["state"] == "ended"
    assert "내일 봐" in body["greeting"]


# --- 오류 형식: 모든 오류 경로가 {code, message, request_id} (명세 4.4 공통) ---


def _assert_error_shape(body: dict, code: str) -> None:
    assert set(body) == {"code", "message", "request_id"}
    assert body["code"] == code
    assert body["message"] and body["request_id"]


async def test_unknown_route_uses_error_shape(client):
    r = await client.get("/api/v1/nope")
    assert r.status_code == 404
    _assert_error_shape(r.json(), "http_error")


async def test_method_not_allowed_keeps_allow_header(client):
    # B14: HTTPException의 headers(405 Allow)를 버리지 않는다
    r = await client.delete("/api/v1/healthz")
    assert r.status_code == 405
    assert "GET" in r.headers.get("allow", "")
    _assert_error_shape(r.json(), "http_error")


async def test_validation_error_uses_error_shape():
    # 지금 3개 API는 검증할 입력이 없어 422가 안 난다. 뒤에 붙을 API를 위해 임시 경로로 확인한다.
    app = create_app()

    @app.get("/api/v1/_probe")
    async def _probe(n: int) -> dict[str, int]:
        return {"n": n}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/_probe", params={"n": "x"})
    assert r.status_code == 422
    _assert_error_shape(r.json(), "invalid_request")


async def test_unhandled_error_uses_error_shape():
    app = create_app()

    @app.get("/api/v1/_boom")
    async def _boom() -> None:
        raise RuntimeError("내부 사정")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/v1/_boom")
    assert r.status_code == 500
    body = r.json()
    _assert_error_shape(body, "internal_error")
    assert "내부 사정" not in body["message"]  # 예외 내용은 응답에 싣지 않는다
