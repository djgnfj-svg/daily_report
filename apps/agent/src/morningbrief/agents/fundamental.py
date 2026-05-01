import json
from dataclasses import dataclass

from morningbrief.llm.base import LLM
from morningbrief.llm.prompts import FUNDAMENTAL_SYSTEM
from morningbrief.utils import clamp


@dataclass(frozen=True)
class FundamentalResult:
    ticker: str
    score: int
    summary: str
    key_metrics: dict


def analyze_fundamental(
    llm: LLM,
    ticker: str,
    financials: list[dict],
    last_close: float,
) -> FundamentalResult:
    user = (
        f"Ticker: {ticker}\n"
        f"Last close (USD): {last_close}\n"
        f"Financials (most recent first):\n{json.dumps(financials, default=str)}\n"
    )
    out = llm.complete_json(system=FUNDAMENTAL_SYSTEM, user=user, tier="cheap")
    return FundamentalResult(
        ticker=ticker,
        score=clamp(int(out.get("score", 50)), 0, 100),
        summary=str(out.get("summary", ""))[:240],
        key_metrics=dict(out.get("key_metrics", {})),
    )
