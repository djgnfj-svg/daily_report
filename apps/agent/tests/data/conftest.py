import pandas as pd
import pytest


@pytest.fixture
def fake_yf_history():
    """Returns a factory that builds a yfinance-shaped DataFrame."""
    def _make(rows):
        # rows: list[(date_str, open, high, low, close, volume)]
        df = pd.DataFrame(
            [{"Open": o, "High": h, "Low": l, "Close": c, "Volume": v}
             for _, o, h, l, c, v in rows],
            index=pd.DatetimeIndex([d for d, *_ in rows], name="Date"),
        )
        return df
    return _make
