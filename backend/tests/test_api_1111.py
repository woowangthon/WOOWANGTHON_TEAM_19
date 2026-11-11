"""11-11 점검 보강: A4 같이 풀기 답 사후 검사, A8 오답 0건 요약.

문장은 전부 합성이다. 실제 공급자는 부르지 않는다(가짜 어댑터).
"""

from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api import get_llm
from app.db import get_db
from app.llm import Reply, ReplyRequest, ScriptedAdapter
from app.main import create_app
from app.models import Message
from app.seed import load_seed
from app.timeutil import get_now

NOW = datetime(2026, 11, 9, 21, 0, tzinfo=UTC)  # 서울 11-10 06:00
SEOUL_TODAY = date(2026, 11, 10)
PROBLEM = "frac-div-nat-01"  # 3/4 ÷ 2, 정답 3/8 (허용: 0.375, 8분의 3, 3÷8)
NEUTRAL = "몰라"  # 판정 없는 아이 말(숫자 없음)


class FakeLive:
    """study·chat 답은 테스트가 정한 문장을 live로 돌려준다. 요약도 테스트가 정한다."""

    def __init__(self) -> None:
        self.calls: list[ReplyRequest] = []
        self.text = "같이 생각해 보자"
        self.summary = "나눗셈을 곱셈으로 바꾸는 곳"
        self._inner = ScriptedAdapter.from_file()

    async def reply(self, req: ReplyRequest) -> Reply:
        self.calls.append(req)
        if req.phase == "summary":
            return Reply(self.summary, "live")
        if req.phase in ("study", "chat"):
            return Reply(self.text, "live")
        return await self._inner.reply(req)

    def summary_calls(self) -> list[ReplyRequest]:
        return [c for c in self.calls if c.phase == "summary"]


@pytest.fixture
def fake() -> FakeLive:
    return FakeLive()


@pytest_asyncio.fixture
async def client(db_session, fake):
    await load_seed(db_session)
    app = create_app()

    async def _db():
        yield db_session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_now] = lambda: NOW
    app.dependency_overrides[get_llm] = lambda: fake
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
    r = await client.post(f"/api/v1/sessions/{sid}/messages", headers=_h(student), json=body)
    assert r.status_code == 200
    return r.json()


async def _mentor_texts(db_session, sid) -> list[str]:
    rows = await db_session.scalars(
        select(Message.text_redacted)
        .where(Message.session_id == sid, Message.role == "mentor")
        .order_by(Message.seq)
    )
    return list(rows.all())


# --- A4 같이 풀기 답 사후 검사 ------------------------------------------------------


@pytest.mark.parametrize(
    "leak",
    [
        "답은 3/8이야!",
        "3 / 8 이 되겠지?",
        "0.375가 나와",
        "8분의 3이야",
        "8 분의 3 이지",
        "3÷8로 써도 돼",
    ],
)
async def test_study_reply_with_answer_is_replaced_by_script(
    client, db_session, student, sid, fake, leak
):
    fake.text = leak
    body = await _send(client, student, sid, kind="text", text=NEUTRAL)
    assert body["source"] == "scripted"
    assert body["reply"] != leak
    assert "3/8" not in body["reply"] and "0.375" not in body["reply"]
    # 저장된 멘토 말도 대본 문장
    assert await _mentor_texts(db_session, sid) == [body["reply"]]


@pytest.mark.parametrize("ok", ["13/8이 아니라 다시 볼까?", "3/80은 아니야", "3/4를 2로 나눠 보자"])
async def test_study_reply_without_answer_is_kept(client, student, sid, fake, ok):
    fake.text = ok
    body = await _send(client, student, sid, kind="text", text=NEUTRAL)
    assert body == body | {"reply": ok, "source": "live"}


async def test_answer_allowed_after_hint_three(client, student, sid, fake):
    for _ in range(3):
        await _send(client, student, sid, kind="hint")
    fake.text = "풀이를 보면 3/8이 돼"
    body = await _send(client, student, sid, kind="text", text=NEUTRAL)
    assert body["reply"] == "풀이를 보면 3/8이 돼" and body["source"] == "live"


async def test_answer_allowed_after_child_solved(client, student, sid, fake):
    fake.text = "맞아, 3/8이야!"
    body = await _send(client, student, sid, kind="text", text="3/8")
    assert body["judge"] == "correct"
    assert body["reply"] == "맞아, 3/8이야!" and body["source"] == "live"
    body = await _send(client, student, sid, kind="text", text=NEUTRAL)
    assert body["reply"] == "맞아, 3/8이야!" and body["source"] == "live"


async def test_leak_log_has_no_sentence(client, student, sid, fake, caplog):
    fake.text = "비밀인데 답은 3/8"
    with caplog.at_level("INFO"):
        await _send(client, student, sid, kind="text", text=NEUTRAL)
    assert "answer_leak" in caplog.text
    assert "비밀인데" not in caplog.text


# --- A8 오답 0건이면 요약 LLM을 부르지 않는다 ----------------------------------------


async def _to_bridge(client, student, sid):
    r = await client.post(
        f"/api/v1/sessions/{sid}/phase", headers=_h(student), json={"to": "bridge"}
    )
    assert r.status_code == 200
    r = await client.get(f"/api/v1/sessions/{sid}/bridge", headers=_h(student))
    assert r.status_code == 200
    return r.json()


async def test_no_wrong_answers_skips_summary_llm(client, student, sid, fake):
    await _send(client, student, sid, kind="text", text="3/8")
    bridge = await _to_bridge(client, student, sid)
    assert fake.summary_calls() == []
    assert bridge["summary"][1] == "틀린 답 없음"


async def test_wrong_answers_still_use_summary_llm(client, student, sid, fake):
    await _send(client, student, sid, kind="text", text="3/4")
    await _send(client, student, sid, kind="text", text="3/8")
    bridge = await _to_bridge(client, student, sid)
    assert len(fake.summary_calls()) == 1
    assert bridge["summary"][1] == "나눗셈을 곱셈으로 바꾸는 곳"
