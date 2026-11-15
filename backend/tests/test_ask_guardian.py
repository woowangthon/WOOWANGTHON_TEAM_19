"""부록 E 「11-15 오후 성호 변경」: 🔴 보호자 알림은 아이가 요청할 때만. 합성 값만."""

from datetime import UTC, datetime, timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app import config
from app.api import CRISIS_REPLY, CRISIS_REPLY_POLITE, get_llm
from app.db import get_db
from app.instructor import get_draft_adapter
from app.llm import ScriptedAdapter
from app.main import create_app
from app.models import Alert
from app.seed import load_seed
from app.timeutil import get_now

NOW = datetime(2026, 11, 9, 21, 0, tzinfo=UTC)  # 서울 11-10 06:00
BASE = "/api/v1/compat"
RED = "죽고 싶어"  # 합성 위기 문장(테스트 전용)


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


def _h(role: str, actor: str) -> dict[str, str]:
    return {"X-Demo-Role": role, "X-Demo-Actor": actor}


async def _crisis_session(client, clock) -> tuple[str, dict, dict]:
    t = (await client.post(f"{BASE}/trial")).json()["trialId"]
    kid, mom = _h("child", f"{t}-child"), _h("guardian", f"{t}-guardian")
    await client.post(f"{BASE}/student/promise", headers=kid)
    sid = (await client.post(f"{BASE}/sessions", json={"difficulty": "초급"}, headers=kid)).json()[
        "id"
    ]
    for _ in range(2):
        clock.now += timedelta(seconds=1)
        await client.post(f"{BASE}/sessions/{sid}/hint", headers=kid)
    await client.post(f"{BASE}/sessions/{sid}/solution", headers=kid)
    await client.post(f"{BASE}/sessions/{sid}/after-study", json={"choice": "chat"}, headers=kid)
    r = await client.post(f"{BASE}/sessions/{sid}/chat", json={"texts": [RED]}, headers=kid)
    assert r.status_code == 200 and r.json()["source"] == "fixed"
    return sid, kid, mom


async def _alerts(db_session, sid: str) -> int:
    return (
        await db_session.scalar(
            select(func.count()).select_from(Alert).where(Alert.session_id == sid)
        )
        or 0
    )


async def test_crisis_alone_sends_no_guardian_alert(client, db_session, clock):
    sid, kid, mom = await _crisis_session(client, clock)
    assert await _alerts(db_session, sid) == 0
    alerts = (await client.get(f"{BASE}/guardian/alerts", headers=mom)).json()
    items = (
        alerts if isinstance(alerts, list) else alerts.get("alerts") or alerts.get("items") or []
    )
    assert items == []
    home = (await client.get(f"{BASE}/student/home", headers=kid)).json()
    assert home["session"]["guardianRequestedAt"] is None
    chat = (await client.get(f"{BASE}/sessions/{sid}/chat", headers=kid)).json()
    assert chat["guardianRequestedAt"] is None
    # 요청 전에는 보호자 첫 화면에도 위기 흔적이 없다(bb 11-15: 「확인했어요」 문구가 새던 것)
    today = (await client.get(f"{BASE}/guardian/today", headers=mom)).json()
    assert today["alertNotice"] is None


async def test_ask_guardian_creates_one_alert_idempotent(client, db_session, clock):
    sid, kid, mom = await _crisis_session(client, clock)
    r1 = await client.post(f"{BASE}/sessions/{sid}/crisis/ask-guardian", headers=kid)
    assert r1.status_code == 200 and r1.json()["requestedAt"]
    clock.now += timedelta(minutes=3)
    r2 = await client.post(f"{BASE}/sessions/{sid}/crisis/ask-guardian", headers=kid)
    assert r2.status_code == 200 and r2.json()["requestedAt"] == r1.json()["requestedAt"]
    assert await _alerts(db_session, sid) == 1
    row = await db_session.scalar(select(Alert).where(Alert.session_id == sid))
    assert row is not None and row.excerpt == ""  # 아이 말 0 그대로
    home = (await client.get(f"{BASE}/student/home", headers=kid)).json()
    assert home["session"]["guardianRequestedAt"] == r1.json()["requestedAt"]
    today = (await client.get(f"{BASE}/guardian/today", headers=mom)).json()
    assert today["alertNotice"]


async def test_ask_guardian_only_own_crisis_session(client, db_session, clock):
    sid, kid, _ = await _crisis_session(client, clock)
    t2 = (await client.post(f"{BASE}/trial")).json()["trialId"]
    other = _h("child", f"{t2}-child")
    r = await client.post(f"{BASE}/sessions/{sid}/crisis/ask-guardian", headers=other)
    assert r.status_code == 404
    await client.post(f"{BASE}/student/promise", headers=other)
    sid2 = (
        await client.post(f"{BASE}/sessions", json={"difficulty": "초급"}, headers=other)
    ).json()["id"]
    r = await client.post(f"{BASE}/sessions/{sid2}/crisis/ask-guardian", headers=other)
    assert r.status_code == 409  # 🔴로 끝난 세션이 아니면
    assert await _alerts(db_session, sid2) == 0


async def test_fixed_sentence_ends_with_trusted_adult_line():
    assert CRISIS_REPLY.endswith("믿을 수 있는 어른에게 같이 도움을 청해 보자.")
    assert CRISIS_REPLY_POLITE.endswith("믿을 수 있는 어른에게 같이 도움을 청해 봐요.")
