from unittest.mock import MagicMock

from morningbrief.agents.risk import analyze_risk, RiskResult, _compute_metrics


def test_compute_metrics_from_synthetic_prices():
    # Linear up trend, no drawdown
    prices = [{"close": 100 + i} for i in range(60)]
    m = _compute_metrics(prices)
    assert m["max_drawdown_pct"] == 0.0
    assert m["volatility_pct"] >= 0


def test_compute_metrics_handles_drawdown():
    prices = [{"close": v} for v in [100, 110, 120, 90, 95]]
    m = _compute_metrics(prices)
    # Peak 120 -> trough 90 -> drawdown -25%
    assert round(m["max_drawdown_pct"], 1) == -25.0


def test_analyze_risk_returns_typed_result():
    mock_llm = MagicMock()
    mock_llm.complete_json.return_value = {
        "score": 65,
        "summary": "Volatility moderate, manageable drawdowns.",
    }
    prices = [{"close": 100 + i * 0.5} for i in range(60)]

    result = analyze_risk(llm=mock_llm, ticker="NVDA", prices=prices)

    assert isinstance(result, RiskResult)
    assert result.ticker == "NVDA"
    assert result.score == 65
    assert "volatility_pct" in result.metrics
    assert "max_drawdown_pct" in result.metrics

    call = mock_llm.complete_json.call_args
    assert call.kwargs["tier"] == "cheap"
