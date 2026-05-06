from datetime import date, timedelta

from morningbrief.data.calendar import is_trading_day


def _load_close(client, ticker: str, on_date: date) -> float | None:
    resp = (
        client.table("prices")
        .select("close")
        .eq("ticker", ticker)
        .eq("date", on_date.isoformat())
        .execute()
    )
    if not resp.data:
        return None
    return float(resp.data[0]["close"])


def _step_to_next_session(d: date) -> date:
    cur = d + timedelta(days=1)
    while not is_trading_day(cur):
        cur += timedelta(days=1)
    return cur


def update_outcomes(
    client,
    signals_with_dates: list[tuple[str, str, date]],
    today: date,
) -> int:
    """For each signal, fill price_7d/return_7d (7 sessions) and price_30d/return_30d (30 sessions).

    `signals_with_dates`: list of (signal_id, ticker, signal_date) tuples.
    """
    payloads = []
    for signal_id, ticker, signal_date in signals_with_dates:
        p0 = _load_close(client, ticker, signal_date)
        if p0 is None:
            continue
        row: dict = {"signal_id": signal_id, "price_at_report": p0}

        d7 = signal_date
        for _ in range(7):
            d7 = _step_to_next_session(d7)
        if d7 < today:
            p7 = _load_close(client, ticker, d7)
            if p7 is not None:
                row["price_7d"] = p7
                row["return_7d"] = round((p7 / p0 - 1.0) * 100.0, 4)

        d30 = signal_date
        for _ in range(30):
            d30 = _step_to_next_session(d30)
        if d30 < today:
            p30 = _load_close(client, ticker, d30)
            if p30 is not None:
                row["price_30d"] = p30
                row["return_30d"] = round((p30 / p0 - 1.0) * 100.0, 4)

        if "return_7d" in row or "return_30d" in row:
            payloads.append(row)

    if payloads:
        client.table("outcomes").upsert(payloads).execute()
    return len(payloads)
