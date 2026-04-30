from morningbrief.data.tickers import TICKERS


def test_tickers_are_the_ten_big_techs():
    assert TICKERS == [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META",
        "NVDA", "TSLA", "AVGO", "ORCL", "NFLX",
    ]


def test_tickers_are_unique():
    assert len(TICKERS) == len(set(TICKERS))
