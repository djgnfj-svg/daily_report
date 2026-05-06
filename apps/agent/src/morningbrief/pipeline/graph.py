from typing import Any

from langgraph.graph import StateGraph, END

from morningbrief.agents.fundamental import FundamentalResult, analyze_fundamental
from morningbrief.agents.risk import RiskResult, analyze_risk
from morningbrief.agents.scoring import top_picks
from morningbrief.agents.debate import (
    OptimistCase,
    PessimistCase,
    Verdict,
    critic_note,
    judge,
    optimist_opening,
    optimist_rebuttal,
    pessimist_opening,
    pessimist_rebuttal,
)
from morningbrief.indicators import compute_indicators
from morningbrief.llm.base import LLM
from morningbrief.pipeline.state import PipelineState

_RETRY_THRESHOLD = 65


def _node_analyze_universe(state: PipelineState, llm: LLM) -> dict:
    fundamentals = {}
    risks = {}
    all_indicators: dict[str, dict] = {}
    for ticker, inputs in state["universe"].items():
        prices = inputs["prices"]
        last_close = prices[-1]["close"] if prices else 0.0
        indicators = compute_indicators(prices) if prices else {}
        all_indicators[ticker] = indicators
        fundamentals[ticker] = analyze_fundamental(
            llm=llm, ticker=ticker, financials=inputs["financials"],
            last_close=last_close, indicators=indicators,
        )
        risks[ticker] = analyze_risk(
            llm=llm, ticker=ticker, prices=prices, indicators=indicators,
        )
    return {"fundamentals": fundamentals, "risks": risks, "indicators": all_indicators}


def _node_select_top3(state: PipelineState) -> dict:
    return {"top3": top_picks(state["fundamentals"], state["risks"], n=3)}


def _run_full_debate(
    llm: LLM, ticker: str, f: FundamentalResult, r: RiskResult
) -> tuple[OptimistCase, PessimistCase, Verdict]:
    o1 = optimist_opening(llm, ticker, f, r)
    p1 = pessimist_opening(llm, ticker, f, r)
    o2 = optimist_rebuttal(llm, ticker, f, r, opening=o1, opponent=p1)
    p2 = pessimist_rebuttal(llm, ticker, f, r, opening=p1, opponent=o1)
    v = judge(llm, ticker, f, r, o2, p2)
    return o2, p2, v


def _node_debate_top3(state: PipelineState, llm: LLM) -> dict:
    optimists: dict[str, OptimistCase] = {}
    pessimists: dict[str, PessimistCase] = {}
    verdicts: dict[str, Verdict] = {}
    critics: dict[str, Any] = {}
    retried: list[str] = []
    for ticker in state["top3"]:
        f = state["fundamentals"][ticker]
        r = state["risks"][ticker]
        o, p, v = _run_full_debate(llm, ticker, f, r)
        if v.confidence < _RETRY_THRESHOLD:
            retried.append(ticker)
            o, p, v = _run_full_debate(llm, ticker, f, r)
        c = critic_note(llm, ticker, f, r, o, p, v)
        optimists[ticker] = o
        pessimists[ticker] = p
        verdicts[ticker] = v
        critics[ticker] = c
    return {
        "optimists": optimists,
        "pessimists": pessimists,
        "verdicts": verdicts,
        "critics": critics,
        "retried_tickers": retried,
    }


def _node_assemble_signals(state: PipelineState) -> dict:
    signals = []
    for ticker, f in state["fundamentals"].items():
        if ticker in state["verdicts"]:
            v = state["verdicts"][ticker]
            signals.append({
                "ticker": ticker,
                "signal": v.signal,
                "confidence": v.confidence,
                "thesis": v.thesis,
                "is_top_pick": True,
            })
        else:
            r = state["risks"][ticker]
            combined = 0.6 * f.score + 0.4 * r.score
            if combined >= 70:
                sig, conf = "BUY", int(combined)
            elif combined <= 35:
                sig, conf = "SELL", int(100 - combined)
            else:
                sig, conf = "HOLD", int(50 + abs(combined - 50) / 2)
            signals.append({
                "ticker": ticker,
                "signal": sig,
                "confidence": conf,
                "thesis": f.summary,
                "is_top_pick": False,
            })
    return {"signals": signals}


def build_graph(llm: LLM) -> Any:
    g = StateGraph(PipelineState)
    g.add_node("analyze_universe", lambda s: _node_analyze_universe(s, llm))
    g.add_node("select_top3", _node_select_top3)
    g.add_node("debate_top3", lambda s: _node_debate_top3(s, llm))
    g.add_node("assemble_signals", _node_assemble_signals)
    g.set_entry_point("analyze_universe")
    g.add_edge("analyze_universe", "select_top3")
    g.add_edge("select_top3", "debate_top3")
    g.add_edge("debate_top3", "assemble_signals")
    g.add_edge("assemble_signals", END)
    return g.compile()
