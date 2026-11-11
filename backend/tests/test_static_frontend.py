"""한 주소 배포(TK-56) — FRONTEND_DIST가 가리키는 프론트 빌드를 FastAPI가 같은 주소에서 서빙.

API(/api/*·/healthz)가 먼저, 나머지는 정적 파일. 앱은 해시 라우팅이라 SPA 폴백은 두지 않는다.
FRONTEND_DIST가 없거나 폴더가 없으면 아무것도 안 한다(로컬·테스트는 지금처럼).
"""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app import db as appdb
from app.actors import DEMO_CHILD_ID
from app.main import create_app

CHILD = {"X-Demo-Role": "child", "X-Demo-Actor": DEMO_CHILD_ID}
INDEX = "<!doctype html><title>chingu1</title><div id=root></div>"


@pytest_asyncio.fixture
async def db_file(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'static.db'}")
    monkeypatch.setattr(appdb, "_engine", None)
    monkeypatch.setattr(appdb, "_sessionmaker", None)
    yield
    if appdb._engine is not None:
        await appdb._engine.dispose()


@pytest_asyncio.fixture
async def dist(tmp_path):
    d = tmp_path / "dist"
    (d / "assets").mkdir(parents=True)
    (d / "index.html").write_text(INDEX, encoding="utf-8")
    (d / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    # 정적 파일이 API 경로를 가리려 해도 API가 이겨야 한다
    (d / "healthz").write_text("static", encoding="utf-8")
    return d


async def _client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_root_serves_index_html(monkeypatch, db_file, dist):
    monkeypatch.setenv("FRONTEND_DIST", str(dist))
    app = create_app()
    async with app.router.lifespan_context(app), await _client(app) as c:
        r = await c.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert r.text == INDEX
        r = await c.get("/assets/app.js")
        assert r.status_code == 200
        assert r.text == "console.log(1)"


async def test_api_routes_win_over_static(monkeypatch, db_file, dist):
    monkeypatch.setenv("FRONTEND_DIST", str(dist))
    app = create_app()
    async with app.router.lifespan_context(app), await _client(app) as c:
        for path in ("/healthz", "/api/v1/healthz"):
            r = await c.get(path)
            assert r.status_code == 200
            assert r.json()["db"] == "ok"
        r = await c.get("/api/v1/compat/student/home", headers=CHILD)
        assert r.status_code == 200
        assert "application/json" in r.headers["content-type"]


async def test_unknown_api_path_is_not_index_html(monkeypatch, db_file, dist):
    monkeypatch.setenv("FRONTEND_DIST", str(dist))
    app = create_app()
    async with app.router.lifespan_context(app), await _client(app) as c:
        r = await c.get("/api/v1/nope")
        assert r.status_code == 404
        assert r.text != INDEX


async def test_relative_dist_resolves_from_backend_dir(monkeypatch, tmp_path):
    """render.yaml은 FRONTEND_DIST=../frontend/dist(backend 기준). 실행 위치와 무관하게 해석."""
    from app import config

    monkeypatch.setenv("FRONTEND_DIST", "../frontend/dist")
    monkeypatch.chdir(tmp_path)
    got = config.frontend_dist()
    assert got is not None
    assert got.parts[-2:] == ("frontend", "dist")
    # backend/ 옆의 frontend/ — 저장소 루트 기준
    assert got.parent.parent.joinpath("backend", "app").is_dir()


async def test_no_dist_keeps_old_behavior(monkeypatch, db_file, tmp_path):
    monkeypatch.setenv("FRONTEND_DIST", str(tmp_path / "missing"))
    app = create_app()
    async with app.router.lifespan_context(app), await _client(app) as c:
        assert (await c.get("/")).status_code == 404
        assert (await c.get("/healthz")).status_code == 200


async def test_unset_env_serves_nothing(monkeypatch, db_file):
    monkeypatch.delenv("FRONTEND_DIST", raising=False)
    app = create_app()
    async with app.router.lifespan_context(app), await _client(app) as c:
        assert (await c.get("/")).status_code == 404
