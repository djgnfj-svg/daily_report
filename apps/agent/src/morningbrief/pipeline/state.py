from datetime import date
from typing import TypedDict

from morningbrief.agents.fundamental import FundamentalResult
from morningbrief.agents.risk import RiskResult
from morningbrief.agents.debate import BullCase, BearCase, Verdict


class TickerInputs(TypedDict):
    financials: list[dict]
    prices: list[dict]


class PipelineState(TypedDict):
    report_date: date
    universe: dict[str, TickerInputs]
    indicators: dict[str, dict]
    fundamentals: dict[str, FundamentalResult]
    risks: dict[str, RiskResult]
    top3: list[str]
    bulls: dict[str, BullCase]
    bears: dict[str, BearCase]
    verdicts: dict[str, Verdict]
    signals: list[dict]
