"""API 11번 GET /guardian/today — 보호자 「오늘」 카드(명세 3.3·4.4·4.8-4). 문장은 전부 합성 값."""

from datetime import UTC, date, datetime, timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.actors import DEMO_CHILD_ID, DEMO_GUARDIAN_ID
from app.db import get_db
from app.main import create_app
from app.models import Alert, InstructorNote, Message, Session
from app.seed import load_seed
from app.timeutil import get_now

# UTC 11-09 21:00 = 서울 11-10 06:00
NOW = datetime(2026, 11, 9, 21, 0, tzinfo=UTC)
SEOUL_TODAY = date(2026, 11, 10)
URL = "/api/v1/guardian/today"
GUARDIAN = {"X-Demo-Role": "guardian", "X-Demo-Actor": DEMO_GUARDIAN_ID}
EMPTY = {"alert": None, "child_line": None, "quiz": None, "instructor_comment": None}


@pytest_asyncio.fixture
async def client(db_session, make_student):
    await load_seed(db_session)
    db_session.add(make_student(id=DEMO_CHILD_ID, nickname="지우"))
    await db_session.flush()
    app = create_app()

    async def _db():
        yield db_session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_now] = lambda: NOW
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _session(db, *, day=SEOUL_TODAY, **kw) -> Session:
    s = Session(student_id=DEMO_CHILD_ID, date=day, problem_id="frac-div-nat-01", **kw)
    db.add(s)
    await db.flush()
    return s


async def test_empty_card_has_four_null_keys(client):
    r = await client.get(URL, headers=GUARDIAN)
    assert r.status_code == 200
    assert r.json() == EMPTY


async def test_missing_headers_401(client):
    r = await client.get(URL)
    assert r.status_code == 401
    assert r.json()["code"] == "no_actor"


async def test_wrong_role_is_forbidden(client):
    for role in ("child", "instructor"):
        r = await client.get(URL, headers={"X-Demo-Role": role, "X-Demo-Actor": DEMO_GUARDIAN_ID})
        assert r.status_code == 403
        assert r.json()["code"] == "forbidden"


async def test_unknown_guardian_404(client):
    # 학생 id를 보호자 id 자리에 넣어도 대응표에 없으면 404
    for actor in ("nobody", DEMO_CHILD_ID):
        r = await client.get(URL, headers={"X-Demo-Role": "guardian", "X-Demo-Actor": actor})
        assert r.status_code == 404
        assert r.json()["code"] == "guardian_not_found"


async def test_red_alert_today_on_top(client, db_session):
    s = await _session(db_session, state="crisis", flag="red", end_reason="crisis")
    old = s.id
    db_session.add(
        Alert.new(
            session_id=old,
            student_id=DEMO_CHILD_ID,
            trigger="R1",
            excerpt="합성 발췌 하나",
            now=NOW - timedelta(minutes=5),
        )
    )
    db_session.add(
        Alert.new(
            session_id=old, student_id=DEMO_CHILD_ID, trigger="R2", excerpt="합성 발췌 둘", now=NOW
        )
    )
    await db_session.flush()
    body = (await client.get(URL, headers=GUARDIAN)).json()
    assert set(body) == set(EMPTY)
    assert "excerpt" not in body["alert"]  # 발췌는 보호자에게 보내지 않는다(11-12 결정, 분류만)
    assert body["alert"]["hotlines"] == ["109", "1388"]
    assert datetime.fromisoformat(body["alert"]["created_at"]) == NOW
    assert body["child_line"] is None  # crisis 세션은 한 줄 없음


async def test_yesterday_alert_not_shown(client, db_session):
    s = await _session(db_session, day=SEOUL_TODAY - timedelta(days=1), state="crisis")
    db_session.add(
        Alert.new(
            session_id=s.id,
            student_id=DEMO_CHILD_ID,
            trigger="R1",
            excerpt="어제 합성 발췌",
            now=NOW - timedelta(days=1),
        )
    )
    await db_session.flush()
    assert (await client.get(URL, headers=GUARDIAN)).json()["alert"] is None


async def test_ended_session_gives_child_line_and_quiz(client, db_session):
    s = await _session(
        db_session,
        state="ended",
        end_reason="normal",
        ended_at=NOW,
        guardian_line="오늘 분수 ÷ 자연수를 다시 풀었어요.",
        quiz_problem_id="frac-div-nat-01",
    )
    db_session.add(
        Message.new(session_id=s.id, seq=1, role="child", text_redacted="합성 대화 문장", now=NOW)
    )
    await db_session.flush()
    r = await client.get(URL, headers=GUARDIAN)
    body = r.json()
    assert body["child_line"] == "오늘 분수 ÷ 자연수를 다시 풀었어요."
    assert body["quiz"] == {"text": "3/4 ÷ 2 를 계산해 보세요."}
    assert body["alert"] is None
    assert "합성 대화 문장" not in r.text  # 대화 내용은 싣지 않는다(명세 3.3)


async def test_in_progress_session_has_no_child_line(client, db_session):
    await _session(db_session, state="chat", guardian_line="아직 끝나지 않은 한 줄")
    body = (await client.get(URL, headers=GUARDIAN)).json()
    assert body["child_line"] is None
    assert body["quiz"] is None


async def test_instructor_comment_only_when_published(client, db_session):
    note = InstructorNote(
        student_id=DEMO_CHILD_ID,
        date=SEOUL_TODAY,
        draft_body="합성 초안",
        final_body=None,
        status="draft",
    )
    db_session.add(note)
    await db_session.flush()
    assert (await client.get(URL, headers=GUARDIAN)).json()["instructor_comment"] is None

    note.status = "published"
    note.final_body = "합성 승인본"
    await db_session.flush()
    assert (await client.get(URL, headers=GUARDIAN)).json()["instructor_comment"] == "합성 승인본"


async def test_skipped_or_other_day_note_not_shown(client, db_session):
    db_session.add(
        InstructorNote(student_id=DEMO_CHILD_ID, date=SEOUL_TODAY, status="skipped", final_body="x")
    )
    db_session.add(
        InstructorNote(
            student_id=DEMO_CHILD_ID,
            date=SEOUL_TODAY - timedelta(days=1),
            status="published",
            final_body="어제 승인본",
        )
    )
    await db_session.flush()
    assert (await client.get(URL, headers=GUARDIAN)).json()["instructor_comment"] is None
