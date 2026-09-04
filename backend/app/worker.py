"""스케줄러 엔트리포인트."""

from __future__ import annotations

import asyncio

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import text

from app.config import get_settings
from app.db import SessionLocal
from app.logging import setup_logging
from app.sources.registry import build_registry

log = structlog.get_logger()


async def tick() -> None:
    """Due watch를 선점하고 collect_watch를 순차 실행.

    SELECT FOR UPDATE SKIP LOCKED — 워커가 여러 개여도 같은 행을 두 번 잡지 않는다.
    선점과 다음-예약을 한 UPDATE 문장으로 처리 (docs/02 §7).
    """
    settings = get_settings()
    registry = build_registry(settings)

    async with SessionLocal() as session:
        rows = await session.execute(
            text(
                """
                WITH due AS (
                  SELECT id FROM watches
                  WHERE status = 'active' AND next_run_at <= now()
                  ORDER BY next_run_at
                  FOR UPDATE SKIP LOCKED
                  LIMIT 5
                )
                UPDATE watches w
                SET next_run_at = now()
                      + (w.interval_min * interval '1 minute')
                      + (random() * interval '3 minutes'),
                    last_run_at = now()
                FROM due WHERE w.id = due.id
                RETURNING w.id
                """
            )
        )
        watch_ids = [r[0] for r in rows.fetchall()]
        await session.commit()

    for wid in watch_ids:
        async with SessionLocal() as s:
            from app.engine.collector import collect_watch

            try:
                await collect_watch(wid, session=s, registry=registry, settings=settings)
            except Exception:  # noqa: BLE001
                log.exception("tick.collect_failed", watch_id=str(wid))


async def cleanup_old_offers() -> None:
    """offer_retention_days 초과 offers 삭제."""
    settings = get_settings()
    async with SessionLocal() as session:
        result = await session.execute(
            text(
                "DELETE FROM offers WHERE collected_at < now() - "
                f"interval '{settings.offer_retention_days} days'"
            )
        )
        await session.commit()
        log.info("worker.cleanup_offers", deleted=result.rowcount)


async def source_health_check() -> None:
    """소스 헬스 체크 stub — Plan 5에서 실제 구현."""
    log.info("worker.source_health_check")


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    log.info("worker.startup", env=settings.app_env)

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(tick, "interval", seconds=60, id="tick", max_instances=1, coalesce=True)
    scheduler.add_job(cleanup_old_offers, "cron", hour=4, minute=0, max_instances=1, id="cleanup")
    scheduler.add_job(source_health_check, "interval", minutes=15, max_instances=1, id="health")
    scheduler.start()

    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown(wait=True)
        log.info("worker.shutdown")


if __name__ == "__main__":
    asyncio.run(main())
