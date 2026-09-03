from __future__ import annotations

import asyncio
import time

import httpx


class RateLimitedClient:
    """도메인별 최소 간격을 강제하는 httpx 래퍼.

    테스트에서는 respx.mock 컨텍스트 안에서 사용하면 httpx가 자동으로 목킹된다.
    """

    def __init__(self, min_interval_sec: float = 1.0, timeout: float = 30.0) -> None:
        self._min_interval = min_interval_sec
        self._timeout = timeout
        self._last_call: dict[str, float] = {}

    async def _wait(self, domain: str) -> None:
        last = self._last_call.get(domain, 0.0)
        gap = self._min_interval - (time.monotonic() - last)
        if gap > 0:
            await asyncio.sleep(gap)
        self._last_call[domain] = time.monotonic()

    async def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict | None = None,
    ) -> httpx.Response:
        domain = str(httpx.URL(url).host)
        await self._wait(domain)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            return await client.get(url, headers=headers or {}, params=params)

    async def post(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        json: dict | None = None,
    ) -> httpx.Response:
        domain = str(httpx.URL(url).host)
        await self._wait(domain)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            return await client.post(url, headers=headers or {}, json=json)
