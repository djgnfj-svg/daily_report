import json
import math
from dataclasses import dataclass

from morningbrief.llm.base import LLM
from morningbrief.llm.prompts import RISK_SYSTEM
from morningbrief.utils import clamp


@dataclass(frozen=True)
class RiskResult:
    ticker: str
    score: int
    summary: str
    metrics: dict


def _compute_metrics(prices: list[dict]) -> dict:
    closes = [float(p["close"]) for p in prices if p.get("close") is not None]
    if len(closes) < 2:
        return {"volatility_pct": 0.0, "max_drawdown_pct": 0.0, "sharpe_naive": 0.0, "n_days": len(closes)}

    rets = [(closes[i] / closes[i - 1] - 1.0) for i in range(1, len(closes))]
    mean_r = sum(rets) / len(rets)
    var = sum((r - mean_r) ** 2 for r in rets) / max(len(rets) - 1, 1)
    daily_vol = math.sqrt(var)
    annual_vol_pct = daily_vol * math.sqrt(252) * 100.0

    peak = closes[0]
    mdd = 0.0
    for c in closes:
        peak = max(peak, c)
        dd = (c / peak - 1.0) * 100.0
        mdd = min(mdd, dd)

    sharpe = (mean_r * 252) / (daily_vol * math.sqrt(252)) if daily_vol > 0 else 0.0

    return {
        "volatility_pct": round(annual_vol_pct, 2),
        "max_drawdown_pct": round(mdd, 2),
        "sharpe_naive": round(sharpe, 3),
        "n_days": len(closes),
    }


def analyze_risk(llm: LLM, ticker: str, prices: list[dict]) -> RiskResult:
    metrics = _compute_metrics(prices)
    user = (
        f"Ticker: {ticker}\n"
        f"Computed metrics:\n{json.dumps(metrics)}\n"
        f"Score the risk profile and write a one-sentence summary."
    )
    out = llm.complete_json(system=RISK_SYSTEM, user=user, tier="cheap")
    return RiskResult(
        ticker=ticker,
        score=clamp(int(out.get("score", 50)), 0, 100),
        summary=str(out.get("summary", ""))[:240],
        metrics=metrics,
    )
