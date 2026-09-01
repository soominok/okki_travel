"""스케줄러 엔트리포인트. 실제 잡은 Plan 4에서 붙는다."""

import asyncio

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings
from app.logging import setup_logging

log = structlog.get_logger()


async def heartbeat() -> None:
    log.info("worker.heartbeat")


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    log.info("worker.startup", env=settings.app_env)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(heartbeat, "interval", seconds=30, id="heartbeat", max_instances=1)
    scheduler.start()

    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown(wait=True)
        log.info("worker.shutdown")


if __name__ == "__main__":
    asyncio.run(main())
