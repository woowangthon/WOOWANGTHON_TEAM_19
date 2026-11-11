"""API 4번 POST /sessions/{id}/messages (명세 4.4·4.3·4.5).

문장은 전부 합성이다. 🔴 문장은 부록 A 평가 문장 R1(시연 대본 문장).
"""

from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.api import build_excerpt, get_llm
from app.db import get_db
from app.llm import Reply, ReplyRequest, ScriptedAdapter
from app.main import create_app
from app.models import Alert, Message, Misconception, Session
from app.seed import load_seed
from app.timeutil import get_now

NOW = datetime(2026, 11, 9, 21, 0, tzinfo=UTC)  # 서울 11-10 06:00
SEOUL_TODAY = date(2026, 11, 10)
PROBLEM = "frac-div-nat-01"  # 3/4 ÷ 2, 정답 3/8
R1 = "요즘 그냥 죽고 싶어"


class SpyAdapter:
    """scripted 대본을 그대로 쓰되 호출을 기록한다."""

    def __init__(self) -> None:
        self.calls: list[ReplyRequest] = []
        self._inner = ScriptedAdapter.from_file()

    async def reply(self, req: ReplyRequest) -> Reply:
        self.calls.append(req)
        return await self._inner.reply(req)


@pytest.fixture
def spy() -> SpyAdapter:
    return SpyAdapter()


@pytest_asyncio.fixture
async def client(db_session, spy):
    await load_seed(db_session)
    app = create_app()

    async def _db():
        yield db_session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_now] = lambda: NOW
    app.dependency_overrides[get_llm] = lambda: spy
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def student(db_session, make_student):
    s = make_student(today_task_problem_id=PROBLEM, today_task_date=SEOUL_TODAY)
    db_session.add(s)
    await db_session.flush()
    return s


def _child(student) -> dict[str, str]:
    return {"X-Demo-Role": "child", "X-Demo-Actor": student.id}


@pytest_asyncio.fixture
async def sid(client, student) -> str:
    r = await client.post("/api/v1/sessions", headers=_child(student))
    return r.json()["session_id"]


async def _send(client, student, sid, **body):
    return await client.post(f"/api/v1/sessions/{sid}/messages", headers=_child(student), json=body)


async def test_wrong_hint_hint_correct_flow(client, student, sid, spy):
    r = await _send(client, student, sid, kind="text", text="3/4")
    assert r.status_code == 200
    body = r.json()
    keys = {"reply", "source", "judge", "hint_level", "state", "crisis", "queued", "pending"}
    assert set(body) == keys and body["source"] == "scripted"
    assert body["judge"] == "wrong" and body["hint_level"] == 0 and body["state"] == "study"
    assert body["crisis"] is None and body["reply"]

    body = (await _send(client, student, sid, kind="hint")).json()
    assert body["judge"] is None and body["hint_level"] == 1
    body = (await _send(client, student, sid, kind="hint")).json()
    assert body["hint_level"] == 2

    body = (await _send(client, student, sid, kind="text", text="8분의 3")).json()
    assert body["judge"] == "correct"
    assert body["state"] == "study"  # 전환은 5번 API가 한다
    assert body["hint_level"] == 2

    assert [c.scenario for c in spy.calls] == ["day3-EBSP"] * 4
    assert [(c.phase, c.hint_level, c.step) for c in spy.calls] == [
        ("study", 0, 1),
        ("study", 1, 1),
        ("study", 2, 1),
        ("study", 2, 2),
    ]


async def test_prompt_gets_judge_and_no_answer(client, student, sid, spy):
    await _send(client, student, sid, kind="text", text="3/4")
    system = spy.calls[0].system
    assert "오답" in system
    assert "3/8" not in system and "0.375" not in system


async def test_live_path_sends_no_answer_to_provider(db_session, student, monkeypatch):
    """LLM_MODE=live + 키 → get_llm이 live 어댑터를 쓰고, 공급자에 가는 요청에도 정답이 없다."""
    sent: list[dict] = []

    class _Text:
        type = "text"
        text = "같이 다시 볼까?"

    class _Resp:
        content = [_Text()]
        stop_reason = "end_turn"

    class _Messages:
        async def create(self, **kwargs):
            sent.append(kwargs)
            return _Resp()

    class _Client:
        messages = _Messages()

    import app.llm as llm_mod

    monkeypatch.setenv("LLM_MODE", "live")
    monkeypatch.setenv("LLM_API_KEY", "synthetic-key-live-path")
    monkeypatch.setattr(llm_mod, "AsyncAnthropic", lambda **kw: _Client())
    await load_seed(db_session)
    app = create_app()

    async def _db():
        yield db_session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_now] = lambda: NOW
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        sid = (await c.post("/api/v1/sessions", headers=_child(student))).json()["session_id"]
        body = (await _send(c, student, sid, kind="text", text="3/4")).json()
    assert body["reply"] == "같이 다시 볼까?"
    assert len(sent) == 1
    flat = sent[0]["system"] + str(sent[0]["messages"])
    assert "3/8" not in flat and "0.375" not in flat


async def test_no_pattern_is_not_judged(client, student, sid):
    body = (await _send(client, student, sid, kind="text", text="이거 어떻게 해?")).json()
    assert body["judge"] is None and body["state"] == "study"


async def test_reply_never_contains_answer(client, student, sid):
    replies = []
    for body in (
        {"kind": "text", "text": "몰라"},
        {"kind": "hint"},
        {"kind": "hint"},
        {"kind": "hint"},
        {"kind": "text", "text": "3/8"},
    ):
        replies.append((await _send(client, student, sid, **body)).json()["reply"])
    for reply in replies:
        for s in ("3/8", "0.375", "8분의 3"):
            assert s not in reply


async def test_hint_three_opens_misconception(client, db_session, student, sid):
    for level in (1, 2, 3):
        body = (await _send(client, student, sid, kind="hint")).json()
        assert body["hint_level"] == level
    rows = (
        await db_session.scalars(
            select(Misconception).where(Misconception.student_id == student.id)
        )
    ).all()
    assert [(m.tag, m.status, m.first_wrong_date) for m in rows] == [
        ("frac-div-nat", "open", SEOUL_TODAY)
    ]
    r = await _send(client, student, sid, kind="hint")
    assert r.status_code == 409
    assert r.json()["code"] == "hint_unavailable"


async def test_hint_three_keeps_existing_misconception(client, db_session, student, sid):
    db_session.add(
        Misconception(
            student_id=student.id,
            tag="frac-div-nat",
            first_wrong_date=date(2026, 11, 1),
            status="resolved",
        )
    )
    await db_session.flush()
    for _ in range(3):
        assert (await _send(client, student, sid, kind="hint")).status_code == 200
    count = await db_session.scalar(
        select(func.count())
        .select_from(Misconception)
        .where(Misconception.student_id == student.id)
    )
    assert count == 1  # UNIQUE(학생, tag) — 이미 있으면 새로 만들지 않는다


async def test_red_keyword_goes_to_crisis_without_llm(client, db_session, student, sid, spy):
    await _send(client, student, sid, kind="text", text="몰라")
    calls_before = len(spy.calls)
    r = await _send(client, student, sid, kind="text", text=R1)
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "crisis"
    assert body["reply"] == "지금 한 말이 걱정돼서, 어른에게 알릴게"
    assert body["judge"] is None
    assert body["crisis"]["hotlines"] == ["109", "1388"]
    assert R1 in body["crisis"]["excerpt"]
    assert len(spy.calls) == calls_before  # LLM 호출 없음

    alerts = (await db_session.scalars(select(Alert).where(Alert.session_id == sid))).all()
    assert len(alerts) == 1
    assert alerts[0].trigger == "K01" and alerts[0].student_id == student.id
    assert alerts[0].excerpt == body["crisis"]["excerpt"]
    assert len(alerts[0].excerpt) <= 300

    row = await db_session.get(Session, sid)
    assert row is not None
    assert (row.state, row.flag, row.end_reason) == ("crisis", "red", "crisis")
    assert row.ended_at is not None

    again = await _send(client, student, sid, kind="text", text="안녕")
    assert again.status_code == 409
    assert again.json()["code"] == "session_finished"


async def test_other_students_session_is_not_found(client, db_session, make_student, sid):
    other = make_student(nickname="다른학생")
    db_session.add(other)
    await db_session.flush()
    r = await _send(client, other, sid, kind="text", text="3/8")
    assert r.status_code == 404
    assert r.json()["code"] == "session_not_found"


async def test_unknown_session_is_not_found(client, student):
    r = await _send(client, student, "nope", kind="text", text="3/8")
    assert r.status_code == 404
    assert r.json()["code"] == "session_not_found"


async def test_stored_messages_are_redacted(client, db_session, student, sid):
    await _send(client, student, sid, kind="text", text="테스트학생 번호 010-1234-5678 이야")
    rows = (
        await db_session.scalars(
            select(Message).where(Message.session_id == sid).order_by(Message.seq)
        )
    ).all()
    assert [(m.seq, m.role) for m in rows] == [(1, "child"), (2, "mentor")]
    child = rows[0].text_redacted
    assert "010-1234-5678" not in child and "테스트학생" not in child
    assert "[전화]" in child and "[이름]" in child


async def test_text_kind_needs_text(client, student, sid):
    r = await _send(client, student, sid, kind="text")
    assert r.status_code == 422
    assert r.json()["code"] == "invalid_request"


async def test_chat_is_not_judged_and_hint_unavailable(client, db_session, student, sid, spy):
    row = await db_session.get(Session, sid)
    assert row is not None
    row.state = "chat"
    row.streak_applied = True
    row.phase_started_at = NOW
    row.deadline_at = NOW + timedelta(minutes=10)
    await db_session.flush()
    body = (await _send(client, student, sid, kind="text", text="3/8")).json()
    assert body["judge"] is None and body["state"] == "chat"
    assert spy.calls[-1].phase == "chat" and spy.calls[-1].step == 1
    r = await _send(client, student, sid, kind="hint")
    assert r.status_code == 409 and r.json()["code"] == "hint_unavailable"


async def test_chat_past_deadline_moves_to_bridge_first(client, db_session, student, sid, spy):
    row = await db_session.get(Session, sid)
    assert row is not None
    row.state = "chat"
    row.streak_applied = True
    row.phase_started_at = NOW - timedelta(minutes=11)
    row.deadline_at = NOW - timedelta(seconds=1)
    await db_session.flush()
    body = (await _send(client, student, sid, kind="text", text="재밌었어")).json()
    assert body["state"] == "bridge"
    assert spy.calls[-1].phase == "bridge"


def test_build_excerpt_keeps_tail_within_300():
    msgs = [("child", "가" * 200), ("mentor", "나" * 200), ("child", R1)]
    excerpt = build_excerpt(msgs)
    assert len(excerpt) <= 300
    assert excerpt.endswith(R1)


def test_build_excerpt_uses_last_three_turns():
    msgs = [("child", "하나"), ("mentor", "둘"), ("child", "셋"), ("mentor", "넷"), ("child", R1)]
    excerpt = build_excerpt(msgs)
    assert "하나" not in excerpt and "둘" not in excerpt
    assert "셋" in excerpt and "넷" in excerpt and R1 in excerpt
