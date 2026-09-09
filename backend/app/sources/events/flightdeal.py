from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

from app.sources.events.base import AirlineEventData, EventAdapter, url_to_external_id

_BASE = "https://flightdeal.kr"


class FlightDealAdapter(EventAdapter):
    source = "flightdeal"
    base_url = _BASE

    @classmethod
    def _parse_html(cls, html: str) -> list[AirlineEventData]:
        soup = BeautifulSoup(html, "lxml")
        events: list[AirlineEventData] = []
        for item in soup.select(".deal-item"):
            a = item.select_one("a[href]")
            if not a:
                continue
            title_el = item.select_one(".deal-title, h2") or a
            title = title_el.get_text(strip=True)
            href = a["href"]
            url = href if href.startswith("http") else f"{_BASE}{href}"
            # external_id: deal item의 id 속성 또는 URL 해시
            item_id = item.get("id", "")
            if item_id.startswith("deal-"):
                ext_id = item_id.replace("deal-", "")
            else:
                ext_id = url_to_external_id(url)
            date_el = item.select_one(".valid-date, .period")
            _, valid_to = _parse_period(date_el.get_text(strip=True) if date_el else "")
            events.append(
                AirlineEventData(
                    source=cls.source,
                    external_id=ext_id,
                    title=title,
                    url=url,
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
