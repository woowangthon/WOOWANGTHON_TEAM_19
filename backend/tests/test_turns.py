"""끊어 보내기 = 턴 묶기 + 서버 흡수, 판정 저장(messages.judge) (명세 3.2·4.2·4.4 #4·#4a, 11-11).

문장은 전부 합성이다. 🔴 문장은 부록 A 평가 문장 R1.
"""

import asyncio
from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app import db as appdb
from app.actors import DEMO_CHILD_ID
from app.api import CRISIS_REPLY, get_llm
from app.db import get_db
from app.llm import FallbackAdapter, Reply, ReplyRequest, ScriptedAdapter
from app.main import create_app
from app.models import Alert, Message, Session
from app.seed import load_seed
from app.timeutil import get_now

NOW = datetime(2026, 11, 9, 21, 0, tzinfo=UTC)  # 서울 11-10 06:00
SEOUL_TODAY = date(2026, 11, 10)
PROBLEM = "frac-div-nat-01"  # 3/4 ÷ 2, 정답 3/8
R1 = "요즘 그냥 죽고 싶어"
ANSWERS = ("3/8", "0.375", "8분의 3")


class SpyAdapter:
    """scripted 대본을 그대로 쓰되 호출을 기록한다."""

    def __init__(self) -> None:
        self.calls: list[ReplyRequest] = []
        self._inner = ScriptedAdapter.from_file()

    async def reply(self, req: ReplyRequest) -> Reply:
        self.calls.append(req)
        return await self._inner.reply(req)


class GateAdapter(SpyAdapter):
    """첫 호출은 release가 열릴 때까지 기다린다(= 답 생성 중). 이후 호출은 바로 답한다."""

    def __init__(self) -> None:
        super().__init__()
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def reply(self, req: ReplyRequest) -> Reply:
        out = await super().reply(req)
        if len(self.calls) == 1:
            self.entered.set()
            await asyncio.wait_for(self.release.wait(), timeout=5)
        return out


@pytest_asyncio.fixture
async def app_parts(db_session, make_student):
    await load_seed(db_session)
    student = make_student(today_task_problem_id=PROBLEM, today_task_date=SEOUL_TODAY)
    db_session.add(student)
    await db_session.flush()
    app = create_app()

    async def _db():
        yield db_session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_now] = lambda: NOW
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield app, c, student


def _headers(student) -> dict[str, str]:
    return {"X-Demo-Role": "child", "X-Demo-Actor": student.id}


async def _start(app_parts, adapter) -> tuple[AsyncClient, object, str]:
    app, c, student = app_parts
    app.dependency_overrides[get_llm] = lambda: adapter
    r = await c.post("/api/v1/sessions", headers=_headers(student))
    return c, student, r.json()["session_id"]


async def _send(c, student, sid, **body):
    return await c.post(f"/api/v1/sessions/{sid}/messages", headers=_headers(student), json=body)


async def _rows(db_session, sid) -> list[Message]:
    return list(
        (
            await db_session.scalars(
                select(Message).where(Message.session_id == sid).order_by(Message.seq)
            )
        ).all()
    )


async def test_three_pieces_one_turn_one_reply(app_parts, db_session):
    spy = SpyAdapter()
    c, student, sid = await _start(app_parts, spy)
    r = await _send(c, student, sid, kind="text", texts=["음", "3/4", "그런가"])
    assert r.status_code == 200
    body = r.json()
    assert body["reply"] and body["judge"] == "wrong"
    assert body["queued"] is False and body["pending"] is False
    assert body["source"] == "scripted"  # B1: 대본으로 답했다는 표시

    rows = await _rows(db_session, sid)
    assert [m.role for m in rows] == ["child", "child", "child", "mentor"]
    assert len({m.turn_id for m in rows}) == 1 and rows[0].turn_id
    assert [m.judge for m in rows] == [None, "wrong", None, None]

    assert len(spy.calls) == 1
    req = spy.calls[0]
    assert req.judge == "wrong"
    assert req.turns[-1] == {"role": "child", "text": "음\n3/4\n그런가"}


async def test_single_text_still_works(app_parts):
    spy = SpyAdapter()
    c, student, sid = await _start(app_parts, spy)
    body = (await _send(c, student, sid, kind="text", text="3/4")).json()
    assert body["judge"] == "wrong" and body["reply"] and body["queued"] is False


@pytest.mark.parametrize(
    "body",
    [
        {"kind": "text", "texts": []},
        {"kind": "text", "texts": ["  ", ""]},
        {"kind": "text", "texts": ["가"] * 6},
        {"kind": "text", "texts": ["가" * 1001]},
    ],
)
async def test_bad_pieces_are_422(app_parts, body):
    c, student, sid = await _start(app_parts, SpyAdapter())
    r = await _send(c, student, sid, **body)
    assert r.status_code == 422 and r.json()["code"] == "invalid_request"


async def test_piece_during_reply_is_absorbed_then_reply_endpoint(app_parts, db_session):
    gate = GateAdapter()
    c, student, sid = await _start(app_parts, gate)
    first = asyncio.create_task(_send(c, student, sid, kind="text", text="3/4"))
    await asyncio.wait_for(gate.entered.wait(), timeout=5)

    r2 = await _send(c, student, sid, kind="text", texts=["아 잠깐", "3/8"])
    assert r2.status_code == 200
    b2 = r2.json()
    assert b2["queued"] is True and b2["reply"] is None and b2["judge"] == "correct"
    assert b2["source"] is None  # 흡수 응답에는 답이 없다
    assert len(gate.calls) == 1  # 흡수는 LLM을 부르지 않는다

    hint = await _send(c, student, sid, kind="hint")  # 답 생성 중 힌트는 409 busy
    assert hint.status_code == 409 and hint.json()["code"] == "busy"

    gate.release.set()
    b1 = (await first).json()
    assert b1["reply"] and b1["judge"] == "wrong" and b1["pending"] is True

    b3 = (await c.post(f"/api/v1/sessions/{sid}/reply", headers=_headers(student))).json()
    assert b3["reply"] and b3["judge"] == "correct" and b3["pending"] is False
    assert b1["source"] == "scripted" and b3["source"] == "scripted"
    assert len(gate.calls) == 2
    assert gate.calls[1].judge == "correct"
    assert gate.calls[1].turns[-1] == {"role": "child", "text": "아 잠깐\n3/8"}

    rows = await _rows(db_session, sid)
    mentors = [m for m in rows if m.role == "mentor"]
    assert len(mentors) == 2
    for m in rows:
        if m.role == "child":
            assert m.turn_id in {x.turn_id for x in mentors}  # 모든 조각이 답을 받았다

    again = await c.post(f"/api/v1/sessions/{sid}/reply", headers=_headers(student))
    assert again.status_code == 409 and again.json()["code"] == "nothing_to_reply"


async def test_reply_endpoint_while_replying_is_queued(app_parts):
    gate = GateAdapter()
    c, student, sid = await _start(app_parts, gate)
    first = asyncio.create_task(_send(c, student, sid, kind="text", text="음"))
    await asyncio.wait_for(gate.entered.wait(), timeout=5)
    r = await c.post(f"/api/v1/sessions/{sid}/reply", headers=_headers(student))
    assert r.status_code == 200 and r.json()["queued"] is True
    assert r.json()["source"] is None
    gate.release.set()
    assert (await first).status_code == 200
    assert len(gate.calls) == 1


async def test_red_piece_during_reply_wins(app_parts, db_session):
    gate = GateAdapter()
    c, student, sid = await _start(app_parts, gate)
    first = asyncio.create_task(_send(c, student, sid, kind="text", text="음"))
    await asyncio.wait_for(gate.entered.wait(), timeout=5)

    r2 = (await _send(c, student, sid, kind="text", texts=["그냥", R1])).json()
    assert r2["state"] == "crisis" and r2["reply"] == CRISIS_REPLY
    assert r2["source"] == "fixed"  # 🔴 고정 문장
    assert r2["crisis"]["hotlines"] == ["109", "1388"]

    gate.release.set()
    b1 = (await first).json()
    assert b1["reply"] is None and b1["state"] == "crisis" and b1["crisis"] is not None

    alerts = await db_session.scalar(
        select(func.count()).select_from(Alert).where(Alert.session_id == sid)
    )
    assert alerts == 1
    mentors = [m.text_redacted for m in await _rows(db_session, sid) if m.role == "mentor"]
    assert mentors == [CRISIS_REPLY]  # 늦게 온 답은 버려졌다
    row = await db_session.get(Session, sid)
    await db_session.refresh(row)
    assert row.replying_until is None


@pytest.mark.parametrize("split", [["요즘 그냥 죽고", "싶어"], ["요즘 그냥 죽", "고 싶어"]])
async def test_red_split_across_pieces_in_one_request(app_parts, db_session, split):
    """🔴 문장을 조각으로 끊어 보내도 걸린다(조각 하나씩은 키워드에 안 걸림)."""
    spy = SpyAdapter()
    c, student, sid = await _start(app_parts, spy)
    r = (await _send(c, student, sid, kind="text", texts=split)).json()
    assert r["state"] == "crisis" and r["reply"] == CRISIS_REPLY
    assert spy.calls == []  # LLM에 합쳐진 문장이 가지 않는다


async def test_red_split_across_absorbed_requests(app_parts, db_session):
    """답 생성 중 앞 조각은 흡수, 뒤 조각이 이어 붙어 🔴이 되면 즉시 위기."""
    gate = GateAdapter()
    c, student, sid = await _start(app_parts, gate)
    first = asyncio.create_task(_send(c, student, sid, kind="text", text="음"))
    await asyncio.wait_for(gate.entered.wait(), timeout=5)

    r2 = (await _send(c, student, sid, kind="text", text="요즘 그냥 죽고")).json()
    assert r2["queued"] is True
    r3 = (await _send(c, student, sid, kind="text", text="싶어")).json()
    assert r3["state"] == "crisis" and r3["reply"] == CRISIS_REPLY

    gate.release.set()
    assert (await first).json()["state"] == "crisis"
    assert len(gate.calls) == 1
    alerts = await db_session.scalar(
        select(func.count()).select_from(Alert).where(Alert.session_id == sid)
    )
    assert alerts == 1


async def test_expired_lease_is_ignored(app_parts, db_session):
    spy = SpyAdapter()
    c, student, sid = await _start(app_parts, spy)
    row = await db_session.get(Session, sid)
    row.replying_until = NOW - timedelta(seconds=1)  # 죽은 요청이 남긴 표시
    await db_session.flush()
    body = (await _send(c, student, sid, kind="text", text="음")).json()
    assert body["queued"] is False and body["reply"]
    await db_session.refresh(row)
    assert row.replying_until is None

    row.replying_until = NOW + timedelta(seconds=10)  # 아직 유효
    await db_session.flush()
    body = (await _send(c, student, sid, kind="text", text="음")).json()
    assert body["queued"] is True


async def test_solved_reads_stored_judge(app_parts, db_session):
    spy = SpyAdapter()
    c, student, sid = await _start(app_parts, spy)
    await _send(c, student, sid, kind="text", text="음")
    r = await c.post(
        f"/api/v1/sessions/{sid}/phase", headers=_headers(student), json={"to": "chat"}
    )
    assert r.status_code == 409  # 아직 정답 없음

    child = next(m for m in await _rows(db_session, sid) if m.role == "child")
    child.judge = "correct"  # 저장된 판정만 읽는지(재판정하지 않는지)
    await db_session.flush()
    r = await c.post(
        f"/api/v1/sessions/{sid}/phase", headers=_headers(student), json={"to": "chat"}
    )
    assert r.status_code == 200 and r.json()["state"] == "chat"


async def test_chat_answer_like_text_is_not_judged(app_parts, db_session):
    spy = SpyAdapter()
    c, student, sid = await _start(app_parts, spy)
    await _send(c, student, sid, kind="text", text="3/8")
    await c.post(f"/api/v1/sessions/{sid}/phase", headers=_headers(student), json={"to": "chat"})
    body = (await _send(c, student, sid, kind="text", text="3/4")).json()
    assert body["judge"] is None
    judges = [m.judge for m in await _rows(db_session, sid) if m.role == "child"]
    assert judges == ["correct", None]


async def test_summary_attempts_are_stored_wrong_pieces(app_parts):
    spy = SpyAdapter()
    c, student, sid = await _start(app_parts, spy)
    await _send(c, student, sid, kind="text", texts=["3/4", "몰라", "2/3"])
    for _ in range(3):
        await _send(c, student, sid, kind="hint")
    await c.post(f"/api/v1/sessions/{sid}/phase", headers=_headers(student), json={"to": "bridge"})
    await c.get(f"/api/v1/sessions/{sid}/bridge", headers=_headers(student))
    summary = [r for r in spy.calls if r.phase == "summary"]
    assert len(summary) == 1
    assert [t["text"] for t in summary[0].turns] == ["3/4", "2/3"]


@pytest.mark.parametrize("style", ["EBSP", "EQLC", "DQSC"])
async def test_scripted_lines_differ_by_judge(style):
    adapter = ScriptedAdapter.from_file()

    def req(judge):
        return ReplyRequest(
            scenario=f"day3-{style}",
            phase="study",
            hint_level=0,
            step=1,
            system="",
            judge=judge,
        )

    correct = (await adapter.reply(req("correct"))).text
    wrong = (await adapter.reply(req("wrong"))).text
    none = (await adapter.reply(req(None))).text
    assert len({correct, wrong, none}) == 3
    assert "다시" not in correct

    # 힌트를 쓴 뒤 정답도 정답 줄(그 힌트 단계의 judge 줄 — 판정 없음 줄로 새지 않는다)
    def later(judge):
        return ReplyRequest(
            scenario=f"day3-{style}", phase="study", hint_level=2, step=3, system="", judge=judge
        )

    later_correct = (await adapter.reply(later("correct"))).text
    assert later_correct not in {(await adapter.reply(later(None))).text, wrong, none}
    assert "다시" not in later_correct
    for s in ANSWERS:
        assert s not in correct and s not in wrong and s not in none


async def test_judge_reaches_live_adapter_through_fallback(app_parts):
    seen: list[ReplyRequest] = []

    class Live:
        async def reply(self, req: ReplyRequest) -> Reply:
            seen.append(req)
            return Reply("합성 응답", "live")

    adapter = FallbackAdapter(Live(), ScriptedAdapter.from_file())
    c, student, sid = await _start(app_parts, adapter)
    body = (await _send(c, student, sid, kind="text", texts=["3/4", "3/8"])).json()
    assert body["source"] == "live"
    assert seen[0].judge == "correct"
    assert "정답(방금 낸 답이 맞았다)" in seen[0].system  # 프롬프트 판정 문장도 같은 칸에서


async def test_answer_never_in_prompt_or_reply(app_parts):
    spy = SpyAdapter()
    c, student, sid = await _start(app_parts, spy)
    bodies = []
    for texts in (["음"], ["3/4"], ["8분의 3"]):
        bodies.append((await _send(c, student, sid, kind="text", texts=texts)).json()["reply"])
    for req in spy.calls:
        assert not any(s in req.system for s in ANSWERS)
    for reply in bodies:
        assert not any(s in reply for s in ANSWERS)


# --- 동시 요청(파일 SQLite, 실제 연결 여러 개) ------------------------------------------


class SlowAdapter:
    async def reply(self, req: ReplyRequest) -> Reply:
        await asyncio.sleep(0.05)
        return Reply("합성 응답", "live")


@pytest_asyncio.fixture
async def booted(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'turns.db'}")
    monkeypatch.setattr(appdb, "_engine", None)
    monkeypatch.setattr(appdb, "_sessionmaker", None)
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield app, c
    if appdb._engine is not None:
        await appdb._engine.dispose()


async def test_five_concurrent_pieces_no_500(booted):
    app, c = booted
    app.dependency_overrides[get_llm] = lambda: SlowAdapter()
    child = {"X-Demo-Role": "child", "X-Demo-Actor": DEMO_CHILD_ID}
    sid = (await c.post("/api/v1/sessions", headers=child)).json()["session_id"]
    url = f"/api/v1/sessions/{sid}/messages"
    rs = await asyncio.gather(
        *(c.post(url, headers=child, json={"kind": "text", "text": f"음 {i}"}) for i in range(5))
    )
    assert all(r.status_code == 200 for r in rs), [r.status_code for r in rs]
    answered = [r for r in rs if not r.json()["queued"]]
    assert len(answered) >= 1

    # 남은 조각은 /reply로 전부 답을 받는다
    for _ in range(5):
        r = await c.post(f"/api/v1/sessions/{sid}/reply", headers=child)
        if r.status_code == 409:
            assert r.json()["code"] == "nothing_to_reply"
            break
        assert r.status_code == 200

    async def check(db):
        rows = (await db.scalars(select(Message).where(Message.session_id == sid))).all()
        mentor_turns = {m.turn_id for m in rows if m.role == "mentor"}
        children = [m for m in rows if m.role == "child"]
        return len(children), all(m.turn_id in mentor_turns for m in children)

    async for db in appdb.get_db():
        assert await check(db) == (5, True)
