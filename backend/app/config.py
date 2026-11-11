"""환경 변수. 키 값은 읽기만 하고 로그·응답에 내보내지 않는다(있는지 여부만)."""

import math
import os
from pathlib import Path


def database_url() -> str:
    """로컬·테스트는 SQLite 그대로. 배포(Supabase)가 주는 `postgres://`·`postgresql://`는
    async 드라이버 `postgresql+asyncpg://`로 바꾼다. libpq 식 `sslmode`는 asyncpg가 모르니
    `ssl`로 옮기고, Vercel 연동이 붙이는 `supa=` 같은 모르는 값은 뺀다."""
    raw = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./dev.db")
    scheme, sep, rest = raw.partition("://")
    if not sep or scheme not in ("postgres", "postgresql"):
        return raw
    base, qsep, query = rest.partition("?")
    kept: list[str] = []
    for pair in query.split("&") if qsep else []:
        key, _, value = pair.partition("=")
        if key == "sslmode":
            kept.append(f"ssl={value}")
        elif key == "ssl":
            kept.append(pair)
    url = f"postgresql+asyncpg://{base}"
    return f"{url}?{'&'.join(kept)}" if kept else url


def llm_mode() -> str:
    return os.environ.get("LLM_MODE", "scripted")  # live / scripted


def llm_key_present() -> bool:
    return bool(os.environ.get("LLM_API_KEY"))


def llm_api_key() -> str | None:
    """어댑터 생성에만 쓴다. 로그·응답에 싣지 않는다."""
    return os.environ.get("LLM_API_KEY") or None


def llm_model() -> str:
    return os.environ.get("LLM_MODEL") or "claude-haiku-5-5"


def llm_effective_mode() -> str:
    """실제로 쓰는 어댑터. LLM_MODE=live여도 키가 없으면 scripted."""
    return "live" if llm_mode() == "live" and llm_key_present() else "scripted"


def cors_origins() -> list[str]:
    """localhost 말고 더 허용할 프론트 주소. 쉼표로 구분(예: 배포 프론트 URL)."""
    raw = os.environ.get("CORS_ORIGINS", "")
    return [o.strip() for o in raw.split(",") if o.strip()]


def frontend_dist() -> Path | None:
    """같은 주소로 서빙할 프론트 빌드 폴더(FRONTEND_DIST). 없으면 None(서빙 안 함).
    상대 경로는 실행 위치가 아니라 backend/ 기준으로 푼다(render.yaml: ../frontend/dist)."""
    raw = os.environ.get("FRONTEND_DIST", "").strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path
    return path.resolve()


def trial_only() -> bool:
    """공개 배포에서는 체험 세트 id(`t-…`)만 받는다 — 헤더를 꾸며 공용 데모 배우를 쓰지 못하게(11-11).

    TRIAL_ONLY가 있으면 그 값(1/true/yes = 켬), 없으면 Vercel(VERCEL=1)에서 켠다. 로컬·테스트는 꺼짐.
    """
    raw = os.environ.get("TRIAL_ONLY")
    if raw is not None:
        return raw.strip().lower() in ("1", "true", "yes")
    return os.environ.get("VERCEL") == "1"


def demo_token() -> str | None:
    """POST /demo/reset 비밀 토큰. 없거나 빈 값이면 None(→ 리셋 403)."""
    return os.environ.get("DEMO_TOKEN") or None


# 리셋(POST /demo/reset)이 정한 배율. 테이블 칸이 없어 프로세스 메모리에 둔다.
# 로컬(영상 촬영)·테스트 전용. Vercel 배포는 함수 인스턴스마다 메모리가 따로라 리셋한
# 인스턴스에만 먹고 나머지는 모른다 → 배포는 실제 시간(명세 4.11-3)이고 환경변수
# TIMER_SCALE도 넣지 않는다. 배포에서 이 값에 기대는 기능을 만들지 않는다.
_timer_scale_override: float | None = None


def set_timer_scale(scale: float) -> None:
    """0 이하·inf·nan이면 ValueError(호출하는 쪽이 422로)."""
    global _timer_scale_override
    if not (math.isfinite(scale) and scale > 0):
        raise ValueError("timer_scale must be a finite number > 0")
    _timer_scale_override = float(scale)


def clear_timer_scale() -> None:
    """리셋이 정한 배율을 지운다(→ 환경변수 TIMER_SCALE)."""
    global _timer_scale_override
    _timer_scale_override = None


def timer_scale() -> float:
    """데모 타이머 단축 배율. 리셋이 정한 값이 먼저, 없으면 TIMER_SCALE.
    TIMER_SCALE이 0·음수·inf·nan·숫자 아님이면 조용히 1."""
    if _timer_scale_override is not None:
        return _timer_scale_override
    try:
        scale = float(os.environ.get("TIMER_SCALE", "1"))
    except ValueError:
        return 1
    return scale if math.isfinite(scale) and scale > 0 else 1
