from datetime import date
from unittest.mock import MagicMock

from morningbrief.pipeline.graph import build_graph
from morningbrief.pipeline.state import PipelineState
from morningbrief.agents.fundamental import FundamentalResult
from morningbrief.agents.risk import RiskResult
from morningbrief.agents.debate import CriticNote, OptimistCase, PessimistCase, Verdict


def _make_optimist(ticker: str, conf: int = 75) -> OptimistCase:
    return OptimistCase(
        ticker=ticker,
        thesis="optimist thesis",
        claims=[],
        confidence=conf,
        rebuttal="rebut",
        counter_claims=[],
    )


def _make_pessimist(ticker: str, conf: int = 50) -> PessimistCase:
    return PessimistCase(
        ticker=ticker,
        thesis="pessimist thesis",
        claims=[],
        confidence=conf,
        rebuttal="rebut",
        counter_claims=[],
    )


def _make_verdict(ticker: str, conf: int = 78) -> Verdict:
    return Verdict(
        ticker=ticker,
        signal="BUY",
        confidence=conf,
        thesis="verdict thesis",
        what_would_change_my_mind="what changes",
        winning_claims=[],
    )


def _make_critic(ticker: str) -> CriticNote:
    return CriticNote(ticker=ticker, note="note", missing_factors=[])


def test_graph_runs_end_to_end_with_stub_agents(monkeypatch):
    fund_scores = {
        "NVDA": 90,
        "MSFT": 80,
        "GOOGL": 70,
        "AAPL": 30,
        "AMZN": 35,
        "META": 40,
        "TSLA": 45,
        "AVGO": 50,
        "ORCL": 55,
        "NFLX": 60,
    }
    risk_scores = {
        "NVDA": 70,
        "MSFT": 65,
        "GOOGL": 60,
        "AAPL": 40,
        "AMZN": 40,
        "META": 40,
        "TSLA": 40,
        "AVGO": 40,
        "ORCL": 40,
        "NFLX": 40,
    }

    def fake_fund(llm, ticker, financials, last_close, indicators=None):
        return FundamentalResult(ticker, score=fund_scores[ticker], summary="f", key_metrics={})

    def fake_risk(llm, ticker, prices, indicators=None):
        return RiskResult(
            ticker,
            score=risk_scores[ticker],
            summary="r",
            metrics={"volatility_pct": 30, "max_drawdown_pct": -10, "sharpe_naive": 1.0},
        )

    def fake_optimist_opening(llm, ticker, f, r):
        return _make_optimist(ticker)

    def fake_pessimist_opening(llm, ticker, f, r):
        return _make_pessimist(ticker)

    def fake_optimist_rebuttal(llm, ticker, f, r, opening, opponent):
        return _make_optimist(ticker)

    def fake_pessimist_rebuttal(llm, ticker, f, r, opening, opponent):
        return _make_pessimist(ticker)

    def fake_judge(llm, ticker, f, r, o, p):
        return _make_verdict(ticker, conf=78)

    def fake_critic(llm, ticker, f, r, o, p, v):
        return _make_critic(ticker)

    monkeypatch.setattr("morningbrief.pipeline.graph.analyze_fundamental", fake_fund)
    monkeypatch.setattr("morningbrief.pipeline.graph.analyze_risk", fake_risk)
    monkeypatch.setattr("morningbrief.pipeline.graph.optimist_opening", fake_optimist_opening)
    monkeypatch.setattr("morningbrief.pipeline.graph.pessimist_opening", fake_pessimist_opening)
    monkeypatch.setattr("morningbrief.pipeline.graph.optimist_rebuttal", fake_optimist_rebuttal)
    monkeypatch.setattr("morningbrief.pipeline.graph.pessimist_rebuttal", fake_pessimist_rebuttal)
    monkeypatch.setattr("morningbrief.pipeline.graph.judge", fake_judge)
    monkeypatch.setattr("morningbrief.pipeline.graph.critic_note", fake_critic)

    universe = {
        t: {
            "financials": [{"period": "2026Q1", "revenue": 1.0}],
            "prices": [{"close": 100 + i} for i in range(60)],
        }
        for t in ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AVGO", "ORCL", "NFLX"]
    }

    initial: PipelineState = {
        "report_date": date(2026, 5, 1),
        "universe": universe,
        "fundamentals": {},
        "risks": {},
        "top3": [],
        "optimists": {},
        "pessimists": {},
        "verdicts": {},
        "critics": {},
        "retried_tickers": [],
        "signals": [],
    }

    graph = build_graph(llm=MagicMock())
    final = graph.invoke(initial)

    assert len(final["fundamentals"]) == 10
    assert len(final["risks"]) == 10
    assert "NVDA" in final["top3"]
    assert len(final["top3"]) == 3
    assert len(final["optimists"]) == 3
    assert len(final["pessimists"]) == 3
    assert len(final["verdicts"]) == 3
    assert len(final["critics"]) == 3
    assert final["retried_tickers"] == []
    assert len(final["signals"]) == 10
    nvda_signal = next(s for s in final["signals"] if s["ticker"] == "NVDA")
    assert nvda_signal["is_top_pick"] is True
    assert nvda_signal["signal"] == "BUY"
    aapl_signal = next(s for s in final["signals"] if s["ticker"] == "AAPL")
    assert aapl_signal["is_top_pick"] is False


def test_debate_retries_when_judge_confidence_below_threshold(monkeypatch):
    """Judge confidence < 65 triggers exactly one retry of full 5-call debate."""
    fund_scores = {
        "NVDA": 90,
        "MSFT": 80,
        "GOOGL": 70,
        "AAPL": 30,
        "AMZN": 35,
        "META": 40,
        "TSLA": 45,
        "AVGO": 50,
        "ORCL": 55,
        "NFLX": 60,
    }
    risk_scores = dict.fromkeys(fund_scores, 50)

    def fake_fund(llm, ticker, financials, last_close, indicators=None):
        return FundamentalResult(ticker, score=fund_scores[ticker], summary="f", key_metrics={})

    def fake_risk(llm, ticker, prices, indicators=None):
        return RiskResult(
            ticker,
            score=risk_scores[ticker],
            summary="r",
            metrics={"volatility_pct": 30, "max_drawdown_pct": -10, "sharpe_naive": 1.0},
        )

    monkeypatch.setattr("morningbrief.pipeline.graph.analyze_fundamental", fake_fund)
    monkeypatch.setattr("morningbrief.pipeline.graph.analyze_risk", fake_risk)

    call_counts = {
        "opt_open": 0,
        "pes_open": 0,
        "opt_reb": 0,
        "pes_reb": 0,
        "judge": 0,
        "critic": 0,
    }
    judge_per_ticker: dict[str, int] = {}

    def fake_optimist_opening(llm, ticker, f, r):
        call_counts["opt_open"] += 1
        return _make_optimist(ticker)

    def fake_pessimist_opening(llm, ticker, f, r):
        call_counts["pes_open"] += 1
        return _make_pessimist(ticker)

    def fake_optimist_rebuttal(llm, ticker, f, r, opening, opponent):
        call_counts["opt_reb"] += 1
        return _make_optimist(ticker)

    def fake_pessimist_rebuttal(llm, ticker, f, r, opening, opponent):
        call_counts["pes_reb"] += 1
        return _make_pessimist(ticker)

    def fake_judge(llm, ticker, f, r, o, p):
        call_counts["judge"] += 1
        n = judge_per_ticker.get(ticker, 0) + 1
        judge_per_ticker[ticker] = n
        # First call returns 50 (forces retry); second returns 80.
        return _make_verdict(ticker, conf=50 if n == 1 else 80)

    def fake_critic(llm, ticker, f, r, o, p, v):
        call_counts["critic"] += 1
        return _make_critic(ticker)

    monkeypatch.setattr("morningbrief.pipeline.graph.optimist_opening", fake_optimist_opening)
    monkeypatch.setattr("morningbrief.pipeline.graph.pessimist_opening", fake_pessimist_opening)
    monkeypatch.setattr("morningbrief.pipeline.graph.optimist_rebuttal", fake_optimist_rebuttal)
    monkeypatch.setattr("morningbrief.pipeline.graph.pessimist_rebuttal", fake_pessimist_rebuttal)
    monkeypatch.setattr("morningbrief.pipeline.graph.judge", fake_judge)
    monkeypatch.setattr("morningbrief.pipeline.graph.critic_note", fake_critic)

    universe = {
        t: {
            "financials": [{"period": "2026Q1", "revenue": 1.0}],
            "prices": [{"close": 100 + i} for i in range(60)],
        }
        for t in fund_scores
    }
    initial: PipelineState = {
        "report_date": date(2026, 5, 1),
        "universe": universe,
        "fundamentals": {},
        "risks": {},
        "top3": [],
        "optimists": {},
        "pessimists": {},
        "verdicts": {},
        "critics": {},
        "retried_tickers": [],
        "signals": [],
    }

    graph = build_graph(llm=MagicMock())
    final = graph.invoke(initial)

    # All 3 top picks retry once each (judge first returns 50, second returns 80).
    assert sorted(final["retried_tickers"]) == sorted(final["top3"])
    # Each ticker invokes the 5-call debate exactly twice (1 initial + 1 retry, capped).
    assert call_counts["judge"] == 6
    assert call_counts["opt_open"] == 6
    assert call_counts["pes_open"] == 6
    assert call_counts["opt_reb"] == 6
    assert call_counts["pes_reb"] == 6
    # Critic called once per ticker AFTER retry decision.
    assert call_counts["critic"] == 3
    # Final verdict reflects the retry result (conf=80).
    for t in final["top3"]:
        assert final["verdicts"][t].confidence == 80
