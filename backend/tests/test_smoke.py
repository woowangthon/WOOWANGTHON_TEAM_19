"""도구 체인 확인용 연기 테스트. 시드 정본이 읽히고 20문제인지만 본다."""

import json
from pathlib import Path

SEED = Path(__file__).resolve().parents[2] / "seed" / "seed_v0.1.json"


def test_seed_file_has_twenty_problems():
    data = json.loads(SEED.read_text(encoding="utf-8"))
    problems = data["problems"] if isinstance(data, dict) and "problems" in data else data
    assert len(problems) == 20
