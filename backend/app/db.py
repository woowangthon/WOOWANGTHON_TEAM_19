"""DB 엔진과 요청별 세션. 주소는 DATABASE_URL 하나로 바꾼다(로컬 SQLite / 배포 Postgres)."""

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import database_url

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _statement_name() -> str:
    return f"__asyncpg_{uuid4()}__"


def engine_options(url: str) -> dict[str, Any]:
    """Postgres(배포: Vercel 함수 + Supabase 풀러)일 때만 붙이는 엔진 옵션. SQLite는 빈 dict.

    - NullPool: 함수 인스턴스가 연결을 쥐고 있지 않는다. 풀링은 Supabase 풀러가 한다.
    - 트랜잭션 모드 풀러(6543)는 prepared statement를 지원하지 않는다 → asyncpg 캐시 0,
      SQLAlchemy 캐시 0, 이름은 매번 새로(같은 이름이 다른 백엔드에서 겹치지 않게).
      근거: Supabase 「Connecting to Postgres」, SQLAlchemy asyncpg 문서 「Prepared Statement
      Name with PGBouncer」. 세션 모드(5432)에서도 그대로 동작한다.
    - 원격 호스트인데 URL에 ssl이 없으면 TLS를 요구한다.
    """
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql":
        return {}
    connect_args: dict[str, Any] = {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "prepared_statement_name_func": _statement_name,
    }
    if "ssl" not in parsed.query and (parsed.host or "") not in _LOCAL_HOSTS:
        connect_args["ssl"] = "require"
    return {"poolclass": NullPool, "connect_args": connect_args}


def get_engine() -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is None:
        url = database_url()
        # hide_parameters: DB 예외 문자열(→ 로그)에 바인딩 값(메시지 치환본 등)을 싣지 않는다
        _engine = create_async_engine(url, hide_parameters=True, **engine_options(url))
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


async def get_db() -> AsyncIterator[AsyncSession]:
    get_engine()
    assert _sessionmaker is not None
    async with _sessionmaker() as session:
        yield session
