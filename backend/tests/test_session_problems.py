"""한 세션 여러 문제(SESSION_PROBLEMS, 11-12). 기본 1 = 예전 그대로, 5면 같은 단원 5문제를 잇는다.

- 첫 문제 = 오늘 정한 문제(강사 지정·오개념). 다음은 같은 태그 시드를 id 순으로(첫 문제 뒤부터 돌아서).
- 문제마다 힌트 0~3. 정답 또는 풀이 보기(힌트 3)면 다음 문제로, hint_level은 0으로.
- 마지막 문제를 끝내거나 20분이 지나면 지금처럼 전환(수다·다리 놓기)으로.
"""

from datetime import UTC, date, datetime, timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select

from app import config
from app.actors import DEMO_CHILD_ID
from app.api import get_llm
from app.db import get_db
from app.llm import Reply, ReplyRequest, ScriptedAdapter
from app.main import create_app
from app.models import Problem, Session
from app.models_org import SessionProblem
from app.seed import load_seed
from app.timeutil import get_now

NOW = datetime(2026, 11, 9, 21, 0, tzinfo=UTC)  # 서울 11-10(화) 06:00
SEOUL_TODAY = date(2026, 11, 10)
BASE = "/api/v1/compat"
CHILD = {"X-Demo-Role": "child", "X-Demo-Actor": DEMO_CHILD_ID}
TWENTY = 20 * 60
TAG_IDS = [f"frac-div-nat-0{i}" for i in range(1, 6)]
ANSWERS = {  # 시드 정답(서버 판정 검사용). 분자/분모
    "frac-div-nat-01": (3, 8),
    "frac-div-nat-02": (2, 7),
    "frac-div-nat-03": (4, 15),
    "frac-div-nat-04": (1, 6),
    "frac-div-nat-05": (7, 16),
}


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def tick(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


class Recording:
    """scripted 답 그대로 + 받은 요청(시스템 프롬프트)을 모아 둔다."""

    def __init__(self) -> None:
        self.inner = ScriptedAdapter.from_file()
        self.requests: list[ReplyRequest] = []

    async def reply(self, req: ReplyRequest) -> Reply:
        self.requests.append(req)
        return await self.inner.reply(req)


async def _client(db_session, clock, make_student, monkeypatch, task: str, flag: str | None):
    monkeypatch.setattr(config, "_timer_scale_override", None)
    monkeypatch.delenv("TIMER_SCALE", raising=False)
    if flag is None:
        monkeypatch.delenv("SESSION_PROBLEMS", raising=False)
    else:
        monkeypatch.setenv("SESSION_PROBLEMS", flag)
    await load_seed(db_session)
    db_session.add(
        make_student(id=DEMO_CHILD_ID, today_task_problem_id=task, today_task_date=SEOUL_TODAY)
    )
    await db_session.flush()
    app = create_app()
    llm = Recording()

    async def _db():
        yield db_session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_now] = lambda: clock.now
    app.dependency_overrides[get_llm] = lambda: llm
    c = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    c.llm = llm  # type: ignore[attr-defined]
    return c


@pytest_asyncio.fixture
async def clock() -> Clock:
    return Clock()


@pytest_asyncio.fixture
async def client(db_session, clock, make_student, monkeypatch):
    c = await _client(db_session, clock, make_student, monkeypatch, TAG_IDS[0], "5")
    async with c:
        yield c


async def _start(client) -> str:
    r = await client.post(f"{BASE}/sessions", headers=CHILD, json={})
    assert r.status_code == 200, r.text
    return r.json()["id"]


async def _problem(client, sid: str) -> dict | None:
    r = await client.get(f"{BASE}/sessions/{sid}/problem", headers=CHILD)
    assert r.status_code == 200, r.text
    return r.json()


async def _view(client, sid: str) -> dict:
    view = (await client.get(f"{BASE}/sessions/active", headers=CHILD)).json()
    assert view["id"] == sid
    return view


async def _answer(client, sid: str, pid: str, ok: bool = True) -> dict:
    num, den = ANSWERS[pid]
    body = {"problemId": pid, "numerator": num if ok else num + 1, "denominator": den}
    r = await client.post(f"{BASE}/sessions/{sid}/answer", headers=CHILD, json=body)
    assert r.status_code == 200, r.text
    return r.json()


async def _hint(client, sid: str) -> dict:
    r = await client.post(f"{BASE}/sessions/{sid}/hint", headers=CHILD, json={})
    assert r.status_code == 200, r.text
    return r.json()


async def _solution(client, sid: str) -> dict:
    r = await client.post(f"{BASE}/sessions/{sid}/solution", headers=CHILD, json={})
    assert r.status_code == 200, r.text
    return r.json()


async def _seed(db_session, pid: str) -> Problem:
    p = await db_session.get(Problem, pid)
    assert p is not None
    return p


# --- 진행 ---------------------------------------------------------------------------


async def test_index_total_progress_and_no_repeat(client):
    sid = await _start(client)
    seen = []
    for i in range(5):
        p = await _problem(client, sid)
        assert p is not None and p["index"] == i and p["total"] == 5
        assert p["hints"] == [] and p["hintsLeft"] == 2
        seen.append(p["id"])
        out = await _answer(client, sid, p["id"])
        assert out["correct"] is True
        view = out["session"]
        assert view["solved"] == i + 1 and view["total"] == 5
        assert view["phase"] == ("solve" if i < 4 else "transition")
    assert seen == TAG_IDS and len(set(seen)) == 5
    assert await _problem(client, sid) is None  # 풀기 단계 끝
    r = await client.post(
        f"{BASE}/sessions/{sid}/after-study", headers=CHILD, json={"choice": "chat"}
    )
    assert r.status_code == 200 and r.json()["phase"] == "chat"


async def test_wrong_answer_stays_on_same_problem(client):
    sid = await _start(client)
    out = await _answer(client, sid, TAG_IDS[0], ok=False)
    assert out["correct"] is False and out["session"]["phase"] == "solve"
    p = await _problem(client, sid)
    assert p is not None and p["index"] == 0 and p["id"] == TAG_IDS[0]


async def test_hint_reset_and_hint_text_per_problem(client, db_session):
    sid = await _start(client)
    # 1번: 힌트 1개 쓰고 정답
    h = await _hint(client, sid)
    assert h["hints"] == [(await _seed(db_session, TAG_IDS[0])).hint1]
    await _answer(client, sid, TAG_IDS[0])
    # 2번: 힌트는 0부터, 문장은 2번 문제 것
    p = await _problem(client, sid)
    assert p is not None and p["id"] == TAG_IDS[1] and p["hints"] == [] and p["hintsLeft"] == 2
    second = await _seed(db_session, TAG_IDS[1])
    assert (await _hint(client, sid))["hints"] == [second.hint1]
    assert (await _hint(client, sid))["hints"] == [second.hint1, second.hint2]
    # 힌트를 다 쓰면 풀이 보기 → 2번 풀이, 그리고 다음 문제로
    sol = await _solution(client, sid)
    assert sol["steps"] == [second.solution]
    assert sol["session"]["phase"] == "solve"
    view = sol["session"]
    assert view["solved"] == 2 and view["assisted"] == 1 and view["hintsUsed"] == 3
    p = await _problem(client, sid)
    assert p is not None and p["index"] == 2 and p["id"] == TAG_IDS[2] and p["hints"] == []
    db_session.expire_all()
    row = await db_session.get(Session, sid)
    assert row is not None and row.hint_level == 0 and row.problem_id == TAG_IDS[2]


async def test_prompt_uses_current_problem_without_answer(client, db_session):
    sid = await _start(client)
    await _answer(client, sid, TAG_IDS[0])
    client.llm.requests.clear()
    await _answer(client, sid, TAG_IDS[1], ok=False)
    req = client.llm.requests[-1]
    second = await _seed(db_session, TAG_IDS[1])
    first = await _seed(db_session, TAG_IDS[0])
    assert second.text in req.system and first.text not in req.system
    assert second.answer["value"] not in req.system  # 정답은 프롬프트에 없다


async def test_solution_at_last_problem_goes_to_transition(client):
    sid = await _start(client)
    for pid in TAG_IDS[:4]:
        await _answer(client, sid, pid)
    await _hint(client, sid)
    await _hint(client, sid)
    sol = await _solution(client, sid)
    view = sol["session"]
    assert view["phase"] == "transition"
    assert view["solved"] == 5 and view["total"] == 5 and view["assisted"] == 1
    assert view["hintsUsed"] == 2
    assert await _problem(client, sid) is None


async def test_cannot_leave_study_mid_session_before_twenty_minutes(client):
    sid = await _start(client)
    await _answer(client, sid, TAG_IDS[0])
    r = await client.post(
        f"{BASE}/sessions/{sid}/after-study", headers=CHILD, json={"choice": "chat"}
    )
    assert r.status_code == 409


async def test_timeout_opens_chat_mid_session(client, clock):
    sid = await _start(client)
    await _answer(client, sid, TAG_IDS[0])
    clock.tick(TWENTY)
    view = await _view(client, sid)
    assert view["timedOut"] is True and view["solved"] == 1 and view["total"] == 5
    r = await client.post(
        f"{BASE}/sessions/{sid}/after-study", headers=CHILD, json={"choice": "chat"}
    )
    assert r.status_code == 200 and r.json()["phase"] == "chat"
    assert r.json()["solved"] == 1 and r.json()["total"] == 5


async def test_timeout_solution_does_not_advance(client, clock):
    sid = await _start(client)
    await _answer(client, sid, TAG_IDS[0])
    clock.tick(TWENTY)
    sol = await _solution(client, sid)
    assert sol["session"]["phase"] == "transition"
    assert sol["session"]["solved"] == 2 and sol["session"]["assisted"] == 1
    assert await _problem(client, sid) is None


async def test_bridge_quiz_summary_and_records(client, db_session):
    sid = await _start(client)
    await _answer(client, sid, TAG_IDS[0])
    await _hint(client, sid)
    await _answer(client, sid, TAG_IDS[1])
    for pid in TAG_IDS[2:]:
        await _answer(client, sid, pid)
    r = await client.post(
        f"{BASE}/sessions/{sid}/after-study", headers=CHILD, json={"choice": "skip"}
    )
    assert r.json()["phase"] == "wrap"
    bridge = (await client.get("/api/v1/sessions/" + sid + "/bridge", headers=CHILD)).json()
    ids = [q["id"] for q in bridge["quiz_options"]]
    assert ids == TAG_IDS[1:4]  # 같은 태그, 첫 문제 뺀 id 순 3개
    assert bridge["summary"][0] == "분수 ÷ 자연수 문제 5개 중 5개, 힌트 1번(풀이 보기 0개)"
    r = await client.post(
        f"{BASE}/sessions/{sid}/wrap",
        headers=CHILD,
        json={"quiz": bridge["quiz_options"][0]["text"]},
    )
    assert r.status_code == 200, r.text
    records = (await client.get(f"{BASE}/student/records", headers=CHILD)).json()
    assert records[0]["solved"] == 5 and records[0]["total"] == 5 and records[0]["hints"] == 1


async def test_unit_with_fewer_problems_caps_total(db_session, clock, make_student, monkeypatch):
    c = await _client(db_session, clock, make_student, monkeypatch, TAG_IDS[1], "5")
    await db_session.execute(delete(Problem).where(Problem.id.in_(TAG_IDS[3:])))
    async with c:
        sid = await _start(c)
        seen = []
        for i in range(3):
            p = await _problem(c, sid)
            assert p is not None and p["index"] == i and p["total"] == 3
            seen.append(p["id"])
            await _answer(c, sid, p["id"])
        assert seen == [TAG_IDS[1], TAG_IDS[2], TAG_IDS[0]]  # 첫 문제 뒤부터 돌아서
        assert await _problem(c, sid) is None


async def test_default_flag_is_single_problem(db_session, clock, make_student, monkeypatch):
    c = await _client(db_session, clock, make_student, monkeypatch, TAG_IDS[0], None)
    async with c:
        sid = await _start(c)
        p = await _problem(c, sid)
        assert p is not None and p["index"] == 0 and p["total"] == 1
        out = await _answer(c, sid, TAG_IDS[0])
        assert out["session"]["phase"] == "transition" and out["session"]["total"] == 1
        assert await _problem(c, sid) is None
    count = await db_session.scalar(select(func.count()).select_from(SessionProblem))
    assert count == 0


def test_session_problems_config(monkeypatch):
    monkeypatch.delenv("SESSION_PROBLEMS", raising=False)
    assert config.session_problems() == 1
    for raw, want in (("5", 5), ("0", 1), ("-3", 1), ("abc", 1), ("", 1), ("3", 3)):
        monkeypatch.setenv("SESSION_PROBLEMS", raw)
        assert config.session_problems() == want, raw
