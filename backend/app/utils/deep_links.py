"""각 OTA 사이트에 사전 입력된 검색 URL을 생성하는 순수 함수."""

from __future__ import annotations


def build_deep_links(
    origin: str,
    destination: str,
    dep_date: str,          # "YYYY-MM-DD"
    ret_date: str | None,   # None이면 편도
) -> dict[str, str]:
    dep_yy = dep_date[2:4]
    dep_mm = dep_date[5:7]
    dep_dd = dep_date[8:10]
    dep_yymmdd = f"{dep_yy}{dep_mm}{dep_dd}"
    dep_nodash = dep_date.replace("-", "")

    if ret_date:
        ret_yy = ret_date[2:4]
        ret_mm = ret_date[5:7]
        ret_dd = ret_date[8:10]
        ret_yymmdd = f"{ret_yy}{ret_mm}{ret_dd}"
        ret_nodash = ret_date.replace("-", "")
    else:
        ret_yymmdd = ""
        ret_nodash = ""

    skyscanner = (
        f"https://www.skyscanner.co.kr/transport/flights/"
        f"{origin}/{destination}/"
        f"{dep_yymmdd}/"
        f"{ret_yymmdd if ret_date else ''}/"
        f"?adults=1&currency=KRW"
    )

    google = (
        f"https://www.google.com/travel/flights/search"
        f"?q=flights+from+{origin}+to+{destination}+on+{dep_date}"
    )

    naver = (
        f"https://flight.naver.com/flights/"
        f"{origin}-{destination}-{dep_nodash}/?adult=1"
        + (f"&returnDate={ret_nodash}" if ret_date else "")
    )

    tripdotcom = (
        f"https://kr.trip.com/flights/show"
        f"?dcity={origin}&acity={destination}"
        f"&ddate={dep_date}"
        + (f"&rdate={ret_date}" if ret_date else "")
        + f"&flightway={'RT' if ret_date else 'OW'}"
    )

    return {
        "skyscanner": skyscanner,
        "google": google,
        "naver": naver,
        "tripdotcom": tripdotcom,
    }
