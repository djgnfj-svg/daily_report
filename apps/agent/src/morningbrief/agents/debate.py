import json
from dataclasses import dataclass, field
from typing import Literal

from morningbrief.agents.fundamental import FundamentalResult
from morningbrief.agents.risk import RiskResult
from morningbrief.llm.base import LLM
from morningbrief.llm.prompts import (
    CRITIC_SYSTEM,
    JUDGE_SYSTEM,
    OPTIMIST_OPENING_SYSTEM,
    OPTIMIST_REBUTTAL_SYSTEM,
    PESSIMIST_OPENING_SYSTEM,
    PESSIMIST_REBUTTAL_SYSTEM,
)
from morningbrief.utils import clamp

Signal = Literal["BUY", "HOLD", "SELL"]


@dataclass(frozen=True)
class OptimistCase:
    ticker: str
    thesis: str
    claims: list[dict]
    confidence: int
    rebuttal: str = ""
    counter_claims: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class PessimistCase:
    ticker: str
    thesis: str
    claims: list[dict]
    confidence: int
    rebuttal: str = ""
    counter_claims: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class Verdict:
    ticker: str
    signal: Signal
    confidence: int
    thesis: str
    what_would_change_my_mind: str
    winning_claims: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class CriticNote:
    ticker: str
    note: str
    missing_factors: list[str]


def _user_inputs(ticker: str, f: FundamentalResult, r: RiskResult) -> str:
    return (
        f"Ticker: {ticker}\n"
        f"Fundamental analysis: score={f.score}, summary={f.summary!r}, "
        f"key_metrics={json.dumps(f.key_metrics)}\n"
        f"Risk analysis: score={r.score}, summary={r.summary!r}, "
        f"metrics={json.dumps(r.metrics)}\n"
    )


def _coerce_claims(raw) -> list[dict]:
    out: list[dict] = []
    if not raw:
        return out
    for c in raw:
        if isinstance(c, dict) and "claim" in c and "metric" in c and "value" in c:
            out.append(
                {"claim": str(c["claim"]), "metric": str(c["metric"]), "value": c["value"]}
            )
    return out


def optimist_opening(
    llm: LLM, ticker: str, f: FundamentalResult, r: RiskResult
) -> OptimistCase:
    out = llm.complete_json(
        system=OPTIMIST_OPENING_SYSTEM, user=_user_inputs(ticker, f, r), tier="premium"
    )
    return OptimistCase(
        ticker=ticker,
        thesis=str(out.get("thesis", "")),
        claims=_coerce_claims(out.get("claims")),
        confidence=clamp(int(out.get("confidence", 50)), 0, 100),
    )


def pessimist_opening(
    llm: LLM, ticker: str, f: FundamentalResult, r: RiskResult
) -> PessimistCase:
    out = llm.complete_json(
        system=PESSIMIST_OPENING_SYSTEM, user=_user_inputs(ticker, f, r), tier="premium"
    )
    return PessimistCase(
        ticker=ticker,
        thesis=str(out.get("thesis", "")),
        claims=_coerce_claims(out.get("claims")),
        confidence=clamp(int(out.get("confidence", 50)), 0, 100),
    )


def optimist_rebuttal(
    llm: LLM,
    ticker: str,
    f: FundamentalResult,
    r: RiskResult,
    opening: OptimistCase,
    opponent: PessimistCase,
) -> OptimistCase:
    user = (
        _user_inputs(ticker, f, r)
        + f"\n[자기 1라운드 발언] thesis={opening.thesis!r}, "
        f"claims={json.dumps(opening.claims, ensure_ascii=False)}\n"
        + f"[비관론자 1라운드 발언] thesis={opponent.thesis!r}, "
        f"claims={json.dumps(opponent.claims, ensure_ascii=False)}\n"
    )
    out = llm.complete_json(system=OPTIMIST_REBUTTAL_SYSTEM, user=user, tier="premium")
    return OptimistCase(
        ticker=ticker,
        thesis=opening.thesis,
        claims=opening.claims,
        confidence=clamp(int(out.get("updated_confidence", opening.confidence)), 0, 100),
        rebuttal=str(out.get("rebuttal", "")),
        counter_claims=_coerce_claims(out.get("counter_claims")),
    )


def pessimist_rebuttal(
    llm: LLM,
    ticker: str,
    f: FundamentalResult,
    r: RiskResult,
    opening: PessimistCase,
    opponent: OptimistCase,
) -> PessimistCase:
    user = (
        _user_inputs(ticker, f, r)
        + f"\n[자기 1라운드 발언] thesis={opening.thesis!r}, "
        f"claims={json.dumps(opening.claims, ensure_ascii=False)}\n"
        + f"[긍정론자 1라운드 발언] thesis={opponent.thesis!r}, "
        f"claims={json.dumps(opponent.claims, ensure_ascii=False)}\n"
    )
    out = llm.complete_json(system=PESSIMIST_REBUTTAL_SYSTEM, user=user, tier="premium")
    return PessimistCase(
        ticker=ticker,
        thesis=opening.thesis,
        claims=opening.claims,
        confidence=clamp(int(out.get("updated_confidence", opening.confidence)), 0, 100),
        rebuttal=str(out.get("rebuttal", "")),
        counter_claims=_coerce_claims(out.get("counter_claims")),
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
        _user_inputs(ticker, f, r)
        + f"\n[긍정론자 1라운드] {optimist.thesis!r} "
        f"claims={json.dumps(optimist.claims, ensure_ascii=False)}\n"
        + f"[긍정론자 2라운드 반박] {optimist.rebuttal!r} "
        f"counter={json.dumps(optimist.counter_claims, ensure_ascii=False)}\n"
        + f"[비관론자 1라운드] {pessimist.thesis!r} "
        f"claims={json.dumps(pessimist.claims, ensure_ascii=False)}\n"
        + f"[비관론자 2라운드 반박] {pessimist.rebuttal!r} "
        f"counter={json.dumps(pessimist.counter_claims, ensure_ascii=False)}\n"
        + f"final confidences: optimist={optimist.confidence}, "
        f"pessimist={pessimist.confidence}\n"
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
        winning_claims=_coerce_claims(out.get("winning_claims")),
    )


def critic_note(
    llm: LLM,
    ticker: str,
    f: FundamentalResult,
    r: RiskResult,
    optimist: OptimistCase,
    pessimist: PessimistCase,
    verdict: Verdict,
) -> CriticNote:
    user = (
        _user_inputs(ticker, f, r)
        + f"\n[긍정 thesis] {optimist.thesis!r}\n[긍정 rebuttal] {optimist.rebuttal!r}\n"
        + f"[비관 thesis] {pessimist.thesis!r}\n[비관 rebuttal] {pessimist.rebuttal!r}\n"
        + f"[판정관] {verdict.signal} conf={verdict.confidence} thesis={verdict.thesis!r}\n"
    )
    out = llm.complete_json(system=CRITIC_SYSTEM, user=user, tier="premium")
    return CriticNote(
        ticker=ticker,
        note=str(out.get("note", ""))[:240],
        missing_factors=[str(x) for x in (out.get("missing_factors") or [])],
    )
