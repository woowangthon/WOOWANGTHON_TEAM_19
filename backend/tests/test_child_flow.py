"""아이 흐름 API 5·6·7·13번과 HTTP 한 바퀴 (명세 3.2·4.4·4.5·4.6·부록 E).

문장은 전부 합성이다. 시계는 테스트가 움직인다(서울 날짜 기준).
"""

from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api import get_llm, next_streak
from app.db import get_db
from app.llm import FIXED_REPLY, Reply, ReplyRequest, ScriptedAdapter
from app.main import create_app
from app.models import Session, Student
from app.seed import load_seed
from app.timeutil import get_now

NOW = datetime(2026, 11, 9, 21, 0, tzinfo=UTC)  # 서울 11-10 06:00
SEOUL_TODAY = date(2026, 11, 10)
YESTERDAY = SEOUL_TODAY - timedelta(days=1)
PROBLEM = "frac-div-nat-01"  # 3/4 ÷ 2, 정답 3/8
CHAT_LINE = "오늘 축구하다 넘어졌어"  # 합성 수다 문장
R1 = "요즘 그냥 죽고 싶어"


class Clock:
    def __init__(self) -> None:
        self.now = NOW


class SpyAdapter:
    """scripted 대본을 쓰되, 요약(phase="summary") 응답은 테스트가 정한다."""

    def __init__(self) -> None:
        self.calls: list[ReplyRequest] = []
        self.summary: str | Exception | None = None  # None이면 scripted 그대로
        self._inner = ScriptedAdapter.from_file()

    async def reply(self, req: ReplyRequest) -> Reply:
        self.calls.append(req)
        if req.phase == "summary" and self.summary is not None:
            if isinstance(self.summary, Exception):
                raise self.summary
            return Reply(self.summary, "live")
        return await self._inner.reply(req)

    def summary_calls(self) -> list[ReplyRequest]:
        return [c for c in self.calls if c.phase == "summary"]


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def spy() -> SpyAdapter:
    return SpyAdapter()


@pytest_asyncio.fixture
async def client(db_session, spy, clock):
    await load_seed(db_session)
    app = create_app()

    async def _db():
        yield db_session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_now] = lambda: clock.now
    app.dependency_overrides[get_llm] = lambda: spy
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def student(db_session, make_student):
    s = make_student(today_task_problem_id=PROBLEM, today_task_date=SEOUL_TODAY)
    db_session.add(s)
    await db_session.flush()
    return s


def _h(student) -> dict[str, str]:
    return {"X-Demo-Role": "child", "X-Demo-Actor": student.id}


@pytest_asyncio.fixture
async def sid(client, student) -> str:
    r = await client.post("/api/v1/sessions", headers=_h(student))
    return r.json()["session_id"]


async def _send(client, student, sid, **body):
    return await client.post(f"/api/v1/sessions/{sid}/messages", headers=_h(student), json=body)


async def _phase(client, student, sid, to):
    return await client.post(f"/api/v1/sessions/{sid}/phase", headers=_h(student), json={"to": to})


async def _bridge(client, student, sid):
    return await client.get(f"/api/v1/sessions/{sid}/bridge", headers=_h(student))


async def _end(client, student, sid, quiz):
    return await client.post(
        f"/api/v1/sessions/{sid}/end", headers=_h(student), json={"quiz_problem_id": quiz}
    )


async def _row(db_session, sid) -> Session:
    row = await db_session.get(Session, sid)
    assert row is not None
    await db_session.refresh(row)
    return row


# --- HTTP 한 바퀴 ------------------------------------------------------------------


async def test_full_day_round_trip(client, db_session, student):
    student.streak_days, student.last_streak_date = 2, YESTERDAY
    await db_session.flush()

    r = await client.post("/api/v1/sessions", headers=_h(student))
    assert r.status_code == 200
    sid = r.json()["session_id"]

    assert (await _send(client, student, sid, kind="text", text="3/4")).json()["judge"] == "wrong"
    assert (await _send(client, student, sid, kind="hint")).json()["hint_level"] == 1
    body = (await _send(client, student, sid, kind="text", text="8분의 3")).json()
    assert body["judge"] == "correct" and body["state"] == "study"

    r = await _phase(client, student, sid, "bridge")
    assert r.status_code == 200
    assert r.json() == {
        "state": "bridge",
        "deadline_at": None,
        "streak_days": 3,
        "streak_text": "3일째 같이 했어",
    }

    r = await _bridge(client, student, sid)
    assert r.status_code == 200
    bridge = r.json()
    assert set(bridge) == {"quiz_options", "guardian_line", "summary"}
    assert [q["id"] for q in bridge["quiz_options"]] == [
        "frac-div-nat-02",
        "frac-div-nat-03",
        "frac-div-nat-04",
    ]
    assert all(set(q) == {"id", "text"} for q in bridge["quiz_options"])
    assert bridge["guardian_line"] == "오늘 분수 ÷ 자연수를 다시 풀었어요."
    assert bridge["summary"] == [
        "분수 ÷ 자연수 문제 1개, 힌트 1단계에서 정답",
        "막힌 곳 기록 없음",  # scripted엔 요약 대본이 없다 → 템플릿
        "미해결 없음",
    ]

    r = await _end(client, student, sid, "frac-div-nat-03")
    assert r.status_code == 200
    assert r.json() == {"state": "ended", "streak_text": "3일째 같이 했어"}

    today = (await client.get("/api/v1/me/today", headers=_h(student))).json()
    assert today["session"]["state"] == "ended"
    assert today["greeting"] == "오늘도 고마워. 내일 봐!"

    row = await _row(db_session, sid)
    assert row.quiz_problem_id == "frac-div-nat-03"
    assert row.end_reason == "normal" and row.ended_at is not None
    assert row.study_summary == bridge["summary"]
    assert row.guardian_line == bridge["guardian_line"]
    await db_session.refresh(student)
    assert (student.streak_days, student.last_streak_date) == (3, SEOUL_TODAY)


# --- 5. phase ------------------------------------------------------------------------


async def test_study_to_chat_sets_ten_minute_deadline(client, student, sid):
    await _send(client, student, sid, kind="text", text="3/8")
    r = await _phase(client, student, sid, "chat")
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "chat"
    assert datetime.fromisoformat(body["deadline_at"]) == NOW + timedelta(minutes=10)
    assert body["streak_days"] == 1 and body["streak_text"] == "1일째 같이 했어"


async def test_second_phase_call_counts_streak_once(client, db_session, student, sid):
    await _send(client, student, sid, kind="text", text="3/8")
    assert (await _phase(client, student, sid, "chat")).json()["streak_days"] == 1
    r = await _phase(client, student, sid, "bridge")
    assert r.status_code == 200
    assert r.json()["state"] == "bridge" and r.json()["streak_days"] == 1
    row = await _row(db_session, sid)
    assert row.streak_applied is True and row.deadline_at is None


async def test_phase_before_solved_is_409(client, student, sid):
    r = await _phase(client, student, sid, "chat")
    assert r.status_code == 409 and r.json()["code"] == "phase_not_allowed"
    await _send(client, student, sid, kind="text", text="3/4")  # 오답만
    r = await _phase(client, student, sid, "bridge")
    assert r.status_code == 409 and r.json()["code"] == "phase_not_allowed"


async def test_hint_three_allows_phase_and_summary_says_solution(client, student, sid):
    for _ in range(3):
        await _send(client, student, sid, kind="hint")
    r = await _phase(client, student, sid, "chat")
    assert r.status_code == 200 and r.json()["state"] == "chat"
    assert (await _phase(client, student, sid, "bridge")).status_code == 200
    bridge = (await _bridge(client, student, sid)).json()
    assert bridge["summary"][0] == "분수 ÷ 자연수 문제 1개, 힌트 3단계에서 풀이 보기"
    assert bridge["summary"][2] == "미해결: 분수 ÷ 자연수"


async def test_chat_cannot_go_back_to_chat_from_bridge(client, student, sid):
    await _send(client, student, sid, kind="text", text="3/8")
    await _phase(client, student, sid, "bridge")
    r = await _phase(client, student, sid, "chat")
    assert r.status_code == 409 and r.json()["code"] == "phase_not_allowed"


async def test_end_chat_after_deadline_is_ok(client, student, sid, clock):
    """수다 마감 직후 「끝내기」를 눌러도 이미 bridge로 넘어갔으니 그대로 bridge."""
    await _send(client, student, sid, kind="text", text="3/8")
    await _phase(client, student, sid, "chat")
    clock.now = NOW + timedelta(minutes=11)
    r = await _phase(client, student, sid, "bridge")
    assert r.status_code == 200
    assert r.json()["state"] == "bridge" and r.json()["streak_days"] == 1


async def test_phase_on_finished_or_unknown_session(client, db_session, student, sid):
    r = await client.post("/api/v1/sessions/nope/phase", headers=_h(student), json={"to": "chat"})
    assert r.status_code == 404 and r.json()["code"] == "session_not_found"
    await _send(client, student, sid, kind="text", text=R1)  # 🔴
    r = await _phase(client, student, sid, "bridge")
    assert r.status_code == 409 and r.json()["code"] == "session_finished"


async def test_phase_rejects_bad_target(client, student, sid):
    r = await _phase(client, student, sid, "ended")
    assert r.status_code == 422 and r.json()["code"] == "invalid_request"


async def test_other_students_session_is_not_found(client, db_session, make_student, sid):
    other = make_student(nickname="다른학생")
    db_session.add(other)
    await db_session.flush()
    for r in (
        await _phase(client, other, sid, "chat"),
        await _bridge(client, other, sid),
        await _end(client, other, sid, None),
    ):
        assert r.status_code == 404 and r.json()["code"] == "session_not_found"


async def test_crisis_after_streak_keeps_streak(client, db_session, student, sid):
    await _send(client, student, sid, kind="text", text="3/8")
    await _phase(client, student, sid, "chat")
    await _send(client, student, sid, kind="text", text=R1)
    await db_session.refresh(student)
    assert student.streak_days == 1


@pytest.mark.parametrize(
    ("days", "last", "expected"),
    [
        (4, YESTERDAY, 5),  # 어제 했으면 +1
        (4, SEOUL_TODAY, 4),  # 오늘 이미 셌으면 그대로
        (4, SEOUL_TODAY - timedelta(days=2), 1),  # 끊기면 1부터
        (0, None, 1),  # 처음
    ],
)
def test_next_streak_rules(days, last, expected):
    assert next_streak(days, last, SEOUL_TODAY) == expected


async def test_streak_broken_restarts_at_one(client, db_session, student, sid):
    student.streak_days, student.last_streak_date = 7, SEOUL_TODAY - timedelta(days=3)
    await db_session.flush()
    await _send(client, student, sid, kind="text", text="3/8")
    body = (await _phase(client, student, sid, "bridge")).json()
    assert body["streak_days"] == 1 and body["streak_text"] == "1일째 같이 했어"


async def test_streak_uses_seoul_date(client, db_session, student, sid, clock):
    """UTC로는 11-09지만 서울은 11-10. 어제 = 서울 11-09."""
    student.streak_days, student.last_streak_date = 1, date(2026, 11, 9)
    await db_session.flush()
    await _send(client, student, sid, kind="text", text="3/8")
    assert (await _phase(client, student, sid, "bridge")).json()["streak_days"] == 2


# --- 6. bridge -----------------------------------------------------------------------


async def test_bridge_before_bridge_state_is_409(client, student, sid):
    r = await _bridge(client, student, sid)
    assert r.status_code == 409 and r.json()["code"] == "phase_not_allowed"


async def test_bridge_is_generated_once_and_stored(client, student, sid, spy):
    spy.summary = "나눗셈을 곱셈으로 바꾸는 단계"
    await _send(client, student, sid, kind="text", text="3/4")
    await _send(client, student, sid, kind="text", text="3/8")
    await _phase(client, student, sid, "bridge")
    first = (await _bridge(client, student, sid)).json()
    assert first["summary"][1] == "나눗셈을 곱셈으로 바꾸는 단계"
    spy.summary = "다른 문장"
    second = (await _bridge(client, student, sid)).json()
    assert second == first
    assert len(spy.summary_calls()) == 1


async def test_summary_input_has_no_chat_and_no_answer(client, student, sid, spy):
    spy.summary = "분모를 나누는 곳"
    await _send(client, student, sid, kind="text", text="3/4")
    await _send(client, student, sid, kind="text", text="6/16")  # 값은 정답과 같다
    await _phase(client, student, sid, "chat")
    await _send(client, student, sid, kind="text", text=CHAT_LINE)
    await _phase(client, student, sid, "bridge")
    await _bridge(client, student, sid)
    (call,) = spy.summary_calls()
    blob = call.system + " ".join(t["text"] for t in call.turns)
    assert CHAT_LINE not in blob
    assert "6/16" not in blob and "3/8" not in blob
    assert [t["text"] for t in call.turns] == ["3/4"]


@pytest.mark.parametrize("bad", [RuntimeError("down"), "", FIXED_REPLY, "답은 3/8이야"])
async def test_summary_falls_back_to_template(client, student, sid, spy, bad):
    spy.summary = bad
    await _send(client, student, sid, kind="text", text="3/8")
    await _phase(client, student, sid, "bridge")
    body = (await _bridge(client, student, sid)).json()
    assert body["summary"][1] == "막힌 곳 기록 없음"


async def test_bridge_after_end_returns_stored(client, student, sid):
    await _send(client, student, sid, kind="text", text="3/8")
    await _phase(client, student, sid, "bridge")
    before = (await _bridge(client, student, sid)).json()
    await _end(client, student, sid, None)
    r = await _bridge(client, student, sid)
    assert r.status_code == 200 and r.json() == before


async def test_bridge_guardian_line_particle(client, db_session, make_student):
    s = make_student(today_task_problem_id="frac-div-frac-diff-05", today_task_date=SEOUL_TODAY)
    db_session.add(s)
    await db_session.flush()
    sid = (await client.post("/api/v1/sessions", headers=_h(s))).json()["session_id"]
    await _send(client, s, sid, kind="text", text="3/4")
    await _phase(client, s, sid, "bridge")
    body = (await _bridge(client, s, sid)).json()
    assert body["guardian_line"] == "오늘 분모가 다른 분수의 나눗셈을 다시 풀었어요."
    assert [q["id"] for q in body["quiz_options"]] == [
        "frac-div-frac-diff-01",
        "frac-div-frac-diff-02",
        "frac-div-frac-diff-03",
    ]


# --- 7. end --------------------------------------------------------------------------


async def test_end_without_bridge_call_generates_card(client, db_session, student, sid):
    await _send(client, student, sid, kind="text", text="3/8")
    await _phase(client, student, sid, "bridge")
    r = await _end(client, student, sid, None)
    assert r.status_code == 200 and r.json()["state"] == "ended"
    row = await _row(db_session, sid)
    assert row.quiz_problem_id is None
    assert row.study_summary is not None and len(row.study_summary) == 3
    assert row.guardian_line == "오늘 분수 ÷ 자연수를 다시 풀었어요."


async def test_end_rejects_quiz_outside_options(client, student, sid):
    await _send(client, student, sid, kind="text", text="3/8")
    await _phase(client, student, sid, "bridge")
    for quiz in (PROBLEM, "frac-div-nat-05", "nat-div-nat-01"):
        r = await _end(client, student, sid, quiz)
        assert r.status_code == 422 and r.json()["code"] == "invalid_request"


async def test_end_outside_bridge(client, student, sid):
    r = await _end(client, student, sid, None)
    assert r.status_code == 409 and r.json()["code"] == "phase_not_allowed"
    await _send(client, student, sid, kind="text", text="3/8")
    await _phase(client, student, sid, "bridge")
    assert (await _end(client, student, sid, None)).status_code == 200
    r = await _end(client, student, sid, None)
    assert r.status_code == 409 and r.json()["code"] == "session_finished"


async def test_end_does_not_touch_streak(client, db_session, student, sid):
    await _send(client, student, sid, kind="text", text="3/8")
    await _phase(client, student, sid, "bridge")
    await _end(client, student, sid, None)
    await db_session.refresh(student)
    assert student.streak_days == 1


# --- 13. mentor ----------------------------------------------------------------------

MENTOR = {"style": "DQSC", "honorific": "unni", "polite": True}


async def test_mentor_updates_student_and_echoes(client, db_session, student):
    r = await client.put("/api/v1/me/mentor", headers=_h(student), json=MENTOR)
    assert r.status_code == 200 and r.json() == MENTOR
    row = await db_session.scalar(select(Student).where(Student.id == student.id))
    assert row is not None
    await db_session.refresh(row)
    assert (row.style, row.honorific, row.polite) == ("DQSC", "unni", True)


async def test_mentor_locked_while_session_in_progress(client, student, sid):
    r = await client.put("/api/v1/me/mentor", headers=_h(student), json=MENTOR)
    assert r.status_code == 409 and r.json()["code"] == "session_in_progress"


async def test_mentor_allowed_after_session_ended(client, student, sid):
    await _send(client, student, sid, kind="text", text="3/8")
    await _phase(client, student, sid, "bridge")
    await _end(client, student, sid, None)
    r = await client.put("/api/v1/me/mentor", headers=_h(student), json=MENTOR)
    assert r.status_code == 200


@pytest.mark.parametrize(
    "bad",
    [
        {**MENTOR, "style": "TIGER"},
        {**MENTOR, "honorific": "noona"},
        {**MENTOR, "polite": "yes"},
        {"style": "EBSP"},
    ],
)
async def test_mentor_rejects_bad_values(client, student, bad):
    r = await client.put("/api/v1/me/mentor", headers=_h(student), json=bad)
    assert r.status_code == 422 and r.json()["code"] == "invalid_request"
