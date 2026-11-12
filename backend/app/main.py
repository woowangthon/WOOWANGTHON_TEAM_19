"""FastAPI 진입점. `uv run uvicorn app.main:app`."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app import config, errors
from app.account_routes import router as account_router
from app.api import health_router, router
from app.compat import router as compat_router
from app.db import get_engine
from app.demo import ensure_demo_actors
from app.demo import router as demo_router
from app.guardian import router as guardian_router
from app.instructor import router as instructor_router
from app.models import Base
from app.org_routes import router as org_router
from app.seed import load_seed
from app.seed_routes import router as seed_router
from app.timeutil import get_now

# 기동 준비를 한 번에 하나씩 하게 거는 Postgres 자문 잠금 번호(임의의 고정값)
_STARTUP_LOCK_KEY = 0x6368696E6775  # "chingu"


async def _enable_rls(conn: AsyncConnection) -> None:
    """Supabase는 public 스키마 테이블을 Data API(anon 키)로 열 수 있다 → RLS만 켠다(정책 없음 =
    anon·authenticated 차단). 앱은 테이블 주인 역할로 붙어 RLS를 받지 않는다.
    이미 켜진 테이블은 건드리지 않는다(ALTER TABLE은 테이블 잠금이라 매 기동마다 걸지 않게)."""
    names = [t.name for t in Base.metadata.sorted_tables]
    rows = await conn.execute(
        text(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = current_schema() AND c.relname = ANY(:names) "
            "AND NOT c.relrowsecurity"
        ),
        {"names": names},
    )
    for (name,) in rows.all():
        await conn.execute(text(f'ALTER TABLE "{name}" ENABLE ROW LEVEL SECURITY'))


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # 테이블 만들고 시드 20문제 적재, 데모 배우가 없으면 day3로 만든다(여러 번 불러도 안전).
    # Vercel은 함수 인스턴스마다 기동이 돈다 → 빈 DB에 동시에 들어와도 깨지지 않게 Postgres는
    # 트랜잭션 자문 잠금으로 한 줄 세운다(뒤 인스턴스는 앞이 커밋한 걸 보고 아무것도 안 한다).
    # 전부 한 트랜잭션: 중간에 죽으면 통째로 되돌아간다. 로컬 SQLite는 예전과 같다.
    async with get_engine().begin() as conn:
        if conn.dialect.name == "postgresql":
            await conn.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _STARTUP_LOCK_KEY})
        await conn.run_sync(Base.metadata.create_all)
        if conn.dialect.name == "postgresql":
            await _enable_rls(conn)
        db = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            await load_seed(db)
            await ensure_demo_actors(db, get_now())
            await db.flush()
        finally:
            await db.close()
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
        # 로그인 쿠키(cm_session)를 실어 보내려면 credentials가 필요하다(명세 4.12).
        # credentials와 `*` 헤더를 같이 쓰지 않고 쓰는 헤더만 적는다
        allow_credentials=True,
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-Demo-Role",
            "X-Demo-Actor",
            "X-Demo-Token",
            "X-Trial-Id",
        ],
    )
    app.include_router(health_router)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(router, prefix="/api/v1")
    app.include_router(instructor_router, prefix="/api/v1")
    app.include_router(demo_router, prefix="/api/v1")
    app.include_router(guardian_router, prefix="/api/v1")
    app.include_router(compat_router, prefix="/api/v1")  # 프론트 v0.5 호환(11-15까지 임시)
    app.include_router(account_router, prefix="/api/v1")  # 계정(명세 4.12), 같은 /compat 아래
    app.include_router(org_router, prefix="/api/v1")  # 연결·학원·강의실(명세 4.12)
    app.include_router(seed_router, prefix="/api/v1")  # 씨앗·상점·도장·기록(명세 4.12)
    # 프론트 빌드를 같은 주소에서 서빙(배포만, FRONTEND_DIST). 라우터 뒤에 마운트해 API가 먼저.
    # 앱은 해시 라우팅이라 index.html 폴백은 두지 않는다. 폴더가 없으면 아무것도 안 한다.
    dist = config.frontend_dist()
    if dist is not None and dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return app


app = create_app()
