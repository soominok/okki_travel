"""
Travelpayouts 유연 날짜 검색 가능성 스파이크.

목적: TripPick의 핵심 차별점인 "기간 범위 + 체류일수" 검색을
      Travelpayouts API로 **적은 호출 수**로 커버할 수 있는지 실제로 확인한다.

이게 안 되면 docs/03-DATA-SOURCES.md의 어댑터 설계를 되돌려야 하므로,
구현(P2) 전에 반드시 돌려본다.

의존성 없음 (표준 라이브러리만). 결과는 stdout + spikes/probe_result.json.

사용법:
    set TRAVELPAYOUTS_TOKEN=...        (PowerShell: $env:TRAVELPAYOUTS_TOKEN="...")
    python spikes/travelpayouts_probe.py
    python spikes/travelpayouts_probe.py --origin ICN --dest FUK --months 2026-11,2026-12
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date, datetime

BASE = "https://api.travelpayouts.com"
TIMEOUT = 30

# Windows 콘솔 기본 코드페이지(cp1252/cp949)로는 한글·이모지 출력이 깨진다.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

# 감시하려는 조건 (docs/01-PRD.md S1 시나리오)
WANT_NIGHTS_MIN = 2
WANT_NIGHTS_MAX = 3

calls_made = 0


def get(path: str, params: dict, token: str) -> dict:
    """API 호출. 토큰은 헤더로 보낸다 (URL 쿼리에 시크릿을 넣지 않는다)."""
    global calls_made
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    url = f"{BASE}{path}?{qs}"
    req = urllib.request.Request(url, headers={
        "X-Access-Token": token,
        "Accept": "application/json",
        "User-Agent": "TripPick-spike/0.1",
    })
    calls_made += 1
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        return {"_http_error": e.code, "_body": body}
    except Exception as e:  # noqa: BLE001 - 스파이크라 넓게 잡는다
        return {"_error": f"{type(e).__name__}: {e}"}


def parse_day(v) -> date | None:
    if not v or not isinstance(v, str):
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(v[:10])
        except ValueError:
            return None


def nights_of(item: dict) -> int | None:
    d, r = parse_day(item.get("departure_at")), parse_day(item.get("return_at"))
    if d and r:
        return (r - d).days
    return None


def show(title: str):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def probe_prices_for_dates(origin, dest, month, token) -> dict:
    """왕복 + 월 단위 범위로 조회했을 때 체류일수 분포가 어떻게 나오는가."""
    show(f"[A] prices_for_dates  {origin}->{dest}  {month} (왕복)")
    res = get("/aviasales/v3/prices_for_dates", {
        "origin": origin, "destination": dest,
        "departure_at": month, "return_at": month,
        "currency": "krw", "sorting": "price", "direct": "false",
        "one_way": "false", "limit": 1000, "page": 1,
    }, token)

    if "_http_error" in res or "_error" in res:
        print(f"  ❌ 실패: {res}")
        return {"ok": False, "detail": res}

    data = res.get("data") or []
    if not isinstance(data, list):
        print(f"  ⚠️ data가 리스트가 아님: {type(data)}  전체 키={list(res)}")
        return {"ok": False, "detail": "unexpected shape", "keys": list(res)}

    print(f"  결과 {len(data)}건")
    if not data:
        return {"ok": True, "count": 0, "matching": 0}

    print(f"  첫 항목 필드: {sorted(data[0].keys())}")

    dist = Counter()
    matching = []
    for it in data:
        n = nights_of(it)
        dist[n] += 1
        if n is not None and WANT_NIGHTS_MIN <= n <= WANT_NIGHTS_MAX:
            matching.append(it)

    print("\n  체류일수 분포:")
    for n, c in sorted(dist.items(), key=lambda x: (x[0] is None, x[0])):
        mark = " ←원하는 범위" if n is not None and WANT_NIGHTS_MIN <= n <= WANT_NIGHTS_MAX else ""
        print(f"    {str(n) + '박' if n is not None else 'return_at 없음':>12} : {c:4d}건{mark}")

    print(f"\n  ⇒ {WANT_NIGHTS_MIN}~{WANT_NIGHTS_MAX}박 조건에 맞는 결과: "
          f"{len(matching)}건 / {len(data)}건")

    if matching:
        cheapest = min(matching, key=lambda x: x.get("price", 1e18))
        print(f"  ⇒ 그중 최저가: {cheapest.get('price'):,}원  "
              f"{cheapest.get('departure_at', '')[:10]} ~ {cheapest.get('return_at', '')[:10]}  "
              f"{cheapest.get('airline')}")

    # 출발일 커버리지: 한 달 중 며칠에 대해 후보가 존재하는가
    days = {parse_day(i.get("departure_at")) for i in matching}
    days.discard(None)
    print(f"  ⇒ 후보가 존재하는 출발일 수: {len(days)}일")

    return {"ok": True, "count": len(data), "matching": len(matching),
            "distinct_departure_days": len(days),
            "nights_distribution": {str(k): v for k, v in dist.items()}}


def probe_grouped(origin, dest, month, token) -> dict:
    """grouped_prices가 날짜별 최저가를 1회 호출로 주는가."""
    show(f"[B] grouped_prices  {origin}->{dest}  {month}  group_by=departure_at")
    res = get("/aviasales/v3/grouped_prices", {
        "origin": origin, "destination": dest,
        "departure_at": month, "return_at": month,
        "currency": "krw", "direct": "false", "group_by": "departure_at",
    }, token)

    if "_http_error" in res or "_error" in res:
        print(f"  ❌ 실패: {res}")
        return {"ok": False, "detail": res}

    data = res.get("data")
    if not isinstance(data, dict):
        print(f"  ⚠️ data가 dict가 아님: {type(data)}  전체 키={list(res)}")
        return {"ok": False, "detail": "unexpected shape"}

    print(f"  그룹 {len(data)}개 (= 출발일 {len(data)}일치를 1회 호출로 획득)")
    sample_key = next(iter(data), None)
    if sample_key:
        print(f"  샘플 키: {sample_key}")
        print(f"  샘플 값: {json.dumps(data[sample_key], ensure_ascii=False)[:300]}")

    has_return = sum(1 for v in data.values()
                     if isinstance(v, dict) and v.get("return_at"))
    print(f"  ⇒ return_at 을 포함한 그룹: {has_return}/{len(data)}")
    print("     (0이면 체류일수 판정 불가 → 이 엔드포인트만으로는 왕복 유연검색 불가)")

    nights_ok = 0
    for v in data.values():
        if isinstance(v, dict):
            n = nights_of(v)
            if n is not None and WANT_NIGHTS_MIN <= n <= WANT_NIGHTS_MAX:
                nights_ok += 1
    print(f"  ⇒ {WANT_NIGHTS_MIN}~{WANT_NIGHTS_MAX}박에 해당하는 그룹: {nights_ok}")

    return {"ok": True, "groups": len(data), "with_return_at": has_return,
            "nights_in_range": nights_ok}


def verdict(a_results: list[dict], b_results: list[dict], months: list[str]) -> None:
    show("판정")

    total_match = sum(r.get("matching", 0) for r in a_results if r.get("ok"))
    total_days = sum(r.get("distinct_departure_days", 0) for r in a_results if r.get("ok"))
    b_usable = any(r.get("ok") and r.get("with_return_at", 0) > 0 for r in b_results)

    print(f"총 API 호출 수: {calls_made}  (조회 기간 {len(months)}개월)")
    print(f"A. prices_for_dates 로 얻은 {WANT_NIGHTS_MIN}~{WANT_NIGHTS_MAX}박 후보: {total_match}건")
    print(f"   후보가 존재하는 출발일: 총 {total_days}일")
    print(f"B. grouped_prices 가 왕복 체류일수 판정에 쓸 수 있는가: {'예' if b_usable else '아니오'}")

    print("\n결론:")
    if total_match == 0:
        print("  🔴 설계 변경 필요.")
        print("     월 단위 왕복 조회로는 원하는 체류일수 후보가 전혀 안 나온다.")
        print("     → docs/03 의 어댑터 설계를 다시 봐야 한다. 대안:")
        print("       (a) 출발일별로 개별 조회 (호출 수 급증 → 캐시·주기 재설계 필요)")
        print("       (b) MVP 범위를 '월 단위 최저가'로 축소하고 정밀 유연검색은 Phase 2")
        print("       (c) Amadeus flight-dates 를 주력 SCAN 소스로 승격")
    elif total_days < len(months) * 8:
        print("  🟠 부분적으로 가능하지만 커버리지가 얇다.")
        print(f"     한 달에 평균 {total_days / max(len(months), 1):.1f}일치 후보만 나온다.")
        print("     → 월당 여러 페이지를 긁거나, 목표가 근처 날짜만 Amadeus 로 보강하는")
        print("       2단계 수집(docs/03 §4)이 필수다. 설계는 유지 가능.")
    else:
        print("  🟢 설계대로 간다.")
        print(f"     월 1회 호출로 {WANT_NIGHTS_MIN}~{WANT_NIGHTS_MAX}박 후보가 충분히 나온다.")
        print(f"     3개월 범위 감시 = 약 {len(months)}회 호출. 6시간 주기로 충분히 감당된다.")

    print("\n다음 할 일: 이 출력을 그대로 Claude Code에 붙여넣고")
    print("            'docs/03 의 어댑터 설계를 이 결과에 맞게 고쳐줘' 라고 하면 된다.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--origin", default="ICN")
    ap.add_argument("--dest", default="FUK")
    ap.add_argument("--months", default="", help="쉼표 구분 YYYY-MM. 기본: 다음 3개월")
    args = ap.parse_args()

    token = os.environ.get("TRAVELPAYOUTS_TOKEN", "").strip()
    if not token:
        print("❌ TRAVELPAYOUTS_TOKEN 환경변수가 없다.")
        print("   https://www.travelpayouts.com 가입 후 대시보드에서 토큰을 받아라.")
        print('   PowerShell: $env:TRAVELPAYOUTS_TOKEN="여기에토큰"')
        return 2

    if args.months:
        months = [m.strip() for m in args.months.split(",") if m.strip()]
    else:
        today = date.today()
        months = []
        y, m = today.year, today.month
        for _ in range(3):
            m += 1
            if m > 12:
                m, y = 1, y + 1
            months.append(f"{y}-{m:02d}")

    print(f"조건: {args.origin} -> {args.dest} / {months} / "
          f"{WANT_NIGHTS_MIN}~{WANT_NIGHTS_MAX}박 왕복")

    a_results = [probe_prices_for_dates(args.origin, args.dest, mo, token) for mo in months]
    b_results = [probe_grouped(args.origin, args.dest, months[0], token)]

    verdict(a_results, b_results, months)

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "probe_result.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"origin": args.origin, "dest": args.dest, "months": months,
                   "calls": calls_made, "prices_for_dates": a_results,
                   "grouped_prices": b_results}, f, ensure_ascii=False, indent=2)
    print(f"\n원본 결과 저장: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
