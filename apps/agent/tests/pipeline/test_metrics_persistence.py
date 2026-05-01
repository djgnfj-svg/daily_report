from datetime import date
from unittest.mock import MagicMock, patch

from morningbrief.agents.fundamental import FundamentalResult
from morningbrief.agents.risk import RiskResult
from morningbrief.pipeline.orchestrator import _build_metrics_and_scores_rows, run_for_date


def _state_with_two_tickers():
    return {
        "report_date": date(2026, 5, 1),
        "top3": ["NVDA"],
        "indicators": {
            "NVDA": {"ma20": 140.0, "ma60": 130.0, "ma200": None,
                     "rsi14": 68.0, "pos_52w_pct": 92.0, "volume_ratio_20d": 1.4},
            "AAPL": {"ma20": 180.0, "ma60": 178.0, "ma200": 170.0,
                     "rsi14": 55.0, "pos_52w_pct": 60.0, "volume_ratio_20d": 0.9},
        },
        "fundamentals": {
            "NVDA": FundamentalResult("NVDA", 78, "growth strong",
                                      {"revenue_yoy_pct": 22.5}),
            "AAPL": FundamentalResult("AAPL", 60, "stable", {"pe": 27.0}),
        },
        "risks": {
            "NVDA": RiskResult("NVDA", 55, "high vol",
                               {"volatility_pct": 42.0, "max_drawdown_pct": -18.0, "sharpe_naive": 1.2}),
            "AAPL": RiskResult("AAPL", 70, "low vol",
                               {"volatility_pct": 22.0, "max_drawdown_pct": -8.0, "sharpe_naive": 1.5}),
        },
    }


def test_build_metrics_rows_merges_indicators_and_risk_metrics():
    metrics, _ = _build_metrics_and_scores_rows(_state_with_two_tickers())
    by_ticker = {r["ticker"]: r for r in metrics}

    nvda = by_ticker["NVDA"]
    assert nvda["date"] == "2026-05-01"
    assert nvda["ma20"] == 140.0
    assert nvda["ma200"] is None
    assert nvda["rsi14"] == 68.0
    assert nvda["volatility_pct"] == 42.0
    assert nvda["max_drawdown_pct"] == -18.0
    assert nvda["sharpe_naive"] == 1.2


def test_build_scores_rows_marks_top_pick_and_combined():
    _, scores = _build_metrics_and_scores_rows(_state_with_two_tickers())
    by_ticker = {r["ticker"]: r for r in scores}

    nvda = by_ticker["NVDA"]
    assert nvda["fundamental_score"] == 78
    assert nvda["risk_score"] == 55
    assert nvda["combined_score"] == round(0.6 * 78 + 0.4 * 55, 2)
    assert nvda["is_top_pick"] is True
    assert nvda["fundamental_key_metrics"] == {"revenue_yoy_pct": 22.5}
    assert nvda["model"]  # 모델명 기록됨

    aapl = by_ticker["AAPL"]
    assert aapl["is_top_pick"] is False


@patch("morningbrief.pipeline.orchestrator.upsert_daily_scores")
@patch("morningbrief.pipeline.orchestrator.upsert_daily_metrics")
@patch("morningbrief.pipeline.orchestrator.ingest_financials", return_value={})
@patch("morningbrief.pipeline.orchestrator.ingest_prices", return_value={})
@patch("morningbrief.pipeline.orchestrator.save_report_with_signals", return_value="rid-1")
@patch("morningbrief.pipeline.orchestrator.load_recent_prices", return_value=[])
@patch("morningbrief.pipeline.orchestrator.load_latest_financials", return_value=[])
@patch("morningbrief.pipeline.orchestrator.build_graph")
@patch("morningbrief.pipeline.orchestrator.render_report", return_value="# md")
@patch("morningbrief.pipeline.orchestrator.get_client")
def test_run_for_date_persists_metrics_and_scores(
    get_client, render, build_graph, lf, lp, save, ip, ifin, up_metrics, up_scores,
):
    get_client.return_value = MagicMock()
    fake = MagicMock()
    fake.invoke.return_value = _state_with_two_tickers() | {
        "universe": {}, "optimists": {}, "pessimists": {}, "verdicts": {}, "signals": [],
    }
    build_graph.return_value = fake

    run_for_date(date(2026, 5, 1), llm=MagicMock())

    up_metrics.assert_called_once()
    up_scores.assert_called_once()
    metrics_rows = up_metrics.call_args.args[1]
    scores_rows = up_scores.call_args.args[1]
    assert len(metrics_rows) == 2
    assert len(scores_rows) == 2
