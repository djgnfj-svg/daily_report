from datetime import date
from unittest.mock import MagicMock

from morningbrief.data.supabase_client import upsert_prices, upsert_financials
from morningbrief.data.yf import PriceRow
from morningbrief.data.edgar import FinancialRow


def test_upsert_prices_calls_supabase_with_correct_payload():
    mock_client = MagicMock()
    rows = [
        PriceRow(ticker="NVDA", date=date(2026, 4, 28),
                 open=100.0, high=102.0, low=99.0, close=101.0, volume=1_000_000),
    ]

    upsert_prices(mock_client, rows)

    mock_client.table.assert_called_once_with("prices")
    upsert_call = mock_client.table.return_value.upsert
    payload = upsert_call.call_args[0][0]
    assert payload == [{
        "ticker": "NVDA",
        "date": "2026-04-28",
        "open": 100.0,
        "high": 102.0,
        "low": 99.0,
        "close": 101.0,
        "volume": 1_000_000,
    }]
    upsert_call.return_value.execute.assert_called_once()


def test_upsert_prices_empty_list_is_noop():
    mock_client = MagicMock()
    upsert_prices(mock_client, [])
    mock_client.table.assert_not_called()


def test_upsert_financials_serializes_dates():
    mock_client = MagicMock()
    rows = [
        FinancialRow(ticker="AAPL", period="2026Q1",
                     revenue=124e9, net_income=36e9, eps=2.40, fcf=None,
                     total_debt=95e9, total_equity=65e9,
                     source="10-Q", filed_at=date(2026, 1, 30)),
    ]
    upsert_financials(mock_client, rows)
    payload = mock_client.table.return_value.upsert.call_args[0][0]
    assert payload[0]["filed_at"] == "2026-01-30"
    assert payload[0]["period"] == "2026Q1"
