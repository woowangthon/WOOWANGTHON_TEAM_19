"""명세 4.13 학년별 문제 시범 — G5 적재, G1 가입 학년 시작 문제(11-14, bb 검토 반영)."""

import shutil
from pathlib import Path

from sqlalchemy import func, select

from app.models import Problem
from app.seed import BANK_DIR, SEED_PATH, load_seed, resolve_bank_dir


def _bank_total() -> int:
    """은행 폴더에서 센다(bb: 숫자를 박지 말 것) + 분수 시드 20."""
    import json as _json

    return 20 + sum(len(_json.loads(f.read_text("utf-8"))) for f in BANK_DIR.glob("*.json"))


async def test_bank_loads_all_once(db_session):
    await load_seed(db_session)
    await load_seed(db_session)  # 두 번 불러도 같음
    n = await db_session.scalar(select(func.count()).select_from(Problem))
    assert n == _bank_total()
    kor = await db_session.get(Problem, "g8-kor-parts-of-speech-01")
    eng = await db_session.get(Problem, "g10-eng-relative-clauses-01")
    math4 = await db_session.get(Problem, "g4-math-large-numbers-01")
    assert kor is not None and kor.expr == "" and kor.standard["subject"] == "korean"
    assert eng is not None and eng.expr == "" and eng.standard["subject"] == "english"
    assert math4 is not None and math4.standard["subject"] == "math" and math4.grade == 4
    frac = await db_session.get(Problem, "frac-div-nat-01")
    assert frac is not None and "subject" not in frac.standard  # 시드는 그대로


async def test_bank_from_bundled_copy(db_session, tmp_path: Path):
    # 배포 함수에는 저장소 seed/가 없다 → 빌드 때 복사한 app/_seed/bank를 읽는다
    bundled = tmp_path / "bank"
    shutil.copytree(BANK_DIR, bundled)
    assert resolve_bank_dir(tmp_path / "없음", bundled) == bundled
    await load_seed(db_session, SEED_PATH, bundled)
    n = await db_session.scalar(select(func.count()).select_from(Problem))
    assert n == _bank_total()


async def test_empty_bank_warns(db_session, tmp_path: Path, caplog):
    empty = tmp_path / "bank"
    empty.mkdir()
    with caplog.at_level("WARNING"):
        await load_seed(db_session, SEED_PATH, empty)
    assert "bank" in caplog.text
    n = await db_session.scalar(select(func.count()).select_from(Problem))
    assert n == 20
