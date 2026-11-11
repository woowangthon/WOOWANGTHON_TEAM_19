"""11-11 A6: 별명 「지우」가 일상어(지우개)를 깨뜨리지 않게. 문장은 전부 합성 값.

(1) 보호자에게 보이는 선생님 코멘트는 표시 직전에 「[이름]」을 별명으로 되돌린다.
    저장본은 여전히 치환본이다.
(2) 별명은 기본으로 가리고, 별명으로 시작하는 일상어(지우개·지우기 등)만 남긴다.
"""

from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.actors import DEMO_CHILD_ID, DEMO_GUARDIAN_ID, DEMO_INSTRUCTOR_ID
from app.db import get_db
from app.main import create_app
from app.models import InstructorNote
from app.pii import redact, unredact_name
from app.seed import load_seed
from app.timeutil import get_now

NAME = "지우"

# ---------- (2) 아이 문장: 이름 + 조사만 가린다 ----------


@pytest.mark.parametrize(
    "raw",
    ["지우개 잃어버렸어", "지우개를 샀어", "새 지우개야", "지우기 싫어", "숙제 다 지웠어"],
)
def test_name_followed_by_non_josa_hangul_is_kept(raw):
    assert redact(raw, names=[NAME]) == raw


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("지우야 안녕", "[이름]야 안녕"),
        ("지우가 그랬어", "[이름]가 그랬어"),
        ("지우는 몰라", "[이름]는 몰라"),
        ("지우를 불렀어", "[이름]를 불렀어"),
        ("지우의 공책", "[이름]의 공책"),
        ("지우에게 줬어", "[이름]에게 줬어"),
        ("지우한테 말했어", "[이름]한테 말했어"),
        ("지우랑 놀았어", "[이름]랑 놀았어"),
        ("지우도 왔어", "[이름]도 왔어"),
        ("지우만 남았어", "[이름]만 남았어"),
        ("지우아 와", "[이름]아 와"),
        ("나는 지우", "나는 [이름]"),
        ("지우 왔어", "[이름] 왔어"),
        ("지우!", "[이름]!"),
        ("(지우)", "([이름])"),
    ],
)
def test_name_at_end_or_before_josa_is_redacted(raw, want):
    assert redact(raw, names=[NAME]) == want


def test_mixed_sentence_keeps_eraser_and_hides_name():
    raw = "지우가 지우개 빌려줬어"
    assert redact(raw, names=[NAME]) == "[이름]가 지우개 빌려줬어"


def test_instructor_memo_uses_same_rule():
    # 강사 메모도 같은 redact를 쓴다: 「지우가 집중」은 여전히 가려진다
    assert redact("지우가 집중을 잘했어요", names=[NAME]) == "[이름]가 집중을 잘했어요"
    assert redact("지우개를 자꾸 떨어뜨려요", names=[NAME]) == "지우개를 자꾸 떨어뜨려요"


# ---------- (1) 표시 때 되돌리기 ----------


def test_unredact_name_restores_nickname():
    assert unredact_name("[이름]가 오늘 집중을 잘했어요", NAME) == "지우가 오늘 집중을 잘했어요"


def test_unredact_name_leaves_other_markers():
    assert unredact_name("[이름] [전화] [학교]", NAME) == "지우 [전화] [학교]"


@pytest.mark.parametrize("nick", [None, "", "  "])
def test_unredact_name_without_nickname_keeps_text(nick):
    assert unredact_name("[이름]가 왔어요", nick) == "[이름]가 왔어요"


def test_unredact_name_none_text():
    assert unredact_name(None, NAME) is None


NOW = datetime(2026, 11, 9, 21, 0, tzinfo=UTC)  # 서울 11-10 06:00
SEOUL_TODAY = date(2026, 11, 10)
GUARDIAN = {"X-Demo-Role": "guardian", "X-Demo-Actor": DEMO_GUARDIAN_ID}
INSTRUCTOR = {"X-Demo-Role": "instructor", "X-Demo-Actor": DEMO_INSTRUCTOR_ID}


@pytest_asyncio.fixture
async def client(db_session, make_student):
    await load_seed(db_session)
    db_session.add(make_student(id=DEMO_CHILD_ID, nickname=NAME))
    await db_session.flush()
    app = create_app()

    async def _db():
        yield db_session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_now] = lambda: NOW
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _published_note(db_session, final: str) -> InstructorNote:
    note = InstructorNote(
        student_id=DEMO_CHILD_ID,
        date=SEOUL_TODAY,
        draft_body="합성 초안",
        final_body=final,
        status="published",
    )
    db_session.add(note)
    await db_session.flush()
    return note


async def test_guardian_today_shows_name_but_store_keeps_marker(client, db_session):
    note = await _published_note(db_session, "[이름]가 오늘 집중을 잘했어요")
    body = (await client.get("/api/v1/guardian/today", headers=GUARDIAN)).json()
    assert body["instructor_comment"] == "지우가 오늘 집중을 잘했어요"
    await db_session.refresh(note)
    assert note.final_body == "[이름]가 오늘 집중을 잘했어요"  # 저장본은 치환본 그대로


async def test_compat_guardian_today_shows_name(client, db_session):
    await _published_note(db_session, "[이름]가 오늘 집중을 잘했어요")
    r = await client.get("/api/v1/compat/guardian/today", headers=GUARDIAN)
    assert r.json()["teacherComment"] == "지우가 오늘 집중을 잘했어요"


async def test_approve_stores_redacted_and_guardian_sees_name(client, db_session):
    note = InstructorNote(
        student_id=DEMO_CHILD_ID, date=SEOUL_TODAY, draft_body="합성 초안", status="draft"
    )
    db_session.add(note)
    await db_session.flush()
    r = await client.post(
        f"/api/v1/instructor/notes/{note.id}/approve",
        headers=INSTRUCTOR,
        json={"final_body": "지우가 오늘 지우개를 잘 썼어요", "action": "publish"},
    )
    assert r.status_code == 200
    await db_session.refresh(note)
    assert note.final_body == "[이름]가 오늘 지우개를 잘 썼어요"
    body = (await client.get("/api/v1/guardian/today", headers=GUARDIAN)).json()
    assert body["instructor_comment"] == "지우가 오늘 지우개를 잘 썼어요"


# ---------- 기본은 가린다(fail closed): 목록 밖 접미사도 가린다 ----------


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("지우하고 놀았어", "[이름]하고 놀았어"),
        ("지우네 집", "[이름]네 집"),
        ("지우까지 왔어", "[이름]까지 왔어"),
        ("지우부터 해", "[이름]부터 해"),
        ("지우쌤", "[이름]쌤"),
        ("지우짱", "[이름]짱"),
    ],
)
def test_name_with_unlisted_suffix_is_still_redacted(raw, want):
    assert redact(raw, names=[NAME]) == want
