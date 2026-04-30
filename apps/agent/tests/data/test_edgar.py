import json
from datetime import date
from pathlib import Path

import responses

from morningbrief.data.edgar import (
    fetch_quarterly_financials,
    FinancialRow,
    TICKER_TO_CIK,
)


FIXTURE = Path(__file__).parent / "fixtures" / "edgar_aapl_facts.json"


@responses.activate
def test_fetch_quarterly_financials_returns_recent_quarters():
    cik_padded = str(TICKER_TO_CIK["AAPL"]).zfill(10)
    responses.add(
        responses.GET,
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json",
        json=json.loads(FIXTURE.read_text()),
        status=200,
    )

    rows = fetch_quarterly_financials("AAPL", n=4)

    assert len(rows) == 4
    assert rows[0] == FinancialRow(
        ticker="AAPL",
        period="2026Q1",
        revenue=124_300_000_000,
        net_income=36_000_000_000,
        eps=2.40,
        fcf=None,
        total_debt=95_000_000_000,
        total_equity=65_000_000_000,
        source="10-Q",
        filed_at=date(2026, 1, 30),
    )
    assert [r.period for r in rows] == ["2026Q1", "2025FY", "2025Q3", "2025Q2"]


def test_ticker_to_cik_covers_all_ten():
    expected = {"AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AVGO", "ORCL", "NFLX"}
    assert expected.issubset(TICKER_TO_CIK.keys())


# Task 8: filings tests
SUBM_FIXTURE = Path(__file__).parent / "fixtures" / "edgar_aapl_submissions.json"


@responses.activate
def test_fetch_recent_filings_8k_only():
    from morningbrief.data.edgar import fetch_recent_filings

    cik_padded = str(TICKER_TO_CIK["AAPL"]).zfill(10)
    responses.add(
        responses.GET,
        f"https://data.sec.gov/submissions/CIK{cik_padded}.json",
        json=json.loads(SUBM_FIXTURE.read_text()),
        status=200,
    )

    rows = fetch_recent_filings("AAPL", since=date(2026, 4, 1), form_types=("8-K",))

    assert len(rows) == 2
    assert rows[0].ticker == "AAPL"
    assert rows[0].form_type == "8-K"
    assert rows[0].filed_at.date() == date(2026, 4, 29)
    assert "aapl_8k_20260429.htm" in rows[0].url


@responses.activate
def test_fetch_recent_filings_filters_by_since():
    from morningbrief.data.edgar import fetch_recent_filings

    cik_padded = str(TICKER_TO_CIK["AAPL"]).zfill(10)
    responses.add(
        responses.GET,
        f"https://data.sec.gov/submissions/CIK{cik_padded}.json",
        json=json.loads(SUBM_FIXTURE.read_text()),
        status=200,
    )

    rows = fetch_recent_filings("AAPL", since=date(2026, 4, 20), form_types=("8-K",))
    assert len(rows) == 1
    assert rows[0].filed_at.date() == date(2026, 4, 29)
