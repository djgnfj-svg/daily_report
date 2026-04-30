from morningbrief.agents.scoring import score_combined, top_picks
from morningbrief.agents.fundamental import FundamentalResult
from morningbrief.agents.risk import RiskResult


def _f(t, s):
    return FundamentalResult(ticker=t, score=s, summary="", key_metrics={})


def _r(t, s):
    return RiskResult(ticker=t, score=s, summary="", metrics={})


def test_score_combined_weighted_06_04():
    # 0.6*80 + 0.4*60 = 48 + 24 = 72
    assert score_combined(_f("X", 80), _r("X", 60)) == 72.0


def test_top_picks_returns_top_n_by_combined_score():
    fundamentals = {
        "AAPL": _f("AAPL", 50),
        "NVDA": _f("NVDA", 90),
        "MSFT": _f("MSFT", 80),
        "AMZN": _f("AMZN", 60),
    }
    risks = {
        "AAPL": _r("AAPL", 60),
        "NVDA": _r("NVDA", 70),
        "MSFT": _r("MSFT", 50),
        "AMZN": _r("AMZN", 80),
    }
    picks = top_picks(fundamentals, risks, n=3)
    assert picks == ["NVDA", "MSFT", "AMZN"]
