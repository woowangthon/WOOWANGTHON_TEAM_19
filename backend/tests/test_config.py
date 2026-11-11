"""config — timer_scale(잘못된 TIMER_SCALE은 조용히 1로, 리셋이 메모리로 덮어씀)·demo_token."""

import pytest

from app import config


@pytest.mark.parametrize("raw", ["0", "-2", "inf", "-inf", "nan", "abc", ""])
def test_timer_scale_invalid_falls_back_to_one(monkeypatch, raw):
    monkeypatch.setenv("TIMER_SCALE", raw)
    assert config.timer_scale() == 1


def test_timer_scale_valid_value_is_used(monkeypatch):
    monkeypatch.setenv("TIMER_SCALE", "60")
    assert config.timer_scale() == 60


def test_timer_scale_default_is_one(monkeypatch):
    monkeypatch.delenv("TIMER_SCALE", raising=False)
    assert config.timer_scale() == 1


@pytest.fixture
def clean_scale(monkeypatch):
    """프로세스 메모리 배율은 테스트 사이에 새지 않게 되돌린다."""
    monkeypatch.setattr(config, "_timer_scale_override", None)


def test_set_timer_scale_overrides_env(monkeypatch, clean_scale):
    monkeypatch.setenv("TIMER_SCALE", "60")
    config.set_timer_scale(10)
    assert config.timer_scale() == 10


@pytest.mark.parametrize("bad", [0, -1, float("inf"), float("nan")])
def test_set_timer_scale_rejects_bad_value(monkeypatch, clean_scale, bad):
    monkeypatch.delenv("TIMER_SCALE", raising=False)
    with pytest.raises(ValueError):
        config.set_timer_scale(bad)
    assert config.timer_scale() == 1


def test_demo_token_absent_or_empty_is_none(monkeypatch):
    monkeypatch.delenv("DEMO_TOKEN", raising=False)
    assert config.demo_token() is None
    monkeypatch.setenv("DEMO_TOKEN", "")
    assert config.demo_token() is None


def test_demo_token_present(monkeypatch):
    monkeypatch.setenv("DEMO_TOKEN", "synthetic-token")
    assert config.demo_token() == "synthetic-token"


@pytest.mark.parametrize(
    ("mode", "key", "effective"),
    [("live", "k", "live"), ("live", None, "scripted"), ("scripted", "k", "scripted")],
)
def test_llm_effective_mode(monkeypatch, mode, key, effective):
    """healthz가 말하는 모드 = 실제로 쓰는 어댑터. live인데 키가 없으면 scripted."""
    monkeypatch.setenv("LLM_MODE", mode)
    if key is None:
        monkeypatch.delenv("LLM_API_KEY", raising=False)
    else:
        monkeypatch.setenv("LLM_API_KEY", key)
    assert config.llm_effective_mode() == effective


def test_seed_path_falls_back_to_bundled_copy(tmp_path):
    """Vercel 백엔드 서비스(루트 backend/)엔 저장소 seed/가 함수에 안 실릴 수 있다 → 빌드 때 복사본."""
    from app import seed

    repo = tmp_path / "repo.json"
    bundled = tmp_path / "bundled.json"
    assert seed.resolve_seed_path(repo, bundled) == bundled
    repo.write_text("[]", encoding="utf-8")
    assert seed.resolve_seed_path(repo, bundled) == repo
