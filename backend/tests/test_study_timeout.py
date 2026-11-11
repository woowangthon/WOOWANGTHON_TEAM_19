"""명세 4.11-4: 같이 풀기 20분이 지나면 「풀이 보기」·「수다로 넘어가기」가 힌트 수와 무관하게 열린다.

20분은 강제 종료가 아니라 선택지가 열리는 시각. 판정은 phase_started_at + 20분 ≤ now(서버 시각).
프론트는 studyRemainingSec / remainingSec == 0을 보고 두 버튼을 연다 — 그 대응을 여기서 고정한다.
"""

from datetime import UTC, date, datetime, timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app import config
from app.actors import DEMO_CHILD_ID
from app.api import get_llm
from app.db import get_db
from app.llm import ScriptedAdapter
from app.main import create_app
from app.models import Session, Student
from app.seed import load_seed
from app.state_machine import (
    SessionState,
    State,
    enter_phase,
    study_remaining_sec,
    study_time_over,
)
from app.timeutil import get_now

NOW = datetime(2026, 11, 9, 21, 0, tzinfo=UTC)  # 서울 11-10(화) 06:00
SEOUL_TODAY = date(2026, 11, 10)
PROBLEM = "frac-div-nat-01"
BASE = "/api/v1/compat"
CHILD = {"X-Demo-Role": "child", "X-Demo-Actor": DEMO_CHILD_ID}
TWENTY = 20 * 60


# --- 순수 함수 ------------------------------------------------------------------------


def test_study_time_over_boundary():
    assert study_time_over(NOW, NOW + timedelta(seconds=TWENTY - 1)) is False
    assert study_time_over(NOW, NOW + timedelta(seconds=TWENTY)) is True  # 20분 ≤ now
    assert study_time_over(None, NOW + timedelta(hours=1)) is False


def test_study_time_over_uses_timer_scale():
    assert study_time_over(NOW, NOW + timedelta(seconds=TWENTY / 10), 10) is True
    assert study_time_over(NOW, NOW + timedelta(seconds=TWENTY / 10 - 1), 10) is False


def test_remaining_zero_iff_time_over():
    for scale in (1, 10):
        for sec in (0, 119, 120, 1199, 1199.5, 1200, 1500):
            now = NOW + timedelta(seconds=sec)
            over = study_time_over(NOW, now, scale)
            assert (study_remaining_sec(NOW, now, scale) == 0) is over, (scale, sec)


def test_enter_phase_after_twenty_minutes_without_hints():
    s = SessionState(state=State.STUDY, phase_started_at=NOW)
    new, streak_inc = enter_phase(s, "chat", NOW + timedelta(seconds=TWENTY))
    assert new.state is State.CHAT and streak_inc is True and new.streak_applied is True


# --- HTTP -----------------------------------------------------------------------------


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def tick(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


@pytest_asyncio.fixture
async def clock() -> Clock:
    return Clock()


@pytest_asyncio.fixture
async def client(db_session, clock, make_student, monkeypatch):
    monkeypatch.setattr(config, "_timer_scale_override", None)
    monkeypatch.delenv("TIMER_SCALE", raising=False)
    await load_seed(db_session)
    db_session.add(
        make_student(id=DEMO_CHILD_ID, today_task_problem_id=PROBLEM, today_task_date=SEOUL_TODAY)
    )
    await db_session.flush()
    app = create_app()
    llm = ScriptedAdapter.from_file()

    async def _db():
        yield db_session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_now] = lambda: clock.now
    app.dependency_overrides[get_llm] = lambda: llm
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _start(client) -> str:
    return (await client.post(f"{BASE}/sessions", headers=CHILD, json={})).json()["id"]


async def _view(client, sid: str) -> dict:
    view = (await client.get(f"{BASE}/sessions/active", headers=CHILD)).json()
    assert view["id"] == sid
    return view


async def _problem(client, sid: str) -> dict:
    return (await client.get(f"{BASE}/sessions/{sid}/problem", headers=CHILD)).json()


async def test_before_twenty_minutes_both_still_409(client, clock):
    sid = await _start(client)
    clock.tick(TWENTY - 1)
    assert (await _view(client, sid))["studyRemainingSec"] == 1
    assert (await _view(client, sid))["timedOut"] is False
    assert (await _problem(client, sid))["remainingSec"] == 1
    r = await client.post(f"{BASE}/sessions/{sid}/solution", headers=CHILD, json={})
    assert r.status_code == 409
    r = await client.post(
        f"{BASE}/sessions/{sid}/after-study", headers=CHILD, json={"choice": "chat"}
    )
    assert r.status_code == 409


async def test_timeout_solution_without_hints(client, clock, db_session):
    sid = await _start(client)
    clock.tick(TWENTY)
    view = await _view(client, sid)
    assert view["studyRemainingSec"] == 0 and view["timedOut"] is True
    prob = await _problem(client, sid)
    assert prob["remainingSec"] == 0 and prob["canShowSolution"] is True
    r = await client.post(f"{BASE}/sessions/{sid}/solution", headers=CHILD, json={})
    assert r.status_code == 200
    body = r.json()
    assert body["steps"] and body["session"]["phase"] == "transition"
    db_session.expire_all()
    row = await db_session.get(Session, sid)
    assert row is not None and row.hint_level == 3


async def test_timeout_after_study_to_chat_counts_streak_once(client, clock, db_session):
    sid = await _start(client)
    child = await db_session.get(Student, DEMO_CHILD_ID)
    assert child is not None
    before = child.streak_days
    clock.tick(TWENTY + 30)
    assert (await _view(client, sid))["studyRemainingSec"] == 0
    r = await client.post(
        f"{BASE}/sessions/{sid}/after-study", headers=CHILD, json={"choice": "chat"}
    )
    assert r.status_code == 200
    view = r.json()
    assert view["phase"] == "chat" and view["chatRemainingSec"] == 600
    assert view["streakDays"] == before + 1 and view["timedOut"] is False
    db_session.expire_all()
    row = await db_session.get(Session, sid)
    assert row is not None and row.streak_applied is True and row.study_sec == TWENTY + 30


async def test_timeout_after_study_skip_to_bridge(client, clock):
    sid = await _start(client)
    clock.tick(TWENTY)
    r = await client.post(
        f"{BASE}/sessions/{sid}/after-study", headers=CHILD, json={"choice": "skip"}
    )
    assert r.status_code == 200 and r.json()["phase"] == "wrap"


async def test_timeout_with_timer_scale(client, clock):
    config.set_timer_scale(10)
    sid = await _start(client)
    clock.tick(TWENTY / 10)
    assert (await _view(client, sid))["studyRemainingSec"] == 0
    r = await client.post(
        f"{BASE}/sessions/{sid}/after-study", headers=CHILD, json={"choice": "chat"}
    )
    assert r.status_code == 200


async def test_default_path_phase_after_timeout(client, clock):
    sid = (await client.post("/api/v1/sessions", headers=CHILD)).json()["session_id"]
    clock.tick(TWENTY - 1)
    r = await client.post(f"/api/v1/sessions/{sid}/phase", headers=CHILD, json={"to": "chat"})
    assert r.status_code == 409
    clock.tick(1)
    r = await client.post(f"/api/v1/sessions/{sid}/phase", headers=CHILD, json={"to": "chat"})
    assert r.status_code == 200 and r.json()["state"] == "chat"
