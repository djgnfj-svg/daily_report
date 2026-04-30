from datetime import date
from unittest.mock import MagicMock, patch

from morningbrief.data.yf import PriceRow
from morningbrief.data.edgar import FinancialRow


def test_backfill_runs_for_all_tickers():
    fake_prices = [PriceRow("X", date(2026, 4, 1), 1, 1, 1, 1, 100)]
    fake_fin = [FinancialRow("X", "2026Q1", 1, 1, 1, None, 1, 1, "10-Q", date(2026, 4, 1))]

    with patch("scripts.backfill.fetch_prices", return_value=fake_prices) as mp, \
         patch("scripts.backfill.fetch_quarterly_financials", return_value=fake_fin) as mf, \
         patch("scripts.backfill.upsert_prices") as up, \
         patch("scripts.backfill.upsert_financials") as uf, \
         patch("scripts.backfill.get_client") as gc:

        gc.return_value = MagicMock()
        from scripts.backfill import main
        main(today=date(2026, 4, 30))

        assert mp.call_count == 10
        assert mf.call_count == 10
        assert up.call_count == 10
        assert uf.call_count == 10

        first_call_args = mp.call_args_list[0]
        ticker_arg, start_arg, end_arg = first_call_args.args
        assert (end_arg - start_arg).days == 90
        assert end_arg == date(2026, 4, 30)
