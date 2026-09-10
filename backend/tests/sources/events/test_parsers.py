"""EventAdapter 파서 단위 테스트 — 실제 HTTP 없음, fixture HTML만 사용."""

from datetime import date
from pathlib import Path

from app.sources.events.airbusan import AirBusanAdapter
from app.sources.events.tway import TwayAdapter
from app.sources.events.jejuair import JejuAirAdapter
from app.sources.events.koreanair import KoreanAirAdapter
from app.sources.events.flightdeal import FlightDealAdapter

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "events"


def _html(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class TestAirBusanParser:
    def test_returns_list(self):
        events = AirBusanAdapter._parse_html(_html("airbusan.html"))
        assert isinstance(events, list)

    def test_finds_events(self):
        events = AirBusanAdapter._parse_html(_html("airbusan.html"))
        assert len(events) >= 1

    def test_event_has_required_fields(self):
        events = AirBusanAdapter._parse_html(_html("airbusan.html"))
        e = events[0]
        assert e.source == "airbusan"
        assert e.external_id
        assert e.title
        assert e.url
        assert "airbusan" in e.url or e.url.startswith("http")

    def test_event_has_valid_to(self):
        events = AirBusanAdapter._parse_html(_html("airbusan.html"))
        assert events[0].valid_to == date(2026, 9, 30)

    def test_airbusan_empty_html(self):
        result = AirBusanAdapter._parse_html("<html><body></body></html>")
        assert result == []


class TestTwayParser:
    def test_returns_list(self):
        events = TwayAdapter._parse_html(_html("tway.html"))
        assert len(events) >= 1

    def test_source_is_tway(self):
        events = TwayAdapter._parse_html(_html("tway.html"))
        assert all(e.source == "tway" for e in events)

    def test_tway_empty_html(self):
        result = TwayAdapter._parse_html("<html><body></body></html>")
        assert result == []


class TestJejuAirParser:
    def test_returns_list(self):
        events = JejuAirAdapter._parse_html(_html("jejuair.html"))
        assert len(events) >= 1

    def test_source_is_jejuair(self):
        events = JejuAirAdapter._parse_html(_html("jejuair.html"))
        assert all(e.source == "jejuair" for e in events)

    def test_jejuair_empty_html(self):
        result = JejuAirAdapter._parse_html("<html><body></body></html>")
        assert result == []


class TestKoreanAirParser:
    def test_returns_list(self):
        events = KoreanAirAdapter._parse_html(_html("koreanair.html"))
        assert len(events) >= 1

    def test_source_is_koreanair(self):
        events = KoreanAirAdapter._parse_html(_html("koreanair.html"))
        assert all(e.source == "koreanair" for e in events)

    def test_koreanair_empty_html(self):
        result = KoreanAirAdapter._parse_html("<html><body></body></html>")
        assert result == []


class TestFlightDealParser:
    def test_returns_list(self):
        events = FlightDealAdapter._parse_html(_html("flightdeal.html"))
        assert len(events) >= 1

    def test_source_is_flightdeal(self):
        events = FlightDealAdapter._parse_html(_html("flightdeal.html"))
        assert all(e.source == "flightdeal" for e in events)

    def test_flightdeal_empty_html(self):
        result = FlightDealAdapter._parse_html("<html><body></body></html>")
        assert result == []
