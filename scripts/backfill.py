"""One-off seed: 90 days of prices + latest 4 quarters of financials.

Run from repo root with PYTHONPATH set to apps/agent/src:
    python -m scripts.backfill
"""
from __future__ import annotations

import logging
import sys
from datetime import date, timedelta

from dotenv import load_dotenv

from morningbrief.data.tickers import TICKERS
from morningbrief.data.yf import fetch_prices
from morningbrief.data.edgar import fetch_quarterly_financials
from morningbrief.data.supabase_client import (
    get_client,
    upsert_prices,
    upsert_financials,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill")


def main(today: date | None = None) -> None:
    today = today or date.today()
    start = today - timedelta(days=90)
    client = get_client()

    for ticker in TICKERS:
        log.info("Backfilling %s prices [%s, %s)", ticker, start, today)
        prices = fetch_prices(ticker, start, today)
        upsert_prices(client, prices)
        log.info("  %d price rows", len(prices))

        log.info("Backfilling %s financials (last 4 quarters)", ticker)
        fins = fetch_quarterly_financials(ticker, n=4)
        upsert_financials(client, fins)
        log.info("  %d financial rows", len(fins))

    log.info("Backfill complete.")


if __name__ == "__main__":
    load_dotenv()
    try:
        main()
    except Exception:
        log.exception("Backfill failed")
        sys.exit(1)
