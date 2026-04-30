from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import requests


# CIK numbers verified from sec.gov public registry (2026)
TICKER_TO_CIK: dict[str, int] = {
    "AAPL":  320193,
    "MSFT":  789019,
    "GOOGL": 1652044,
    "AMZN":  1018724,
    "META":  1326801,
    "NVDA":  1045810,
    "TSLA":  1318605,
    "AVGO":  1730168,
    "ORCL":  1341439,
    "NFLX":  1065280,
}

USER_AGENT = "MorningBrief research bot contact@reseeall.com"


@dataclass(frozen=True)
class FinancialRow:
    ticker: str
    period: str
    revenue: float | None
    net_income: float | None
    eps: float | None
    fcf: float | None
    total_debt: float | None
    total_equity: float | None
    source: str
    filed_at: date


def _fetch_company_facts(cik: int) -> dict[str, Any]:
    cik_padded = str(cik).zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _period_label(fp: str, fy: int) -> str:
    return f"{fy}{fp}"


REVENUE_TAGS = (
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
)


def _index_concept(facts: dict, tag: str, unit: str) -> dict[str, dict]:
    """Return {period_label: entry}, keeping latest filing per period."""
    entries = (
        facts.get("facts", {})
        .get("us-gaap", {})
        .get(tag, {})
        .get("units", {})
        .get(unit, [])
    )
    out: dict[str, dict] = {}
    for e in entries:
        label = _period_label(e["fp"], e["fy"])
        if label not in out or e["filed"] > out[label]["filed"]:
            out[label] = e
    return out


def _index_first_nonempty(facts: dict, tags: tuple[str, ...], unit: str) -> dict[str, dict]:
    for tag in tags:
        idx = _index_concept(facts, tag, unit)
        if idx:
            return idx
    return {}


def fetch_quarterly_financials(ticker: str, n: int = 4) -> list[FinancialRow]:
    """Return the most recent `n` quarterly/annual periods, newest first."""
    if ticker not in TICKER_TO_CIK:
        raise ValueError(f"Unknown ticker: {ticker}")
    facts = _fetch_company_facts(TICKER_TO_CIK[ticker])

    revenue = _index_first_nonempty(facts, REVENUE_TAGS, "USD")
    net_income = _index_concept(facts, "NetIncomeLoss", "USD")
    eps = _index_concept(facts, "EarningsPerShareBasic", "USD/shares")
    debt = _index_concept(facts, "LongTermDebt", "USD")
    equity = _index_concept(facts, "StockholdersEquity", "USD")

    periods = sorted(revenue.keys(), key=lambda p: revenue[p]["end"], reverse=True)[:n]

    rows: list[FinancialRow] = []
    for p in periods:
        rev = revenue[p]
        rows.append(FinancialRow(
            ticker=ticker,
            period=p,
            revenue=float(rev["val"]),
            net_income=float(net_income[p]["val"]) if p in net_income else None,
            eps=float(eps[p]["val"]) if p in eps else None,
            fcf=None,
            total_debt=float(debt[p]["val"]) if p in debt else None,
            total_equity=float(equity[p]["val"]) if p in equity else None,
            source=rev["form"],
            filed_at=date.fromisoformat(rev["filed"]),
        ))
    return rows


# ----- Task 8: filings -----

@dataclass(frozen=True)
class FilingRow:
    ticker: str
    form_type: str
    filed_at: datetime
    url: str


def _fetch_submissions(cik: int) -> dict[str, Any]:
    cik_padded = str(cik).zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
    resp.raise_for_status()
    return resp.json()


def fetch_recent_filings(
    ticker: str,
    since: date,
    form_types: tuple[str, ...] = ("8-K",),
) -> list[FilingRow]:
    """Return filings of given form types filed on/after `since`, newest first."""
    if ticker not in TICKER_TO_CIK:
        raise ValueError(f"Unknown ticker: {ticker}")
    cik = TICKER_TO_CIK[ticker]
    data = _fetch_submissions(cik)
    recent = data["filings"]["recent"]

    rows: list[FilingRow] = []
    for i, form in enumerate(recent["form"]):
        if form not in form_types:
            continue
        filed = date.fromisoformat(recent["filingDate"][i])
        if filed < since:
            continue
        accession = recent["accessionNumber"][i].replace("-", "")
        primary = recent["primaryDocument"][i]
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{primary}"
        rows.append(FilingRow(
            ticker=ticker,
            form_type=form,
            filed_at=datetime(filed.year, filed.month, filed.day, tzinfo=timezone.utc),
            url=url,
        ))
    return rows
