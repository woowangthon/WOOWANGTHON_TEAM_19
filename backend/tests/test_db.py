"""앱 DB 엔진 설정. 예외 메시지(→ 로그)에 바인딩 값(아이 문장 치환본)이 실리지 않아야 한다."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import cast

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import NullPool

from app import config
from app import db as appdb
from app.models import Base, Message


async def test_db_error_does_not_include_bound_values(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(appdb, "_engine", None)
    monkeypatch.setattr(appdb, "_sessionmaker", None)
    engine = appdb.get_engine()
    gen = cast(AsyncGenerator[AsyncSession, None], appdb.get_db())
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        now = datetime.now(UTC)
        s = await anext(gen)
        s.add(Message.new(session_id="s1", seq=1, role="child", text_redacted="가나", now=now))
        await s.flush()
        s.add(Message.new(session_id="s1", seq=1, role="child", text_redacted="다라", now=now))
        with pytest.raises(IntegrityError) as exc:
            await s.flush()
        assert "다라" not in str(exc.value)
    finally:
        await gen.aclose()
        await engine.dispose()


# --- 배포 Postgres(Supabase 풀러) 설정 — 4.11-1. 실제 연결 없이 설정 값만 본다 ---


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("postgres://u:p@h:6543/postgres", "postgresql+asyncpg://u:p@h:6543/postgres"),
        ("postgresql://u:p@h:6543/postgres", "postgresql+asyncpg://u:p@h:6543/postgres"),
        ("postgresql+asyncpg://u:p@h/db", "postgresql+asyncpg://u:p@h/db"),
        ("sqlite+aiosqlite:///./dev.db", "sqlite+aiosqlite:///./dev.db"),
    ],
)
def test_database_url_uses_asyncpg_driver(monkeypatch, raw, expected):
    monkeypatch.setenv("DATABASE_URL", raw)
    assert config.database_url() == expected


def test_database_url_maps_sslmode_and_drops_unknown_query(monkeypatch):
    """libpq 식 sslmode는 asyncpg가 모른다 → ssl. Vercel 연동이 붙이는 supa=도 뺀다."""
    monkeypatch.setenv(
        "DATABASE_URL", "postgres://u:p@h:6543/postgres?sslmode=require&supa=base-pooler.x"
    )
    assert config.database_url() == "postgresql+asyncpg://u:p@h:6543/postgres?ssl=require"


def test_engine_options_postgres_are_pooler_safe():
    opts = appdb.engine_options("postgresql+asyncpg://u:p@db.example.com:6543/postgres")
    assert opts["poolclass"] is NullPool  # 함수 인스턴스마다 연결을 쥐고 있지 않는다
    args = opts["connect_args"]
    assert args["statement_cache_size"] == 0  # asyncpg 자체 캐시
    assert args["prepared_statement_cache_size"] == 0  # SQLAlchemy 쪽 캐시
    name_func = args["prepared_statement_name_func"]
    assert name_func() != name_func()  # 풀러 뒤 백엔드에서 이름이 겹치지 않게
    assert args["ssl"] == "require"  # 원격 호스트는 TLS


def test_engine_options_postgres_keeps_explicit_ssl_and_local_plain():
    local = appdb.engine_options("postgresql+asyncpg://u@127.0.0.1:5432/db")
    assert "ssl" not in local["connect_args"]
    explicit = appdb.engine_options("postgresql+asyncpg://u@db.example.com/db?ssl=disable")
    assert "ssl" not in explicit["connect_args"]  # URL의 값이 그대로 asyncpg로 간다


def test_engine_options_sqlite_unchanged():
    assert appdb.engine_options("sqlite+aiosqlite:///./dev.db") == {}
