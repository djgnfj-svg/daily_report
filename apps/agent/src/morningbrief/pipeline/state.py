from datetime import date
from typing import TypedDict

from morningbrief.agents.fundamental import FundamentalResult
from morningbrief.agents.risk import RiskResult
from morningbrief.agents.debate import OptimistCase, PessimistCase, Verdict


class TickerInputs(TypedDict):
    financials: list[dict]
    prices: list[dict]


class PipelineState(TypedDict, total=False):
    report_date: date
    universe: dict[str, TickerInputs]
    indicators: dict[str, dict]
    fundamentals: dict[str, FundamentalResult]
    risks: dict[str, RiskResult]
    top3: list[str]
    optimists: dict[str, OptimistCase]
    pessimists: dict[str, PessimistCase]
    verdicts: dict[str, Verdict]
    retried_tickers: list[str]
    signals: list[dict]
