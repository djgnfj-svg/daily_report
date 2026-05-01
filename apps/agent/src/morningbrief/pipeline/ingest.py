"""매일 cron이 호출하는 데이터 갱신 단계.

- 가격: DB 최신일 기준 누락분만 yfinance에서 받아 upsert. 400일치 미달이면 자동 시드.
- 재무: 최신 filed_at이 오래됐으면 EDGAR 재조회.
- 멱등: upsert라 며칠 결방되거나 중복 실행돼도 안전.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from morningbrief.data.calendar import is_trading_day
from morningbrief.data.edgar import fetch_quarterly_financials
from morningbrief.data.supabase_client import (
    get_latest_filed_at,
    get_latest_price_date,
    upsert_financials,
    upsert_prices,
)
from morningbrief.data.tickers import TICKERS
from morningbrief.data.yf import fetch_prices

log = logging.getLogger(__name__)

LOOKBACK_DAYS = 400          # 자동 시드 윈도우 (252 거래일+버퍼)
FINANCIALS_STALE_DAYS = 7    # 재무 갱신 쿨다운


def ingest_prices(client, today: date, lookback_days: int = LOOKBACK_DAYS) -> dict[str, int]:
    """각 ticker별로 누락된 가격 행을 받아 upsert. {ticker: 추가행수} 반환."""
    if not is_trading_day(today):
        log.info("ingest_prices: %s is not a trading day, skip", today)
        return {}

    added: dict[str, int] = {}
    seed_threshold = today - timedelta(days=lookback_days)

    for ticker in TICKERS:
        last = get_latest_price_date(client, ticker)
        if last is None or last < seed_threshold:
            start = seed_threshold
            mode = "seed"
        else:
            start = last + timedelta(days=1)
            mode = "incremental"

        end_exclusive = today + timedelta(days=1)  # yfinance end는 exclusive
        if start >= end_exclusive:
            added[ticker] = 0
            continue

        log.info("ingest_prices %s [%s, %s) mode=%s", ticker, start, end_exclusive, mode)
        rows = fetch_prices(ticker, start, end_exclusive)
        upsert_prices(client, rows)
        added[ticker] = len(rows)

    return added


def ingest_financials(
    client, today: date, stale_days: int = FINANCIALS_STALE_DAYS
) -> dict[str, int]:
    """최신 filed_at이 stale_days 이상 됐거나 비어 있으면 최근 4분기 재조회."""
    refreshed: dict[str, int] = {}
    cutoff = today - timedelta(days=stale_days)

    for ticker in TICKERS:
        last_filed = get_latest_filed_at(client, ticker)
        if last_filed is not None and last_filed > cutoff:
            refreshed[ticker] = 0
            continue
        log.info("ingest_financials %s last_filed=%s, refreshing", ticker, last_filed)
        rows = fetch_quarterly_financials(ticker, n=4)
        upsert_financials(client, rows)
        refreshed[ticker] = len(rows)

    return refreshed
