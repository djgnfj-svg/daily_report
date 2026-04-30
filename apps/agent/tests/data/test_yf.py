from datetime import date

from morningbrief.data.yf import fetch_prices, PriceRow


def test_fetch_prices_returns_rows(monkeypatch, fake_yf_history):
    df = fake_yf_history([
        ("2026-04-28", 100.0, 102.0, 99.0, 101.0, 1_000_000),
        ("2026-04-29", 101.0, 103.0, 100.5, 102.5, 1_200_000),
    ])

    class FakeTicker:
        def __init__(self, sym): self.sym = sym
        def history(self, start, end, auto_adjust=False):
            return df

    monkeypatch.setattr("morningbrief.data.yf.yf.Ticker", FakeTicker)

    rows = fetch_prices("NVDA", date(2026, 4, 28), date(2026, 4, 30))

    assert rows == [
        PriceRow(ticker="NVDA", date=date(2026, 4, 28),
                 open=100.0, high=102.0, low=99.0, close=101.0, volume=1_000_000),
        PriceRow(ticker="NVDA", date=date(2026, 4, 29),
                 open=101.0, high=103.0, low=100.5, close=102.5, volume=1_200_000),
    ]


def test_fetch_prices_empty_returns_empty_list(monkeypatch, fake_yf_history):
    df = fake_yf_history([])

    class FakeTicker:
        def __init__(self, sym): pass
        def history(self, **kw): return df

    monkeypatch.setattr("morningbrief.data.yf.yf.Ticker", FakeTicker)
    assert fetch_prices("XXXX", date(2026, 4, 28), date(2026, 4, 30)) == []
