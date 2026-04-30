import os
from dataclasses import asdict
from datetime import date, datetime
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
