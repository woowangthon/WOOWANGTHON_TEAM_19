"""시드 20문제 + 학년별 시범 60문제 적재(명세 4.13). 정본은 저장소 루트의 seed/."""

import json
import logging
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

# 명세 4.13 학년별 시범 단원(초4 수학·중2 국어·고1 영어 각 20). AI 초안·교사 검수 전
_REPO_BANK = Path(__file__).resolve().parents[2] / "seed" / "drafts" / "bank" / "problems_v2"
_BUNDLED_BANK = Path(__file__).resolve().parent / "_seed" / "bank"


def resolve_bank_dir(repo: Path = _REPO_BANK, bundled: Path = _BUNDLED_BANK) -> Path:
    return repo if repo.is_dir() else bundled


BANK_DIR = resolve_bank_dir()
log = logging.getLogger(__name__)


def _bank_problems(bank: Path) -> list[dict]:
    """은행 파일 → 문제 행 모양. 새 칸 없이: 과목은 standard.subject, expr가 없으면 ""."""
    out: list[dict] = []
    for f in sorted(bank.glob("*.json")) if bank.is_dir() else []:
        for p in json.loads(f.read_text(encoding="utf-8")):
            out.append(
                {
                    **p,
                    "standard": {
                        **p["standard"],
                        "subject": p["subject"],
                        "difficulty": p.get("difficulty"),  # 명세 4.13-7 D1
                    },
                    "expr": p.get("expr") or "",
                }
            )
    if not out:
        log.warning("problem bank empty: %s (학년별 시범 문제 없음, 분수 시드만)", bank)
    return out


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


def _seed_difficulty(bank: Path) -> dict[str, str]:
    """분수 시드 20문제 난이도(bb가 매김, 교사 검수 전 — 명세 4.13-7 D1). 은행 폴더 옆 파일."""
    f = bank.parent / "seed_difficulty_v0.1.json"
    if not f.exists():
        f = bank / "seed_difficulty_v0.1.json"  # 배포 복사본(app/_seed/bank)
    if not f.exists():
        log.warning("seed difficulty file missing: %s", f)
        return {}
    return {r["id"]: r["difficulty"] for r in json.loads(f.read_text(encoding="utf-8"))}


async def load_seed(db: AsyncSession, path: Path = SEED_PATH, bank: Path = BANK_DIR) -> int:
    """없는 문제만 넣고 넣은 개수를 돌려준다. 여러 번 불러도 안전.
    명세 4.13-7 D1: 이미 있는 행도 standard.difficulty가 비어 있으면 채운다(새 칸 없음)."""
    seed_diff = _seed_difficulty(bank)
    seed = [
        {**p, "standard": {**p["standard"], "difficulty": seed_diff.get(p["id"])}}
        for p in json.loads(path.read_text(encoding="utf-8"))
    ]
    problems = seed + _bank_problems(bank)
    want = {p["id"]: p["standard"].get("difficulty") for p in problems}
    rows = {r.id: r for r in (await db.scalars(select(Problem))).all()}
    added = 0
    for p in problems:
        if p["id"] in rows:
            continue
        db.add(Problem(**{k: p.get(k) for k in _FIELDS}))
        added += 1
    for pid, row in rows.items():
        d = want.get(pid)
        if d and not (row.standard or {}).get("difficulty"):
            row.standard = {**(row.standard or {}), "difficulty": d}  # 새 dict라 JSON 변경이 잡힌다
    await db.flush()
    return added


async def grade_unit_first(db: AsyncSession, grade: int | None) -> str | None:
    """그 학년 시범 단원(은행 문제 = standard.subject 있음)의 첫 문제 id. 없으면 None(명세 4.13-2·5)."""
    if grade is None:
        return None
    rows = (
        await db.scalars(select(Problem).where(Problem.grade == grade).order_by(Problem.id))
    ).all()
    return next((p.id for p in rows if "subject" in (p.standard or {})), None)
