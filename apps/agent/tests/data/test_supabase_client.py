from datetime import date
from unittest.mock import MagicMock

from morningbrief.data.supabase_client import (
    upsert_prices,
    upsert_financials,
    save_report_with_signals,
    load_recent_prices,
    load_latest_financials,
)
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


def test_save_report_with_signals_inserts_report_then_signals():
    mock_client = MagicMock()
    insert_chain = mock_client.table.return_value.insert.return_value
    insert_chain.execute.return_value.data = [{"id": "REPORT-UUID"}]

    report = {"date": "2026-05-01", "body_md": "# hi", "trace_url": None, "cost_usd": 0.05}
    signals = [
        {"ticker": "NVDA", "signal": "BUY", "confidence": 70, "thesis": "...", "is_top_pick": True},
        {"ticker": "AAPL", "signal": "HOLD", "confidence": 55, "thesis": "...", "is_top_pick": False},
    ]

    report_id = save_report_with_signals(mock_client, report, signals)

    assert report_id == "REPORT-UUID"
    assert mock_client.table.call_args_list[0].args == ("reports",)
    assert mock_client.table.call_args_list[1].args == ("signals",)
    inserted_signals = mock_client.table.return_value.insert.call_args_list[1].args[0]
    assert inserted_signals[0]["report_id"] == "REPORT-UUID"
    assert inserted_signals[0]["ticker"] == "NVDA"


def test_load_recent_prices_queries_with_date_filter():
    mock_client = MagicMock()
    chain = mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value
    chain.execute.return_value.data = [
        {"ticker": "NVDA", "date": "2026-04-29", "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 100},
    ]

    rows = load_recent_prices(mock_client, "NVDA", days=90, as_of=date(2026, 4, 30))

    mock_client.table.assert_called_with("prices")
    assert len(rows) == 1
    assert rows[0]["ticker"] == "NVDA"


def test_load_latest_financials_returns_n_rows():
    mock_client = MagicMock()
    chain = mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value
    chain.execute.return_value.data = [
        {"ticker": "AAPL", "period": "2026Q1", "revenue": 1.0, "net_income": 0.1, "eps": 1, "fcf": None,
         "total_debt": 0.5, "total_equity": 0.5, "source": "10-Q", "filed_at": "2026-01-30"},
    ]
    rows = load_latest_financials(mock_client, "AAPL", n=4)
    mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.assert_called_with(4)
    assert len(rows) == 1
