from datetime import date
from unittest.mock import MagicMock

from morningbrief.pipeline.graph import build_graph
from morningbrief.pipeline.state import PipelineState
from morningbrief.agents.fundamental import FundamentalResult
from morningbrief.agents.risk import RiskResult
from morningbrief.agents.debate import BullCase, BearCase, Verdict


def test_graph_runs_end_to_end_with_stub_agents(monkeypatch):
    fund_scores = {"NVDA": 90, "MSFT": 80, "GOOGL": 70, "AAPL": 30, "AMZN": 35,
                   "META": 40, "TSLA": 45, "AVGO": 50, "ORCL": 55, "NFLX": 60}
    risk_scores = {"NVDA": 70, "MSFT": 65, "GOOGL": 60, "AAPL": 40, "AMZN": 40,
                   "META": 40, "TSLA": 40, "AVGO": 40, "ORCL": 40, "NFLX": 40}

    def fake_fund(llm, ticker, financials, last_close, indicators=None):
        return FundamentalResult(ticker, score=fund_scores[ticker], summary="f", key_metrics={})

    def fake_risk(llm, ticker, prices, indicators=None):
        return RiskResult(ticker, score=risk_scores[ticker], summary="r",
                          metrics={"volatility_pct": 30, "max_drawdown_pct": -10, "sharpe_naive": 1.0})

    def fake_bull(llm, ticker, f, r):
        return BullCase(ticker, "bull thesis", ["m"], "rebut", 75)

    def fake_bear(llm, ticker, f, r):
        return BearCase(ticker, "bear thesis", ["m"], "rebut", 50)

    def fake_super(llm, ticker, f, r, b, br):
        return Verdict(ticker, "BUY", 78, "verdict thesis", "what changes")

    monkeypatch.setattr("morningbrief.pipeline.graph.analyze_fundamental", fake_fund)
    monkeypatch.setattr("morningbrief.pipeline.graph.analyze_risk", fake_risk)
    monkeypatch.setattr("morningbrief.pipeline.graph.bull_case", fake_bull)
    monkeypatch.setattr("morningbrief.pipeline.graph.bear_case", fake_bear)
    monkeypatch.setattr("morningbrief.pipeline.graph.supervisor", fake_super)

    universe = {
        t: {"financials": [{"period": "2026Q1", "revenue": 1.0}], "prices": [{"close": 100 + i} for i in range(60)]}
        for t in ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AVGO", "ORCL", "NFLX"]
    }

    initial: PipelineState = {
        "report_date": date(2026, 5, 1),
        "universe": universe,
        "fundamentals": {},
        "risks": {},
        "top3": [],
        "bulls": {},
        "bears": {},
        "verdicts": {},
        "signals": [],
    }

    graph = build_graph(llm=MagicMock())
    final = graph.invoke(initial)

    assert len(final["fundamentals"]) == 10
    assert len(final["risks"]) == 10
    assert "NVDA" in final["top3"]
    assert len(final["top3"]) == 3
    assert len(final["bulls"]) == 3
    assert len(final["bears"]) == 3
    assert len(final["verdicts"]) == 3
    assert len(final["signals"]) == 10
    nvda_signal = next(s for s in final["signals"] if s["ticker"] == "NVDA")
    assert nvda_signal["is_top_pick"] is True
    assert nvda_signal["signal"] == "BUY"
    aapl_signal = next(s for s in final["signals"] if s["ticker"] == "AAPL")
    assert aapl_signal["is_top_pick"] is False
