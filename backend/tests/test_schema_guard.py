"""배포 뒤 칸이 늘어도 기동 때 빠진 칸만 더한다(11-14 구조 점검).

create_all은 없는 표만 만든다. 운영 DB에 표가 이미 있으면 새 칸이 안 생겨 그 화면이 500이 된다.
add_missing_columns는 빠진 칸만 ADD COLUMN 한다(지우기·바꾸기 없음). 값은 합성.
"""

from datetime import datetime

import pytest_asyncio
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    inspect,
    text,
)
from sqlalchemy.ext.asyncio import create_async_engine

from app.models import Base
from app.schema_guard import add_missing_columns


@pytest_asyncio.fixture
async def eng():
    e = create_async_engine("sqlite+aiosqlite:///:memory:")
    yield e
    await e.dispose()


async def _cols(conn, table: str) -> set[str]:
    return await conn.run_sync(lambda c: {x["name"] for x in inspect(c).get_columns(table)})


async def test_adds_missing_column_with_default_and_keeps_rows(eng):
    async with eng.begin() as conn:
        # 운영 DB에 옛 모양으로 이미 있는 표(currency 칸 이전)
        await conn.execute(
            text(
                "CREATE TABLE seed_ledger (id VARCHAR(40) PRIMARY KEY, student_account_id "
                "VARCHAR(40) NOT NULL, date DATE NOT NULL, amount INTEGER NOT NULL, source "
                "VARCHAR(20) NOT NULL, note VARCHAR(60) NOT NULL, by VARCHAR(40) NOT NULL, "
                "once_key VARCHAR(100), created_at DATETIME, trial_id VARCHAR(20))"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO seed_ledger VALUES ('r1','s1','2026-11-12',3,'학습 완료','',"
                "'system',NULL,NULL,NULL)"
            )
        )
        await conn.run_sync(Base.metadata.create_all)  # 없는 표만 만든다 → currency 없음
        assert "currency" not in await _cols(conn, "seed_ledger")
        added = await conn.run_sync(add_missing_columns)
        assert "seed_ledger.currency" in added
        assert "currency" in await _cols(conn, "seed_ledger")
        got = (await conn.execute(text("SELECT currency FROM seed_ledger"))).scalar_one()
        assert got == "seed"  # 기존 줄은 기본값
        # 두 번째 기동은 할 일 없음
        assert await conn.run_sync(add_missing_columns) == []


async def test_column_kinds_and_unsafe_columns_are_skipped(eng):
    md = MetaData()
    Table(
        "toy",
        md,
        Column("id", Integer, primary_key=True),
        Column("flag", Boolean, nullable=False, default=True),
        Column("note", String(10), nullable=True),
        Column("made", DateTime(timezone=True), nullable=False, default=datetime.now),
        Column("must", String(10), nullable=False),  # 기본값 없는 필수 칸 → 못 더함
    )
    async with eng.begin() as conn:
        await conn.execute(text("CREATE TABLE toy (id INTEGER PRIMARY KEY)"))
        await conn.execute(text("INSERT INTO toy (id) VALUES (1)"))
        added = await conn.run_sync(lambda c: add_missing_columns(c, md))
        assert added == ["toy.flag", "toy.note", "toy.made"]
        assert "must" not in await _cols(conn, "toy")
        row = (await conn.execute(text("SELECT flag, note, made FROM toy"))).one()
        assert row[0] in (1, True) and row[1] is None and row[2] is not None
