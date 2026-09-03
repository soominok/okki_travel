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


def _grouped_to_offer(key: str, item: dict, currency: str) -> Offer | None:
    dep = _parse_dt(item.get("departure_at") or key)
    ret = _parse_dt(item.get("return_at"))
    price = item.get("price")
    if price is None:
        return None
    airline = item.get("airline", "")
    fn = item.get("flight_number", "")
    dep_s = dep.isoformat() if dep else key
    # Mod 6: ext_id includes return_date when available
    ret_s = f"_{ret.isoformat()}" if ret else ""
    ext_id = f"tp_g_{item.get('origin', '')}{item.get('destination', '')}_{dep_s}{ret_s}_{airline}{fn}"
    return Offer(
        source="travelpayouts",
        external_id=ext_id,
        kind="flight",
        price_krw=int(price),
        price_original=float(price),
        currency_original=currency,
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


def _prices_to_offer(item: dict, currency: str) -> Offer | None:
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
        currency_original=currency,
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
        # Mod 2: 달 경계 유효성 검사 — 어댑터는 1회 호출에 1개월만 처리한다
        if (
            req.depart_from.year != req.depart_to.year
            or req.depart_from.month != req.depart_to.month
        ):
            return SourceResult(
                ok=False,
                error=(
                    "TravelpayoutsAdapter requires depart_from and depart_to in the same "
                    f"calendar month; got {req.depart_from} – {req.depart_to}"
                ),
            )

        month = req.depart_from.strftime("%Y-%m")
        offers_by_id: dict[str, Offer] = {}

        # grouped_prices — 실패 시 전체 ok=False (Mod 4)
        try:
            grouped_resp = await self._client.get(
                _GROUPED,
                headers=self._headers(),
                params={
                    "origin": req.origin,
                    "destination": req.destination,
                    "departure_at": month,
                    # Mod 3: return_at 제거 — 귀국일 필터가 다음 달로 넘어가는 항공권을 자른다
                    "currency": req.currency.lower(),  # Mod 1
                    "direct": "false",
                    "group_by": "departure_at",
                },
            )
            grouped_resp.raise_for_status()

            grouped_body = grouped_resp.json()
            currency = grouped_body.get("currency", "krw").upper()  # Mod 1

            # Mod 1: KRW 외 통화 거부 — 환율 변환 없이 price_krw에 넣으면 숫자가 뒤섞인다
            if currency != "KRW":
                return SourceResult(
                    ok=False,
                    error=f"Travelpayouts returned non-KRW currency: {currency}",
                )

            for key, item in (grouped_body.get("data") or {}).items():
                if not isinstance(item, dict):
                    continue
                dep = _parse_dt(item.get("departure_at") or key)
                ret = _parse_dt(item.get("return_at"))
                if not _in_range(dep, ret, req):
                    continue
                try:  # Mod 5: 행 단위 파싱 실패 격리
                    o = _grouped_to_offer(key, item, currency)
                    if o:
                        offers_by_id[o.external_id] = o
                except Exception:  # noqa: BLE001
                    continue

        except Exception as e:  # noqa: BLE001
            return SourceResult(ok=False, error=str(e))

        # prices_for_dates — 실패해도 grouped 결과는 반환한다 (Mod 4)
        try:
            prices_resp = await self._client.get(
                _PRICES,
                headers=self._headers(),
                params={
                    "origin": req.origin,
                    "destination": req.destination,
                    "departure_at": month,
                    "return_at": req.depart_to.strftime("%Y-%m"),
                    "currency": req.currency.lower(),  # Mod 1
                    "sorting": "price",
                    "direct": "false",
                    "one_way": "false",
                    "limit": 1000,
                    "page": 1,
                },
            )
            prices_resp.raise_for_status()

            prices_body = prices_resp.json()
            prices_currency = prices_body.get("currency", "krw").upper()
            if prices_currency != "KRW":
                pass  # 비-KRW prices_for_dates: 이 엔드포인트 결과만 건너뜀

            for item in (prices_body.get("data") or [] if prices_currency == "KRW" else []):
                if not isinstance(item, dict):
                    continue
                dep = _parse_dt(item.get("departure_at"))
                ret = _parse_dt(item.get("return_at"))
                if not _in_range(dep, ret, req):
                    continue
                try:  # Mod 5: 행 단위 파싱 실패 격리
                    o = _prices_to_offer(item, prices_currency)
                    if o and o.external_id not in offers_by_id:
                        offers_by_id[o.external_id] = o
                except Exception:  # noqa: BLE001
                    continue

        except Exception:  # noqa: BLE001
            pass  # 보완 엔드포인트 실패는 치명적이지 않다

        return SourceResult(ok=True, offers=list(offers_by_id.values()))
