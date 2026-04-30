from morningbrief.agents.fundamental import FundamentalResult
from morningbrief.agents.risk import RiskResult


def score_combined(f: FundamentalResult, r: RiskResult) -> float:
    return 0.6 * f.score + 0.4 * r.score


def top_picks(
    fundamentals: dict[str, FundamentalResult],
    risks: dict[str, RiskResult],
    n: int = 3,
) -> list[str]:
    """Return top `n` tickers ranked by combined score (descending)."""
    scored = [
        (t, score_combined(fundamentals[t], risks[t]))
        for t in fundamentals
        if t in risks
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [t for t, _ in scored[:n]]
