"""LLM 분석 1종목 스모크. fundamental + risk 에이전트만 실제 호출.

비용: gpt-4o-mini 2회 호출 (~$0.001). debate/scoring은 별도.

실행:
    apps/agent/.venv/Scripts/python.exe -m scripts.smoke_llm
옵션:
    --ticker AAPL  : 다른 종목
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from dotenv import load_dotenv

logging.basicConfig(level=logging.WARNING)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", default="AAPL")
    args = ap.parse_args()
    ticker = args.ticker

    load_dotenv()

    from morningbrief.agents.fundamental import analyze_fundamental
    from morningbrief.agents.risk import analyze_risk
    from morningbrief.data.supabase_client import (
        get_client,
        load_latest_financials,
        load_recent_prices,
    )
    from morningbrief.indicators import compute_indicators
    from morningbrief.llm.base import OpenAILLM

    client = get_client()
    today = date.today()

    prices = load_recent_prices(client, ticker, days=365, as_of=today)
    fins = load_latest_financials(client, ticker, n=4)
    if not prices or not fins:
        print(f"[FAIL] missing data: prices={len(prices)} financials={len(fins)}")
        sys.exit(1)
    indicators = compute_indicators(prices)
    last_close = float(prices[-1]["close"])

    print(f"--- {ticker} input ---")
    print(f"  N_prices={len(prices)} last_close={last_close} N_fins={len(fins)}")
    print(f"  indicators={indicators}")

    llm = OpenAILLM()

    print(f"\n--- fundamental (gpt-4o-mini) ---")
    f = analyze_fundamental(llm, ticker, fins, last_close, indicators)
    print(f"  score={f.score}")
    print(f"  summary={f.summary}")
    print(f"  key_metrics={f.key_metrics}")

    print(f"\n--- risk (gpt-4o-mini) ---")
    r = analyze_risk(llm, ticker, prices, indicators)
    print(f"  score={r.score}")
    print(f"  summary={r.summary}")
    print(f"  metrics={r.metrics}")

    # sanity
    fail = []
    if not (0 <= f.score <= 100):
        fail.append("fundamental score out of range")
    if not (0 <= r.score <= 100):
        fail.append("risk score out of range")
    if not f.summary:
        fail.append("fundamental summary empty")
    if not r.summary:
        fail.append("risk summary empty")

    print()
    if fail:
        for x in fail:
            print(f"[FAIL] {x}")
        sys.exit(1)
    print("[PASS] LLM analysis sane")


if __name__ == "__main__":
    main()
