from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from morningbrief.config import CONFIG
from morningbrief.data.tickers import TICKERS
from morningbrief.pipeline.ingest import (
    ingest_financials,
    ingest_prices,
)

LOOKBACK_DAYS = CONFIG.price_backfill_days


@patch("morningbrief.pipeline.ingest.is_trading_day", return_value=False)
def test_ingest_prices_skips_on_holiday(_is_td):
    client = MagicMock()
    out = ingest_prices(client, date(2026, 7, 4))
    assert out == {}
    client.assert_not_called()


@patch("morningbrief.pipeline.ingest.is_trading_day", return_value=True)
@patch("morningbrief.pipeline.ingest.fetch_prices")
@patch("morningbrief.pipeline.ingest.upsert_prices")
@patch("morningbrief.pipeline.ingest.get_latest_price_date")
def test_ingest_prices_seeds_when_db_empty(get_last, upsert, fetch, _is_td):
    get_last.return_value = None
    fetch.return_value = ["row"] * 5

    today = date(2026, 5, 1)
    out = ingest_prices(MagicMock(), today)

    assert all(out[t] == 5 for t in TICKERS)
    first_call = fetch.call_args_list[0]
    ticker, start, end = first_call.args
    assert start == today - timedelta(days=LOOKBACK_DAYS)
    assert end == today + timedelta(days=1)


@patch("morningbrief.pipeline.ingest.is_trading_day", return_value=True)
@patch("morningbrief.pipeline.ingest.fetch_prices")
@patch("morningbrief.pipeline.ingest.upsert_prices")
@patch("morningbrief.pipeline.ingest.get_latest_price_date")
def test_ingest_prices_increments_when_recent(get_last, upsert, fetch, _is_td):
    today = date(2026, 5, 1)
    get_last.return_value = today - timedelta(days=2)  # 최근
    fetch.return_value = ["row"] * 2

    ingest_prices(MagicMock(), today)

    _, start, end = fetch.call_args_list[0].args
    assert start == today - timedelta(days=1)
    assert end == today + timedelta(days=1)


@patch("morningbrief.pipeline.ingest.is_trading_day", return_value=True)
@patch("morningbrief.pipeline.ingest.fetch_prices")
@patch("morningbrief.pipeline.ingest.upsert_prices")
@patch("morningbrief.pipeline.ingest.get_latest_price_date")
def test_ingest_prices_reseeds_when_too_old(get_last, upsert, fetch, _is_td):
    today = date(2026, 5, 1)
    get_last.return_value = today - timedelta(days=LOOKBACK_DAYS + 50)
    fetch.return_value = []

    ingest_prices(MagicMock(), today)

    _, start, _ = fetch.call_args_list[0].args
    assert start == today - timedelta(days=LOOKBACK_DAYS)


@patch("morningbrief.pipeline.ingest.is_trading_day", return_value=True)
@patch("morningbrief.pipeline.ingest.fetch_prices")
@patch("morningbrief.pipeline.ingest.upsert_prices")
@patch("morningbrief.pipeline.ingest.get_latest_price_date")
def test_ingest_prices_noop_when_already_today(get_last, upsert, fetch, _is_td):
    today = date(2026, 5, 1)
    get_last.return_value = today
    out = ingest_prices(MagicMock(), today)
    assert all(v == 0 for v in out.values())
    fetch.assert_not_called()
    upsert.assert_not_called()


@patch("morningbrief.pipeline.ingest.fetch_quarterly_financials")
@patch("morningbrief.pipeline.ingest.upsert_financials")
@patch("morningbrief.pipeline.ingest.get_latest_filed_at")
def test_ingest_financials_skips_when_fresh(get_last, upsert, fetch):
    today = date(2026, 5, 1)
    get_last.return_value = today - timedelta(days=3)
    out = ingest_financials(MagicMock(), today, stale_days=7)
    assert all(v == 0 for v in out.values())
    fetch.assert_not_called()


@patch("morningbrief.pipeline.ingest.fetch_quarterly_financials")
@patch("morningbrief.pipeline.ingest.upsert_financials")
@patch("morningbrief.pipeline.ingest.get_latest_filed_at")
def test_ingest_financials_refreshes_when_stale(get_last, upsert, fetch):
    today = date(2026, 5, 1)
    get_last.return_value = today - timedelta(days=30)
    fetch.return_value = ["q"] * 4
    out = ingest_financials(MagicMock(), today, stale_days=7)
    assert all(v == 4 for v in out.values())
    assert fetch.call_count == len(TICKERS)


@patch("morningbrief.pipeline.ingest.fetch_quarterly_financials")
@patch("morningbrief.pipeline.ingest.upsert_financials")
@patch("morningbrief.pipeline.ingest.get_latest_filed_at")
def test_ingest_financials_refreshes_when_empty(get_last, upsert, fetch):
    get_last.return_value = None
    fetch.return_value = ["q"] * 4
    out = ingest_financials(MagicMock(), date(2026, 5, 1))
    assert all(v == 4 for v in out.values())
