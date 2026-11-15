"""명세 4.11-10: 심사용 고정 세트 3벌 + 「처음 상태로 되돌리기」(성호 11-15). 합성 값만."""

from datetime import UTC, datetime, timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app import config
from app.account_routes import ensure_judge_sets
from app.api import get_llm
from app.db import get_db
from app.instructor import get_draft_adapter
from app.llm import ScriptedAdapter
from app.main import create_app
from app.models import Session
from app.models_org import Account
from app.seed import load_seed
from app.timeutil import get_now
from app.trial import JUDGE_SETS

NOW = datetime(2026, 11, 9, 21, 0, tzinfo=UTC)  # 서울 11-10 06:00
BASE = "/api/v1/compat"


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


async def _login(client, login_id: str, trial_header: str | None = None) -> dict[str, str]:
    headers = {"X-Trial-Id": trial_header} if trial_header else {}
    r = await client.post(
        f"{BASE}/auth/login", json={"loginId": login_id, "password": "demo1234"}, headers=headers
    )
    assert r.status_code == 200, r.text
    token = r.cookies.get("cm_session")
    client.cookies.clear()
    assert token
    return {"Authorization": f"Bearer {token}"}


async def test_judge_sets_created_once_with_fixed_ids(db_session):
    assert await ensure_judge_sets(db_session, NOW) == 3
    assert await ensure_judge_sets(db_session, NOW) == 0  # 멱등
    for n in (1, 2, 3):
        for login in (f"jiwoo_judge{n}", f"jiwoo_mom_judge{n}", f"kim_teacher_judge{n}"):
            acc = await db_session.scalar(select(Account).where(Account.login_id == login))
            assert acc is not None and acc.trial_id == JUDGE_SETS[n - 1]


async def test_judge_login_works_even_with_other_trial_header(client, db_session):
    await ensure_judge_sets(db_session, NOW)
    await db_session.commit()
    other = (await client.post(f"{BASE}/trial")).json()["trialId"]  # 화면이 받아 둔 무작위 세트
    kid = await _login(client, "jiwoo_judge1", trial_header=other)
    me = (await client.get(f"{BASE}/me", headers={**kid, "X-Trial-Id": other})).json()
    assert me["loginId"] == "jiwoo_judge1" and me["resettable"] is True
    home = await client.get(f"{BASE}/student/home", headers={**kid, "X-Trial-Id": other})
    assert home.status_code == 200
    t = JUDGE_SETS[0]
    r = await client.post(
        f"{BASE}/sessions", json={"difficulty": "초급"}, headers={**kid, "X-Trial-Id": other}
    )
    assert r.status_code in (200, 409), r.text  # 약속 전이면 409 needs_promise
    if r.status_code == 200:
        row = await db_session.get(Session, r.json()["id"])
        assert row is not None and row.student_id == f"{t}-child"


async def test_reset_mine_restores_same_ids_and_logs_out(client, db_session, clock):
    await ensure_judge_sets(db_session, NOW)
    await db_session.commit()
    t = JUDGE_SETS[1]
    kid = await _login(client, "jiwoo_judge2")
    await client.post(f"{BASE}/student/promise", headers=kid)
    assert (
        await client.post(f"{BASE}/sessions", json={"difficulty": "초급"}, headers=kid)
    ).status_code == 200
    n = await db_session.scalar(
        select(func.count()).select_from(Session).where(Session.student_id == f"{t}-child")
    )
    assert n and n >= 1
    mom = await _login(client, "jiwoo_mom_judge2")
    r = await client.post(f"{BASE}/demo/reset-mine", headers=mom)  # 보호자도 되돌릴 수 있다
    assert r.status_code == 204, r.text
    assert (
        await client.get(f"{BASE}/me", headers=kid)
    ).json() is None  # 토큰도 지워짐(로그인 전 = null)
    clock.now += timedelta(seconds=1)
    kid = await _login(client, "jiwoo_judge2")  # 같은 아이디·비밀번호
    me = (await client.get(f"{BASE}/me", headers=kid)).json()
    assert me["id"] == f"{t}-child" and me["linked"]  # 가족 연결 그대로
    home = (await client.get(f"{BASE}/student/home", headers=kid)).json()
    assert home["session"] is None and home["doneToday"] is False  # 오늘 다시 할 수 있다
    # 다른 세트는 그대로
    other = await db_session.scalar(
        select(func.count()).select_from(Account).where(Account.trial_id == JUDGE_SETS[0])
    )
    assert other and other > 0


async def test_reset_mine_refuses_non_judge_accounts(client, db_session):
    tid = (await client.post(f"{BASE}/trial")).json()["trialId"]
    r = await client.get(f"{BASE}/demo/accounts", headers={"X-Trial-Id": tid})
    assert r.status_code == 200
    login_id = next(a["loginId"] for a in r.json() if a["loginId"].startswith("jiwoo_"))
    kid = await _login(client, login_id, trial_header=tid)
    me = (await client.get(f"{BASE}/me", headers=kid)).json()
    assert me["resettable"] is False
    r = await client.post(f"{BASE}/demo/reset-mine", headers=kid)
    assert r.status_code == 403 and r.json()["code"] == "not_resettable"
    assert (await client.post(f"{BASE}/demo/reset-mine")).status_code == 401
