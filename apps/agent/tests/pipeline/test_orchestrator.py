from datetime import date
from unittest.mock import MagicMock, patch

from morningbrief.pipeline.orchestrator import run_for_date


@patch("morningbrief.pipeline.orchestrator.save_report_with_signals", return_value="rid-123")
@patch("morningbrief.pipeline.orchestrator.load_recent_prices")
@patch("morningbrief.pipeline.orchestrator.load_latest_financials")
@patch("morningbrief.pipeline.orchestrator.build_graph")
@patch("morningbrief.pipeline.orchestrator.render_report", return_value="# md")
@patch("morningbrief.pipeline.orchestrator.get_client")
def test_run_for_date_loads_renders_saves(get_client, render, build_graph, lf, lp, save):
    get_client.return_value = MagicMock()
    lp.return_value = [{"close": 100, "date": "2026-04-29"}]
    lf.return_value = [{"period": "2026Q1", "revenue": 1.0}]

    fake_compiled = MagicMock()
    fake_compiled.invoke.return_value = {
        "report_date": date(2026, 5, 1),
        "universe": {},
        "fundamentals": {}, "risks": {}, "top3": [],
        "bulls": {}, "bears": {}, "verdicts": {},
        "signals": [{"ticker": "NVDA", "signal": "BUY", "confidence": 78, "thesis": "x", "is_top_pick": True}],
    }
    build_graph.return_value = fake_compiled

    rid = run_for_date(date(2026, 5, 1), llm=MagicMock())

    assert rid == "rid-123"
    save.assert_called_once()
    saved_report = save.call_args.args[1]
    assert saved_report["date"] == "2026-05-01"
    assert saved_report["body_md"] == "# md"
