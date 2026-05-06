from datetime import date
from unittest.mock import MagicMock

from morningbrief.pipeline.outcomes import update_outcomes


class _FakeTable:
    def __init__(self, prices):
        self._prices = prices  # {(ticker, date_iso): close}
        self.upserts: list[dict] = []
        self._filter: dict = {}
        self._mode = "select"

    def select(self, *_):
        self._mode = "select"
        return self

    def eq(self, k, v):
        self._filter[k] = v
        return self

    def upsert(self, payloads):
        self._mode = "upsert"
        self.upserts.extend(payloads)
        return self

    def execute(self):
        if self._mode == "upsert":
            self._mode = "select"
            return None
        f = self._filter
        key = (f["ticker"], f["date"])
        rows = [{"close": self._prices[key]}] if key in self._prices else []
        self._filter = {}

        class R:
            data = rows

        return R()


class _FakeClient:
    def __init__(self, prices):
        self._t = _FakeTable(prices)

    def table(self, _name):
        return self._t


def test_fills_return_7d_and_30d_when_sessions_passed():
    # 5/1 신호 → 7세션 후 5/12, 30세션 후 6/15 가격 모두 존재
    prices = {
        ("AAPL", "2026-05-01"): 100.0,
        ("AAPL", "2026-05-12"): 110.0,
        ("AAPL", "2026-06-15"): 130.0,
    }
    client = _FakeClient(prices)
    n = update_outcomes(
        client,
        signals_with_dates=[("sig-1", "AAPL", date(2026, 5, 1))],
        today=date(2026, 6, 16),
    )
    assert n == 1
    upserts = client._t.upserts
    assert len(upserts) == 1
    row = upserts[0]
    assert row["signal_id"] == "sig-1"
    assert row["price_at_report"] == 100.0
    assert row["price_7d"] == 110.0
    assert row["return_7d"] == 10.0
    assert row["price_30d"] == 130.0
    assert row["return_30d"] == 30.0
    # 1d 컬럼은 더 이상 채우지 않는다
    assert "return_1d" not in row
    assert "price_1d" not in row


def test_fills_only_7d_when_30_sessions_not_passed():
    prices = {
        ("AAPL", "2026-05-01"): 100.0,
        ("AAPL", "2026-05-12"): 110.0,
    }
    client = _FakeClient(prices)
    n = update_outcomes(
        client,
        signals_with_dates=[("sig-1", "AAPL", date(2026, 5, 1))],
        today=date(2026, 5, 20),
    )
    assert n == 1
    row = client._t.upserts[0]
    assert row["return_7d"] == 10.0
    assert "return_30d" not in row


def test_skips_when_prices_not_yet_available():
    mock_client = MagicMock()

    import morningbrief.pipeline.outcomes as outcomes_mod

    outcomes_mod._load_close = lambda c, t, d: None

    n = update_outcomes(
        mock_client,
        signals_with_dates=[("sig1", "NVDA", date(2026, 4, 29))],
        today=date(2026, 4, 30),
    )
    assert n == 0
    mock_client.table.return_value.upsert.assert_not_called()
