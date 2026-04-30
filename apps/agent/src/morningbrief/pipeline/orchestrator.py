from __future__ import annotations

import logging
from datetime import date

from morningbrief.data.tickers import TICKERS
from morningbrief.data.supabase_client import (
    get_client,
    load_recent_prices,
    load_latest_financials,
    save_report_with_signals,
)
from morningbrief.llm.base import LLM, OpenAILLM
from morningbrief.pipeline.graph import build_graph
from morningbrief.pipeline.render import render_report

log = logging.getLogger(__name__)


def run_for_date(report_date: date, llm: LLM | None = None) -> str:
    client = get_client()
    llm = llm or OpenAILLM()

    universe = {}
    for ticker in TICKERS:
        prices = load_recent_prices(client, ticker, days=90, as_of=report_date)
        financials = load_latest_financials(client, ticker, n=4)
        universe[ticker] = {"prices": prices, "financials": financials}

    initial = {
        "report_date": report_date,
        "universe": universe,
        "fundamentals": {}, "risks": {},
        "top3": [],
        "bulls": {}, "bears": {}, "verdicts": {},
        "signals": [],
    }

    graph = build_graph(llm=llm)
    final = graph.invoke(initial)

    body_md = render_report(final, prior_outcomes=[])

    report = {
        "date": report_date.isoformat(),
        "body_md": body_md,
        "trace_url": None,
        "cost_usd": 0.0,
    }
    return save_report_with_signals(client, report, final["signals"])
