"""DB의 실제 가격 데이터로 indicators가 합리적인 값을 내는지 점검.

각 종목별로 MA20/60/200, RSI14, 52w 위치, 거래량비를 계산해
범위 sanity check + 표로 출력.

실행:
    apps/agent/.venv/Scripts/python.exe -m scripts.smoke_indicators
"""
from __future__ import annotations

import logging
import sys
from datetime import date

from dotenv import load_dotenv

logging.basicConfig(level=logging.WARNING)


def main():
    load_dotenv()

    from morningbrief.data.supabase_client import get_client, load_recent_prices
    from morningbrief.data.tickers import TICKERS
    from morningbrief.indicators import compute_indicators

    client = get_client()
    today = date.today()
    failed: list[str] = []

    print(f"{'TICKER':<7} {'N':>4} {'last':>10} {'MA20':>9} {'MA60':>9} "
          f"{'MA200':>9} {'RSI14':>6} {'52w%':>6} {'volR':>6}")
    print("-" * 80)

    for t in TICKERS:
        prices = load_recent_prices(client, t, days=365, as_of=today)
        if not prices:
            print(f"{t:<7} (no data)")
            failed.append(t)
            continue

        ind = compute_indicators(prices)
        last = prices[-1]
        last_close = float(last["close"])

        def fmt(v, w=9, p=2):
            return f"{v:>{w}.{p}f}" if v is not None else " " * (w - 1) + "-"

        print(
            f"{t:<7} {len(prices):>4} {last_close:>10.2f} "
            f"{fmt(ind['ma20'])} {fmt(ind['ma60'])} {fmt(ind['ma200'])} "
            f"{fmt(ind['rsi14'], 6)} {fmt(ind['pos_52w_pct'], 6)} "
            f"{fmt(ind['volume_ratio_20d'], 6)}"
        )

        # sanity checks
        if ind["rsi14"] is not None and not (0 <= ind["rsi14"] <= 100):
            print(f"  [FAIL] {t} RSI out of range")
            failed.append(t)
        if ind["pos_52w_pct"] is not None and not (0 <= ind["pos_52w_pct"] <= 100):
            print(f"  [FAIL] {t} 52w position out of range")
            failed.append(t)
        if ind["ma20"] is None and len(prices) >= 20:
            print(f"  [FAIL] {t} MA20 None despite {len(prices)} rows")
            failed.append(t)

    print()
    if failed:
        print(f"[FAIL] issues: {failed}")
        sys.exit(1)
    print("[PASS] all tickers sane")


if __name__ == "__main__":
    main()
