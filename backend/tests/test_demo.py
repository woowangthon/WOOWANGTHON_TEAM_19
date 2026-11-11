"""API 1번 POST /demo/reset — day3 시드 배우(명세 4.4·4.8-3). 토큰·별명·문장은 합성 값."""

from datetime import UTC, date, datetime

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app import config
from app.actors import DEMO_CHILD_ID
from app.db import get_db
from app.main import create_app
from app.models import Alert, InstructorNote, Message, Misconception, Session, Student
from app.timeutil import get_now

# UTC 11-09 21:00 = 서울 11-10 06:00
NOW = datetime(2026, 11, 9, 21, 0, tzinfo=UTC)
SEOUL_TODAY = date(2026, 11, 10)
TOKEN = "synthetic-demo-token"
OK = {"X-Demo-Token": TOKEN}
CHILD = {"X-Demo-Role": "child", "X-Demo-Actor": DEMO_CHILD_ID}
URL = "/api/v1/demo/reset"


@pytest_asyncio.fixture
async def client(db_session, monkeypatch):
    monkeypatch.setenv("DEMO_TOKEN", TOKEN)
    monkeypatch.setattr(config, "_timer_scale_override", None)
    app = create_app()

    async def _db():
        yield db_session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_now] = lambda: NOW
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _snapshot(db) -> dict:
    db.expire_all()
    s = await db.get(Student, DEMO_CHILD_ID)
    assert s is not None
    mis = (
        await db.execute(
            select(Misconception.tag, Misconception.status, Misconception.first_wrong_date)
            .where(Misconception.student_id == DEMO_CHILD_ID)
            .order_by(Misconception.tag)
        )
    ).all()
    return {
        "student": {
            k: getattr(s, k)
            for k in (
                "nickname",
                "grade_band",
                "style",
                "honorific",
                "polite",
                "streak_days",
                "last_streak_date",
                "freezes",
                "today_task_problem_id",
                "today_task_date",
            )
        },
        "misconceptions": [tuple(m) for m in mis],
        "sessions": await db.scalar(
            select(func.count()).select_from(Session).where(Session.student_id == DEMO_CHILD_ID)
        ),
        "notes": await db.scalar(
            select(func.count())
            .select_from(InstructorNote)
            .where(InstructorNote.student_id == DEMO_CHILD_ID)
        ),
    }


async def test_reset_without_token_is_forbidden(client):
    r = await client.post(URL, json={})
    assert r.status_code == 403
    assert r.json()["code"] == "forbidden"


async def test_reset_token_checked_before_body(client):
    r = await client.post(URL, json={"scenario": "fresh"})
    assert r.status_code == 403


async def test_reset_wrong_token_is_forbidden(client):
    r = await client.post(URL, json={}, headers={"X-Demo-Token": "wrong"})
    assert r.status_code == 403
    assert TOKEN not in r.text


async def test_reset_forbidden_when_env_token_missing(client, monkeypatch):
    monkeypatch.delenv("DEMO_TOKEN")
    r = await client.post(URL, json={}, headers={"X-Demo-Token": ""})
    assert r.status_code == 403
    r = await client.post(URL, json={}, headers=OK)
    assert r.status_code == 403


async def test_reset_response_shape(client):
    r = await client.post(URL, json={}, headers=OK)
    assert r.status_code == 200
    body = r.json()
    assert body == {
        "ok": True,
        "actors": [
            {"role": "child", "id": "demo-child-minsu", "label": "민수"},
            {"role": "guardian", "id": "demo-guardian-minsu", "label": "민수 보호자"},
            {"role": "instructor", "id": "demo-instructor", "label": "강사"},
        ],
        "date": "2026-11-10",
    }
    assert TOKEN not in r.text


async def test_reset_body_may_be_omitted(client):
    r = await client.post(URL, headers=OK)
    assert r.status_code == 200


async def test_reset_builds_day3_state(client, db_session):
    await client.post(URL, json={}, headers=OK)
    snap = await _snapshot(db_session)
    st = snap["student"]
    assert st["nickname"] == "민수"
    assert (st["style"], st["honorific"], st["polite"]) == ("EBSP", "hyung", False)
    assert st["streak_days"] == 3
    assert st["last_streak_date"] == date(2026, 11, 9)  # 어제(서울)
    assert st["today_task_problem_id"] == "frac-div-nat-01"  # 3/4 ÷ 2 (명세 3.2)
    assert st["today_task_date"] == SEOUL_TODAY
    statuses = sorted(m[1] for m in snap["misconceptions"])
    assert statuses == ["open", "open", "resolved"]
    open_tags = {m[0] for m in snap["misconceptions"] if m[1] == "open"}
    assert "frac-div-nat" in open_tags  # 오늘 할 것과 태그를 맞춘다
    assert snap["sessions"] == 0 and snap["notes"] == 0


async def test_child_today_after_reset(client):
    await client.post(URL, json={}, headers=OK)
    r = await client.get("/api/v1/me/today", headers=CHILD)
    assert r.status_code == 200
    body = r.json()
    assert body["streak_text"] == "3일째 같이 했어"
    assert body["today_task"] == {"problem_id": "frac-div-nat-01", "source": "instructor"}
    assert body["session"] is None


async def test_reset_twice_same_state(client, db_session):
    await client.post(URL, json={}, headers=OK)
    first = await _snapshot(db_session)
    r = await client.post(URL, json={}, headers=OK)
    assert r.status_code == 200
    assert await _snapshot(db_session) == first


async def test_reset_wipes_sessions_and_alerts(client, db_session):
    await client.post(URL, json={}, headers=OK)
    r = await client.post("/api/v1/sessions", headers=CHILD)
    assert r.status_code == 200
    sid = r.json()["session_id"]
    db_session.add(Message.new(session_id=sid, seq=1, role="child", text_redacted="x", now=NOW))
    db_session.add(
        Alert.new(session_id=sid, student_id=DEMO_CHILD_ID, trigger="R1", excerpt="x", now=NOW)
    )
    db_session.add(InstructorNote(student_id=DEMO_CHILD_ID, date=SEOUL_TODAY, status="draft"))
    await db_session.flush()

    r = await client.post(URL, json={}, headers=OK)
    assert r.status_code == 200
    for model in (Session, Alert, InstructorNote):
        n = await db_session.scalar(
            select(func.count()).select_from(model).where(model.student_id == DEMO_CHILD_ID)
        )
        assert n == 0, model.__name__
    assert await db_session.scalar(select(func.count()).select_from(Message)) == 0
    # 세션이 지워졌으니 오늘 할 것이 다시 지정돼 있다
    body = (await client.get("/api/v1/me/today", headers=CHILD)).json()
    assert body["session"] is None and body["today_task"]["problem_id"] == "frac-div-nat-01"


async def test_reset_keeps_other_students(client, db_session, make_student):
    other = make_student(streak_days=7)
    db_session.add(other)
    await db_session.flush()
    other_id = other.id
    db_session.add(
        Misconception(student_id=other_id, tag="nat-div-nat", first_wrong_date=SEOUL_TODAY)
    )
    await db_session.flush()

    await client.post(URL, json={}, headers=OK)
    db_session.expire_all()
    kept = await db_session.get(Student, other_id)
    assert kept is not None and kept.streak_days == 7
    n = await db_session.scalar(
        select(func.count()).select_from(Misconception).where(Misconception.student_id == other_id)
    )
    assert n == 1


async def test_reset_applies_style_options(client, db_session):
    r = await client.post(
        URL,
        json={
            "scenario": "day3",
            "style": "EQLC",
            "honorific": "unni",
            "polite": True,
            "timer_scale": 30,
        },
        headers=OK,
    )
    assert r.status_code == 200
    st = (await _snapshot(db_session))["student"]
    assert (st["style"], st["honorific"], st["polite"]) == ("EQLC", "unni", True)
    assert config.timer_scale() == 30


async def test_reset_default_timer_scale_is_one(client):
    await client.post(URL, json={"timer_scale": 30}, headers=OK)
    await client.post(URL, json={}, headers=OK)
    assert config.timer_scale() == 1


async def test_reset_rejects_bad_options(client):
    bad_bodies = [
        {"scenario": "fresh"},
        {"style": "TIGER"},
        {"honorific": "sir"},
        {"timer_scale": 0},
        {"timer_scale": -3},
        {"timer_scale": "fast"},
    ]
    for body in bad_bodies:
        r = await client.post(URL, json=body, headers=OK)
        assert r.status_code == 422, body
        assert r.json()["code"] == "invalid_request"
    assert config.timer_scale() == 1


async def test_reset_without_timer_scale_keeps_env(client, monkeypatch):
    """본문에 timer_scale이 없으면 환경변수 TIMER_SCALE을 덮지 않는다."""
    monkeypatch.setenv("TIMER_SCALE", "60")
    r = await client.post(URL, json={"style": "EQLC"}, headers=OK)
    assert r.status_code == 200
    assert config.timer_scale() == 60
    await client.post(URL, json={"timer_scale": 5}, headers=OK)
    assert config.timer_scale() == 5
    await client.post(URL, headers=OK)  # 다시 생략 → 환경변수로 돌아간다
    assert config.timer_scale() == 60
