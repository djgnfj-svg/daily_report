from datetime import date, timedelta
from functools import lru_cache

import pandas_market_calendars as mcal

_NYSE = mcal.get_calendar("NYSE")


@lru_cache(maxsize=1024)
def _trading_days_set(year: int) -> frozenset[date]:
    schedule = _NYSE.schedule(start_date=f"{year}-01-01", end_date=f"{year}-12-31")
    return frozenset(d.date() for d in schedule.index)


def is_trading_day(d: date) -> bool:
    return d in _trading_days_set(d.year)


def last_trading_day(ref: date) -> date:
    """Return the most recent trading day strictly before `ref`."""
    candidate = ref - timedelta(days=1)
    while not is_trading_day(candidate):
        candidate -= timedelta(days=1)
    return candidate
