"""FastAPI 진입점. `uv run uvicorn app.main:app`."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import config, errors
from app.api import health_router, router
from app.compat import router as compat_router
from app.db import get_db, get_engine
from app.demo import ensure_demo_actors
from app.demo import router as demo_router
from app.guardian import router as guardian_router
from app.instructor import router as instructor_router
from app.models import Base
from app.seed import load_seed
from app.timeutil import get_now


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # 로컬 SQLite용: 테이블 만들고 시드 20문제 적재(여러 번 불러도 안전).
    # 데모 배우가 없으면 day3로 만든다(배포 DB는 휘발성 — 재시작 뒤에도 바로 쓸 수 있게).
    # 빈 DB 동시 기동은 안전하지 않으니 워커는 1개로 띄운다(render.yaml).
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async for db in get_db():
        await load_seed(db)
        await ensure_demo_actors(db, get_now())
        await db.commit()
    yield


def _setup_logging() -> None:
    """uvicorn은 app.* 로거를 설정하지 않아 INFO(source·토큰 수·단계)가 버려진다.
    app 로거에만 핸들러를 단다. 수준은 INFO 고정(DEBUG는 치환본이 찍힐 수 있다)."""
    logger = logging.getLogger("app")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s %(message)s"))
        logger.addHandler(handler)
        logger.propagate = False
    logger.setLevel(logging.INFO)


def create_app() -> FastAPI:
    _setup_logging()
    app = FastAPI(title="chingu1", lifespan=lifespan)
    errors.install(app)
    # 로컬 프론트(localhost·127.0.0.1, 포트 무관)는 항상 허용, 배포 주소는 CORS_ORIGINS로
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins(),
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(router, prefix="/api/v1")
    app.include_router(instructor_router, prefix="/api/v1")
    app.include_router(demo_router, prefix="/api/v1")
    app.include_router(guardian_router, prefix="/api/v1")
    app.include_router(compat_router, prefix="/api/v1")  # 프론트 v0.5 호환(11-15까지 임시)
    # 프론트 빌드를 같은 주소에서 서빙(배포만, FRONTEND_DIST). 라우터 뒤에 마운트해 API가 먼저.
    # 앱은 해시 라우팅이라 index.html 폴백은 두지 않는다. 폴더가 없으면 아무것도 안 한다.
    dist = config.frontend_dist()
    if dist is not None and dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return app


app = create_app()
