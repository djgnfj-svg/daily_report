import json
from dataclasses import dataclass
from typing import Literal

from morningbrief.llm.base import LLM
from morningbrief.llm.prompts import OPTIMIST_SYSTEM, PESSIMIST_SYSTEM, JUDGE_SYSTEM
from morningbrief.agents.fundamental import FundamentalResult
from morningbrief.agents.risk import RiskResult
from morningbrief.utils import clamp


Signal = Literal["BUY", "HOLD", "SELL"]


@dataclass(frozen=True)
class OptimistCase:
    ticker: str
    thesis: str
    key_metrics: list[str]
    rebuttal: str
    confidence: int


@dataclass(frozen=True)
class PessimistCase:
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


def optimist_case(llm: LLM, ticker: str, f: FundamentalResult, r: RiskResult) -> OptimistCase:
    out = llm.complete_json(system=OPTIMIST_SYSTEM, user=_user_for_debate(ticker, f, r), tier="premium")
    return OptimistCase(
        ticker=ticker,
        thesis=str(out.get("thesis", "")),
        key_metrics=list(out.get("key_metrics", [])),
        rebuttal=str(out.get("rebuttal", "")),
        confidence=clamp(int(out.get("confidence", 50)), 0, 100),
    )


def pessimist_case(llm: LLM, ticker: str, f: FundamentalResult, r: RiskResult) -> PessimistCase:
    out = llm.complete_json(system=PESSIMIST_SYSTEM, user=_user_for_debate(ticker, f, r), tier="premium")
    return PessimistCase(
        ticker=ticker,
        thesis=str(out.get("thesis", "")),
        key_metrics=list(out.get("key_metrics", [])),
        rebuttal=str(out.get("rebuttal", "")),
        confidence=clamp(int(out.get("confidence", 50)), 0, 100),
    )


def judge(
    llm: LLM,
    ticker: str,
    f: FundamentalResult,
    r: RiskResult,
    optimist: OptimistCase,
    pessimist: PessimistCase,
) -> Verdict:
    user = (
        _user_for_debate(ticker, f, r)
        + f"Optimist case: thesis={optimist.thesis!r}, confidence={optimist.confidence}, rebuttal={optimist.rebuttal!r}\n"
        + f"Pessimist case: thesis={pessimist.thesis!r}, confidence={pessimist.confidence}, rebuttal={pessimist.rebuttal!r}\n"
    )
    out = llm.complete_json(system=JUDGE_SYSTEM, user=user, tier="premium")
    raw_signal = str(out.get("signal", "HOLD")).upper()
    if raw_signal not in ("BUY", "HOLD", "SELL"):
        raw_signal = "HOLD"
    confidence = clamp(int(out.get("confidence", 50)), 0, 100)
    final_signal: Signal = "HOLD" if confidence < 60 else raw_signal  # type: ignore[assignment]
    return Verdict(
        ticker=ticker,
        signal=final_signal,
        confidence=confidence,
        thesis=str(out.get("thesis", "")),
        what_would_change_my_mind=str(out.get("what_would_change_my_mind", "")),
    )
