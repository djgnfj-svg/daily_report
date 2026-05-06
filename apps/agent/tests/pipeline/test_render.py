from datetime import date

from morningbrief.pipeline.render import render_report
from morningbrief.agents.fundamental import FundamentalResult
from morningbrief.agents.risk import RiskResult
from morningbrief.agents.debate import OptimistCase, PessimistCase, Verdict


def _state():
    return {
        "report_date": date(2026, 5, 1),
        "universe": {t: {"financials": [], "prices": [{"close": 100.0}]} for t in [
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AVGO", "ORCL", "NFLX"]},
        "fundamentals": {t: FundamentalResult(t, 60, f"{t} fund", {}) for t in [
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AVGO", "ORCL", "NFLX"]},
        "risks": {t: RiskResult(t, 50, f"{t} risk", {"volatility_pct": 30, "max_drawdown_pct": -10}) for t in [
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AVGO", "ORCL", "NFLX"]},
        "top3": ["NVDA", "MSFT", "AVGO"],
        "optimists": {
            "NVDA": OptimistCase("NVDA", "Optimist NVDA", ["m"], "rebut", 78),
            "MSFT": OptimistCase("MSFT", "Optimist MSFT", ["m"], "rebut", 65),
            "AVGO": OptimistCase("AVGO", "Optimist AVGO", ["m"], "rebut", 71),
        },
        "pessimists": {
            "NVDA": PessimistCase("NVDA", "Pessimist NVDA", ["m"], "rebut", 60),
            "MSFT": PessimistCase("MSFT", "Pessimist MSFT", ["m"], "rebut", 55),
            "AVGO": PessimistCase("AVGO", "Pessimist AVGO", ["m"], "rebut", 50),
        },
        "verdicts": {
            "NVDA": Verdict("NVDA", "BUY", 78, "Verdict NVDA", "Catalyst X"),
            "MSFT": Verdict("MSFT", "BUY", 65, "Verdict MSFT", "Catalyst Y"),
            "AVGO": Verdict("AVGO", "HOLD", 58, "Verdict AVGO", "Catalyst Z"),
        },
        "signals": [
            {"ticker": "NVDA", "signal": "BUY", "confidence": 78, "thesis": "Verdict NVDA", "is_top_pick": True},
            {"ticker": "MSFT", "signal": "BUY", "confidence": 65, "thesis": "Verdict MSFT", "is_top_pick": True},
            {"ticker": "AVGO", "signal": "HOLD", "confidence": 58, "thesis": "Verdict AVGO", "is_top_pick": True},
            {"ticker": "AAPL", "signal": "HOLD", "confidence": 55, "thesis": "AAPL fund", "is_top_pick": False},
            {"ticker": "GOOGL", "signal": "HOLD", "confidence": 50, "thesis": "GOOGL fund", "is_top_pick": False},
            {"ticker": "AMZN", "signal": "HOLD", "confidence": 50, "thesis": "AMZN fund", "is_top_pick": False},
            {"ticker": "META", "signal": "HOLD", "confidence": 50, "thesis": "META fund", "is_top_pick": False},
            {"ticker": "TSLA", "signal": "HOLD", "confidence": 50, "thesis": "TSLA fund", "is_top_pick": False},
            {"ticker": "ORCL", "signal": "HOLD", "confidence": 50, "thesis": "ORCL fund", "is_top_pick": False},
            {"ticker": "NFLX", "signal": "HOLD", "confidence": 50, "thesis": "NFLX fund", "is_top_pick": False},
        ],
    }


def test_render_has_header_and_top3_sections():
    md = render_report(_state(), prior_outcomes=[])
    assert "MorningBrief — 2026-05-01" in md
    assert "## 🎯 오늘의 Top 3" in md
    assert "### 1. NVDA" in md
    assert "긍정론자" in md
    assert "비관론자" in md
    assert "판정관" in md
    assert "결과를 뒤집을 조건" in md


def test_render_has_remaining_seven_table():
    md = render_report(_state(), prior_outcomes=[])
    assert "## 📊 나머지 7종 요약" in md
    for t in ["AAPL", "GOOGL", "AMZN", "META", "TSLA", "ORCL", "NFLX"]:
        assert f"| {t} " in md


def test_render_includes_outcomes_block_when_provided():
    outs = [
        {"ticker": "NVDA", "signal": "BUY", "return_7d": 2.1, "return_30d": 5.5, "spy_return_30d": -0.8},
        {"ticker": "AAPL", "signal": "HOLD", "return_7d": 0.3, "return_30d": 1.0, "spy_return_30d": -0.8},
    ]
    md = render_report(_state(), prior_outcomes=outs)
    assert "## 📈 어제 시그널 결과" in md
    assert "+5.5%" in md or "5.5%" in md


def test_render_skips_outcomes_block_when_empty():
    md = render_report(_state(), prior_outcomes=[])
    assert "## 📈 어제 시그널 결과" not in md
