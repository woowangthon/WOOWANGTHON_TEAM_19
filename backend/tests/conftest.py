"""공유 픽스처. DB는 SQLite 인메모리, 테스트마다 트랜잭션을 열고 끝나면 rollback."""

from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.models import Base, Student


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    async with engine.connect() as conn:
        async with conn.begin() as trans:
            session = AsyncSession(bind=conn, expire_on_commit=False)
            yield session
            await session.close()
            if trans.is_active:  # IntegrityError 테스트는 이미 풀려 있다
                await trans.rollback()


@pytest.fixture
def make_student():
    """학생 행 팩토리. 별명은 합성 값만 쓴다."""

    def _factory(**overrides) -> Student:
        values: dict = {
            "nickname": "테스트학생",
            "grade_band": "초5-6",
            "style": "EBSP",
            "honorific": "friend",
            "polite": False,
        }
        values.update(overrides)
        return Student(**values)

    return _factory


TODAY = date(2026, 11, 10)
