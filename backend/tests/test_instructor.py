"""강사 API 8·9·10번 (/instructor/notes, /approve, /today-task). 명세 4.4·3.4·4.6.

메모·별명·전화번호는 전부 합성 값이다.
"""

from datetime import UTC, date, datetime

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db import get_db
from app.instructor import _parse_draft, _template_body, get_draft_adapter
from app.llm import Reply, ReplyRequest
from app.main import create_app
from app.models import InstructorNote, Student
from app.seed import load_seed
from app.timeutil import get_now

# UTC 11-09 21:00 = 서울 11-10 06:00
NOW = datetime(2026, 11, 9, 21, 0, tzinfo=UTC)
SEOUL_TODAY = date(2026, 11, 10)
INSTRUCTOR = {"X-Demo-Role": "instructor", "X-Demo-Actor": "teacher-demo"}


class _FakeAdapter:
    """초안 어댑터 대역. 정해 둔 응답을 주거나 예외를 던진다."""

    def __init__(self, reply: str | None = None, error: Exception | None = None):
        self._reply = reply
        self._error = error
        self.requests: list[ReplyRequest] = []

    async def reply(self, req: ReplyRequest) -> Reply:
        self.requests.append(req)
        if self._error is not None:
            raise self._error
        return Reply(self._reply or "", "live")


def _provide(fake: _FakeAdapter):
    def _dep() -> _FakeAdapter:
        return fake

    return _dep


@pytest_asyncio.fixture
async def app_and_client(db_session, monkeypatch):
    monkeypatch.delenv("LLM_MODE", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    await load_seed(db_session)
    app = create_app()

    async def _db():
        yield db_session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_now] = lambda: NOW
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield app, c


@pytest_asyncio.fixture
async def client(app_and_client):
    return app_and_client[1]


@pytest_asyncio.fixture
async def student(db_session, make_student):
    s = make_student(nickname="별빛토끼")
    db_session.add(s)
    await db_session.flush()
    return s


def _note_body(student: Student, **overrides) -> dict[str, str]:
    body = {
        "student_id": student.id,
        "covered": "분수 ÷ 자연수",
        "stuck": "나눗셈을 곱셈으로 바꾸는 단계",
        "homework": "익힘책 24쪽",
        "memo": "힌트 한 번 뒤에 스스로 풀었음",
    }
    body.update(overrides)
    return body


# ---------- 인증 ----------


async def test_instructor_requires_actor(client, student):
    r = await client.put(
        f"/api/v1/instructor/students/{student.id}/today-task",
        json={"problem_id": "frac-div-nat-01"},
        headers={"X-Demo-Role": "instructor"},
    )
    assert r.status_code == 401
    assert r.json()["code"] == "no_actor"


async def test_child_role_is_forbidden_on_instructor_api(client, student):
    r = await client.get(
        "/api/v1/instructor/notes",
        params={"student_id": student.id},
        headers={"X-Demo-Role": "child", "X-Demo-Actor": student.id},
    )
    assert r.status_code == 403
    assert r.json()["code"] == "forbidden"


# ---------- #10 today-task ----------


async def test_put_today_task_sets_student_row(client, db_session, student):
    r = await client.put(
        f"/api/v1/instructor/students/{student.id}/today-task",
        json={"problem_id": "frac-div-nat-01"},
        headers=INSTRUCTOR,
    )
    assert r.status_code == 200
    assert r.json() == {"problem_id": "frac-div-nat-01", "assigned_date": "2026-11-10"}
    await db_session.refresh(student)
    assert student.today_task_problem_id == "frac-div-nat-01"
    assert student.today_task_date == SEOUL_TODAY


async def test_put_today_task_overwrites(client, db_session, student):
    url = f"/api/v1/instructor/students/{student.id}/today-task"
    await client.put(url, json={"problem_id": "frac-div-nat-01"}, headers=INSTRUCTOR)
    r = await client.put(url, json={"problem_id": "frac-div-nat-02"}, headers=INSTRUCTOR)
    assert r.status_code == 200
    await db_session.refresh(student)
    assert student.today_task_problem_id == "frac-div-nat-02"


async def test_put_today_task_unknown_student(client):
    r = await client.put(
        "/api/v1/instructor/students/nope/today-task",
        json={"problem_id": "frac-div-nat-01"},
        headers=INSTRUCTOR,
    )
    assert r.status_code == 404
    assert r.json()["code"] == "student_not_found"


async def test_put_today_task_unknown_problem(client, student):
    r = await client.put(
        f"/api/v1/instructor/students/{student.id}/today-task",
        json={"problem_id": "no-such-problem"},
        headers=INSTRUCTOR,
    )
    assert r.status_code == 404
    assert r.json()["code"] == "problem_not_found"


# ---------- #8 notes ----------


async def test_post_note_falls_back_to_template(client, student):
    # 기본 어댑터(scripted)에는 초안 대본이 없다 → 템플릿
    r = await client.post("/api/v1/instructor/notes", json=_note_body(student), headers=INSTRUCTOR)
    assert r.status_code == 200
    body = r.json()
    assert body["note_id"]
    assert body["status"] == "draft"
    draft = body["draft"]
    assert "분수 ÷ 자연수" in draft["body"]
    assert "나눗셈을 곱셈으로 바꾸는 단계" in draft["body"]
    assert "힌트 한 번 뒤에 스스로 풀었음" in draft["body"]
    # 숙제는 본문이 아니라 사실 칸으로(부록 D)
    assert "익힘책" not in draft["body"]
    assert draft["facts"] == {"homework": "익힘책 24쪽", "score": None}


async def test_post_note_redacts_pii_before_storing(client, db_session, student):
    r = await client.post(
        "/api/v1/instructor/notes",
        json=_note_body(
            student,
            covered="별빛토끼와 분수 나눗셈",
            stuck="연락은 010-1234-5678로",
            memo="별빛토끼 어머님 test@example.com 확인",
        ),
        headers=INSTRUCTOR,
    )
    assert r.status_code == 200
    note = await db_session.get(InstructorNote, r.json()["note_id"])
    assert note is not None
    stored = " ".join([note.covered, note.stuck, note.memo_redacted, note.draft_body or "", r.text])
    assert "별빛토끼" not in stored
    assert "010-1234-5678" not in stored
    assert "test@example.com" not in stored
    assert "[이름]" in note.memo_redacted and "[이메일]" in note.memo_redacted
    assert "[전화]" in note.stuck


async def test_post_note_uses_adapter_json_body(app_and_client, student):
    app, client = app_and_client
    fake = _FakeAdapter(reply='{"body": "오늘은 분수 나눗셈을 잘 해냈습니다."}')
    app.dependency_overrides[get_draft_adapter] = lambda: fake
    r = await client.post(
        "/api/v1/instructor/notes",
        json=_note_body(student, memo="별빛토끼 메모"),
        headers=INSTRUCTOR,
    )
    assert r.json()["draft"]["body"] == "오늘은 분수 나눗셈을 잘 해냈습니다."
    # 어댑터로 가는 입력에도 치환본만, 숙제는 넣지 않는다
    sent = repr(fake.requests[0])
    assert "별빛토끼" not in sent
    assert "익힘책" not in sent


async def test_post_note_template_when_adapter_fails(app_and_client, db_session, make_student):
    app, client = app_and_client
    fakes = (
        _FakeAdapter(error=RuntimeError("boom")),
        _FakeAdapter(reply=""),
        _FakeAdapter(reply='{"body": "   "}'),
        _FakeAdapter(reply="JSON 아님"),
    )
    for i, fake in enumerate(fakes):
        # 같은 날 같은 학생은 기존 노트가 돌아오므로 경우마다 학생을 새로 만든다
        s = make_student(nickname=f"합성학생{i}")
        db_session.add(s)
        await db_session.flush()
        # 람다 기본 인자는 FastAPI가 쿼리 파라미터로 보고 복사하므로 클로저로 넘긴다
        app.dependency_overrides[get_draft_adapter] = _provide(fake)
        r = await client.post("/api/v1/instructor/notes", json=_note_body(s), headers=INSTRUCTOR)
        assert r.status_code == 200
        assert fake.requests, "어댑터를 먼저 불러야 한다"
        assert "분수 ÷ 자연수" in r.json()["draft"]["body"]


async def test_post_note_same_day_returns_existing(app_and_client, db_session, student):
    app, client = app_and_client
    first = await client.post(
        "/api/v1/instructor/notes", json=_note_body(student), headers=INSTRUCTOR
    )
    fake = _FakeAdapter(reply='{"body": "다른 초안"}')
    app.dependency_overrides[get_draft_adapter] = lambda: fake
    second = await client.post(
        "/api/v1/instructor/notes",
        json=_note_body(student, covered="다른 내용"),
        headers=INSTRUCTOR,
    )
    assert second.status_code == 200
    assert second.json() == first.json()  # 재생성 없음(명세 3.4)
    assert fake.requests == []


async def test_post_note_unknown_student(client):
    r = await client.post(
        "/api/v1/instructor/notes",
        json={"student_id": "nope", "covered": "", "stuck": "", "homework": "", "memo": ""},
        headers=INSTRUCTOR,
    )
    assert r.status_code == 404
    assert r.json()["code"] == "student_not_found"


async def test_get_note_today_or_null(client, student):
    r = await client.get(
        "/api/v1/instructor/notes", params={"student_id": student.id}, headers=INSTRUCTOR
    )
    assert r.status_code == 200
    assert r.json() is None
    posted = await client.post(
        "/api/v1/instructor/notes", json=_note_body(student), headers=INSTRUCTOR
    )
    r = await client.get(
        "/api/v1/instructor/notes", params={"student_id": student.id}, headers=INSTRUCTOR
    )
    assert r.json() == posted.json()


async def test_get_note_unknown_student(client):
    r = await client.get(
        "/api/v1/instructor/notes", params={"student_id": "nope"}, headers=INSTRUCTOR
    )
    assert r.status_code == 404
    assert r.json()["code"] == "student_not_found"


# ---------- #9 approve ----------


async def _post_note(client, student) -> str:
    r = await client.post("/api/v1/instructor/notes", json=_note_body(student), headers=INSTRUCTOR)
    return r.json()["note_id"]


async def test_approve_publish_stores_redacted_final(client, db_session, student):
    note_id = await _post_note(client, student)
    r = await client.post(
        f"/api/v1/instructor/notes/{note_id}/approve",
        json={"final_body": "별빛토끼가 잘했어요. 010-9876-5432", "action": "publish"},
        headers=INSTRUCTOR,
    )
    assert r.status_code == 200
    assert r.json() == {"status": "published"}
    note = await db_session.get(InstructorNote, note_id)
    assert note is not None
    assert note.status == "published"
    assert note.final_body is not None
    assert "별빛토끼" not in note.final_body and "010-9876-5432" not in note.final_body
    assert "잘했어요" in note.final_body


async def test_approve_skip(client, db_session, student):
    note_id = await _post_note(client, student)
    r = await client.post(
        f"/api/v1/instructor/notes/{note_id}/approve",
        json={"final_body": "", "action": "skip"},
        headers=INSTRUCTOR,
    )
    assert r.status_code == 200
    assert r.json() == {"status": "skipped"}
    note = await db_session.get(InstructorNote, note_id)
    assert note is not None and note.final_body is None


async def test_approve_twice_conflicts(client, student):
    note_id = await _post_note(client, student)
    url = f"/api/v1/instructor/notes/{note_id}/approve"
    await client.post(url, json={"final_body": "확인", "action": "publish"}, headers=INSTRUCTOR)
    r = await client.post(url, json={"final_body": "", "action": "skip"}, headers=INSTRUCTOR)
    assert r.status_code == 409
    assert r.json()["code"] == "note_closed"


async def test_approve_unknown_note(client):
    r = await client.post(
        "/api/v1/instructor/notes/nope/approve",
        json={"final_body": "확인", "action": "publish"},
        headers=INSTRUCTOR,
    )
    assert r.status_code == 404
    assert r.json()["code"] == "note_not_found"


async def test_approve_publish_blank_body_rejected(client, student):
    note_id = await _post_note(client, student)
    r = await client.post(
        f"/api/v1/instructor/notes/{note_id}/approve",
        json={"final_body": "  ", "action": "publish"},
        headers=INSTRUCTOR,
    )
    assert r.status_code == 422
    assert r.json()["code"] == "invalid_request"


async def test_approve_bad_action_rejected(client, student):
    note_id = await _post_note(client, student)
    r = await client.post(
        f"/api/v1/instructor/notes/{note_id}/approve",
        json={"final_body": "확인", "action": "delete"},
        headers=INSTRUCTOR,
    )
    assert r.status_code == 422


# --- B5: 초안 파싱(코드 펜스·앞뒤 설명)과 템플릿 문장 이음 ---


def test_parse_draft_strips_code_fence():
    raw = '```json\n{"body": "합성 초안 문장입니다."}\n```'
    assert _parse_draft(raw) == "합성 초안 문장입니다."


def test_parse_draft_ignores_text_around_json():
    raw = '초안입니다:\n{"body": "합성 초안 문장입니다."}\n이상입니다.'
    assert _parse_draft(raw) == "합성 초안 문장입니다."


def test_parse_draft_still_rejects_non_json():
    assert _parse_draft("```\n그냥 문장\n```") is None
    assert _parse_draft("") is None


def test_template_body_adds_period_to_memo_without_one():
    body = _template_body("", "", "숙제를 잘 해 왔어요")
    assert "숙제를 잘 해 왔어요. 다음 시간에" in body
    # 이미 끝맺음이 있으면 더 붙이지 않는다
    assert "잘했어요! 다음 시간에" in _template_body("", "", "잘했어요!")


async def test_fenced_llm_draft_is_used_not_template(app_and_client, db_session, student):
    app, client = app_and_client
    fake = _FakeAdapter(reply='```json\n{"body": "합성 펜스 초안입니다."}\n```')
    app.dependency_overrides[get_draft_adapter] = _provide(fake)
    r = await client.post("/api/v1/instructor/notes", json=_note_body(student), headers=INSTRUCTOR)
    assert r.json()["draft"]["body"] == "합성 펜스 초안입니다."
