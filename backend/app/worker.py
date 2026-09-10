"""스케줄러 엔트리포인트."""

from __future__ import annotations

import asyncio

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import get_settings
from app.db import SessionLocal
from app.logging import setup_logging
from app.models.event import AirlineEvent
from app.sources.events.airbusan import AirBusanAdapter
from app.sources.events.flightdeal import FlightDealAdapter
from app.sources.events.jejuair import JejuAirAdapter
from app.sources.events.koreanair import KoreanAirAdapter
from app.sources.events.tway import TwayAdapter
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


def build_event_adapters():
    """이벤트 어댑터 인스턴스 목록을 반환한다. 테스트에서 패치 가능하도록 분리."""
    return [
        AirBusanAdapter(),
        TwayAdapter(),
        JejuAirAdapter(),
        KoreanAirAdapter(),
        FlightDealAdapter(),
    ]


async def event_tick() -> None:
    """항공사 이벤트 페이지 수집. 6시간마다 실행."""
    settings = get_settings()
    if not settings.crawl_enabled:
        log.info("worker.event_tick.skipped", reason="CRAWL_ENABLED=false")
        return

    adapters = build_event_adapters()
    new_count = 0
    new_events_for_slack: list = []

    for adapter in adapters:
        try:
            events = await adapter.fetch_events()
            if not events:
                continue

            async with SessionLocal() as session:
                for ev in events:
                    stmt = (
                        pg_insert(AirlineEvent)
                        .values(
                            source=ev.source,
                            external_id=ev.external_id,
                            title=ev.title,
                            url=ev.url,
                            origin=ev.origin,
                            destination=ev.destination,
                            valid_from=ev.valid_from,
                            valid_to=ev.valid_to,
                            discount_info=ev.discount_info,
                            is_active=True,
                        )
                        .on_conflict_do_nothing(constraint="uq_airline_events_source_ext")
                    )
                    result = await session.execute(stmt)
                    if result.rowcount:
                        new_count += 1
                        new_events_for_slack.append(ev)
                await session.commit()
        except Exception:  # noqa: BLE001
            log.exception("event_tick.adapter_error", source=adapter.source)
            continue

    log.info("worker.event_tick.done", new_events=new_count)

    # 신규 이벤트가 있으면 슬랙 알림 (per-adapter 순회 후)
    if new_events_for_slack and settings.slack_webhook_url:
        from app.notify.base import Confidence, NotificationMessage
        from app.notify.slack import SlackNotifier

        notifier = SlackNotifier(settings.slack_webhook_url.get_secret_value())
        for ev in new_events_for_slack[:10]:  # 최대 10건만 알림
            msg = NotificationMessage(
                severity="info",
                confidence=Confidence(
                    verified=False,
                    freshness="live",
                    age_label="방금",
                    source=ev.source,
                ),
                title=f"새 이벤트: [{ev.source}]",
                summary=ev.title,
                fields=[],
                link=ev.url,
                link_label="이벤트 보기",
                dedup_key=f"event:{ev.source}:{ev.external_id}",
            )
            await notifier.send(msg)


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    log.info("worker.startup", env=settings.app_env)

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(tick, "interval", seconds=60, id="tick", max_instances=1, coalesce=True)
    scheduler.add_job(cleanup_old_offers, "cron", hour=4, minute=0, max_instances=1, id="cleanup")
    scheduler.add_job(source_health_check, "interval", minutes=15, max_instances=1, id="health")
    scheduler.add_job(
        event_tick, "interval", hours=6, id="event_tick", max_instances=1, coalesce=True
    )
    scheduler.start()

    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown(wait=True)
        log.info("worker.shutdown")


if __name__ == "__main__":
    asyncio.run(main())
