from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
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
    """무인증. DB 연결은 Task 2에서 실제로 확인하도록 바뀐다."""
    return {"status": "ok", "db": "unchecked"}
