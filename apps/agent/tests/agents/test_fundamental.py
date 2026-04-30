from unittest.mock import MagicMock

from morningbrief.agents.fundamental import analyze_fundamental, FundamentalResult


def test_analyze_fundamental_returns_typed_result():
    mock_llm = MagicMock()
    mock_llm.complete_json.return_value = {
        "score": 78,
        "summary": "Revenue growth strong, FCF margin expanding.",
        "key_metrics": {"revenue_yoy_pct": 22.5, "net_margin_pct": 28.0, "pe": 27.5},
    }

    financials = [
        {"period": "2026Q1", "revenue": 100e9, "net_income": 28e9, "eps": 2.0, "total_debt": 50e9, "total_equity": 80e9},
        {"period": "2025Q4", "revenue": 95e9, "net_income": 25e9, "eps": 1.8, "total_debt": 50e9, "total_equity": 75e9},
    ]

    result = analyze_fundamental(
        llm=mock_llm,
        ticker="NVDA",
        financials=financials,
        last_close=1142.30,
    )

    assert isinstance(result, FundamentalResult)
    assert result.ticker == "NVDA"
    assert result.score == 78
    assert result.summary.startswith("Revenue growth")
    assert result.key_metrics["revenue_yoy_pct"] == 22.5

    call = mock_llm.complete_json.call_args
    assert call.kwargs["tier"] == "cheap"
    assert "NVDA" in call.kwargs["user"]
    assert "1142" in call.kwargs["user"]


def test_analyze_fundamental_clamps_score_out_of_range():
    mock_llm = MagicMock()
    mock_llm.complete_json.return_value = {"score": 150, "summary": "x", "key_metrics": {}}
    r = analyze_fundamental(llm=mock_llm, ticker="X", financials=[], last_close=10.0)
    assert r.score == 100

    mock_llm.complete_json.return_value = {"score": -5, "summary": "x", "key_metrics": {}}
    r = analyze_fundamental(llm=mock_llm, ticker="X", financials=[], last_close=10.0)
    assert r.score == 0
