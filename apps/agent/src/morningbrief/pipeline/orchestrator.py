from __future__ import annotations

import logging
from datetime import date

from morningbrief.data.tickers import TICKERS
from morningbrief.data.supabase_client import (
    get_client,
    load_recent_prices,
    load_latest_financials,
    save_report_with_signals,
    upsert_daily_metrics,
    upsert_daily_scores,
)
from morningbrief.llm.base import LLM, MODEL_TIERS, OpenAILLM
from morningbrief.pipeline.graph import build_graph
from morningbrief.pipeline.ingest import ingest_financials, ingest_prices
from morningbrief.pipeline.render import render_report
from morningbrief.pipeline.outcomes import update_outcomes
from morningbrief.pipeline.send import send_report

log = logging.getLogger(__name__)


_METRIC_KEYS = (
    "ma20", "ma60", "ma200", "rsi14", "pos_52w_pct", "volume_ratio_20d",
    "volatility_pct", "max_drawdown_pct", "sharpe_naive",
)


def _build_metrics_and_scores_rows(state) -> tuple[list[dict], list[dict]]:
    """state에서 daily_metrics·daily_scores 행들을 만든다."""
    rdate = state["report_date"].isoformat()
    top3 = set(state.get("top3", []))
    indicators = state.get("indicators", {})
    fundamentals = state.get("fundamentals", {})
    risks = state.get("risks", {})

    metrics_rows: list[dict] = []
    scores_rows: list[dict] = []

    for ticker, f in fundamentals.items():
        ind = indicators.get(ticker, {})
        r = risks.get(ticker)
        merged: dict = {"ticker": ticker, "date": rdate}
        merged.update({k: ind.get(k) for k in _METRIC_KEYS if k in ind})
        if r is not None:
            for k in ("volatility_pct", "max_drawdown_pct", "sharpe_naive"):
                if k in r.metrics:
                    merged[k] = r.metrics[k]
        metrics_rows.append(merged)

        f_score = f.score
        r_score = r.score if r is not None else None
        combined = round(0.6 * f_score + 0.4 * r_score, 2) if r_score is not None else None
        scores_rows.append({
            "ticker": ticker,
            "date": rdate,
            "fundamental_score": f_score,
            "fundamental_summary": f.summary,
            "fundamental_key_metrics": f.key_metrics,
            "risk_score": r_score,
            "risk_summary": r.summary if r is not None else None,
            "combined_score": combined,
            "is_top_pick": ticker in top3,
            "model": MODEL_TIERS["cheap"],
        })
    return metrics_rows, scores_rows


def _load_unprocessed_signals(client, lookback_days: int = 10) -> list[tuple[str, str, date]]:
    """Return (signal_id, ticker, signal_date) for recent BUY/SELL signals to evaluate outcomes."""
    cutoff_iso = date.fromordinal(date.today().toordinal() - lookback_days).isoformat()
    resp = (
        client.table("signals")
        .select("id, ticker, reports!inner(date)")
        .gte("reports.date", cutoff_iso)
        .in_("signal", ["BUY", "SELL"])
        .execute()
    )
    out = []
    for row in resp.data or []:
        rdate = row.get("reports", {}).get("date")
        if rdate:
            out.append((row["id"], row["ticker"], date.fromisoformat(rdate)))
    return out


def run_for_date(
    report_date: date,
    llm: LLM | None = None,
    send: bool = False,
    site_url: str = "https://reseeall.com",
) -> str:
    client = get_client()
    llm = llm or OpenAILLM()

    try:
        added = ingest_prices(client, report_date)
        log.info("Ingested prices: %s", added)
    except Exception:
        log.exception("ingest_prices failed; continuing with existing DB rows")

    try:
        refreshed = ingest_financials(client, report_date)
        log.info("Refreshed financials: %s", refreshed)
    except Exception:
        log.exception("ingest_financials failed; continuing")

    if send:
        try:
            n = update_outcomes(client, _load_unprocessed_signals(client), today=report_date)
            log.info("Updated outcomes for %d signals", n)
        except Exception:
            log.exception("Outcomes update failed; continuing")

    universe = {}
    for ticker in TICKERS:
        prices = load_recent_prices(client, ticker, days=365, as_of=report_date)
        financials = load_latest_financials(client, ticker, n=4)
        universe[ticker] = {"prices": prices, "financials": financials}

    initial = {
        "report_date": report_date, "universe": universe, "indicators": {},
        "fundamentals": {}, "risks": {}, "top3": [],
        "bulls": {}, "bears": {}, "verdicts": {}, "signals": [],
    }

    graph = build_graph(llm=llm)
    final = graph.invoke(initial)

    body_md = render_report(final, prior_outcomes=[])
    report = {"date": report_date.isoformat(), "body_md": body_md, "trace_url": None, "cost_usd": 0.0}
    rid = save_report_with_signals(client, report, final["signals"])

    try:
        metrics_rows, scores_rows = _build_metrics_and_scores_rows(final)
        upsert_daily_metrics(client, metrics_rows)
        upsert_daily_scores(client, scores_rows)
        log.info("Upserted %d metrics, %d scores rows", len(metrics_rows), len(scores_rows))
    except Exception:
        log.exception("daily_metrics/scores upsert failed; continuing")

    if send:
        try:
            sent = send_report(
                client=client, site_url=site_url,
                report_date=report_date.isoformat(),
                subject=f"MorningBrief — {report_date.isoformat()}",
                body_md=body_md,
            )
            log.info("Sent report to %d subscribers", sent)
        except Exception:
            log.exception("Send failed")

    return rid
