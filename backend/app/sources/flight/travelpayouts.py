from __future__ import annotations

from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from app.sources.base import FetchRequest, Offer, SourceCapability, SourceResult

if TYPE_CHECKING:
    from app.sources.http import RateLimitedClient

_BASE = "https://api.travelpayouts.com"
_GROUPED = f"{_BASE}/aviasales/v3/grouped_prices"
_PRICES = f"{_BASE}/aviasales/v3/prices_for_dates"


def _parse_dt(v: str | None) -> date | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _nights(dep: date | None, ret: date | None) -> int | None:
    if dep and ret:
        return (ret - dep).days
    return None


def _in_range(dep: date | None, ret: date | None, req: FetchRequest) -> bool:
    if dep is None:
        return False
    if not (req.depart_from <= dep <= req.depart_to):
        return False
    if req.nights_min is not None or req.nights_max is not None:
        n = _nights(dep, ret)
        if n is None:
            return False
        if req.nights_min is not None and n < req.nights_min:
            return False
        if req.nights_max is not None and n > req.nights_max:
            return False
    return True


def _grouped_to_offer(key: str, item: dict) -> Offer | None:
    dep = _parse_dt(item.get("departure_at") or key)
    ret = _parse_dt(item.get("return_at"))
    price = item.get("price")
    if price is None:
        return None
    airline = item.get("airline", "")
    fn = item.get("flight_number", "")
    ext_id = f"tp_g_{item.get('origin', '')}{item.get('destination', '')}_{key}_{airline}{fn}"
    return Offer(
        source="travelpayouts",
        external_id=ext_id,
        kind="flight",
        price_krw=int(price),
        price_original=float(price),
        currency_original="KRW",
        depart_date=dep,
        return_date=ret,
        carrier=airline or None,
        deep_link=item.get("link"),
        raw=item,
        collected_at=datetime.now(tz=timezone.utc),
        freshness="cached",
        cache_age_days=None,
        observed_at=None,
    )


def _prices_to_offer(item: dict) -> Offer | None:
    dep = _parse_dt(item.get("departure_at"))
    ret = _parse_dt(item.get("return_at"))
    price = item.get("price")
    if price is None or dep is None:
        return None
    airline = item.get("airline", "")
    fn = item.get("flight_number", "")
    dep_s = dep.isoformat() if dep else ""
    ret_s = ret.isoformat() if ret else ""
    ext_id = f"tp_p_{item.get('origin', '')}{item.get('destination', '')}_{dep_s}_{ret_s}_{airline}{fn}"
    return Offer(
        source="travelpayouts",
        external_id=ext_id,
        kind="flight",
        price_krw=int(price),
        price_original=float(price),
        currency_original="KRW",
        depart_date=dep,
        return_date=ret,
        carrier=airline or None,
        deep_link=item.get("link"),
        raw=item,
        collected_at=datetime.now(tz=timezone.utc),
        freshness="cached",
        cache_age_days=None,
        observed_at=None,
    )


class TravelpayoutsAdapter:
    name = "travelpayouts"
    kind = "flight"
    capability = SourceCapability(
        role="scan",
        date_range_native=True,
        max_span_days=31,
        trip_length_filter=False,
        cost_per_call=0,
        freshness="cached",
        max_cache_age_days=7,
    )

    def __init__(self, token: str, client: RateLimitedClient) -> None:
        self._token = token
        self._client = client

    def _headers(self) -> dict[str, str]:
        return {
            "X-Access-Token": self._token,
            "Accept": "application/json",
            "User-Agent": "TripPick/0.1",
        }

    async def health(self) -> bool:
        try:
            resp = await self._client.get(
                _GROUPED,
                headers=self._headers(),
                params={
                    "origin": "ICN",
                    "destination": "FUK",
                    "departure_at": "2026-10",
                    "currency": "krw",
                    "group_by": "departure_at",
                },
            )
            return resp.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    async def fetch(self, req: FetchRequest) -> SourceResult:
        try:
            month = req.depart_from.strftime("%Y-%m")
            ret_month = req.depart_to.strftime("%Y-%m")

            grouped_resp = await self._client.get(
                _GROUPED,
                headers=self._headers(),
                params={
                    "origin": req.origin,
                    "destination": req.destination,
                    "departure_at": month,
                    "return_at": ret_month,
                    "currency": "krw",
                    "direct": "false",
                    "group_by": "departure_at",
                },
            )
            grouped_resp.raise_for_status()

            prices_resp = await self._client.get(
                _PRICES,
                headers=self._headers(),
                params={
                    "origin": req.origin,
                    "destination": req.destination,
                    "departure_at": month,
                    "return_at": ret_month,
                    "currency": "krw",
                    "sorting": "price",
                    "direct": "false",
                    "one_way": "false",
                    "limit": 1000,
                    "page": 1,
                },
            )
            prices_resp.raise_for_status()

            grouped_data: dict = grouped_resp.json().get("data") or {}
            prices_data: list = prices_resp.json().get("data") or []

            offers_by_id: dict[str, Offer] = {}

            for key, item in grouped_data.items():
                if not isinstance(item, dict):
                    continue
                dep = _parse_dt(item.get("departure_at") or key)
                ret = _parse_dt(item.get("return_at"))
                if not _in_range(dep, ret, req):
                    continue
                o = _grouped_to_offer(key, item)
                if o:
                    offers_by_id[o.external_id] = o

            for item in prices_data:
                if not isinstance(item, dict):
                    continue
                dep = _parse_dt(item.get("departure_at"))
                ret = _parse_dt(item.get("return_at"))
                if not _in_range(dep, ret, req):
                    continue
                o = _prices_to_offer(item)
                if o and o.external_id not in offers_by_id:
                    offers_by_id[o.external_id] = o

            return SourceResult(ok=True, offers=list(offers_by_id.values()))

        except Exception as e:  # noqa: BLE001
            return SourceResult(ok=False, error=str(e))
