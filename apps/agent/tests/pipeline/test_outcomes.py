from datetime import date
from unittest.mock import MagicMock

from morningbrief.pipeline.outcomes import update_outcomes


def test_update_outcomes_writes_1d_return_when_one_trading_day_passed():
    mock_client = MagicMock()

    import morningbrief.pipeline.outcomes as outcomes_mod
    outcomes_mod._load_close = lambda c, t, d: {
        ("NVDA", date(2026, 4, 28)): 100.0,
        ("NVDA", date(2026, 4, 29)): 102.0,
    }.get((t, d))

    n_updated = update_outcomes(
        mock_client,
        signals_with_dates=[("sig1", "NVDA", date(2026, 4, 28))],
        today=date(2026, 4, 30),
    )

    assert n_updated == 1
    upsert_payload = mock_client.table.return_value.upsert.call_args[0][0]
    assert upsert_payload[0]["signal_id"] == "sig1"
    assert upsert_payload[0]["price_at_report"] == 100.0
    assert upsert_payload[0]["price_1d"] == 102.0
    assert round(upsert_payload[0]["return_1d"], 2) == 2.0


def test_update_outcomes_skips_when_prices_not_yet_available():
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
