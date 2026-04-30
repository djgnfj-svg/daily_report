from dataclasses import dataclass
from datetime import date

import yfinance as yf


@dataclass(frozen=True)
class PriceRow:
    ticker: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


def fetch_prices(ticker: str, start: date, end: date) -> list[PriceRow]:
    """Fetch daily OHLCV bars [start, end) (yfinance convention)."""
    df = yf.Ticker(ticker).history(
        start=start.isoformat(), end=end.isoformat(), auto_adjust=False
    )
    rows: list[PriceRow] = []
    for ts, r in df.iterrows():
        rows.append(PriceRow(
            ticker=ticker,
            date=ts.date() if hasattr(ts, "date") else ts,
            open=float(r["Open"]),
            high=float(r["High"]),
            low=float(r["Low"]),
            close=float(r["Close"]),
            volume=int(r["Volume"]),
        ))
    return rows
