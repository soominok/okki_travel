from app.utils.deep_links import build_deep_links


def test_roundtrip_returns_four_keys():
    links = build_deep_links("ICN", "NRT", "2026-10-01", "2026-10-05")
    assert set(links.keys()) == {"skyscanner", "google", "naver", "tripdotcom"}


def test_oneway_returns_four_keys():
    links = build_deep_links("ICN", "NRT", "2026-10-01", None)
    assert set(links.keys()) == {"skyscanner", "google", "naver", "tripdotcom"}


def test_skyscanner_url_format_roundtrip():
    links = build_deep_links("ICN", "NRT", "2026-10-01", "2026-10-05")
    assert "ICN" in links["skyscanner"]
    assert "NRT" in links["skyscanner"]
    assert "261001" in links["skyscanner"]  # YYMMDD
    assert "261005" in links["skyscanner"]


def test_skyscanner_url_format_oneway():
    links = build_deep_links("ICN", "NRT", "2026-10-01", None)
    # 편도: 귀국 날짜 없이 URL이 만들어져야 함
    assert "skyscanner" in links["skyscanner"]
    assert "NRT" in links["skyscanner"]
    # 이중 슬래시 없어야 함
    assert "//" not in links["skyscanner"].replace("https://", "")
    assert links["skyscanner"].endswith("?adults=1&currency=KRW")


def test_naver_oneway_no_return_param():
    links = build_deep_links("ICN", "NRT", "2026-10-01", None)
    assert "returnDate" not in links["naver"]


def test_naver_roundtrip_has_return_param():
    links = build_deep_links("ICN", "NRT", "2026-10-01", "2026-10-05")
    assert "returnDate" in links["naver"]


def test_tripdotcom_oneway():
    links = build_deep_links("ICN", "NRT", "2026-10-01", None)
    assert "OW" in links["tripdotcom"]


def test_tripdotcom_roundtrip():
    links = build_deep_links("ICN", "NRT", "2026-10-01", "2026-10-05")
    assert "RT" in links["tripdotcom"]
