"""Watch CRUD 라우터."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_token
from app.config import get_settings
from app.db import SessionLocal
from app.engine.collector import collect_watch
from app.models.price import Offer, PriceSnapshot
from app.models.watch import Watch, WatchRun
from app.schemas.watch import OfferOut, RunOut, SnapshotOut, WatchCreate, WatchPatch, WatchRead
from app.sources.registry import build_registry
from app.utils.deep_links import build_deep_links

router = APIRouter(prefix="/api/watches", tags=["watches"])
_auth = Depends(require_token)


@router.get("", response_model=list[WatchRead], dependencies=[_auth])
async def list_watches(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Watch).order_by(Watch.created_at.desc()))
    return result.scalars().all()


@router.post(
    "", response_model=WatchRead, status_code=status.HTTP_201_CREATED, dependencies=[_auth]
)
async def create_watch(body: WatchCreate, db: AsyncSession = Depends(get_db)):
    watch = Watch(
        kind=body.kind,
        title=body.title,
        params=body.params.model_dump(mode="json"),
        rules=[r.model_dump(mode="json") for r in body.rules],
        interval_min=body.interval_min,
        status="active",
        next_run_at=datetime.now(tz=UTC),
    )
    db.add(watch)
    await db.commit()
    await db.refresh(watch)
    return watch


@router.get("/{watch_id}", response_model=WatchRead, dependencies=[_auth])
async def get_watch(watch_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    watch = await db.get(Watch, watch_id)
    if watch is None:
        raise HTTPException(status_code=404, detail="watch not found")
    return watch


@router.patch("/{watch_id}", response_model=WatchRead, dependencies=[_auth])
async def patch_watch(watch_id: uuid.UUID, body: WatchPatch, db: AsyncSession = Depends(get_db)):
    watch = await db.get(Watch, watch_id)
    if watch is None:
        raise HTTPException(status_code=404, detail="watch not found")
    if body.params is not None:
        watch.params = body.params.model_dump(mode="json")
    if body.rules is not None:
        watch.rules = [r.model_dump(mode="json") for r in body.rules]
    if body.interval_min is not None:
        watch.interval_min = body.interval_min
    if body.status is not None:
        watch.status = body.status
    await db.commit()
    await db.refresh(watch)
    return watch


@router.delete("/{watch_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_auth])
async def delete_watch(watch_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    watch = await db.get(Watch, watch_id)
    if watch is None:
        raise HTTPException(status_code=404, detail="watch not found")
    await db.delete(watch)
    await db.commit()


@router.post("/{watch_id}/run", status_code=status.HTTP_202_ACCEPTED, dependencies=[_auth])
async def run_watch(
    watch_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    watch = await db.get(Watch, watch_id)
    if watch is None:
        raise HTTPException(status_code=404, detail="watch not found")
    if watch.status == "paused":
        raise HTTPException(status_code=409, detail="watch is paused")

    run = WatchRun(watch_id=watch_id, status="running")
    db.add(run)
    await db.commit()
    run_id = run.id

    settings = get_settings()
    registry = build_registry(settings)

    async def _bg() -> None:
        async with SessionLocal() as s:
            await collect_watch(
                watch_id, run_id=run_id, session=s, registry=registry, settings=settings
            )

    background_tasks.add_task(_bg)
    return {"run_id": str(run_id)}


@router.get("/{watch_id}/snapshots", response_model=list[SnapshotOut], dependencies=[_auth])
async def get_snapshots(
    watch_id: uuid.UUID,
    limit: int = 90,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PriceSnapshot)
        .where(PriceSnapshot.watch_id == watch_id)
        .order_by(desc(PriceSnapshot.captured_at))
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{watch_id}/offers", response_model=list[OfferOut], dependencies=[_auth])
async def get_offers(
    watch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    watch = await db.get(Watch, watch_id)
    if watch is None:
        raise HTTPException(status_code=404, detail="watch not found")

    # (source, external_id) 기준 가장 최근 수집된 것 하나씩만 반환
    latest_subq = (
        select(
            Offer.source,
            Offer.external_id,
            func.max(Offer.collected_at).label("max_at"),
        )
        .where(Offer.watch_id == watch_id)
        .group_by(Offer.source, Offer.external_id)
        .subquery()
    )
    result = await db.execute(
        select(Offer)
        .join(
            latest_subq,
            and_(
                Offer.source == latest_subq.c.source,
                Offer.external_id == latest_subq.c.external_id,
                Offer.collected_at == latest_subq.c.max_at,
                Offer.watch_id == watch_id,
            ),
        )
        .order_by(Offer.price_krw)
    )
    offers = result.scalars().all()

    # Watch params에서 딥링크 재료 추출 (flight 종류만)
    params = watch.params
    origin = params.get("origin") if isinstance(params, dict) else None
    destination = params.get("destination") if isinstance(params, dict) else None
    depart_from = params.get("depart_from") if isinstance(params, dict) else None

    out_list: list[OfferOut] = []
    for offer in offers:
        out = OfferOut.model_validate(offer)
        if origin and destination:
            dep = str(offer.depart_date) if offer.depart_date else depart_from
            ret = str(offer.return_date) if offer.return_date else None
            if dep:
                out.deep_links = build_deep_links(origin, destination, dep, ret)
        out_list.append(out)
    return out_list


@router.get("/{watch_id}/runs", response_model=list[RunOut], dependencies=[_auth])
async def get_runs(
    watch_id: uuid.UUID,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WatchRun)
        .where(WatchRun.watch_id == watch_id)
        .order_by(desc(WatchRun.started_at))
        .limit(limit)
    )
    return result.scalars().all()
