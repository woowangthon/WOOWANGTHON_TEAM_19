"""기동 때 빠진 칸만 더한다(11-14 구조 점검).

create_all은 없는 표만 만든다. 운영 DB(Supabase)에 표가 이미 있으면, 코드에 새로 생긴 칸이 DB에
안 생겨 그 칸을 읽는 화면이 500이 된다(NOTE 「배포 뒤 열 변경 금지」 함정). 그래서 lifespan이
create_all 바로 뒤에 이 함수를 부른다.

- 하는 일: 코드에 있고 DB에 없는 칸을 ALTER TABLE … ADD COLUMN. 지우기·이름 바꾸기·형 바꾸기는 안 한다.
- 기존 줄의 값: 칸의 고정 기본값(예: currency='seed', active=true), 시각 칸은 지금 시각,
  비어도 되는 칸은 NULL.
- 못 더하는 칸(기본값 없는 필수 칸, 기본키)은 건너뛰고 경고 로그만 남긴다 → 사람이 SQL로.
- 로그에는 표·칸 이름만(값 없음).
"""

import logging
from typing import Any

from sqlalchemy import Column, DateTime, MetaData, inspect, literal
from sqlalchemy.engine import Connection

from app.models import Base

log = logging.getLogger(__name__)


def _default_sql(col: Column[Any], conn: Connection) -> str | None:
    """기존 줄에 넣을 기본값 SQL. 없으면 None."""
    d = col.default
    if d is not None and getattr(d, "is_scalar", False):
        arg = d.arg  # type: ignore[attr-defined]
        return str(
            literal(arg, col.type).compile(
                dialect=conn.dialect, compile_kwargs={"literal_binds": True}
            )
        )
    if d is not None and isinstance(col.type, DateTime):
        return "CURRENT_TIMESTAMP"  # 만든 시각 같은 칸(파이썬 함수 기본값)
    return None


def _existing_columns(conn: Connection) -> dict[str, set[str]]:
    """DB에 있는 표 → 칸 이름들. Postgres는 쿼리 1번(콜드 스타트마다 돌아서 표마다 묻지 않는다)."""
    if conn.dialect.name == "postgresql":
        rows = conn.exec_driver_sql(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema()"
        )
        out: dict[str, set[str]] = {}
        for table, column in rows:
            out.setdefault(table, set()).add(column)
        return out
    insp = inspect(conn)
    return {t: {c["name"] for c in insp.get_columns(t)} for t in insp.get_table_names()}


def add_missing_columns(conn: Connection, metadata: MetaData | None = None) -> list[str]:
    """빠진 칸을 더하고 더한 「표.칸」 목록을 돌려준다(이미 다 있으면 빈 목록)."""
    md = metadata or Base.metadata
    existing = _existing_columns(conn)
    prep = conn.dialect.identifier_preparer
    added: list[str] = []
    for table in md.sorted_tables:
        have = existing.get(table.name)
        if have is None:
            continue  # create_all이 만든다
        for col in table.columns:
            if col.name in have:
                continue
            default = _default_sql(col, conn)
            if col.primary_key or (not col.nullable and default is None):
                log.warning(
                    "schema: 칸을 더하지 못함 %s.%s (기본값 없는 필수 칸)", table.name, col.name
                )
                continue
            ddl = (
                f"ALTER TABLE {prep.quote(table.name)} ADD COLUMN {prep.quote(col.name)} "
                f"{col.type.compile(dialect=conn.dialect)}"
            )
            # SQLite(로컬)는 ADD COLUMN에 CURRENT_TIMESTAMP를 못 받는다 → 칸만 더하고 값을 채움.
            # 운영 Postgres는 DEFAULT CURRENT_TIMESTAMP NOT NULL을 그대로 받는다
            backfill = default == "CURRENT_TIMESTAMP" and conn.dialect.name == "sqlite"
            if default is not None and not backfill:
                ddl += f" DEFAULT {default}"
                if not col.nullable:
                    ddl += " NOT NULL"
            conn.exec_driver_sql(ddl)
            if backfill:
                conn.exec_driver_sql(
                    f"UPDATE {prep.quote(table.name)} SET {prep.quote(col.name)} = CURRENT_TIMESTAMP"
                )
            added.append(f"{table.name}.{col.name}")
            if col.unique or col.index:
                log.warning("schema: %s.%s 색인·유일 제약은 직접 만들어야 함", table.name, col.name)
    if added:
        log.info("schema: 칸 더함 %s", ", ".join(added))
    return added
