"""명세 4.11 공개 체험: 방문자별 체험 세트(2번)와 남용 상한(5번).

문장은 합성 구절만 쓴다. 시계는 테스트가 고정한다(서울 날짜 기준).
"""

import re
from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app import config
from app.actors import DEMO_CHILD_ID, DEMO_INSTRUCTOR_ID
from app.api import get_llm
from app.db import get_db
from app.instructor import get_draft_adapter
from app.llm import ReplyRequest, ScriptedAdapter
from app.main import create_app
from app.models import Message, Misconception, Problem, Session, Student
from app.seed import load_seed
from app.timeutil import get_now
from app.trial import AI_DAILY_MAX, TRIAL_HOURLY_MAX

NOW = datetime(2026, 11, 9, 21, 0, tzinfo=UTC)  # 서울 11-10(화) 06:00
SEOUL_TODAY = date(2026, 11, 10)
PROBLEM = "frac-div-nat-01"
BASE = "/api/v1/compat"
CHILD = {"X-Demo-Role": "child", "X-Demo-Actor": DEMO_CHILD_ID}
PLAIN = "줄넘기 했어"  # 합성 평범한 구절
ID_RE = re.compile(r"^t-[a-z0-9]{16}$")


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def tick(self, seconds: int = 1) -> None:
        self.now += timedelta(seconds=seconds)


class SpyLlm:
    """scripted를 감싸 호출 수를 센다."""

    def __init__(self) -> None:
        self.inner = ScriptedAdapter.from_file()
        self.calls = 0

    async def reply(self, req: ReplyRequest):
        self.calls += 1
        return await self.inner.reply(req)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def spy() -> SpyLlm:
    return SpyLlm()


@pytest_asyncio.fixture
async def client(db_session, clock, spy, make_student, monkeypatch):
    monkeypatch.setattr(config, "_timer_scale_override", None)
    await load_seed(db_session)
    db_session.add(
        make_student(id=DEMO_CHILD_ID, today_task_problem_id=PROBLEM, today_task_date=SEOUL_TODAY)
    )
    await db_session.flush()
    app = create_app()

    async def _db():
        yield db_session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_now] = lambda: clock.now
    app.dependency_overrides[get_llm] = lambda: spy
    app.dependency_overrides[get_draft_adapter] = ScriptedAdapter.from_file
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _trial(client) -> dict:
    r = await client.post(f"{BASE}/trial")
    assert r.status_code == 200
    return r.json()


def _h(role: str, actor: str) -> dict[str, str]:
    return {"X-Demo-Role": role, "X-Demo-Actor": actor}


# --- 세트 발급 -----------------------------------------------------------------------


async def test_trial_issues_set_with_day3_child_before_promise(client, db_session):
    body = await _trial(client)
    tid = body["trialId"]
    assert ID_RE.match(tid)
    assert body["actors"] == {
        "child": f"{tid}-child",
        "guardian": f"{tid}-guardian",
        "instructor": f"{tid}-instructor",
    }
    assert body["date"] == SEOUL_TODAY.isoformat()

    db_session.expire_all()
    child = await db_session.get(Student, f"{tid}-child")
    assert child is not None
    assert child.nickname == "지우" and child.consent is False
    assert child.streak_days == 3 and child.today_task_date == SEOUL_TODAY
    assert child.created_at is not None
    task = await db_session.get(Problem, child.today_task_problem_id)
    assert task is not None and task.expr == "3/4 / 2"
    statuses = (
        await db_session.scalars(
            select(Misconception.status).where(Misconception.student_id == child.id)
        )
    ).all()
    assert sorted(statuses) == ["open", "open", "resolved"]

    # 약속 화면부터: 아이 홈이 열리고 약속 전 상태다
    home = await client.get(f"{BASE}/student/home", headers=_h("child", child.id))
    assert home.status_code == 200


async def test_trial_sets_are_separate(client):
    a, b = await _trial(client), await _trial(client)
    assert a["trialId"] != b["trialId"]


# --- 신원: 보호자 --------------------------------------------------------------------


async def test_trial_guardian_sees_own_child(client):
    body = await _trial(client)
    r = await client.get(
        f"{BASE}/guardian/today", headers=_h("guardian", body["actors"]["guardian"])
    )
    assert r.status_code == 200
    assert r.json()["childName"] == "지우"


@pytest.mark.parametrize(
    ("actor", "code"),
    [
        ("t-0000000000000000-guardian", "student_not_found"),  # 형식은 맞지만 세트 없음
        ("t-short-guardian", "guardian_not_found"),
        ("t-ABCDEFGHIJKLMNOP-guardian", "guardian_not_found"),
    ],
)
async def test_trial_guardian_unknown(client, actor, code):
    r = await client.get(f"{BASE}/guardian/today", headers=_h("guardian", actor))
    assert r.status_code == 404
    assert r.json()["code"] == code


# --- 신원: 학습지도자 ----------------------------------------------------------------


async def test_trial_instructor_sees_only_own_child(client):
    a, b = await _trial(client), await _trial(client)
    r = await client.get(
        f"{BASE}/teacher/today", headers=_h("instructor", a["actors"]["instructor"])
    )
    assert r.status_code == 200
    assert [s["id"] for s in r.json()["students"]] == [a["actors"]["child"]]

    # 공용 데모 강사·임의 강사는 체험 아이를 못 본다(공개 URL에서 헤더를 꾸며도, 11-11)
    for actor in (DEMO_INSTRUCTOR_ID, "any-teacher"):
        r = await client.get(f"{BASE}/teacher/today", headers=_h("instructor", actor))
        ids = {s["id"] for s in r.json()["students"]}
        assert DEMO_CHILD_ID in ids
        assert not ids & {a["actors"]["child"], b["actors"]["child"]}
        r = await client.get(
            f"{BASE}/teacher/students/{a['actors']['child']}/memo",
            headers=_h("instructor", actor),
        )
        assert r.status_code == 404


async def test_trial_instructor_missing_set_is_trial_not_found(client):
    """DB가 바뀌어 세트 아이가 없으면 404 trial_not_found(프론트가 새 세트를 받는다)."""
    head = _h("instructor", "t-0000000000000000-instructor")
    r = await client.get(f"{BASE}/teacher/today", headers=head)
    assert r.status_code == 404 and r.json()["code"] == "trial_not_found"


async def test_trial_instructor_other_set_is_404(client):
    a, b = await _trial(client), await _trial(client)
    head = _h("instructor", a["actors"]["instructor"])
    for other in (b["actors"]["child"], DEMO_CHILD_ID):
        url = f"{BASE}/teacher/students/{other}"
        calls = [
            client.get(f"{url}/memo", headers=head),
            client.put(f"{url}/memo", headers=head, json={"covered": "분수"}),
            client.post(f"{url}/draft", headers=head),
            client.put(f"{url}/draft", headers=head, json={"comment": "잘했어요"}),
            client.post(f"{url}/draft/approve", headers=head),
            client.put(f"{url}/task", headers=head, json={"unit": None}),
        ]
        for call in calls:
            r = await call
            assert r.status_code == 404, r.text
            assert r.json()["code"] == "student_not_found"
    # 기본 경로도 같은 규칙
    r = await client.get(
        "/api/v1/instructor/notes", params={"student_id": b["actors"]["child"]}, headers=head
    )
    assert r.status_code == 404 and r.json()["code"] == "student_not_found"
    r = await client.put(
        f"/api/v1/instructor/students/{b['actors']['child']}/today-task",
        headers=head,
        json={"problem_id": PROBLEM},
    )
    assert r.status_code == 404 and r.json()["code"] == "student_not_found"


async def test_trial_instructor_full_flow_on_own_child(client):
    a = await _trial(client)
    head = _h("instructor", a["actors"]["instructor"])
    url = f"{BASE}/teacher/students/{a['actors']['child']}"
    assert (
        await client.put(f"{url}/memo", headers=head, json={"covered": "분수"})
    ).status_code == 204
    assert (await client.post(f"{url}/draft", headers=head)).status_code == 200
    r = await client.post(f"{url}/draft/approve", headers=head)
    assert r.status_code == 200 and r.json()["status"] == "승인됨"
    r = await client.put(f"{url}/task", headers=head, json={"unit": None})
    assert r.status_code == 200


# --- 남용 상한 -----------------------------------------------------------------------


async def test_trial_limit_per_hour(client, db_session, make_student, clock):
    for i in range(TRIAL_HOURLY_MAX):
        db_session.add(
            make_student(id=f"t-{i:016d}-child", created_at=clock.now - timedelta(minutes=30))
        )
    await db_session.flush()
    r = await client.post(f"{BASE}/trial")
    assert r.status_code == 429
    assert r.json()["code"] == "trial_limit"
    assert r.json()["message"] == "잠시 뒤 다시 시도해 주세요."

    clock.tick(31 * 60)  # 한 시간이 지나면 다시 된다
    assert (await client.post(f"{BASE}/trial")).status_code == 200


async def _to_chat(client, clock) -> str:
    sid = (await client.post(f"{BASE}/sessions", headers=CHILD, json={})).json()["id"]
    clock.tick(5 * 60)
    await client.post(
        f"{BASE}/sessions/{sid}/answer",
        headers=CHILD,
        json={"problemId": PROBLEM, "numerator": 3, "denominator": 8},
    )
    await client.post(f"{BASE}/sessions/{sid}/after-study", headers=CHILD, json={"choice": "chat"})
    clock.tick()
    return sid


async def _fill_mentor(db, sid: str, total: int, now: datetime) -> None:
    have = await db.scalar(
        select(func.count())
        .select_from(Message)
        .where(Message.session_id == sid, Message.role == "mentor")
    )
    top = await db.scalar(select(func.max(Message.seq)).where(Message.session_id == sid)) or 0
    for i in range(total - have):
        db.add(
            Message.new(
                session_id=sid, seq=top + 1 + i, role="mentor", text_redacted="대본", now=now
            )
        )
    await db.flush()


@pytest.mark.parametrize(
    ("mentor", "llm_called"), [(AI_DAILY_MAX - 1, True), (AI_DAILY_MAX, False)]
)
async def test_ai_daily_cap_uses_script(client, db_session, clock, spy, mentor, llm_called):
    sid = await _to_chat(client, clock)
    assert (await db_session.get(Session, sid)) is not None
    await _fill_mentor(db_session, sid, mentor, clock.now)
    before = spy.calls
    r = (
        await client.post(f"{BASE}/sessions/{sid}/chat", headers=CHILD, json={"text": PLAIN})
    ).json()
    assert r["reply"] and r["source"] == "scripted"
    assert (spy.calls > before) is llm_called


async def test_ai_hourly_cap_across_sets_uses_script(client, db_session, clock, spy, monkeypatch):
    """세트를 새로 받아 아이당 상한을 피해도, 서버 전체 최근 1시간 멘토 답이 상한이면 대본(4.11-5)."""
    import app.api as api_module

    monkeypatch.setattr(api_module, "AI_HOURLY_MAX", 3)
    sid = await _to_chat(client, clock)
    await _fill_mentor(db_session, sid, 3, clock.now)
    before = spy.calls
    r = (
        await client.post(f"{BASE}/sessions/{sid}/chat", headers=CHILD, json={"text": PLAIN})
    ).json()
    assert r["reply"] and r["source"] == "scripted"
    assert spy.calls == before


# --- 공개 배포: 체험 세트만(11-11) ---------------------------------------------------


@pytest.mark.parametrize(
    ("env", "want"),
    [
        ({}, False),
        ({"VERCEL": "1"}, True),
        ({"VERCEL": "1", "TRIAL_ONLY": "0"}, False),
        ({"TRIAL_ONLY": "1"}, True),
    ],
)
def test_trial_only_flag(monkeypatch, env, want):
    for k in ("VERCEL", "TRIAL_ONLY"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert config.trial_only() is want


async def test_trial_only_blocks_public_demo_actors(client, monkeypatch):
    """공개 주소에서는 헤더를 꾸며도 공용 데모 아이·보호자·임의 강사로 못 들어온다."""
    monkeypatch.setenv("TRIAL_ONLY", "1")
    blocked = [
        ("child", DEMO_CHILD_ID, "/student/home"),
        ("guardian", "demo-guardian-minsu", "/guardian/today"),
        ("instructor", DEMO_INSTRUCTOR_ID, "/teacher/today"),
        ("instructor", "any-teacher", "/teacher/today"),
    ]
    for role, actor, path in blocked:
        r = await client.get(f"{BASE}{path}", headers=_h(role, actor))
        assert r.status_code == 403, (actor, r.text)
        assert r.json()["code"] == "trial_only"
    # 다른 역할의 세트 id를 써도 막는다(아이 자리에 보호자 id)
    a = await _trial(client)
    r = await client.get(f"{BASE}/student/home", headers=_h("child", a["actors"]["guardian"]))
    assert r.status_code == 403
    # 체험 세트는 그대로 된다
    for role, path in (
        ("child", "/student/home"),
        ("guardian", "/guardian/today"),
        ("instructor", "/teacher/today"),
    ):
        r = await client.get(f"{BASE}{path}", headers=_h(role, a["actors"][role]))
        assert r.status_code == 200, r.text
    assert (await client.post(f"{BASE}/trial")).status_code == 200


async def test_over_cap_fallback_is_logged_with_reason(client, db_session, clock, spy, caplog):
    # 수정 명세 B31: 남용 상한으로 대본이 될 때 이유가 로그에 없었다(원문 없이 세션·단계·이유)
    import logging

    sid = await _to_chat(client, clock)
    await _fill_mentor(db_session, sid, AI_DAILY_MAX, clock.now)
    with caplog.at_level(logging.WARNING, logger="app.api"):
        await client.post(f"{BASE}/sessions/{sid}/chat", headers=CHILD, json={"text": PLAIN})
    lines = [r.getMessage() for r in caplog.records if "fallback" in r.getMessage()]
    assert len(lines) == 1
    assert f"session={sid}" in lines[0] and "reason=over_cap" in lines[0]
    assert PLAIN not in lines[0]
