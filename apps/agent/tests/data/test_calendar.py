from datetime import date

from morningbrief.data.calendar import is_trading_day, last_trading_day


def test_christmas_2025_is_not_trading_day():
    assert is_trading_day(date(2025, 12, 25)) is False


def test_normal_weekday_is_trading_day():
    # 2025-12-22 was a Monday, normal trading day
    assert is_trading_day(date(2025, 12, 22)) is True


def test_saturday_is_not_trading_day():
    # 2025-12-20 was Saturday
    assert is_trading_day(date(2025, 12, 20)) is False


def test_last_trading_day_skips_weekend():
    # Sunday 2025-12-21 -> previous Friday 2025-12-19
    assert last_trading_day(date(2025, 12, 21)) == date(2025, 12, 19)


def test_last_trading_day_skips_christmas():
    # 2025-12-26 (day after Christmas) -> 2025-12-24 (half-day, still trading)
    assert last_trading_day(date(2025, 12, 26)) == date(2025, 12, 24)
