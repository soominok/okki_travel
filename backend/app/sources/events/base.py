"""EventAdapter 추상 기반 클래스."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

import structlog

from app.sources.http import RateLimitedClient
from app.sources.policy import CrawlPolicy

log = structlog.get_logger()


@dataclass
class AirlineEventData:
    source: str
    external_id: str
    title: str
    url: str
    origin: str | None = None
    destination: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    discount_info: str | None = None


def url_to_external_id(url: str) -> str:
    """URL에서 이벤트 번호를 추출 못 할 때 SHA256 앞 16자 사용."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


class EventAdapter(ABC):
    source: str  # 서브클래스에서 선언
    base_url: str  # 이벤트 목록 URL

    def __init__(self, client: RateLimitedClient | None = None) -> None:
        self._client = client or RateLimitedClient(min_interval_sec=2.0)

    async def fetch_events(self) -> list[AirlineEventData]:
        """policy.py 게이트 → HTTP → 파싱. 예외는 빈 리스트로 흡수."""
        from urllib.parse import urlparse

        try:
            CrawlPolicy.require_enabled()
        except RuntimeError:
            log.warning("event_adapter.crawl_disabled", source=self.source)
            return []
        domain = urlparse(self.base_url).netloc
        if not CrawlPolicy.check_allowed(domain):
            log.warning("event_adapter.domain_not_allowed", source=self.source, domain=domain)
            return []
        try:
            resp = await self._client.get(
                self.base_url,
                headers={"User-Agent": "TripPickBot/1.0 (+https://github.com/soominok/trip_pick)"},
            )
            resp.raise_for_status()
            return self._parse_html(resp.text)
        except Exception:
            log.exception("event_adapter.fetch_failed", source=self.source)
            return []

    @classmethod
    @abstractmethod
    def _parse_html(cls, html: str) -> list[AirlineEventData]:
        """HTML 문자열 → AirlineEventData 리스트. 예외 없이 빈 리스트 반환 가능."""
        ...
