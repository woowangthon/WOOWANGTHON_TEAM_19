"""배포 1차(TK-56) 결함 — 빈 DB 기동·같은 세션 동시 요청. 파일 SQLite로 실제 연결 2개를 쓴다.

문장은 전부 합성이다. 🔴 문장은 부록 A 평가 문장 R1.
"""

import asyncio
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app import api
from app import db as appdb
from app.actors import DEMO_CHILD_ID, DEMO_GUARDIAN_ID
from app.api import get_llm
from app.llm import Reply, ReplyRequest
from app.main import create_app
from app.models import Alert, Message, Session, Student

CHILD = {"X-Demo-Role": "child", "X-Demo-Actor": DEMO_CHILD_ID}
GUARDIAN = {"X-Demo-Role": "guardian", "X-Demo-Actor": DEMO_GUARDIAN_ID}
R1 = "요즘 그냥 죽고 싶어"


class GateAdapter:
    """첫 요청이 LLM 단계에 들어간 걸 알리고, release가 열릴 때까지 답하지 않는다(= 답 생성 중)."""

    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def reply(self, req: ReplyRequest) -> Reply:
        self.entered.set()
        await asyncio.wait_for(self.release.wait(), timeout=5)
        return Reply("합성 응답", "live")


@pytest_asyncio.fixture
async def db_file(tmp_path, monkeypatch):
    path = tmp_path / "deploy.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{path}")
    monkeypatch.setattr(appdb, "_engine", None)
    monkeypatch.setattr(appdb, "_sessionmaker", None)
    yield path
    if appdb._engine is not None:
        await appdb._engine.dispose()


@pytest_asyncio.fixture
async def booted(db_file):
    """빈 DB로 lifespan(기동)을 돌린 앱과 클라이언트."""
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield app, c


async def _read(fn):
    async for db in appdb.get_db():
        return await fn(db)


async def test_empty_db_boot_creates_demo_actors(booted):
    _, c = booted
    r = await c.get("/api/v1/me/today", headers=CHILD)
    assert r.status_code == 200
    assert r.json()["streak_text"] == "3일째 같이 했어"
    r = await c.get("/api/v1/guardian/today", headers=GUARDIAN)
    assert r.status_code == 200


async def test_boot_does_not_touch_existing_demo_child(db_file):
    app = create_app()
    async with app.router.lifespan_context(app):
        pass

    async def bump(db):
        s = await db.get(Student, DEMO_CHILD_ID)
        s.streak_days = 9
        await db.commit()

    await _read(bump)
    async with app.router.lifespan_context(app):  # 재기동
        pass

    async def streak(db):
        return (await db.get(Student, DEMO_CHILD_ID)).streak_days

    assert await _read(streak) == 9


async def test_concurrent_hints_one_wins_other_busy(booted):
    """답 생성 중(replying_until) 힌트는 기다리지 않고 409 busy(11-11)."""
    app, c = booted
    adapter = GateAdapter()
    app.dependency_overrides[get_llm] = lambda: adapter
    sid = (await c.post("/api/v1/sessions", headers=CHILD)).json()["session_id"]
    url = f"/api/v1/sessions/{sid}/messages"

    first = asyncio.create_task(c.post(url, headers=CHILD, json={"kind": "hint"}))
    await asyncio.wait_for(adapter.entered.wait(), timeout=5)
    r2 = await c.post(url, headers=CHILD, json={"kind": "hint"})
    adapter.release.set()
    r1 = await first
    codes = sorted([r1.status_code, r2.status_code])
    assert codes == [200, 409]
    busy = r1 if r1.status_code == 409 else r2
    assert busy.json()["code"] == "busy"

    async def state(db):
        n = await db.scalar(
            select(func.count()).select_from(Message).where(Message.session_id == sid)
        )
        row = await db.get(Session, sid)
        return n, row.hint_level

    # 진 쪽은 아무것도 커밋되지 않았다: 응답 1개, 힌트 1단계
    assert await _read(state) == (1, 1)


async def test_crisis_survives_seq_conflict(booted, db_file, monkeypatch):
    """🔴 요청이 seq 경합에서 지면 한 번 더 써서 알림을 잃지 않는다."""
    _, c = booted
    sid = (await c.post("/api/v1/sessions", headers=CHILD)).json()["session_id"]
    original = api.build_excerpt
    calls = {"n": 0}

    def conflicting_excerpt(turns):
        calls["n"] += 1
        if calls["n"] == 1:
            # 다른 요청이 같은 seq를 먼저 커밋한 상황(별도 연결)
            con = sqlite3.connect(db_file)
            seq = con.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM messages WHERE session_id = ?", (sid,)
            ).fetchone()[0]
            con.execute(
                "INSERT INTO messages (id, session_id, seq, role, text_redacted, expires_at)"
                " VALUES (?, ?, ?, 'mentor', '합성 응답', ?)",
                (
                    str(uuid.uuid4()),
                    sid,
                    seq,
                    str(datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=72)),
                ),
            )
            con.commit()
            con.close()
        return original(turns)

    monkeypatch.setattr(api, "build_excerpt", conflicting_excerpt)
    r = await c.post(
        f"/api/v1/sessions/{sid}/messages", headers=CHILD, json={"kind": "text", "text": R1}
    )
    assert r.status_code == 200
    assert r.json()["state"] == "crisis" and r.json()["crisis"] is not None

    async def check(db):
        alerts = await db.scalar(
            select(func.count()).select_from(Alert).where(Alert.session_id == sid)
        )
        seqs = (
            await db.scalars(
                select(Message.seq).where(Message.session_id == sid).order_by(Message.seq)
            )
        ).all()
        return alerts, list(seqs)

    assert await _read(check) == (1, [1, 2, 3])
