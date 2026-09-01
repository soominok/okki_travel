from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from app.logging import setup_logging

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)
    log.info("api.startup", env=settings.app_env)
    yield
    log.info("api.shutdown")


app = FastAPI(title="TripPick API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().public_web_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz() -> dict:
    """무인증. DB 연결까지 실제로 확인한다."""
    db_status = "ok"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - 헬스체크는 원인을 문자열로 보고한다
        db_status = f"error: {type(exc).__name__}"
    return {"status": "ok" if db_status == "ok" else "degraded", "db": db_status}
