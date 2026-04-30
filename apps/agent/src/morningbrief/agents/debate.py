import json
from dataclasses import dataclass
from typing import Literal

from morningbrief.llm.base import LLM
from morningbrief.llm.prompts import BULL_SYSTEM, BEAR_SYSTEM, SUPERVISOR_SYSTEM
from morningbrief.agents.fundamental import FundamentalResult
from morningbrief.agents.risk import RiskResult


Signal = Literal["BUY", "HOLD", "SELL"]


@dataclass(frozen=True)
class BullCase:
    ticker: str
    thesis: str
    key_metrics: list[str]
    rebuttal: str
    confidence: int


@dataclass(frozen=True)
class BearCase:
    ticker: str
    thesis: str
    key_metrics: list[str]
    rebuttal: str
    confidence: int


@dataclass(frozen=True)
class Verdict:
    ticker: str
    signal: Signal
    confidence: int
    thesis: str
    what_would_change_my_mind: str


def _user_for_debate(ticker: str, f: FundamentalResult, r: RiskResult) -> str:
    return (
        f"Ticker: {ticker}\n"
        f"Fundamental analysis: score={f.score}, summary={f.summary!r}, key_metrics={json.dumps(f.key_metrics)}\n"
        f"Risk analysis: score={r.score}, summary={r.summary!r}, metrics={json.dumps(r.metrics)}\n"
    )


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def bull_case(llm: LLM, ticker: str, f: FundamentalResult, r: RiskResult) -> BullCase:
    out = llm.complete_json(system=BULL_SYSTEM, user=_user_for_debate(ticker, f, r), tier="premium")
    return BullCase(
        ticker=ticker,
        thesis=str(out.get("thesis", "")),
        key_metrics=list(out.get("key_metrics", [])),
        rebuttal=str(out.get("rebuttal", "")),
        confidence=_clamp(int(out.get("confidence", 50)), 0, 100),
    )


def bear_case(llm: LLM, ticker: str, f: FundamentalResult, r: RiskResult) -> BearCase:
    out = llm.complete_json(system=BEAR_SYSTEM, user=_user_for_debate(ticker, f, r), tier="premium")
    return BearCase(
        ticker=ticker,
        thesis=str(out.get("thesis", "")),
        key_metrics=list(out.get("key_metrics", [])),
        rebuttal=str(out.get("rebuttal", "")),
        confidence=_clamp(int(out.get("confidence", 50)), 0, 100),
    )


def supervisor(
    llm: LLM,
    ticker: str,
    f: FundamentalResult,
    r: RiskResult,
    bull: BullCase,
    bear: BearCase,
) -> Verdict:
    user = (
        _user_for_debate(ticker, f, r)
        + f"Bull case: thesis={bull.thesis!r}, confidence={bull.confidence}, rebuttal={bull.rebuttal!r}\n"
        + f"Bear case: thesis={bear.thesis!r}, confidence={bear.confidence}, rebuttal={bear.rebuttal!r}\n"
    )
    out = llm.complete_json(system=SUPERVISOR_SYSTEM, user=user, tier="premium")
    raw_signal = str(out.get("signal", "HOLD")).upper()
    if raw_signal not in ("BUY", "HOLD", "SELL"):
        raw_signal = "HOLD"
    confidence = _clamp(int(out.get("confidence", 50)), 0, 100)
    final_signal: Signal = "HOLD" if confidence < 60 else raw_signal  # type: ignore[assignment]
    return Verdict(
        ticker=ticker,
        signal=final_signal,
        confidence=confidence,
        thesis=str(out.get("thesis", "")),
        what_would_change_my_mind=str(out.get("what_would_change_my_mind", "")),
    )
