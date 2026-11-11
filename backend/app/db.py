"""DB 엔진과 요청별 세션. 주소는 DATABASE_URL 하나로 바꾼다(로컬 SQLite / 배포 Postgres)."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import database_url

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is None:
        # hide_parameters: DB 예외 문자열(→ 로그)에 바인딩 값(메시지 치환본 등)을 싣지 않는다
        _engine = create_async_engine(database_url(), hide_parameters=True)
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


async def get_db() -> AsyncIterator[AsyncSession]:
    get_engine()
    assert _sessionmaker is not None
    async with _sessionmaker() as session:
        yield session
