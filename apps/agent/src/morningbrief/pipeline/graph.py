from typing import Any

from langgraph.graph import StateGraph, END

from morningbrief.agents.fundamental import analyze_fundamental
from morningbrief.agents.risk import analyze_risk
from morningbrief.agents.scoring import top_picks
from morningbrief.agents.debate import bull_case, bear_case, supervisor
from morningbrief.llm.base import LLM
from morningbrief.pipeline.state import PipelineState


def _node_analyze_universe(state: PipelineState, llm: LLM) -> dict:
    fundamentals = {}
    risks = {}
    for ticker, inputs in state["universe"].items():
        last_close = inputs["prices"][-1]["close"] if inputs["prices"] else 0.0
        fundamentals[ticker] = analyze_fundamental(
            llm=llm, ticker=ticker, financials=inputs["financials"], last_close=last_close
        )
        risks[ticker] = analyze_risk(llm=llm, ticker=ticker, prices=inputs["prices"])
    return {"fundamentals": fundamentals, "risks": risks}


def _node_select_top3(state: PipelineState) -> dict:
    # Compute scores for all tickers
    scored = [
        (t, 0.6 * state["fundamentals"][t].score + 0.4 * state["risks"][t].score)
        for t in state["fundamentals"]
        if t in state["risks"]
    ]
    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    # Collect all tickers, with tied ones in reverse order
    result = []
    prev_score = None
    current_batch = []
    for t, s in scored:
        if s != prev_score and current_batch:
            result.extend(reversed(current_batch))
            current_batch = []
            prev_score = s
        current_batch.append(t)
    if current_batch:
        result.extend(reversed(current_batch))

    return {"top3": result[:3]}


def _node_debate_top3(state: PipelineState, llm: LLM) -> dict:
    bulls, bears, verdicts = {}, {}, {}
    for ticker in state["top3"]:
        f = state["fundamentals"][ticker]
        r = state["risks"][ticker]
        b = bull_case(llm, ticker, f, r)
        br = bear_case(llm, ticker, f, r)
        v = supervisor(llm, ticker, f, r, b, br)
        bulls[ticker] = b
        bears[ticker] = br
        verdicts[ticker] = v
    return {"bulls": bulls, "bears": bears, "verdicts": verdicts}


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
