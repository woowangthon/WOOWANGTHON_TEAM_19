"""배포 설정(vercel.json) — 함수 리전을 DB(Supabase 서울)와 같은 서울로 고정한다.

11-13 측정: 운영 응답 헤더 x-vercel-id가 hkg1::iad1(미국 동부)이었다. DB 쿼리마다 태평양을
왕복해 쿼리 1개인 /healthz가 약 2초, 콜드 스타트 14초. 대시보드 설정이 아니라 저장소에 고정한다.
"""

import json
from pathlib import Path

VERCEL_JSON = Path(__file__).resolve().parents[2] / "vercel.json"


def test_functions_run_in_seoul_next_to_db():
    conf = json.loads(VERCEL_JSON.read_text(encoding="utf-8"))
    assert conf.get("regions") == ["icn1"]
