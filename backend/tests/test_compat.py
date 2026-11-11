"""프론트 v0.5 호환 라우터 /api/v1/compat (11-15까지 임시).

판정·전환은 기존 서버 함수 그대로라, 여기서는 프론트 JSON 모양과 「정답이 새지 않음」만 본다.
문장은 전부 합성이다. 시계는 테스트가 움직인다(서울 날짜 기준).
"""

from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.actors import DEMO_CHILD_ID, DEMO_GUARDIAN_ID, DEMO_INSTRUCTOR_ID
from app.api import TAG_NAME, get_llm
from app.db import get_db
from app.llm import ScriptedAdapter
from app.main import create_app
from app.models import Problem, Session, Student
from app.seed import load_seed
from app.timeutil import get_now

NOW = datetime(2026, 11, 9, 21, 0, tzinfo=UTC)  # 서울 11-10(화) 06:00
SEOUL_TODAY = date(2026, 11, 10)
PROBLEM = "frac-div-nat-01"  # 3/4 ÷ 2
BASE = "/api/v1/compat"
CHILD = {"X-Demo-Role": "child", "X-Demo-Actor": DEMO_CHILD_ID}
GUARDIAN = {"X-Demo-Role": "guardian", "X-Demo-Actor": DEMO_GUARDIAN_ID}
INSTRUCTOR = {"X-Demo-Role": "instructor", "X-Demo-Actor": DEMO_INSTRUCTOR_ID}
CHAT_LINE = "오늘 운동장에서 줄넘기 했어"  # 합성 수다 문장
RED_LINE = "요즘 그냥 죽고 싶어"  # 합성 🔴 문장


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def tick(self, seconds: int = 1) -> None:
        self.now += timedelta(seconds=seconds)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest_asyncio.fixture
async def client(db_session, clock, make_student):
    await load_seed(db_session)
    db_session.add(
        make_student(id=DEMO_CHILD_ID, today_task_problem_id=PROBLEM, today_task_date=SEOUL_TODAY)
    )
    await db_session.flush()
    app = create_app()

    async def _db():
        yield db_session

    scripted = ScriptedAdapter.from_file()
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_now] = lambda: clock.now
    app.dependency_overrides[get_llm] = lambda: scripted
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


class Recorder:
    """compat 응답 본문을 모두 모아 둔다(정답 누출 검사용)."""

    def __init__(self, client: AsyncClient) -> None:
        self.c = client
        self.bodies: list[str] = []

    async def __call__(self, method: str, path: str, headers=CHILD, **kw):
        r = await self.c.request(method, BASE + path, headers=headers, **kw)
        self.bodies.append(r.text)
        return r


async def _answer_strings(db_session) -> list[str]:
    p = await db_session.get(Problem, PROBLEM)
    assert p is not None
    return [p.answer["value"], *p.answer.get("accepted", []), *p.forbidden]


async def test_day_flow(client, db_session, clock):
    call = Recorder(client)

    home = (await call("GET", "/student/home")).json()
    assert home["session"] is None and home["doneToday"] is False
    assert home["task"]["unit"] == "분수 ÷ 자연수"
    assert len(home["attendance"]) == 7 and home["todayIndex"] == 1  # 화요일
    assert (await call("GET", "/sessions/active")).json() is None

    s = (await call("POST", "/sessions", json={"difficulty": "중급"})).json()
    sid = s["id"]
    assert s["phase"] == "solve" and s["total"] == 1 and s["solved"] == 0

    p = (await call("GET", f"/sessions/{sid}/problem")).json()
    assert p["id"] == PROBLEM
    assert p["text"].startswith("3/4 ÷ 2")
    assert p["left"] == [3, 4] and p["right"] == [2, 1] and p["op"] == "÷"
    assert p["hints"] == [] and p["hintsLeft"] == 2 and p["canShowSolution"] is False
    assert "answer" not in p and "solution" not in p

    clock.tick()
    wrong = await call(
        "POST",
        f"/sessions/{sid}/answer",
        json={"problemId": PROBLEM, "numerator": 3, "denominator": 2},
    )
    w = wrong.json()
    assert w["correct"] is False and w["autoHint"] is None  # 힌트는 버튼으로만(명세 3.2)
    assert w["message"] and w["session"]["phase"] == "solve"
    assert w["hintsLeft"] == 2 and w["canShowSolution"] is False

    h = (await call("POST", f"/sessions/{sid}/hint", json={"problemId": PROBLEM})).json()
    assert len(h["hints"]) == 1 and h["hintsLeft"] == 1

    clock.tick()
    ok = (
        await call(
            "POST",
            f"/sessions/{sid}/answer",
            json={"problemId": PROBLEM, "numerator": 3, "denominator": 8},
        )
    ).json()
    assert ok["correct"] is True
    assert ok["session"]["phase"] == "transition" and ok["session"]["solved"] == 1
    assert (await call("GET", f"/sessions/{sid}/problem")).json() is None

    clock.tick()
    v = (await call("POST", f"/sessions/{sid}/after-study", json={"choice": "chat"})).json()
    assert v["phase"] == "chat" and v["streakDays"] == 1
    assert v["chatRemainingSec"] == 600

    clock.tick()
    reply = (await call("POST", f"/sessions/{sid}/chat", json={"text": CHAT_LINE})).json()
    assert reply["crisis"] is False and reply["reply"]
    chat = (await call("GET", f"/sessions/{sid}/chat")).json()
    assert [m["from"] for m in chat["messages"]] == ["me", "mentor"]  # 풀이 단계 메시지는 빠진다

    v = (await call("POST", f"/sessions/{sid}/chat/end")).json()
    assert v["phase"] == "wrap"

    wrap = (await call("GET", f"/sessions/{sid}/wrap")).json()
    assert len(wrap["quizOptions"]) == 3 and wrap["aiLine"]
    quiz = wrap["quizOptions"][0]
    done = (
        await call("POST", f"/sessions/{sid}/wrap", json={"hardPoint": None, "quiz": quiz})
    ).json()
    assert done["phase"] == "done"

    home = (await call("GET", "/student/home")).json()
    assert home["doneToday"] is True and home["session"]["phase"] == "done"

    card = (await call("GET", "/guardian/today", headers=GUARDIAN)).json()
    assert card["done"] is True and card["quiz"] == quiz and card["line"]
    assert (await call("GET", "/guardian/alerts", headers=GUARDIAN)).json() == []

    leaks = await _answer_strings(db_session)
    for body in call.bodies:
        assert not any(s in body for s in leaks), body


async def test_crisis_in_chat(client, clock):
    call = Recorder(client)
    sid = (await call("POST", "/sessions", json={"difficulty": "초급"})).json()["id"]
    for _ in range(2):
        await call("POST", f"/sessions/{sid}/hint", json={"problemId": PROBLEM})
    sol = (await call("POST", f"/sessions/{sid}/solution", json={"problemId": PROBLEM})).json()
    assert sol["steps"] and sol["session"]["phase"] == "transition"
    clock.tick()
    await call("POST", f"/sessions/{sid}/after-study", json={"choice": "chat"})
    clock.tick()

    r = (await call("POST", f"/sessions/{sid}/chat", json={"text": RED_LINE})).json()
    assert r["crisis"] is True and r["session"]["phase"] == "crisis"
    assert r["hotlines"] == ["109", "1388"]

    alerts = (await call("GET", "/guardian/alerts", headers=GUARDIAN)).json()
    assert len(alerts) == 1
    a = alerts[0]
    assert a["level"] == "긴급" and a["status"] == "미확인"
    assert a["excerpt"]  # 현재 정책(발췌 ±2턴·300자) 그대로 — 11-10 안건 2
    card = (await call("GET", "/guardian/today", headers=GUARDIAN)).json()
    assert card["done"] is False and card["line"] is None


async def test_solution_needs_both_hints(client):
    call = Recorder(client)
    sid = (await call("POST", "/sessions", json={"difficulty": "초급"})).json()["id"]
    r = await call("POST", f"/sessions/{sid}/solution", json={"problemId": PROBLEM})
    assert r.status_code == 409 and r.json()["detail"]


@pytest.mark.parametrize("path", ["hint", "solution"])
async def test_hint_and_solution_busy_while_replying(client, db_session, clock, path):
    """답 생성 중에는 기본 경로 kind:hint처럼 409 busy(계약 프론트 할 일 9)."""
    call = Recorder(client)
    sid = (await call("POST", "/sessions", json={"difficulty": "중급"})).json()["id"]
    row = await db_session.get(Session, sid)
    row.replying_until = clock.now + timedelta(seconds=10)
    await db_session.flush()
    r = await call("POST", f"/sessions/{sid}/{path}", json={"problemId": PROBLEM})
    assert r.status_code == 409 and r.json()["code"] == "busy"
    await db_session.refresh(row)
    assert row.hint_level == 0


async def test_answer_carries_source(client):
    call = Recorder(client)
    sid = (await call("POST", "/sessions", json={"difficulty": "초급"})).json()["id"]
    body = {"problemId": PROBLEM, "numerator": 1, "denominator": 2}
    r = (await call("POST", f"/sessions/{sid}/answer", json=body)).json()
    assert r["message"] and r["queued"] is False and r["source"] == "scripted"


async def test_answer_while_replying_is_queued(client, db_session, clock):
    """B7: 답 생성 중 제출은 흡수 — queued:true, 빈 message, 판정은 저장된 대로."""
    call = Recorder(client)
    sid = (await call("POST", "/sessions", json={"difficulty": "초급"})).json()["id"]
    row = await db_session.get(Session, sid)
    row.replying_until = clock.now + timedelta(seconds=10)
    await db_session.flush()
    body = {"problemId": PROBLEM, "numerator": 3, "denominator": 8}
    r = (await call("POST", f"/sessions/{sid}/answer", json=body)).json()
    assert r["queued"] is True and r["message"] == "" and r["source"] is None
    assert r["correct"] is True


async def test_mentor_round_trip(client):
    call = Recorder(client)
    body = {"style": "들어주는", "title": "언니", "speech": "존댓말", "animal": "horse"}
    assert (await call("PUT", "/student/mentor", json=body)).status_code == 200
    got = (await call("GET", "/student/mentor")).json()
    assert got == {"style": "들어주는", "title": "언니", "speech": "존댓말", "animal": None}


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/student/home"),
        ("GET", "/sessions/active"),
        ("POST", "/sessions"),
        ("GET", "/guardian/today"),
        ("GET", "/guardian/alerts"),
    ],
)
async def test_rejects_without_headers(client, method, path):
    kw = {"json": {"difficulty": "초급"}} if method == "POST" else {}
    r = await client.request(method, BASE + path, **kw)
    assert r.status_code == 401
    body = r.json()
    assert body["code"] == "no_actor" and body["detail"] == body["message"]


async def _to_chat(call, clock) -> str:
    sid = (await call("POST", "/sessions", json={"difficulty": "초급"})).json()["id"]
    clock.tick(5 * 60)
    await call(
        "POST",
        f"/sessions/{sid}/answer",
        json={"problemId": PROBLEM, "numerator": 3, "denominator": 8},
    )
    await call("POST", f"/sessions/{sid}/after-study", json={"choice": "chat"})
    clock.tick()
    return sid


async def test_chat_empty_is_422_and_after_crisis_is_409(client, clock):
    call = Recorder(client)
    sid = await _to_chat(call, clock)
    r = await call("POST", f"/sessions/{sid}/chat", json={"text": "  "})
    assert r.status_code == 422 and r.json()["code"] == "invalid_request"
    r = await call("POST", f"/sessions/{sid}/chat", json={"text": RED_LINE})
    assert r.json()["crisis"] is True
    r = await call("POST", f"/sessions/{sid}/chat", json={"text": CHAT_LINE})
    assert r.status_code == 409 and r.json()["code"] == "session_finished"


async def test_chat_pieces_and_reply_route(client, clock):
    call = Recorder(client)
    sid = await _to_chat(call, clock)
    r = (await call("POST", f"/sessions/{sid}/chat", json={"texts": ["음", CHAT_LINE]})).json()
    assert r["reply"] and r["queued"] is False and r["pending"] is False
    assert r["source"] == "scripted"
    r = await call("POST", f"/sessions/{sid}/reply")
    assert r.status_code == 409 and r.json()["code"] == "nothing_to_reply"


async def test_study_min_survives_phase_change(client, clock):
    call = Recorder(client)
    await _to_chat(call, clock)
    v = (await call("GET", "/sessions/active")).json()
    assert v["phase"] == "chat" and v["studyMin"] == 5


# --- 약속 화면 동의 저장 ---------------------------------------------------------------


async def test_promise_sets_consent(client, db_session):
    call = Recorder(client)
    assert (await call("GET", "/student/home")).json()[
        "needsOnboarding"
    ] is True  # 합성 학생은 동의 전
    r = await call("POST", "/student/promise")
    assert r.status_code == 204
    assert (await call("GET", "/student/home")).json()["needsOnboarding"] is False
    student = await db_session.get(Student, DEMO_CHILD_ID)
    assert student is not None and student.consent is True


# --- 강사 (F5) ------------------------------------------------------------------------

MEMO = {
    "covered": "분수 ÷ 자연수",
    "stuck": "나눗셈을 곱셈으로 바꾸는 단계",
    "homework": "익힘책 2쪽",
    "note": "집중을 잘 했어요",
}
EDITED = "테스트학생이 오늘 끝까지 잘 풀었어요. 궁금하시면 010-2222-3333으로 연락 주세요."


@pytest.fixture
def scripted_draft(monkeypatch):
    # 초안은 scripted(대본 없음) → 템플릿. 결정적이다
    monkeypatch.delenv("LLM_MODE", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)


async def test_teacher_memo_draft_edit_approve_reaches_guardian(client, db_session, scripted_draft):
    call = Recorder(client)

    today = (await call("GET", "/teacher/today", headers=INSTRUCTOR)).json()
    assert today["units"] == list(TAG_NAME.values())
    assert today["dateLabel"] and today["className"]
    row = next(s for s in today["students"] if s["id"] == DEMO_CHILD_ID)
    assert row == {
        "id": DEMO_CHILD_ID,
        "name": "테스트학생",
        "task": "분수 ÷ 자연수",
        "status": "지정됨",
        "draftStatus": None,
    }

    empty = (
        await call("GET", f"/teacher/students/{DEMO_CHILD_ID}/memo", headers=INSTRUCTOR)
    ).json()
    assert empty == {
        "memo": {"covered": "", "stuck": "", "homework": "", "note": ""},
        "draft": None,
    }

    url = f"/teacher/students/{DEMO_CHILD_ID}"
    r = await call("PUT", f"{url}/memo", headers=INSTRUCTOR, json=MEMO)
    assert r.status_code == 204
    draft = (await call("POST", f"{url}/draft", headers=INSTRUCTOR)).json()
    assert draft["studentId"] == DEMO_CHILD_ID and draft["studentName"] == "테스트학생"
    assert draft["scope"] == "분수 ÷ 자연수"
    assert draft["amount"] == "미완료" and draft["mode"] == "-"
    assert draft["comment"] and draft["status"] == "승인 대기"

    # 같은 날 메모를 다시 저장해도 초안은 그대로(재생성 없음, 명세 3.4)
    await call("PUT", f"{url}/memo", headers=INSTRUCTOR, json={**MEMO, "note": "다른 메모"})
    again = (await call("POST", f"{url}/draft", headers=INSTRUCTOR)).json()
    assert again["comment"] == draft["comment"]

    got = (await call("GET", f"{url}/memo", headers=INSTRUCTOR)).json()
    assert got["memo"] == MEMO and got["draft"] == draft

    edited = (
        await call("PUT", f"{url}/draft", headers=INSTRUCTOR, json={"comment": EDITED})
    ).json()
    assert edited["status"] == "승인 대기"
    assert "[이름]" in edited["comment"] and "[전화]" in edited["comment"]
    assert "테스트학생" not in edited["comment"] and "010-2222-3333" not in edited["comment"]
    row = (await call("GET", "/teacher/today", headers=INSTRUCTOR)).json()["students"][0]
    assert row["draftStatus"] == "승인 대기"

    approved = (await call("POST", f"{url}/draft/approve", headers=INSTRUCTOR)).json()
    assert approved["status"] == "승인됨" and approved["comment"] == edited["comment"]
    card = (await call("GET", "/guardian/today", headers=GUARDIAN)).json()
    assert card["teacherComment"] == edited["comment"]
    row = (await call("GET", "/teacher/today", headers=INSTRUCTOR)).json()["students"][0]
    assert row["draftStatus"] == "승인됨"

    # 승인 뒤 고치기·다시 승인은 409
    r = await call("PUT", f"{url}/draft", headers=INSTRUCTOR, json={"comment": "다시 고침"})
    assert r.status_code == 409 and r.json()["code"] == "note_closed"
    r = await call("POST", f"{url}/draft/approve", headers=INSTRUCTOR)
    assert r.status_code == 409 and r.json()["code"] == "note_closed"

    for leaked in await _answer_strings(db_session):
        assert all(leaked not in b for b in call.bodies)


async def test_teacher_draft_without_memo_is_409(client, scripted_draft):
    url = f"{BASE}/teacher/students/{DEMO_CHILD_ID}"
    r = await client.post(f"{url}/draft", headers=INSTRUCTOR)
    assert r.status_code == 409 and r.json()["code"] == "no_note"
    r = await client.put(f"{url}/draft", headers=INSTRUCTOR, json={"comment": "합성 문장"})
    assert r.status_code == 409 and r.json()["code"] == "no_note"
    r = await client.post(f"{url}/draft/approve", headers=INSTRUCTOR)
    assert r.status_code == 409 and r.json()["code"] == "no_note"


async def test_teacher_blank_edit_is_422(client, scripted_draft):
    url = f"{BASE}/teacher/students/{DEMO_CHILD_ID}"
    await client.put(f"{url}/memo", headers=INSTRUCTOR, json=MEMO)
    r = await client.put(f"{url}/draft", headers=INSTRUCTOR, json={"comment": "  "})
    assert r.status_code == 422


async def test_teacher_assign_unit_reaches_child_home(client, db_session):
    unit = "분모가 다른 분수의 나눗셈"
    first = await db_session.scalar(
        select(Problem.id).where(Problem.tag == "frac-div-frac-diff").order_by(Problem.id).limit(1)
    )
    url = f"{BASE}/teacher/students/{DEMO_CHILD_ID}/task"
    today = (await client.put(url, headers=INSTRUCTOR, json={"unit": unit})).json()
    row = next(s for s in today["students"] if s["id"] == DEMO_CHILD_ID)
    assert row["task"] == unit and row["status"] == "지정됨"
    student = await db_session.get(Student, DEMO_CHILD_ID)
    assert student is not None and student.today_task_problem_id == first
    home = (await client.get(f"{BASE}/student/home", headers=CHILD)).json()
    assert home["task"]["unit"] == unit

    # 해제
    today = (await client.put(url, headers=INSTRUCTOR, json={"unit": None})).json()
    row = next(s for s in today["students"] if s["id"] == DEMO_CHILD_ID)
    assert row["task"] is None and row["status"] == "지정 전"
    home = (await client.get(f"{BASE}/student/home", headers=CHILD)).json()
    assert home["task"] is None

    r = await client.put(url, headers=INSTRUCTOR, json={"unit": "없는 단원"})
    assert r.status_code == 422


async def test_teacher_status_and_facts_follow_session(client, clock, scripted_draft):
    call = Recorder(client)
    await _to_chat(call, clock)
    row = (await call("GET", "/teacher/today", headers=INSTRUCTOR)).json()["students"][0]
    assert row["status"] == "진행 중"
    url = f"/teacher/students/{DEMO_CHILD_ID}"
    await call("PUT", f"{url}/memo", headers=INSTRUCTOR, json=MEMO)
    draft = (await call("POST", f"{url}/draft", headers=INSTRUCTOR)).json()
    assert draft["amount"] == "1/1문제" and draft["mode"] == "힌트 0번"


async def test_teacher_alerts_empty(client):
    r = await client.get(f"{BASE}/teacher/alerts", headers=INSTRUCTOR)
    assert r.status_code == 200 and r.json() == []


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/teacher/today"),
        ("PUT", f"/teacher/students/{DEMO_CHILD_ID}/task"),
        ("GET", f"/teacher/students/{DEMO_CHILD_ID}/memo"),
        ("PUT", f"/teacher/students/{DEMO_CHILD_ID}/memo"),
        ("POST", f"/teacher/students/{DEMO_CHILD_ID}/draft"),
        ("PUT", f"/teacher/students/{DEMO_CHILD_ID}/draft"),
        ("POST", f"/teacher/students/{DEMO_CHILD_ID}/draft/approve"),
        ("GET", "/teacher/alerts"),
    ],
)
async def test_teacher_routes_reject_child_header(client, method, path):
    kw = {"json": {}} if method in ("PUT", "POST") else {}
    r = await client.request(method, BASE + path, headers=CHILD, **kw)
    assert r.status_code == 403 and r.json()["code"] == "forbidden"
    r = await client.request(method, BASE + path, **kw)
    assert r.status_code == 401


async def test_teacher_task_and_scope_follow_started_session(client, scripted_draft):
    """아이가 시작하면 지정은 세션으로 옮겨져 비워진다(명세 4.2). 그래도 강사 화면에는
    오늘 푸는 단원이 보이고, 초안의 scope도 다음 지정이 아니라 오늘 푼 단원이다."""
    call = Recorder(client)
    await call("POST", "/sessions", json={"difficulty": "중급"})
    today = (await call("GET", "/teacher/today", headers=INSTRUCTOR)).json()
    row = next(s for s in today["students"] if s["id"] == DEMO_CHILD_ID)
    assert row["task"] == "분수 ÷ 자연수" and row["status"] == "진행 중"

    await call(
        "PUT",
        f"/teacher/students/{DEMO_CHILD_ID}/task",
        headers=INSTRUCTOR,
        json={"unit": "분모가 같은 분수의 나눗셈"},
    )
    await call(
        "PUT",
        f"/teacher/students/{DEMO_CHILD_ID}/memo",
        headers=INSTRUCTOR,
        json={"covered": "합성 메모", "stuck": "", "homework": "", "note": ""},
    )
    draft = (
        await call("POST", f"/teacher/students/{DEMO_CHILD_ID}/draft", headers=INSTRUCTOR)
    ).json()
    assert draft["scope"] == "분수 ÷ 자연수"
