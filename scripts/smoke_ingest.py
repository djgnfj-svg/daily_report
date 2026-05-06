"""실제 외부 API를 호출해서 백필/정적데이터 수집 경로를 점검한다.

AAPL 1종목으로 yfinance, EDGAR, Supabase까지 진짜 한 번 다녀온다.
단위 테스트(mock)와 달리 환경/네트워크/키 문제까지 잡아낸다.

실행:
    apps/agent/.venv/Scripts/python.exe -m scripts.smoke_ingest
옵션:
    --no-db   : Supabase upsert 건너뛰기 (yfinance/EDGAR 응답만 확인)
    --ticker  : 종목 변경 (기본 AAPL)
"""
from __future__ import annotations

import argparse
import logging
import sys
import traceback
from datetime import date, timedelta

from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("smoke")

PASS = "[PASS]"
FAIL = "[FAIL]"
SKIP = "[SKIP]"


def _step(name: str, fn):
    print(f"\n--- {name} ---")
    try:
        result = fn()
        print(f"{PASS} {name}")
        return result
    except Exception as e:
        print(f"{FAIL} {name}: {type(e).__name__}: {e}")
        traceback.print_exc()
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", default="AAPL")
    ap.add_argument("--no-db", action="store_true")
    args = ap.parse_args()

    load_dotenv()

    today = date.today()
    ticker = args.ticker
    failed: list[str] = []

    # 1. NYSE calendar
    def _calendar():
        from morningbrief.data.calendar import is_trading_day, last_trading_day
        td = is_trading_day(today)
        ltd = last_trading_day(today)
        print(f"  today={today} is_trading_day={td}, last_trading_day={ltd}")
        assert isinstance(ltd, date)
        return ltd

    last_td = _step("NYSE calendar", _calendar)
    if last_td is None:
        failed.append("calendar")

    # 2. yfinance prices (5 days)
    def _yf():
        from morningbrief.data.yf import fetch_prices
        start = today - timedelta(days=10)
        end = today + timedelta(days=1)
        rows = fetch_prices(ticker, start, end)
        assert rows, "fetch_prices returned empty"
        last = rows[-1]
        print(f"  rows={len(rows)} last={last.date} close={last.close} vol={last.volume:,}")
        return rows

    prices = _step(f"yfinance fetch_prices ({ticker})", _yf)
    if prices is None:
        failed.append("yfinance")

    # 3. EDGAR financials (latest 4)
    def _edgar():
        from morningbrief.data.edgar import fetch_quarterly_financials
        rows = fetch_quarterly_financials(ticker, n=4)
        assert rows, "EDGAR returned no rows"
        for r in rows:
            print(
                f"  {r.period} rev={r.revenue:,.0f} ni={r.net_income} "
                f"eps={r.eps} filed={r.filed_at}"
            )
        return rows

    fins = _step(f"EDGAR fetch_quarterly_financials ({ticker})", _edgar)
    if fins is None:
        failed.append("edgar")

    # 4. EDGAR 8-K filings (recent)
    def _filings():
        from morningbrief.data.edgar import fetch_recent_filings
        since = today - timedelta(days=180)
        rows = fetch_recent_filings(ticker, since=since, form_types=("8-K",))
        print(f"  8-K filings since {since}: {len(rows)}")
        for r in rows[:3]:
            print(f"    {r.filed_at.date()} {r.url}")
        return rows

    _step(f"EDGAR fetch_recent_filings ({ticker})", _filings)

    # 5. Supabase connectivity + upsert
    if args.no_db:
        print(f"\n--- Supabase upsert ---\n{SKIP} (--no-db)")
    else:
        def _db():
            from morningbrief.data.supabase_client import (
                get_client,
                upsert_prices,
                upsert_financials,
                get_latest_price_date,
                get_latest_filed_at,
            )
            client = get_client()
            print("  client connected")

            if prices:
                upsert_prices(client, prices)
                latest = get_latest_price_date(client, ticker)
                print(f"  prices upserted, latest={latest}")
            if fins:
                upsert_financials(client, fins)
                latest_f = get_latest_filed_at(client, ticker)
                print(f"  financials upserted, latest_filed={latest_f}")
            return True

        if _step("Supabase upsert (prices+financials)", _db) is None:
            failed.append("supabase")

    # Summary
    print("\n========== SUMMARY ==========")
    if failed:
        print(f"{FAIL} {len(failed)} step(s) failed: {', '.join(failed)}")
        sys.exit(1)
    print(f"{PASS} all steps passed")


if __name__ == "__main__":
    main()
