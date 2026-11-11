"""compat 11-11 추가분: A1 마감 뒤 수다 말 · home.endedInCrisis. (/demo/restart는 4.11에서 없앰)

문장은 안전 키워드 검증용 합성 구절만 쓴다. 시계는 테스트가 움직인다(서울 날짜 기준).
"""

from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app import config
from app.actors import DEMO_CHILD_ID, DEMO_GUARDIAN_ID
from app.api import get_llm
from app.db import get_db
from app.llm import ReplyRequest, ScriptedAdapter
from app.main import create_app
from app.models import Alert, Message, Session
from app.seed import load_seed
from app.timeutil import get_now

NOW = datetime(2026, 11, 9, 21, 0, tzinfo=UTC)  # 서울 11-10(화) 06:00
SEOUL_TODAY = date(2026, 11, 10)
PROBLEM = "frac-div-nat-01"
BASE = "/api/v1/compat"
CHILD = {"X-Demo-Role": "child", "X-Demo-Actor": DEMO_CHILD_ID}
GUARDIAN = {"X-Demo-Role": "guardian", "X-Demo-Actor": DEMO_GUARDIAN_ID}
PLAIN = "줄넘기 했어"  # 합성 평범한 구절
RED = "죽고 싶어"  # 합성 🔴 구절


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def tick(self, seconds: int = 1) -> None:
        self.now += timedelta(seconds=seconds)


class SpyLlm:
    """scripted를 감싸 호출 수를 센다."""

    def __init__(self) -> None:
        self.inner = ScriptedAdapter.from_file()
        self.calls = 0

    async def reply(self, req: ReplyRequest):
        self.calls += 1
        return await self.inner.reply(req)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def spy() -> SpyLlm:
    return SpyLlm()


@pytest_asyncio.fixture
async def client(db_session, clock, spy, make_student, monkeypatch):
    monkeypatch.setattr(config, "_timer_scale_override", None)
    await load_seed(db_session)
    db_session.add(
        make_student(id=DEMO_CHILD_ID, today_task_problem_id=PROBLEM, today_task_date=SEOUL_TODAY)
    )
    await db_session.flush()
    app = create_app()

    async def _db():
        yield db_session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_now] = lambda: clock.now
    app.dependency_overrides[get_llm] = lambda: spy
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _post(client, path, headers=CHILD, **kw):
    return await client.post(BASE + path, headers=headers, **kw)


async def _to_chat(client, clock) -> str:
    sid = (await _post(client, "/sessions", json={})).json()["id"]
    clock.tick(5 * 60)
    await _post(
        client,
        f"/sessions/{sid}/answer",
        json={"problemId": PROBLEM, "numerator": 3, "denominator": 8},
    )
    await _post(client, f"/sessions/{sid}/after-study", json={"choice": "chat"})
    clock.tick()
    return sid


async def _child_count(db, sid: str) -> int:
    return await db.scalar(
        select(func.count())
        .select_from(Message)
        .where(Message.session_id == sid, Message.role == "child")
    )


# --- A1 수다 마감 뒤 도착한 말 ---------------------------------------------------------


async def test_red_after_chat_deadline_alerts(client, db_session, clock):
    sid = await _to_chat(client, clock)
    clock.tick(11 * 60)  # 수다 10분 마감이 지났다
    r = (await _post(client, f"/sessions/{sid}/chat", json={"text": RED})).json()
    assert r["crisis"] is True and r["hotlines"] == ["109", "1388"]
    assert r["session"]["phase"] == "crisis"
    db_session.expire_all()
    row = await db_session.get(Session, sid)
    assert row is not None and row.state == "crisis" and row.flag == "red"
    alerts = await db_session.scalar(
        select(func.count()).select_from(Alert).where(Alert.session_id == sid)
    )
    assert alerts == 1


async def test_red_in_bridge_pieces_alerts(client, db_session, clock):
    """끊어 보낸 조각도 기본 경로와 같이 묶어서 본다."""
    sid = await _to_chat(client, clock)
    await _post(client, f"/sessions/{sid}/chat/end")
    r = (await _post(client, f"/sessions/{sid}/chat", json={"texts": ["죽고", "싶어"]})).json()
    assert r["crisis"] is True


async def test_plain_after_chat_deadline_saved_without_llm(client, db_session, clock, spy):
    sid = await _to_chat(client, clock)
    clock.tick(11 * 60)
    before_child = await _child_count(db_session, sid)
    before_calls = spy.calls
    r = (await _post(client, f"/sessions/{sid}/chat", json={"text": PLAIN})).json()
    assert r["reply"] == "" and r["crisis"] is False and r["source"] is None
    assert r["queued"] is False and r["pending"] is False
    assert r["session"]["phase"] == "wrap"
    assert spy.calls == before_calls
    db_session.expire_all()
    assert await _child_count(db_session, sid) == before_child + 1
    row = await db_session.get(Session, sid)
    assert row is not None and row.state == "bridge" and row.replying_until is None
    # 다리 놓기는 그대로 이어진다
    wrap = (await client.get(f"{BASE}/sessions/{sid}/wrap", headers=CHILD)).json()
    assert len(wrap["quizOptions"]) == 3


# --- 계약 #2 home.endedInCrisis --------------------------------------------------------


async def _home(client) -> dict:
    return (await client.get(f"{BASE}/student/home", headers=CHILD)).json()


async def test_home_ended_in_crisis_no_session(client):
    assert (await _home(client))["endedInCrisis"] is False


async def test_home_ended_in_crisis_in_progress_and_normal_end(client, clock):
    sid = await _to_chat(client, clock)
    assert (await _home(client))["endedInCrisis"] is False
    await _post(client, f"/sessions/{sid}/chat/end")
    wrap = (await client.get(f"{BASE}/sessions/{sid}/wrap", headers=CHILD)).json()
    await _post(client, f"/sessions/{sid}/wrap", json={"quiz": wrap["quizOptions"][0]})
    home = await _home(client)
    assert home["doneToday"] is True and home["endedInCrisis"] is False


async def test_home_ended_in_crisis_true(client, clock):
    sid = await _to_chat(client, clock)
    await _post(client, f"/sessions/{sid}/chat", json={"text": RED})
    home = await _home(client)
    assert home["endedInCrisis"] is True and home["doneToday"] is True
