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
from app.compat import GUARDIAN_ALERT_NOTICE
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
    # 완료 화면은 수다·끝으로 넘어갈 때 셀 연속 일수를 미리 보여 준다(3 → 4 어긋남 없앰, 11-11)
    assert ok["session"]["streakDays"] == 1
    assert (await call("GET", "/guardian/today", headers=GUARDIAN)).json()["alertNotice"] is None
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
    assert a["excerpt"]  # 🔴이면 발췌 ±2턴·300자가 보호자에게 간다(결정 11-10·11-11)
    card = (await call("GET", "/guardian/today", headers=GUARDIAN)).json()
    assert card["done"] is False and card["line"] is None
    # 위기로 끝난 날 보호자 첫 화면: 「공부 전」 대신 알림 확인 안내(문구는 상수 한곳, 11-11)
    assert card["alertNotice"] == GUARDIAN_ALERT_NOTICE


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
    # 저장본은 치환본, 학습지도자 화면에는 이름만 되돌려 보인다(11-11 성호). 전화는 계속 가림
    assert "테스트학생" in edited["comment"] and "[이름]" not in edited["comment"]
    assert "[전화]" in edited["comment"] and "010-2222-3333" not in edited["comment"]
    row = (await call("GET", "/teacher/today", headers=INSTRUCTOR)).json()["students"][0]
    assert row["draftStatus"] == "승인 대기"

    approved = (await call("POST", f"{url}/draft/approve", headers=INSTRUCTOR)).json()
    assert approved["status"] == "승인됨" and approved["comment"] == edited["comment"]
    card = (await call("GET", "/guardian/today", headers=GUARDIAN)).json()
    # 보호자 화면에서는 표시 직전에 「[이름]」을 별명으로 되돌린다(11-11 A6)
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


# --- 11-12 이상 입력 점검(탐침) 결과 ------------------------------------------------------


async def test_study_chat_still_checks_red_keyword(client, clock):
    """같이 풀기 중에 수다 경로로 온 말도 🔴 검사를 거친다(단계가 어긋난 화면에서 사라지지 않게)."""
    call = Recorder(client)
    sid = (await call("POST", "/sessions", json={"difficulty": "초급"})).json()["id"]
    r = (await call("POST", f"/sessions/{sid}/chat", json={"text": CHAT_LINE})).json()
    assert r["crisis"] is False and r["reply"] == ""
    r = (
        await call("POST", f"/sessions/{sid}/chat", json={"texts": ["요즘 그냥", "죽고 싶어"]})
    ).json()
    assert r["crisis"] is True and r["hotlines"] == ["109", "1388"]
    alerts = (await call("GET", "/guardian/alerts", headers=GUARDIAN)).json()
    assert len(alerts) == 1


async def test_huge_answer_is_422_not_500(client):
    call = Recorder(client)
    sid = (await call("POST", "/sessions", json={"difficulty": "초급"})).json()["id"]
    big = int("9" * 600)
    r = await call(
        "POST",
        f"/sessions/{sid}/answer",
        json={"problemId": PROBLEM, "numerator": big, "denominator": big},
    )
    assert r.status_code == 422 and r.json()["code"] == "invalid_request"


async def test_memo_long_student_id_is_404(client, scripted_draft):
    call = Recorder(client)
    r = await call("PUT", f"/teacher/students/{'x' * 37}/memo", headers=INSTRUCTOR, json=MEMO)
    assert r.status_code == 404 and r.json()["code"] == "student_not_found"


@pytest.mark.parametrize("field", ["covered", "comment"])
async def test_long_draft_can_be_approved(client, scripted_draft, field):
    """템플릿 문장·이름 치환으로 초안이 2000자를 넘어도 승인은 된다(강사 화면이 막히지 않게)."""
    call = Recorder(client)
    url = f"/teacher/students/{DEMO_CHILD_ID}"
    memo = {**MEMO, "covered": "분수" * 1000} if field == "covered" else MEMO
    assert (await call("PUT", f"{url}/memo", headers=INSTRUCTOR, json=memo)).status_code == 204
    if field == "comment":
        r = await call("PUT", f"{url}/draft", headers=INSTRUCTOR, json={"comment": "지우 " * 400})
        assert r.status_code == 200
    r = await call("POST", f"{url}/draft/approve", headers=INSTRUCTOR)
    assert r.status_code == 200, r.text


async def test_reply_after_chat_deadline_does_not_answer(client, db_session, clock):
    """A1: 마감 뒤(다리 놓기)에 온 말에는 /reply로도 AI가 답하지 않는다."""
    from sqlalchemy import func, select

    from app.models import Message

    async def mentor_count() -> int:
        q = select(func.count()).select_from(Message)
        return await db_session.scalar(q.where(Message.session_id == sid, Message.role == "mentor"))

    call = Recorder(client)
    sid = await _to_chat(call, clock)
    clock.tick(11 * 60)
    r = (await call("POST", f"/sessions/{sid}/chat", json={"text": CHAT_LINE})).json()
    assert r["reply"] == "" and r["session"]["phase"] == "wrap"
    before = await mentor_count()
    r = await call("POST", f"/sessions/{sid}/reply")
    assert r.status_code == 200 and r.json()["reply"] == ""
    assert await mentor_count() == before


async def test_homework_reaches_guardian_only_after_approval(client, scripted_draft):
    # 명세 부록 D: 숙제는 초안 본문이 아니라 사실 칸으로 서버가 카드에 붙인다(11-13 전체 흐름 시험에서 빠짐 발견)
    url = f"/teacher/students/{DEMO_CHILD_ID}"
    memo = {**MEMO, "homework": "익힘책 2쪽, 테스트학생 엄마께 010-2222-3333"}
    await client.put(BASE + f"{url}/memo", headers=INSTRUCTOR, json=memo)
    before = (await client.get(BASE + "/guardian/today", headers=GUARDIAN)).json()
    assert before["homework"] is None  # 승인 전에는 보호자에게 아무것도 안 간다
    await client.post(BASE + f"{url}/draft/approve", headers=INSTRUCTOR)
    after = (await client.get(BASE + "/guardian/today", headers=GUARDIAN)).json()
    assert after["homework"].startswith("익힘책 2쪽")
    assert "테스트학생" in after["homework"] and "[이름]" not in after["homework"]
    assert "010-2222-3333" not in after["homework"]  # 전화는 계속 가림


async def test_draft_says_when_it_is_the_template(client, scripted_draft):
    # 수정 명세 B33: 초안이 템플릿으로 바뀌어도 응답에 표시가 없어 강사가 AI 초안인지 몰랐다
    url = f"/teacher/students/{DEMO_CHILD_ID}"
    await client.put(BASE + f"{url}/memo", headers=INSTRUCTOR, json=MEMO)
    draft = (await client.post(BASE + f"{url}/draft", headers=INSTRUCTOR)).json()
    assert draft["source"] == "template"


async def test_draft_source_live_when_model_wrote_it():
    from app.instructor import _draft_body
    from app.llm import Reply

    class Live:
        async def reply(self, req):
            return Reply('{"body": "오늘 분수 나눗셈을 끝까지 풀었습니다."}', "live")

    class Student:
        style = "EBSP"

    body, source = await _draft_body(Live(), Student(), "분수", "역수", "", [])  # type: ignore[arg-type]
    assert source == "live" and body.startswith("오늘 분수")
