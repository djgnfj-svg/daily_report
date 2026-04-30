from unittest.mock import MagicMock

from morningbrief.agents.debate import (
    bull_case, bear_case, supervisor,
    BullCase, BearCase, Verdict,
)
from morningbrief.agents.fundamental import FundamentalResult
from morningbrief.agents.risk import RiskResult


def _f():
    return FundamentalResult("NVDA", 80, "fund summary", {"pe": 65, "rev_yoy": 22})


def _r():
    return RiskResult("NVDA", 60, "risk summary", {"volatility_pct": 38, "max_drawdown_pct": -12})


def test_bull_case_returns_BullCase_using_premium_tier():
    llm = MagicMock()
    llm.complete_json.return_value = {
        "thesis": "Bull thesis", "key_metrics": ["pe=65"], "rebuttal": "Bear's point is...", "confidence": 78,
    }
    out = bull_case(llm, "NVDA", _f(), _r())
    assert isinstance(out, BullCase)
    assert out.confidence == 78
    assert out.thesis == "Bull thesis"
    assert llm.complete_json.call_args.kwargs["tier"] == "premium"


def test_bear_case_returns_BearCase():
    llm = MagicMock()
    llm.complete_json.return_value = {
        "thesis": "Bear thesis", "key_metrics": ["pe=65 high"], "rebuttal": "Bull missed...", "confidence": 55,
    }
    out = bear_case(llm, "NVDA", _f(), _r())
    assert isinstance(out, BearCase)
    assert out.confidence == 55


def test_supervisor_returns_HOLD_when_confidence_under_60():
    llm = MagicMock()
    llm.complete_json.return_value = {
        "signal": "BUY", "confidence": 45,
        "thesis": "...", "what_would_change_my_mind": "...",
    }
    bull = BullCase("NVDA", "t", ["m"], "r", 50)
    bear = BearCase("NVDA", "t", ["m"], "r", 50)
    v = supervisor(llm, "NVDA", _f(), _r(), bull, bear)
    assert v.signal == "HOLD"
    assert v.confidence == 45


def test_supervisor_returns_BUY_when_signal_BUY_and_confidence_high():
    llm = MagicMock()
    llm.complete_json.return_value = {
        "signal": "BUY", "confidence": 78, "thesis": "t", "what_would_change_my_mind": "X",
    }
    bull = BullCase("NVDA", "t", ["m"], "r", 78)
    bear = BearCase("NVDA", "t", ["m"], "r", 50)
    v = supervisor(llm, "NVDA", _f(), _r(), bull, bear)
    assert v.signal == "BUY"
    assert v.confidence == 78
    assert v.what_would_change_my_mind == "X"
