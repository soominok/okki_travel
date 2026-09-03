"""Watch CRUD 라우터."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_token
from app.models.watch import Watch
from app.schemas.watch import WatchCreate, WatchPatch, WatchRead

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
