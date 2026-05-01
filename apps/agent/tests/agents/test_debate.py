from unittest.mock import MagicMock

from morningbrief.agents.debate import (
    optimist_case, pessimist_case, judge,
    OptimistCase, PessimistCase,
)
from morningbrief.agents.fundamental import FundamentalResult
from morningbrief.agents.risk import RiskResult


def _f():
    return FundamentalResult("NVDA", 80, "fund summary", {"pe": 65, "rev_yoy": 22})


def _r():
    return RiskResult("NVDA", 60, "risk summary", {"volatility_pct": 38, "max_drawdown_pct": -12})


def test_optimist_case_returns_OptimistCase_using_premium_tier():
    llm = MagicMock()
    llm.complete_json.return_value = {
        "thesis": "Optimist thesis", "key_metrics": ["pe=65"], "rebuttal": "Pessimist's point is...", "confidence": 78,
    }
    out = optimist_case(llm, "NVDA", _f(), _r())
    assert isinstance(out, OptimistCase)
    assert out.confidence == 78
    assert out.thesis == "Optimist thesis"
    assert llm.complete_json.call_args.kwargs["tier"] == "premium"


def test_pessimist_case_returns_PessimistCase():
    llm = MagicMock()
    llm.complete_json.return_value = {
        "thesis": "Pessimist thesis", "key_metrics": ["pe=65 high"], "rebuttal": "Optimist missed...", "confidence": 55,
    }
    out = pessimist_case(llm, "NVDA", _f(), _r())
    assert isinstance(out, PessimistCase)
    assert out.confidence == 55


def test_judge_returns_HOLD_when_confidence_under_60():
    llm = MagicMock()
    llm.complete_json.return_value = {
        "signal": "BUY", "confidence": 45,
        "thesis": "...", "what_would_change_my_mind": "...",
    }
    optimist = OptimistCase("NVDA", "t", ["m"], "r", 50)
    pessimist = PessimistCase("NVDA", "t", ["m"], "r", 50)
    v = judge(llm, "NVDA", _f(), _r(), optimist, pessimist)
    assert v.signal == "HOLD"
    assert v.confidence == 45


def test_judge_returns_BUY_when_signal_BUY_and_confidence_high():
    llm = MagicMock()
    llm.complete_json.return_value = {
        "signal": "BUY", "confidence": 78, "thesis": "t", "what_would_change_my_mind": "X",
    }
    optimist = OptimistCase("NVDA", "t", ["m"], "r", 78)
    pessimist = PessimistCase("NVDA", "t", ["m"], "r", 50)
    v = judge(llm, "NVDA", _f(), _r(), optimist, pessimist)
    assert v.signal == "BUY"
    assert v.confidence == 78
    assert v.what_would_change_my_mind == "X"
