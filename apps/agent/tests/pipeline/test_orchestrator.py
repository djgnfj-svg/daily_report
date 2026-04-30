from datetime import date
from unittest.mock import MagicMock, patch

from morningbrief.pipeline.orchestrator import run_for_date


@patch("morningbrief.pipeline.orchestrator.save_report_with_signals", return_value="rid-123")
@patch("morningbrief.pipeline.orchestrator.load_recent_prices")
@patch("morningbrief.pipeline.orchestrator.load_latest_financials")
@patch("morningbrief.pipeline.orchestrator.build_graph")
@patch("morningbrief.pipeline.orchestrator.render_report", return_value="# md")
@patch("morningbrief.pipeline.orchestrator.get_client")
def test_run_for_date_default_does_not_send(get_client, render, build_graph, lf, lp, save):
    get_client.return_value = MagicMock()
    lp.return_value = []
    lf.return_value = []
    fake = MagicMock()
    fake.invoke.return_value = {
        "report_date": date(2026, 5, 1), "universe": {}, "fundamentals": {}, "risks": {},
        "top3": [], "bulls": {}, "bears": {}, "verdicts": {},
        "signals": [{"ticker": "NVDA", "signal": "BUY", "confidence": 78, "thesis": "x", "is_top_pick": True}],
    }
    build_graph.return_value = fake

    rid = run_for_date(date(2026, 5, 1), llm=MagicMock())
    assert rid == "rid-123"


@patch("morningbrief.pipeline.orchestrator.send_report", return_value=2)
@patch("morningbrief.pipeline.orchestrator.update_outcomes", return_value=0)
@patch("morningbrief.pipeline.orchestrator.save_report_with_signals", return_value="rid-456")
@patch("morningbrief.pipeline.orchestrator.load_recent_prices")
@patch("morningbrief.pipeline.orchestrator.load_latest_financials")
@patch("morningbrief.pipeline.orchestrator.build_graph")
@patch("morningbrief.pipeline.orchestrator.render_report", return_value="# md")
@patch("morningbrief.pipeline.orchestrator.get_client")
def test_run_for_date_with_send_invokes_send_and_outcomes(
    get_client, render, build_graph, lf, lp, save, update_outcomes, send_report,
):
    get_client.return_value = MagicMock()
    lp.return_value = []
    lf.return_value = []
    fake = MagicMock()
    fake.invoke.return_value = {
        "report_date": date(2026, 5, 1), "universe": {}, "fundamentals": {}, "risks": {},
        "top3": [], "bulls": {}, "bears": {}, "verdicts": {},
        "signals": [],
    }
    build_graph.return_value = fake

    run_for_date(date(2026, 5, 1), llm=MagicMock(), send=True, site_url="https://reseeall.com")

    update_outcomes.assert_called_once()
    send_report.assert_called_once()
