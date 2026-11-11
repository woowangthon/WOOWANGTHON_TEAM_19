"""시드 20문제 적재. 정본은 저장소 루트의 seed/seed_v0.1.json."""

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Problem

SEED_PATH = Path(__file__).resolve().parents[2] / "seed" / "seed_v0.1.json"
_FIELDS = (
    "id",
    "tag",
    "standard",
    "grade",
    "text",
    "expr",
    "answer",
    "hint1",
    "hint2",
    "solution",
    "forbidden",
)


async def load_seed(db: AsyncSession, path: Path = SEED_PATH) -> int:
    """없는 문제만 넣고 넣은 개수를 돌려준다. 여러 번 불러도 안전."""
    problems = json.loads(path.read_text(encoding="utf-8"))
    existing = set((await db.scalars(select(Problem.id))).all())
    added = 0
    for p in problems:
        if p["id"] in existing:
            continue
        db.add(Problem(**{k: p.get(k) for k in _FIELDS}))
        added += 1
    await db.flush()
    return added
