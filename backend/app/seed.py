"""시드 20문제 적재. 정본은 저장소 루트의 seed/seed_v0.1.json."""

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Problem

_REPO_SEED = Path(__file__).resolve().parents[2] / "seed" / "seed_v0.1.json"
# Vercel 백엔드 서비스는 루트가 backend/라 저장소 seed/가 함수 묶음에 안 실릴 수 있다.
# 그래서 빌드 때 여기로 복사한다(vercel.json backend.buildCommand). 정본은 여전히 seed/.
_BUNDLED_SEED = Path(__file__).resolve().parent / "_seed" / "seed_v0.1.json"


def resolve_seed_path(repo: Path = _REPO_SEED, bundled: Path = _BUNDLED_SEED) -> Path:
    """저장소 정본이 있으면 그것, 없으면(배포 함수) 빌드 때 복사한 것."""
    return repo if repo.exists() else bundled


SEED_PATH = resolve_seed_path()
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
