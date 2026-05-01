import os
from dataclasses import asdict
from datetime import date, datetime, timedelta
from typing import Any

from supabase import create_client, Client

from morningbrief.data.yf import PriceRow
from morningbrief.data.edgar import FinancialRow, FilingRow


def get_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _row_to_dict(row: Any) -> dict:
    return {k: _serialize(v) for k, v in asdict(row).items()}


def upsert_prices(client: Client, rows: list[PriceRow]) -> None:
    if not rows:
        return
    payload = [_row_to_dict(r) for r in rows]
    client.table("prices").upsert(payload).execute()


def upsert_financials(client: Client, rows: list[FinancialRow]) -> None:
    if not rows:
        return
    payload = [_row_to_dict(r) for r in rows]
    client.table("financials").upsert(payload).execute()


def insert_filings(client: Client, rows: list[FilingRow]) -> None:
    if not rows:
        return
    payload = [_row_to_dict(r) for r in rows]
    client.table("filings").insert(payload).execute()


def upsert_daily_metrics(client: Client, rows: list[dict]) -> None:
    if not rows:
        return
    client.table("daily_metrics").upsert(rows).execute()


def upsert_daily_scores(client: Client, rows: list[dict]) -> None:
    if not rows:
        return
    client.table("daily_scores").upsert(rows).execute()


def save_report_with_signals(client: Client, report: dict, signals: list[dict]) -> str:
    """Upsert a report by date, replace its signals. 같은 날짜 재실행 시 멱등."""
    resp = client.table("reports").upsert(report, on_conflict="date").execute()
    report_id = resp.data[0]["id"]
    client.table("signals").delete().eq("report_id", report_id).execute()
    if signals:
        rows = [{**s, "report_id": report_id} for s in signals]
        client.table("signals").insert(rows).execute()
    return report_id


def load_recent_prices(client: Client, ticker: str, days: int, as_of: date) -> list[dict]:
    """Return prices for `ticker` in [as_of - days, as_of], oldest first."""
    start = (as_of - timedelta(days=days)).isoformat()
    resp = (
        client.table("prices")
        .select("*")
        .eq("ticker", ticker)
        .gte("date", start)
        .order("date", desc=False)
        .execute()
    )
    return resp.data


def get_latest_price_date(client: Client, ticker: str) -> date | None:
    resp = (
        client.table("prices")
        .select("date")
        .eq("ticker", ticker)
        .order("date", desc=True)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return None
    return date.fromisoformat(resp.data[0]["date"])


def get_latest_filed_at(client: Client, ticker: str) -> date | None:
    resp = (
        client.table("financials")
        .select("filed_at")
        .eq("ticker", ticker)
        .order("filed_at", desc=True)
        .limit(1)
        .execute()
    )
    if not resp.data or not resp.data[0]["filed_at"]:
        return None
    return date.fromisoformat(resp.data[0]["filed_at"])


def load_latest_financials(client: Client, ticker: str, n: int = 4) -> list[dict]:
    """Return up to `n` most recent financial periods for `ticker`."""
    resp = (
        client.table("financials")
        .select("*")
        .eq("ticker", ticker)
        .order("filed_at", desc=True)
        .limit(n)
        .execute()
    )
    return resp.data
