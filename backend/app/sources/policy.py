from __future__ import annotations

import os


class CrawlPolicy:
    """크롤러 활성화 게이트.

    공식 API 어댑터는 이 클래스를 사용하지 않는다.
    Plan 4+ 크롤 어댑터는 fetch() 진입 시 require_enabled()를 호출해야 한다.
    """

    @staticmethod
    def require_enabled() -> None:
        """CRAWL_ENABLED=false 면 RuntimeError. 크롤 어댑터 시작 시 호출."""
        if os.environ.get("CRAWL_ENABLED", "false").lower() != "true":
            raise RuntimeError(
                "CRAWL_ENABLED is false — crawl adapters are disabled. "
                "Set CRAWL_ENABLED=true in .env to enable."
            )

    @staticmethod
    def check_allowed(domain: str, path: str = "/") -> bool:
        """robots.txt 파싱은 Plan 4+에서 구현. 지금은 항상 False."""
        return False
