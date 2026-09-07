from __future__ import annotations

from app.sources.base import SourceAdapter


class SourceRegistry:
    def __init__(self) -> None:
        self._adapters: list[SourceAdapter] = []

    def register(self, adapter: SourceAdapter) -> None:
        self._adapters.append(adapter)

    def get(self, kind: str, role: str) -> list[SourceAdapter]:
        return [a for a in self._adapters if a.kind == kind and a.capability.role == role]

    def get_by_name(self, name: str) -> SourceAdapter | None:
        return next((a for a in self._adapters if a.name == name), None)

    def all(self) -> list[SourceAdapter]:
        return list(self._adapters)


def build_registry(settings) -> SourceRegistry:
    """API 키가 있는 어댑터만 등록한다."""
    from app.sources.flight.brightdata import BrightDataAdapter
    from app.sources.flight.travelpayouts import TravelpayoutsAdapter
    from app.sources.http import RateLimitedClient
    from app.sources.stay.hotellook import HotellookAdapter

    registry = SourceRegistry()
    client = RateLimitedClient(min_interval_sec=1.0)

    if settings.travelpayouts_token:
        tp_token = settings.travelpayouts_token.get_secret_value()
        registry.register(TravelpayoutsAdapter(token=tp_token, client=client))
        registry.register(HotellookAdapter(token=tp_token, client=client))

    if settings.brightdata_api_key:
        bd_key = settings.brightdata_api_key.get_secret_value()
        registry.register(BrightDataAdapter(api_key=bd_key, client=client))

    return registry
