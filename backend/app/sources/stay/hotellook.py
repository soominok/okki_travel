from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from app.sources.base import FetchRequest, Offer, SourceCapability, SourceResult

if TYPE_CHECKING:
    from app.sources.http import RateLimitedClient

HL_CACHE_URL = "https://engine.hotellook.com/api/v2/cache.json"


class HotellookAdapter:
    name = "hotellook"
    kind = "stay"
    capability = SourceCapability(
        role="scan",
        date_range_native=False,
        max_span_days=1,
        trip_length_filter=False,
        cost_per_call=0,
        freshness="cached",
        max_cache_age_days=7,
    )

    def __init__(self, token: str, client: RateLimitedClient) -> None:
        self._token = token
        self._client = client

    async def health(self) -> bool:
        return bool(self._token)

    async def fetch(self, req: FetchRequest) -> SourceResult:
        if req.currency.upper() != "KRW":
            return SourceResult(
                ok=False, error=f"HotellookAdapter only supports KRW; got {req.currency.upper()}"
            )
        check_in = req.depart_from
        if req.nights_min is not None:
            nights = req.nights_min
        else:
            nights = (req.depart_to - req.depart_from).days
        check_out = check_in + timedelta(days=max(nights, 1))

        try:
            resp = await self._client.get(
                HL_CACHE_URL,
                headers={"User-Agent": "TripPick/0.1"},
                params={
                    "location": req.destination,
                    "checkIn": check_in.isoformat(),
                    "checkOut": check_out.isoformat(),
                    "currency": req.currency.lower(),
                    "token": self._token,
                    "limit": 100,
                    "adults": req.adults,
                },
            )
            resp.raise_for_status()

            currency = req.currency.upper()

            data = resp.json()
            if not isinstance(data, list):
                return SourceResult(ok=False, error=f"unexpected response shape: {type(data)}")

            offers: list[Offer] = []
            now = datetime.now(tz=UTC)
            for hotel in data:
                price = hotel.get("priceFrom")
                hotel_id = hotel.get("hotelId")
                if price is None or hotel_id is None:
                    continue
                ext_id = f"hl_{hotel_id}_{check_in.isoformat()}_{check_out.isoformat()}"
                offers.append(
                    Offer(
                        source="hotellook",
                        external_id=ext_id,
                        kind="stay",
                        price_krw=int(price),
                        price_original=float(price),
                        currency_original=currency,
                        depart_date=check_in,
                        return_date=check_out,
                        carrier=None,
                        deep_link=hotel.get("deeplink"),
                        raw=hotel,
                        collected_at=now,
                        freshness="cached",
                        cache_age_days=None,
                        observed_at=None,
                    )
                )

            return SourceResult(ok=True, offers=offers)

        except Exception as e:  # noqa: BLE001
            return SourceResult(ok=False, error=str(e))
