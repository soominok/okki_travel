from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

from app.sources.events.base import AirlineEventData, EventAdapter, url_to_external_id

_BASE = "https://www.airbusan.com"


class AirBusanAdapter(EventAdapter):
    source = "airbusan"
    base_url = f"{_BASE}/ko/flyNEvent/"

    @classmethod
    def _parse_html(cls, html: str) -> list[AirlineEventData]:
        soup = BeautifulSoup(html, "lxml")
        events: list[AirlineEventData] = []
        for item in soup.select(".event-item"):
            a = item.select_one("a[href]")
            if not a:
                continue
            title_el = a.select_one(".event-title") or a
            title = title_el.get_text(strip=True)
            href = a["href"]
            url = href if href.startswith("http") else f"{_BASE}{href}"
            # external_id: eventId 파라미터 추출 시도
            m = re.search(r"eventId=([A-Za-z0-9_-]+)", href)
            ext_id = m.group(1) if m else url_to_external_id(url)
            # 기간 파싱
            period_el = item.select_one(".event-period")
            period_text = period_el.get_text(strip=True) if period_el else ""
            valid_from, valid_to = _parse_period(period_text)
            events.append(
                AirlineEventData(
                    source=cls.source,
                    external_id=ext_id,
                    title=title,
                    url=url,
                    valid_from=valid_from,
                    valid_to=valid_to,
                )
            )
        return events


def _parse_period(text: str) -> tuple[date | None, date | None]:
    """'2026.09.15 ~ 2026.09.30' 형태 파싱."""
    dates = re.findall(r"(\d{4})[./](\d{2})[./](\d{2})", text)
    if len(dates) >= 2:
        return (_to_date(*dates[0]), _to_date(*dates[1]))
    if len(dates) == 1:
        return (None, _to_date(*dates[0]))
    return (None, None)


def _to_date(y: str, m: str, d: str) -> date:
    return date(int(y), int(m), int(d))
