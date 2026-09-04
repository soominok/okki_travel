"""수집 파이프라인 — SCAN → SAMPLE → VERIFY → DB 저장."""

from __future__ import annotations

import calendar
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.price import Offer as DbOffer
from app.models.price import PriceSnapshot
from app.models.watch import Watch, WatchRun
from app.sources.base import FetchRequest
from app.sources.budget import ensure_budget_row, reserve_sample, reserve_verify
from app.sources.registry import SourceRegistry

log = structlog.get_logger()


def _monthly_chunks(depart_from: date, depart_to: date) -> list[tuple[date, date]]:
    """날짜 범위를 같은-달 청크로 분할.

    Travelpayouts는 달 경계를 넘길 수 없다 (Ruling R7).
    >>> _monthly_chunks(date(2026, 10, 1), date(2026, 10, 31))
    [(date(2026, 10, 1), date(2026, 10, 31))]
    >>> _monthly_chunks(date(2026, 10, 15), date(2026, 11, 10))
    [(date(2026, 10, 15), date(2026, 10, 31)), (date(2026, 11, 1), date(2026, 11, 10))]
    """
    chunks: list[tuple[date, date]] = []
    cur = depart_from
    while cur <= depart_to:
        last_day = calendar.monthrange(cur.year, cur.month)[1]
        month_end = date(cur.year, cur.month, last_day)
        chunk_end = min(month_end, depart_to)
        chunks.append((cur, chunk_end))
        if chunk_end >= depart_to:
            break
        cur = chunk_end + timedelta(days=1)
    return chunks


def _build_requests(watch: Watch) -> list[FetchRequest]:
    """Watch.params → FetchRequest 목록. 월 경계로 청크 분할."""
    p = watch.params
    if watch.kind == "flight":
        depart_from = date.fromisoformat(p["depart_from"])
        depart_to = date.fromisoformat(p["depart_to"])
        chunks = _monthly_chunks(depart_from, depart_to)
        return [
            FetchRequest(
                origin=p.get("origin", ""),
                destination=p["destination"],
                depart_from=start,
                depart_to=end,
                nights_min=p.get("nights_min"),
                nights_max=p.get("nights_max"),
                adults=p.get("adults", 1),
                cabin=p.get("cabin", "economy"),
                currency="KRW",
            )
            for start, end in chunks
        ]
    # stay
    return [
        FetchRequest(
            origin="",
            destination=p["city_code"],
            depart_from=date.fromisoformat(p["checkin_from"]),
            depart_to=date.fromisoformat(p["checkin_to"]),
            nights_min=p.get("nights"),
            adults=p.get("guests", 2),
            currency="KRW",
        )
    ]


def _target_price(rules: list[dict]) -> int | None:
    for r in rules:
        if r.get("type") == "threshold":
            return int(r["price_krw"])
    return None


def _days_left_in_month() -> int:
    today = date.today()
    last = calendar.monthrange(today.year, today.month)[1]
    return max(1, last - today.day + 1)


async def collect_watch(
    watch_id: UUID,
    *,
    session: AsyncSession,
    registry: SourceRegistry,
    settings: Settings,
    run_id: UUID | None = None,
) -> WatchRun:
    """Watch 1개를 SCAN → SAMPLE → VERIFY → 저장.

    예외를 밖으로 던지지 않는다. 실패는 WatchRun.status='failed'로 기록.
    session은 호출자가 넘긴다. budget은 별도 SessionLocal 세션으로 처리.
    run_id가 주어지면 기존 WatchRun을 재사용한다 (/run 엔드포인트 사전 생성 경우).
    """
    from app.db import SessionLocal

    run: WatchRun | None = None
    try:
        # 1. Watch 로드
        watch = await session.get(Watch, watch_id)
        if watch is None or watch.status != "active":
            if run_id is not None:
                run = await session.get(WatchRun, run_id)
            if run is None:
                run = WatchRun(watch_id=watch_id)
                session.add(run)
            run.status = "failed"
            run.error = "watch not found or inactive"
            run.finished_at = datetime.now(tz=UTC)
            run.offers_found = 0
            run.credits_used = 0
            await session.commit()
            return run

        # 2. WatchRun 로드 or 생성
        if run_id is not None:
            run = await session.get(WatchRun, run_id)
        if run is None:
            run = WatchRun(watch_id=watch_id)
            session.add(run)
            await session.flush()  # run.id 확보

        sources_ok: list[str] = []
        sources_failed: dict[str, str] = {}
        all_offers: list = []  # sources/base.py Offer 인스턴스
        credits_used = 0

        requests = _build_requests(watch)
        scan_adapters = registry.get(kind=watch.kind, role="scan")

        # 3. SCAN — 무료 소스
        for req in requests:
            for adapter in scan_adapters:
                try:
                    result = await adapter.fetch(req)
                except Exception as e:  # noqa: BLE001
                    sources_failed[adapter.name] = str(e)
                    continue
                if result.ok:
                    all_offers.extend(result.offers)
                    if adapter.name not in sources_ok:
                        sources_ok.append(adapter.name)
                else:
                    sources_failed[adapter.name] = result.error or "unknown"

        # 4. SAMPLE — SCAN 결과 없을 때 유료 소스 1회
        if not all_offers and requests:
            sample_adapters = registry.get(kind=watch.kind, role="verify")
            for adapter in sample_adapters:
                if adapter.capability.cost_per_call > 0:
                    async with SessionLocal() as bsession:
                        await ensure_budget_row(
                            bsession,
                            adapter.name,
                            total=settings.brightdata_monthly_credits,
                            sample_cap_ratio=settings.brightdata_sample_cap_ratio,
                        )
                        ok = await reserve_sample(
                            bsession,
                            adapter.name,
                            n=1,
                            days_left=_days_left_in_month(),
                        )
                    if not ok:
                        log.info("collector.sample.budget_exhausted", source=adapter.name)
                        continue
                    credits_used += adapter.capability.cost_per_call
                try:
                    result = await adapter.fetch(requests[0])
                except Exception as e:  # noqa: BLE001
                    sources_failed[adapter.name] = str(e)
                    continue
                if result.ok:
                    all_offers.extend(result.offers)
                    if adapter.name not in sources_ok:
                        sources_ok.append(adapter.name)
                else:
                    sources_failed[adapter.name] = result.error or "unknown"

        # 5. VERIFY — best_price ≤ threshold * ratio のとき確認
        target = _target_price(watch.rules)
        if target and all_offers:
            best_offer = min(all_offers, key=lambda o: o.price_krw)
            threshold = int(target * settings.verify_threshold_ratio)
            if best_offer.price_krw <= threshold:
                verify_adapters = registry.get(kind=watch.kind, role="verify")
                for adapter in verify_adapters:
                    if adapter.capability.cost_per_call > 0:
                        async with SessionLocal() as bsession:
                            await ensure_budget_row(
                                bsession,
                                adapter.name,
                                total=settings.brightdata_monthly_credits,
                                sample_cap_ratio=settings.brightdata_sample_cap_ratio,
                            )
                            ok = await reserve_verify(bsession, adapter.name)
                        if not ok:
                            log.info("collector.verify.budget_exhausted", source=adapter.name)
                            continue
                        credits_used += adapter.capability.cost_per_call
                    req_v = FetchRequest(
                        origin=watch.params.get("origin", ""),
                        destination=watch.params.get("destination")
                        or watch.params.get("city_code", ""),
                        depart_from=best_offer.depart_date or date.today(),
                        depart_to=best_offer.depart_date or date.today(),
                        nights_min=watch.params.get("nights_min") or watch.params.get("nights"),
                        currency="KRW",
                    )
                    try:
                        result = await adapter.fetch(req_v)
                    except Exception as e:  # noqa: BLE001
                        sources_failed[adapter.name] = str(e)
                        continue
                    if result.ok and result.offers:
                        all_offers.extend(result.offers)
                        if adapter.name not in sources_ok:
                            sources_ok.append(adapter.name)

        # 6. Offers DB 저장 — (source, external_id) 중복 제거 후 삽입
        seen_keys: set[tuple[str, str]] = set()
        unique_offers = []
        for o in all_offers:
            key = (o.source, o.external_id)
            if key not in seen_keys:
                seen_keys.add(key)
                unique_offers.append(o)
        all_offers = unique_offers

        for o in all_offers:
            db_offer = DbOffer(
                watch_id=watch_id,
                run_id=run.id,
                source=o.source,
                external_id=o.external_id,
                kind=o.kind,
                price_krw=o.price_krw,
                price_original=Decimal(str(o.price_original))
                if o.price_original is not None
                else None,
                currency_original=o.currency_original,
                depart_date=o.depart_date,
                return_date=o.return_date,
                carrier=o.carrier,
                deep_link=o.deep_link,
                raw=o.raw,
                collected_at=o.collected_at,
                freshness=o.freshness,
                cache_age_days=o.cache_age_days,
                observed_at=o.observed_at,
            )
            session.add(db_offer)
        await session.flush()

        # 7. PriceSnapshot (offer가 있을 때만)
        if all_offers:
            prices = sorted(o.price_krw for o in all_offers)
            snap = PriceSnapshot(
                watch_id=watch_id,
                min_price_krw=prices[0],
                median_price_krw=prices[len(prices) // 2],
                offer_count=len(prices),
                coverage_pct=None,  # Plan 4에서 채움
                live_pct=None,
                credits_used=credits_used,
            )
            session.add(snap)
            await session.flush()

        # 8. WatchRun 완료
        run.finished_at = datetime.now(tz=UTC)
        run.status = "ok" if not sources_failed else ("partial" if all_offers else "failed")
        run.sources_ok = list(set(sources_ok)) or None
        run.sources_failed = sources_failed or None
        run.offers_found = len(all_offers)
        run.best_price_krw = min(o.price_krw for o in all_offers) if all_offers else None
        run.credits_used = credits_used

        # 9. Watch.last_run_at 갱신
        watch.last_run_at = datetime.now(tz=UTC)

        await session.commit()
        return run

    except Exception as exc:  # noqa: BLE001
        log.exception("collect_watch.unexpected_error", watch_id=str(watch_id))
        try:
            await session.rollback()
            if run is not None:
                run.status = "failed"
                run.error = type(exc).__name__
                run.finished_at = datetime.now(tz=UTC)
                session.add(run)
                await session.commit()
        except Exception:  # noqa: BLE001
            pass
        if run is None:
            run = WatchRun(
                watch_id=watch_id,
                status="failed",
                finished_at=datetime.now(tz=UTC),
                offers_found=0,
                credits_used=0,
            )
        return run
