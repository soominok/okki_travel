from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

from app.sources.events.base import AirlineEventData, EventAdapter, url_to_external_id

_BASE = "https://www.twayair.com"


class TwayAdapter(EventAdapter):
    source = "tway"
    base_url = f"{_BASE}/app/promotion/event/being"

    @classmethod
    def _parse_html(cls, html: str) -> list[AirlineEventData]:
        soup = BeautifulSoup(html, "lxml")
        events: list[AirlineEventData] = []
        for card in soup.select(".event-card"):
            a = card.select_one("a[href]")
            if not a:
                continue
            name_el = a.select_one(".event-name") or a
            title = name_el.get_text(strip=True)
            href = a["href"]
            url = href if href.startswith("http") else f"{_BASE}{href}"
            m = re.search(r"eventId=([A-Za-z0-9_-]+)", href)
            ext_id = m.group(1) if m else url_to_external_id(url)
            period_el = card.select_one(".period")
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
    dates = re.findall(r"(\d{4})[./](\d{2})[./](\d{2})", text)
    if len(dates) >= 2:
        return (
            date(int(dates[0][0]), int(dates[0][1]), int(dates[0][2])),
            date(int(dates[1][0]), int(dates[1][1]), int(dates[1][2])),
        )
    if len(dates) == 1:
        return (None, date(int(dates[0][0]), int(dates[0][1]), int(dates[0][2])))
    return (None, None)
