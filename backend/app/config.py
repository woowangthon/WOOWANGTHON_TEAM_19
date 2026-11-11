"""환경 변수. 키 값은 읽기만 하고 로그·응답에 내보내지 않는다(있는지 여부만)."""

import math
import os


def database_url() -> str:
    return os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./dev.db")


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


def demo_token() -> str | None:
    """POST /demo/reset 비밀 토큰. 없거나 빈 값이면 None(→ 리셋 403)."""
    return os.environ.get("DEMO_TOKEN") or None


# 리셋(POST /demo/reset)이 정한 배율. 테이블 칸이 없어 프로세스 메모리에 둔다.
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
