"""앱 DB 엔진 설정. 예외 메시지(→ 로그)에 바인딩 값(아이 문장 치환본)이 실리지 않아야 한다."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import cast

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

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
