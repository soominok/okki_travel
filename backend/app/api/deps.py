"""FastAPI 의존성."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import SessionLocal

_bearer = HTTPBearer()


def require_token(
    cred: HTTPAuthorizationCredentials = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> None:
    if cred.credentials != settings.app_api_token.get_secret_value():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid token")


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
