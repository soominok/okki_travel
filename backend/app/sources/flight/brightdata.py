from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from app.sources.base import FetchRequest, Offer, SourceCapability, SourceResult

if TYPE_CHECKING:
    from app.sources.http import RateLimitedClient

# Bright Data SERP API — Google Flights 엔드포인트
# 대시보드 → API reference → Google Flights 에서 확인 필요 (미확인)
BD_SERP_URL = "https://api.brightdata.com/serp"


def _parse_date_str(v: str | None) -> date | None:
    """'YYYY-MM-DD HH:MM' 또는 'YYYY-MM-DD' 형태를 date로 파싱."""
    if not v:
        return None
    try:
        return datetime.strptime(v[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _flight_group_to_offer(group: dict) -> Offer | None:
    price = group.get("price")
    if price is None:
        return None

    flights = group.get("flights") or []
    returns = group.get("return_flights") or []

    dep_date = _parse_date_str(flights[0].get("departure_time") if flights else None)
    ret_date = _parse_date_str(returns[0].get("departure_time") if returns else None)

    airline = (flights[0].get("airline") or "") if flights else ""
    flight_no = (flights[0].get("flight_number") or "") if flights else ""

    dep_s = dep_date.isoformat() if dep_date else "unknown"
    ret_s = ret_date.isoformat() if ret_date else "unknown"
    ext_id = (
        f"bd_{dep_s}_{ret_s}_{airline.replace(' ', '')}_{flight_no.replace(' ', '')}"
    )

    now = datetime.now(tz=timezone.utc)
    return Offer(
        source="brightdata",
        external_id=ext_id,
        kind="flight",
        price_krw=int(price),
        price_original=float(price),
        currency_original="KRW",
        depart_date=dep_date,
        return_date=ret_date,
        carrier=airline or None,
        deep_link=None,
        raw=group,
        collected_at=now,
        freshness="live",
        cache_age_days=None,
        observed_at=now,
    )


class BrightDataAdapter:
    """Bright Data SERP API를 통해 Google Flights 가격을 VERIFY/SAMPLE 역할로 조회.

    cost_per_call=1 — 호출자(collector)가 예산을 선점한 뒤에만 이 어댑터를 호출해야 한다.
    어댑터 자체는 예산 선점을 하지 않는다 (CLAUDE.md §11).
    """

    name = "brightdata"
    kind = "flight"
    capability = SourceCapability(
        role="verify",
        date_range_native=False,
        max_span_days=1,
        trip_length_filter=False,
        cost_per_call=1,
        freshness="live",
        max_cache_age_days=None,
    )

    def __init__(self, api_key: str, client: RateLimitedClient) -> None:
        self._api_key = api_key
        self._client = client

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def health(self) -> bool:
        return bool(self._api_key)

    async def fetch(self, req: FetchRequest) -> SourceResult:
        # fan-out 금지: 단일 출발일(depart_from)만 처리한다. 기간 분할은 collector가 한다.
        return_date: date | None = None
        if req.nights_min is not None:
            return_date = req.depart_from + timedelta(days=req.nights_min)

        payload: dict = {
            "engine": "google_flights",
            "hl": "en",
            "gl": "kr",
            "departure_id": req.origin,
            "arrival_id": req.destination,
            "outbound_date": req.depart_from.isoformat(),
            "currency": req.currency,
        }
        if return_date is not None:
            payload["return_date"] = return_date.isoformat()
            payload["type"] = "1"  # round trip
        else:
            payload["type"] = "2"  # one way

        try:
            resp = await self._client.post(
                BD_SERP_URL,
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()

            body = resp.json()
            best = body.get("best_flights") or []
            other = body.get("other_flights") or []
            all_groups = best + other

            offers: list[Offer] = []
            seen: set[str] = set()
            for group in all_groups:
                try:
                    o = _flight_group_to_offer(group)
                    if o is not None and o.external_id not in seen:
                        offers.append(o)
                        seen.add(o.external_id)
                except Exception:  # noqa: BLE001
                    continue

            return SourceResult(ok=True, offers=offers, credits_used=1)

        except Exception as e:  # noqa: BLE001
            return SourceResult(ok=False, error=str(e))
