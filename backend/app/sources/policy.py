from __future__ import annotations

from app.config import get_settings

_ALLOWED_EVENT_DOMAINS = frozenset(
    {
        "www.airbusan.com",
        "www.twayair.com",
        "www.jejuair.net",
        "www.koreanair.com",
        "flightdeal.kr",
    }
)


class CrawlPolicy:
    """크롤러 활성화 게이트.

    공식 API 어댑터는 이 클래스를 사용하지 않는다.
    Plan 4+ 크롤 어댑터는 fetch() 진입 시 require_enabled()를 호출해야 한다.
    """

    @staticmethod
    def require_enabled() -> None:
        """crawl_enabled=False 면 RuntimeError. 크롤 어댑터 시작 시 호출."""
        if not get_settings().crawl_enabled:
            raise RuntimeError(
                "CRAWL_ENABLED is false — crawl adapters are disabled. "
                "Set CRAWL_ENABLED=true in .env to enable."
            )

    @staticmethod
    def check_allowed(domain: str, path: str = "/") -> bool:
        """하드코딩된 이벤트 도메인 허용목록. robots.txt 실제 확인 미완료 (crawl_enabled=False로 비활성)."""
        return domain in _ALLOWED_EVENT_DOMAINS
