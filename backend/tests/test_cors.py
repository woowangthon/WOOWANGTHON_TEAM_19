"""CORS — 지금은 localhost(포트 무관)만 허용. 배포 프론트 주소는 CORS_ORIGINS로 더한다."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


async def _preflight(origin: str) -> tuple[int, str | None]:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.options(
            "/api/v1/healthz",
            headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
        )
    return r.status_code, r.headers.get("access-control-allow-origin")


@pytest.mark.parametrize(
    "origin", ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"]
)
async def test_preflight_allows_localhost(monkeypatch, origin):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    status, allowed = await _preflight(origin)
    assert status == 200
    assert allowed == origin


@pytest.mark.parametrize(
    "origin", ["https://evil.example", "http://localhost.evil.example", "https://localhost:5173"]
)
async def test_preflight_rejects_other_origins(monkeypatch, origin):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    _, allowed = await _preflight(origin)
    assert allowed is None


async def test_cors_origins_env_adds_deployed_frontend(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://chingu1.example.app, https://b.example.app")
    status, allowed = await _preflight("https://b.example.app")
    assert status == 200
    assert allowed == "https://b.example.app"
