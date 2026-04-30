# MorningBrief Plan 2 — Agent Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the LangGraph multi-agent pipeline that turns Supabase data (prices + financials) into a daily markdown report with BUY/HOLD/SELL signals, persists `reports` + `signals`, and updates `outcomes` for prior signals.

**Architecture:** Layered Python under `apps/agent/src/morningbrief/`:
- `llm/` — thin OpenAI adapter (Protocol-based, swappable)
- `agents/` — pure functions per agent role (Fundamental, Risk, Bull, Bear, Supervisor)
- `pipeline/` — LangGraph wiring + state + orchestrator + outcomes updater + markdown renderer
- `data/` — extended with read helpers and report persistence

Each agent is a pure function `(state) -> partial_state` that reads from Supabase-loaded inputs and emits typed dataclasses. LangGraph composes them; Langfuse traces every LLM call. Bull/Bear/Supervisor only run on the rule-selected top 3 tickers (cost control). The remaining 7 get signals from Fundamental+Risk only.

Out of scope (handled in Plan 3): Resend send, Astro frontend, archive page, GitHub Actions cron.

**Tech Stack:** OpenAI Python SDK (gpt-4o-mini, gpt-4o), LangGraph 0.2, Langfuse Python SDK, existing Plan 1 stack.

---

## Known Issue Carried Over From Plan 1

EDGAR financials backfill was uneven:
- AAPL: 1 row (uses `RevenueFromContractWithCustomerExcludingAssessedTax`)
- AMZN: 0 rows (same issue)
- AVGO: 3 rows (one quarter missing)

**Task 1 fixes this** before any agent code is written.

---

## File Structure

```
apps/agent/src/morningbrief/
├── data/
│   ├── tickers.py
│   ├── yf.py
│   ├── edgar.py             # Task 1: multi-tag revenue fallback
│   ├── calendar.py
│   └── supabase_client.py   # Task 2: add load_* and save_report
├── llm/
│   ├── __init__.py
│   ├── base.py              # Task 3: LLM Protocol + OpenAILLM
│   └── prompts.py           # Task 4-7: prompt templates per agent
├── agents/
│   ├── __init__.py
│   ├── fundamental.py       # Task 4
│   ├── risk.py              # Task 5
│   ├── scoring.py           # Task 6
│   └── debate.py            # Task 7 (Bull, Bear, Supervisor)
├── pipeline/
│   ├── __init__.py
│   ├── state.py             # Task 8 (LangGraph State TypedDict)
│   ├── graph.py             # Task 8 (graph wiring)
│   ├── render.py            # Task 9 (markdown report)
│   ├── outcomes.py          # Task 10 (1d/7d return updater)
│   └── orchestrator.py      # Task 11 (entry point)
└── ...
apps/agent/tests/
├── llm/test_base.py
├── agents/{test_fundamental,test_risk,test_scoring,test_debate}.py
├── pipeline/{test_render,test_outcomes,test_graph,test_orchestrator}.py
└── data/test_edgar.py        # extended in Task 1
```

Each file has one responsibility. Agents are pure functions. The LLM adapter is the only place we touch the OpenAI SDK directly.

---

## Task 1: Fix EDGAR multi-tag revenue fallback

**Files:**
- Modify: `apps/agent/src/morningbrief/data/edgar.py`
- Modify: `apps/agent/tests/data/test_edgar.py`
- Create: `apps/agent/tests/data/fixtures/edgar_amzn_facts.json`

The fix: try multiple revenue concept tags in priority order, take the first one that has data.

- [ ] **Step 1: Create AMZN-style fixture (uses different tag)**

`apps/agent/tests/data/fixtures/edgar_amzn_facts.json`:
```json
{
  "cik": 1018724,
  "entityName": "Amazon.com, Inc.",
  "facts": {
    "us-gaap": {
      "RevenueFromContractWithCustomerExcludingAssessedTax": {
        "units": {
          "USD": [
            {"end": "2026-03-31", "val": 158000000000, "fp": "Q1", "fy": 2026, "form": "10-Q", "filed": "2026-04-25"},
            {"end": "2025-12-31", "val": 170000000000, "fp": "FY", "fy": 2025, "form": "10-K", "filed": "2026-02-01"},
            {"end": "2025-09-30", "val": 143000000000, "fp": "Q3", "fy": 2025, "form": "10-Q", "filed": "2025-10-25"},
            {"end": "2025-06-30", "val": 134000000000, "fp": "Q2", "fy": 2025, "form": "10-Q", "filed": "2025-07-26"}
          ]
        }
      },
      "NetIncomeLoss": {
        "units": {
          "USD": [
            {"end": "2026-03-31", "val": 12000000000, "fp": "Q1", "fy": 2026, "form": "10-Q", "filed": "2026-04-25"}
          ]
        }
      }
    }
  }
}
```

- [ ] **Step 2: Write the failing test**

Append to `apps/agent/tests/data/test_edgar.py`:

```python


# Task 1: multi-tag revenue fallback
AMZN_FIXTURE = Path(__file__).parent / "fixtures" / "edgar_amzn_facts.json"


@responses.activate
def test_fetch_quarterly_financials_falls_back_to_alternate_revenue_tag():
    cik_padded = str(TICKER_TO_CIK["AMZN"]).zfill(10)
    responses.add(
        responses.GET,
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json",
        json=json.loads(AMZN_FIXTURE.read_text()),
        status=200,
    )

    rows = fetch_quarterly_financials("AMZN", n=4)
    assert len(rows) == 4
    assert rows[0].revenue == 158_000_000_000
    assert rows[0].period == "2026Q1"
```

- [ ] **Step 3: Confirm RED**

```
.venv/Scripts/python.exe -m pytest tests/data/test_edgar.py::test_fetch_quarterly_financials_falls_back_to_alternate_revenue_tag -v
```
Expected: 0 rows returned (assertion fails on `len(rows) == 4`).

- [ ] **Step 4: Modify `fetch_quarterly_financials` to try multiple tags**

In `apps/agent/src/morningbrief/data/edgar.py`, replace the body of `fetch_quarterly_financials` with:

```python
REVENUE_TAGS = (
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
)


def _index_first_nonempty(facts: dict, tags: tuple[str, ...], unit: str) -> dict[str, dict]:
    for tag in tags:
        idx = _index_concept(facts, tag, unit)
        if idx:
            return idx
    return {}


def fetch_quarterly_financials(ticker: str, n: int = 4) -> list[FinancialRow]:
    """Return the most recent `n` quarterly/annual periods, newest first."""
    if ticker not in TICKER_TO_CIK:
        raise ValueError(f"Unknown ticker: {ticker}")
    facts = _fetch_company_facts(TICKER_TO_CIK[ticker])

    revenue = _index_first_nonempty(facts, REVENUE_TAGS, "USD")
    net_income = _index_concept(facts, "NetIncomeLoss", "USD")
    eps = _index_concept(facts, "EarningsPerShareBasic", "USD/shares")
    debt = _index_concept(facts, "LongTermDebt", "USD")
    equity = _index_concept(facts, "StockholdersEquity", "USD")

    periods = sorted(revenue.keys(), key=lambda p: revenue[p]["end"], reverse=True)[:n]
    rows: list[FinancialRow] = []
    for p in periods:
        rev = revenue[p]
        rows.append(FinancialRow(
            ticker=ticker,
            period=p,
            revenue=float(rev["val"]),
            net_income=float(net_income[p]["val"]) if p in net_income else None,
            eps=float(eps[p]["val"]) if p in eps else None,
            fcf=None,
            total_debt=float(debt[p]["val"]) if p in debt else None,
            total_equity=float(equity[p]["val"]) if p in equity else None,
            source=rev["form"],
            filed_at=date.fromisoformat(rev["filed"]),
        ))
    return rows
```

(Remove the old `revenue = _index_concept(facts, "Revenues", "USD")` line.)

- [ ] **Step 5: Confirm GREEN (all edgar tests pass)**

```
.venv/Scripts/python.exe -m pytest tests/data/test_edgar.py -v
```
Expected: 5 passed (4 existing + 1 new).

- [ ] **Step 6: Re-run real backfill for AAPL/AMZN/AVGO**

From repo root:
```bash
PYTHONPATH=apps/agent/src apps/agent/.venv/Scripts/python.exe -m scripts.backfill
```

This is idempotent (upsert), so re-running fills the gaps. Verify with the supabase MCP `execute_sql` tool that all 10 tickers now have ≥3 financial rows. (The orchestrator will assist; this step is manual verification.)

- [ ] **Step 7: Commit**

```bash
git -c user.email=djgnfj3795@gmail.com -c user.name="djgnfj3795" commit -m "fix(agent): EDGAR revenue tag fallback for AAPL/AMZN/etc"
```

---

## Task 2: Extend supabase_client with load helpers + save_report

**Files:**
- Modify: `apps/agent/src/morningbrief/data/supabase_client.py`
- Modify: `apps/agent/tests/data/test_supabase_client.py`

We need: `load_recent_prices(ticker, days)`, `load_latest_financials(ticker, n)`, `save_report_with_signals(report, signals)`, `load_signals_on_date(date)`, `update_outcome(signal_id, ...)`.

- [ ] **Step 1: Write failing tests**

Append to `apps/agent/tests/data/test_supabase_client.py`:

```python
from datetime import datetime, timezone

from morningbrief.data.supabase_client import (
    save_report_with_signals,
    load_recent_prices,
    load_latest_financials,
)


def test_save_report_with_signals_inserts_report_then_signals():
    mock_client = MagicMock()
    # Mock chain: client.table("reports").insert(...).execute() -> object with .data=[{"id": "rid"}]
    insert_chain = mock_client.table.return_value.insert.return_value
    insert_chain.execute.return_value.data = [{"id": "REPORT-UUID"}]

    report = {"date": "2026-05-01", "body_md": "# hi", "trace_url": None, "cost_usd": 0.05}
    signals = [
        {"ticker": "NVDA", "signal": "BUY", "confidence": 70, "thesis": "...", "is_top_pick": True},
        {"ticker": "AAPL", "signal": "HOLD", "confidence": 55, "thesis": "...", "is_top_pick": False},
    ]

    report_id = save_report_with_signals(mock_client, report, signals)

    assert report_id == "REPORT-UUID"
    # First call: reports table insert
    assert mock_client.table.call_args_list[0].args == ("reports",)
    # Then signals
    assert mock_client.table.call_args_list[1].args == ("signals",)
    inserted_signals = mock_client.table.return_value.insert.call_args_list[1].args[0]
    assert inserted_signals[0]["report_id"] == "REPORT-UUID"
    assert inserted_signals[0]["ticker"] == "NVDA"


def test_load_recent_prices_queries_with_date_filter():
    mock_client = MagicMock()
    chain = mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value
    chain.execute.return_value.data = [
        {"ticker": "NVDA", "date": "2026-04-29", "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 100},
    ]

    rows = load_recent_prices(mock_client, "NVDA", days=90, as_of=date(2026, 4, 30))

    mock_client.table.assert_called_with("prices")
    assert len(rows) == 1
    assert rows[0]["ticker"] == "NVDA"


def test_load_latest_financials_returns_n_rows():
    mock_client = MagicMock()
    chain = mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value
    chain.execute.return_value.data = [
        {"ticker": "AAPL", "period": "2026Q1", "revenue": 1.0, "net_income": 0.1, "eps": 1, "fcf": None,
         "total_debt": 0.5, "total_equity": 0.5, "source": "10-Q", "filed_at": "2026-01-30"},
    ]
    rows = load_latest_financials(mock_client, "AAPL", n=4)
    mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.assert_called_with(4)
    assert len(rows) == 1
```

- [ ] **Step 2: Confirm RED**

```
.venv/Scripts/python.exe -m pytest tests/data/test_supabase_client.py -v
```

- [ ] **Step 3: Add the implementations**

Append to `apps/agent/src/morningbrief/data/supabase_client.py`:

```python
from datetime import timedelta


def save_report_with_signals(client: Client, report: dict, signals: list[dict]) -> str:
    """Insert a report row, then signals tagged with the new report's id. Returns the report id."""
    resp = client.table("reports").insert(report).execute()
    report_id = resp.data[0]["id"]
    if signals:
        rows = [{**s, "report_id": report_id} for s in signals]
        client.table("signals").insert(rows).execute()
    return report_id


def load_recent_prices(client: Client, ticker: str, days: int, as_of: date) -> list[dict]:
    """Return prices for `ticker` in [as_of - days, as_of], newest last."""
    start = (as_of - timedelta(days=days)).isoformat()
    resp = (
        client.table("prices")
        .select("*")
        .eq("ticker", ticker)
        .gte("date", start)
        .order("date", desc=False)
        .execute()
    )
    return resp.data


def load_latest_financials(client: Client, ticker: str, n: int = 4) -> list[dict]:
    """Return up to `n` most recent financial periods for `ticker`."""
    resp = (
        client.table("financials")
        .select("*")
        .eq("ticker", ticker)
        .order("filed_at", desc=True)
        .limit(n)
        .execute()
    )
    return resp.data
```

- [ ] **Step 4: Confirm GREEN**

```
.venv/Scripts/python.exe -m pytest tests/data/test_supabase_client.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git -c user.email=djgnfj3795@gmail.com -c user.name="djgnfj3795" commit -m "feat(agent): add load helpers and save_report_with_signals"
```

---

## Task 3: LLM adapter (OpenAI)

**Files:**
- Create: `apps/agent/src/morningbrief/llm/__init__.py` (empty)
- Create: `apps/agent/src/morningbrief/llm/base.py`
- Create: `apps/agent/tests/llm/__init__.py` (empty)
- Create: `apps/agent/tests/llm/test_base.py`
- Modify: `apps/agent/pyproject.toml` (add `openai>=1.50`)

The adapter exposes `LLM` (Protocol) and `OpenAILLM` with `complete_json(system, user, model_tier) -> dict`. JSON-mode response forced. We mock the OpenAI client in tests — no real network.

- [ ] **Step 1: Add openai to deps**

Edit `apps/agent/pyproject.toml` `dependencies`:
```toml
dependencies = [
  "yfinance>=0.2.40",
  "requests>=2.31",
  "pandas>=2.2",
  "pandas-market-calendars>=4.4",
  "supabase>=2.5",
  "python-dotenv>=1.0",
  "openai>=1.50",
  "langgraph>=0.2",
  "langfuse>=2.40",
]
```

Run install: `apps/agent/.venv/Scripts/python.exe -m pip install -e "apps/agent[dev]"`

- [ ] **Step 2: Write failing test**

`apps/agent/tests/llm/__init__.py`: empty file.

`apps/agent/tests/llm/test_base.py`:
```python
import json
from unittest.mock import MagicMock

from morningbrief.llm.base import OpenAILLM, MODEL_TIERS


def test_openai_llm_calls_correct_model_for_tier(monkeypatch):
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value.choices[0].message.content = json.dumps({"score": 80})

    llm = OpenAILLM(client=fake_client)
    result = llm.complete_json(system="sys", user="usr", tier="cheap")

    fake_client.chat.completions.create.assert_called_once()
    call = fake_client.chat.completions.create.call_args.kwargs
    assert call["model"] == MODEL_TIERS["cheap"]
    assert call["response_format"] == {"type": "json_object"}
    assert call["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "usr"},
    ]
    assert result == {"score": 80}


def test_openai_llm_premium_tier_uses_premium_model():
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value.choices[0].message.content = '{"x":1}'
    OpenAILLM(client=fake_client).complete_json(system="s", user="u", tier="premium")
    assert fake_client.chat.completions.create.call_args.kwargs["model"] == MODEL_TIERS["premium"]


def test_model_tiers_has_cheap_and_premium():
    assert MODEL_TIERS == {"cheap": "gpt-4o-mini", "premium": "gpt-4o"}
```

- [ ] **Step 3: Confirm RED**

```
.venv/Scripts/python.exe -m pytest tests/llm -v
```

- [ ] **Step 4: Write implementation**

`apps/agent/src/morningbrief/llm/__init__.py`: empty.

`apps/agent/src/morningbrief/llm/base.py`:
```python
import json
import os
from typing import Any, Literal, Protocol

from openai import OpenAI


MODEL_TIERS: dict[str, str] = {
    "cheap": "gpt-4o-mini",
    "premium": "gpt-4o",
}


class LLM(Protocol):
    def complete_json(self, system: str, user: str, tier: Literal["cheap", "premium"]) -> dict[str, Any]: ...


class OpenAILLM:
    def __init__(self, client: OpenAI | None = None) -> None:
        self._client = client or OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def complete_json(self, system: str, user: str, tier: Literal["cheap", "premium"]) -> dict[str, Any]:
        resp = self._client.chat.completions.create(
            model=MODEL_TIERS[tier],
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        content = resp.choices[0].message.content
        return json.loads(content)
```

- [ ] **Step 5: Confirm GREEN**

```
.venv/Scripts/python.exe -m pytest tests/llm -v
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git -c user.email=djgnfj3795@gmail.com -c user.name="djgnfj3795" commit -m "feat(agent): add OpenAI LLM adapter with cheap/premium tiers"
```

---

## Task 4: Fundamental analyst agent

**Files:**
- Create: `apps/agent/src/morningbrief/agents/__init__.py` (empty)
- Create: `apps/agent/src/morningbrief/agents/fundamental.py`
- Create: `apps/agent/src/morningbrief/llm/prompts.py`
- Create: `apps/agent/tests/agents/__init__.py` (empty)
- Create: `apps/agent/tests/agents/test_fundamental.py`

Input: ticker, latest 4 financials (list[dict]), latest close price. Output: `FundamentalResult(ticker, score: int 0-100, summary: str, key_metrics: dict)`.

- [ ] **Step 1: Write failing test**

`apps/agent/tests/agents/__init__.py`: empty.

`apps/agent/tests/agents/test_fundamental.py`:
```python
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

    # LLM was called with cheap tier
    call = mock_llm.complete_json.call_args
    assert call.kwargs["tier"] == "cheap"
    # User prompt mentions ticker and includes financial JSON
    assert "NVDA" in call.kwargs["user"]
    assert "1142" in call.kwargs["user"]


def test_analyze_fundamental_clamps_score_out_of_range():
    mock_llm = MagicMock()
    mock_llm.complete_json.return_value = {"score": 150, "summary": "x", "key_metrics": {}}
    r = analyze_fundamental(llm=mock_llm, ticker="X", financials=[], last_close=10.0)
    assert r.score == 100  # clamped

    mock_llm.complete_json.return_value = {"score": -5, "summary": "x", "key_metrics": {}}
    r = analyze_fundamental(llm=mock_llm, ticker="X", financials=[], last_close=10.0)
    assert r.score == 0
```

- [ ] **Step 2: Confirm RED**

```
.venv/Scripts/python.exe -m pytest tests/agents/test_fundamental.py -v
```

- [ ] **Step 3: Write prompt template**

`apps/agent/src/morningbrief/llm/prompts.py`:
```python
FUNDAMENTAL_SYSTEM = """You are a buy-side equity fundamental analyst.
Given a company's recent quarterly financials and current price, output a strict JSON object:
  {"score": int 0-100, "summary": str (<=180 chars), "key_metrics": {<3-6 named metrics>: number}}
Score reflects fundamental quality + valuation: 100 = compelling buy, 0 = avoid, 50 = neutral.
Cite numbers from the inputs only. Do not fabricate.
"""

RISK_SYSTEM = """You are a buy-side risk analyst.
Given 90 trading days of OHLCV for a ticker, compute risk metrics and output strict JSON:
  {"score": int 0-100, "summary": str (<=180 chars), "metrics": {"volatility_pct": float, "max_drawdown_pct": float, "sharpe_naive": float}}
Higher score = better risk-adjusted profile (lower vol, smaller MDD).
Compute from inputs only.
"""

BULL_SYSTEM = """You are a Bull researcher in a debate format.
Given Fundamental and Risk analyses for a ticker, build the strongest BUY case.
Cite specific numbers from those analyses (no fabrication). Acknowledge the bear case briefly and rebut.
Output JSON: {"thesis": str, "key_metrics": [str], "rebuttal": str, "confidence": int 0-100}
"""

BEAR_SYSTEM = """You are a Bear researcher in a debate format.
Given Fundamental and Risk analyses for a ticker, build the strongest SELL case.
Cite specific numbers from those analyses (no fabrication). Acknowledge the bull case briefly and rebut.
Output JSON: {"thesis": str, "key_metrics": [str], "rebuttal": str, "confidence": int 0-100}
"""

SUPERVISOR_SYSTEM = """You are a senior portfolio manager.
Read the Bull and Bear arguments. Issue a verdict.
Rules:
- If neither side reaches confidence >= 60, output HOLD.
- If sides strongly conflict and you are uncertain, output HOLD.
- Always include "what would change my mind".
Output JSON: {"signal": "BUY"|"HOLD"|"SELL", "confidence": int 0-100, "thesis": str, "what_would_change_my_mind": str}
"""
```

- [ ] **Step 4: Write fundamental.py**

`apps/agent/src/morningbrief/agents/__init__.py`: empty.

`apps/agent/src/morningbrief/agents/fundamental.py`:
```python
import json
from dataclasses import dataclass

from morningbrief.llm.base import LLM
from morningbrief.llm.prompts import FUNDAMENTAL_SYSTEM


@dataclass(frozen=True)
class FundamentalResult:
    ticker: str
    score: int
    summary: str
    key_metrics: dict


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


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
        score=_clamp(int(out.get("score", 50)), 0, 100),
        summary=str(out.get("summary", ""))[:240],
        key_metrics=dict(out.get("key_metrics", {})),
    )
```

- [ ] **Step 5: Confirm GREEN**

```
.venv/Scripts/python.exe -m pytest tests/agents/test_fundamental.py -v
```
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git -c user.email=djgnfj3795@gmail.com -c user.name="djgnfj3795" commit -m "feat(agent): add Fundamental analyst agent"
```

---

## Task 5: Risk analyst agent

**Files:**
- Create: `apps/agent/src/morningbrief/agents/risk.py`
- Create: `apps/agent/tests/agents/test_risk.py`

Risk uses LLM for narrative, but pre-computes the metrics deterministically (volatility, MDD) from prices then passes them to the LLM for scoring + summary. This keeps the math reliable.

- [ ] **Step 1: Write failing test**

`apps/agent/tests/agents/test_risk.py`:
```python
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
```

- [ ] **Step 2: Confirm RED**

```
.venv/Scripts/python.exe -m pytest tests/agents/test_risk.py -v
```

- [ ] **Step 3: Implementation**

`apps/agent/src/morningbrief/agents/risk.py`:
```python
import json
import math
from dataclasses import dataclass

from morningbrief.llm.base import LLM
from morningbrief.llm.prompts import RISK_SYSTEM


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

    # Daily returns
    rets = [(closes[i] / closes[i - 1] - 1.0) for i in range(1, len(closes))]
    mean_r = sum(rets) / len(rets)
    var = sum((r - mean_r) ** 2 for r in rets) / max(len(rets) - 1, 1)
    daily_vol = math.sqrt(var)
    annual_vol_pct = daily_vol * math.sqrt(252) * 100.0

    # Max drawdown
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


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


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
        score=_clamp(int(out.get("score", 50)), 0, 100),
        summary=str(out.get("summary", ""))[:240],
        metrics=metrics,
    )
```

- [ ] **Step 4: Confirm GREEN**

```
.venv/Scripts/python.exe -m pytest tests/agents/test_risk.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git -c user.email=djgnfj3795@gmail.com -c user.name="djgnfj3795" commit -m "feat(agent): add Risk analyst agent with deterministic metrics"
```

---

## Task 6: Top-3 scoring rule

**Files:**
- Create: `apps/agent/src/morningbrief/agents/scoring.py`
- Create: `apps/agent/tests/agents/test_scoring.py`

- [ ] **Step 1: Failing test**

`apps/agent/tests/agents/test_scoring.py`:
```python
from morningbrief.agents.scoring import score_combined, top_picks
from morningbrief.agents.fundamental import FundamentalResult
from morningbrief.agents.risk import RiskResult


def _f(t, s):
    return FundamentalResult(ticker=t, score=s, summary="", key_metrics={})


def _r(t, s):
    return RiskResult(ticker=t, score=s, summary="", metrics={})


def test_score_combined_weighted_06_04():
    # 0.6*80 + 0.4*60 = 48 + 24 = 72
    assert score_combined(_f("X", 80), _r("X", 60)) == 72.0


def test_top_picks_returns_top_n_by_combined_score():
    fundamentals = {
        "AAPL": _f("AAPL", 50),
        "NVDA": _f("NVDA", 90),
        "MSFT": _f("MSFT", 80),
        "AMZN": _f("AMZN", 60),
    }
    risks = {
        "AAPL": _r("AAPL", 60),
        "NVDA": _r("NVDA", 70),
        "MSFT": _r("MSFT", 50),
        "AMZN": _r("AMZN", 80),
    }
    picks = top_picks(fundamentals, risks, n=3)
    assert picks == ["NVDA", "MSFT", "AMZN"]
```

- [ ] **Step 2: RED**

```
.venv/Scripts/python.exe -m pytest tests/agents/test_scoring.py -v
```

- [ ] **Step 3: Implementation**

`apps/agent/src/morningbrief/agents/scoring.py`:
```python
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
```

- [ ] **Step 4: GREEN**

```
.venv/Scripts/python.exe -m pytest tests/agents/test_scoring.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git -c user.email=djgnfj3795@gmail.com -c user.name="djgnfj3795" commit -m "feat(agent): add rule-based top-3 scoring"
```

---

## Task 7: Bull / Bear / Supervisor debate

**Files:**
- Create: `apps/agent/src/morningbrief/agents/debate.py`
- Create: `apps/agent/tests/agents/test_debate.py`

- [ ] **Step 1: Failing test**

`apps/agent/tests/agents/test_debate.py`:
```python
from unittest.mock import MagicMock

from morningbrief.agents.debate import (
    bull_case, bear_case, supervisor,
    BullCase, BearCase, Verdict,
)
from morningbrief.agents.fundamental import FundamentalResult
from morningbrief.agents.risk import RiskResult


def _f():
    return FundamentalResult("NVDA", 80, "fund summary", {"pe": 65, "rev_yoy": 22})


def _r():
    return RiskResult("NVDA", 60, "risk summary", {"volatility_pct": 38, "max_drawdown_pct": -12})


def test_bull_case_returns_BullCase_using_premium_tier():
    llm = MagicMock()
    llm.complete_json.return_value = {
        "thesis": "Bull thesis", "key_metrics": ["pe=65"], "rebuttal": "Bear's point is...", "confidence": 78,
    }
    out = bull_case(llm, "NVDA", _f(), _r())
    assert isinstance(out, BullCase)
    assert out.confidence == 78
    assert out.thesis == "Bull thesis"
    assert llm.complete_json.call_args.kwargs["tier"] == "premium"


def test_bear_case_returns_BearCase():
    llm = MagicMock()
    llm.complete_json.return_value = {
        "thesis": "Bear thesis", "key_metrics": ["pe=65 high"], "rebuttal": "Bull missed...", "confidence": 55,
    }
    out = bear_case(llm, "NVDA", _f(), _r())
    assert isinstance(out, BearCase)
    assert out.confidence == 55


def test_supervisor_returns_HOLD_when_confidence_under_60():
    llm = MagicMock()
    llm.complete_json.return_value = {
        "signal": "BUY", "confidence": 45,  # supervisor returned BUY but confidence too low
        "thesis": "...", "what_would_change_my_mind": "...",
    }
    bull = BullCase("NVDA", "t", ["m"], "r", 50)
    bear = BearCase("NVDA", "t", ["m"], "r", 50)
    v = supervisor(llm, "NVDA", _f(), _r(), bull, bear)
    assert v.signal == "HOLD"
    assert v.confidence == 45


def test_supervisor_returns_BUY_when_signal_BUY_and_confidence_high():
    llm = MagicMock()
    llm.complete_json.return_value = {
        "signal": "BUY", "confidence": 78, "thesis": "t", "what_would_change_my_mind": "X",
    }
    bull = BullCase("NVDA", "t", ["m"], "r", 78)
    bear = BearCase("NVDA", "t", ["m"], "r", 50)
    v = supervisor(llm, "NVDA", _f(), _r(), bull, bear)
    assert v.signal == "BUY"
    assert v.confidence == 78
    assert v.what_would_change_my_mind == "X"
```

- [ ] **Step 2: RED**

```
.venv/Scripts/python.exe -m pytest tests/agents/test_debate.py -v
```

- [ ] **Step 3: Implementation**

`apps/agent/src/morningbrief/agents/debate.py`:
```python
import json
from dataclasses import dataclass
from typing import Literal

from morningbrief.llm.base import LLM
from morningbrief.llm.prompts import BULL_SYSTEM, BEAR_SYSTEM, SUPERVISOR_SYSTEM
from morningbrief.agents.fundamental import FundamentalResult
from morningbrief.agents.risk import RiskResult


Signal = Literal["BUY", "HOLD", "SELL"]


@dataclass(frozen=True)
class BullCase:
    ticker: str
    thesis: str
    key_metrics: list[str]
    rebuttal: str
    confidence: int


@dataclass(frozen=True)
class BearCase:
    ticker: str
    thesis: str
    key_metrics: list[str]
    rebuttal: str
    confidence: int


@dataclass(frozen=True)
class Verdict:
    ticker: str
    signal: Signal
    confidence: int
    thesis: str
    what_would_change_my_mind: str


def _user_for_debate(ticker: str, f: FundamentalResult, r: RiskResult) -> str:
    return (
        f"Ticker: {ticker}\n"
        f"Fundamental analysis: score={f.score}, summary={f.summary!r}, key_metrics={json.dumps(f.key_metrics)}\n"
        f"Risk analysis: score={r.score}, summary={r.summary!r}, metrics={json.dumps(r.metrics)}\n"
    )


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def bull_case(llm: LLM, ticker: str, f: FundamentalResult, r: RiskResult) -> BullCase:
    out = llm.complete_json(system=BULL_SYSTEM, user=_user_for_debate(ticker, f, r), tier="premium")
    return BullCase(
        ticker=ticker,
        thesis=str(out.get("thesis", "")),
        key_metrics=list(out.get("key_metrics", [])),
        rebuttal=str(out.get("rebuttal", "")),
        confidence=_clamp(int(out.get("confidence", 50)), 0, 100),
    )


def bear_case(llm: LLM, ticker: str, f: FundamentalResult, r: RiskResult) -> BearCase:
    out = llm.complete_json(system=BEAR_SYSTEM, user=_user_for_debate(ticker, f, r), tier="premium")
    return BearCase(
        ticker=ticker,
        thesis=str(out.get("thesis", "")),
        key_metrics=list(out.get("key_metrics", [])),
        rebuttal=str(out.get("rebuttal", "")),
        confidence=_clamp(int(out.get("confidence", 50)), 0, 100),
    )


def supervisor(
    llm: LLM,
    ticker: str,
    f: FundamentalResult,
    r: RiskResult,
    bull: BullCase,
    bear: BearCase,
) -> Verdict:
    user = (
        _user_for_debate(ticker, f, r)
        + f"Bull case: thesis={bull.thesis!r}, confidence={bull.confidence}, rebuttal={bull.rebuttal!r}\n"
        + f"Bear case: thesis={bear.thesis!r}, confidence={bear.confidence}, rebuttal={bear.rebuttal!r}\n"
    )
    out = llm.complete_json(system=SUPERVISOR_SYSTEM, user=user, tier="premium")
    raw_signal = str(out.get("signal", "HOLD")).upper()
    if raw_signal not in ("BUY", "HOLD", "SELL"):
        raw_signal = "HOLD"
    confidence = _clamp(int(out.get("confidence", 50)), 0, 100)
    # Rule: low confidence forces HOLD
    final_signal: Signal = "HOLD" if confidence < 60 else raw_signal  # type: ignore[assignment]
    return Verdict(
        ticker=ticker,
        signal=final_signal,
        confidence=confidence,
        thesis=str(out.get("thesis", "")),
        what_would_change_my_mind=str(out.get("what_would_change_my_mind", "")),
    )
```

- [ ] **Step 4: GREEN**

```
.venv/Scripts/python.exe -m pytest tests/agents/test_debate.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git -c user.email=djgnfj3795@gmail.com -c user.name="djgnfj3795" commit -m "feat(agent): add Bull/Bear/Supervisor debate agents"
```

---

## Task 8: LangGraph state + graph wiring

**Files:**
- Create: `apps/agent/src/morningbrief/pipeline/__init__.py` (empty)
- Create: `apps/agent/src/morningbrief/pipeline/state.py`
- Create: `apps/agent/src/morningbrief/pipeline/graph.py`
- Create: `apps/agent/tests/pipeline/__init__.py` (empty)
- Create: `apps/agent/tests/pipeline/test_graph.py`

The graph is straightforward — for each ticker run Fundamental + Risk in sequence (LangGraph doesn't trivially do dynamic fan-out for this pattern; we just iterate inside one node). Then ScoreAndRank → Bull → Bear → Supervisor for top 3.

We use a single LangGraph with these nodes: `analyze_universe` (fund+risk over all 10), `select_top3`, `debate_top3` (bull+bear+supervisor), `assemble_signals`. Persistence to Supabase happens in the orchestrator (Task 11), not inside the graph.

- [ ] **Step 1: Failing test**

`apps/agent/tests/pipeline/__init__.py`: empty.

`apps/agent/tests/pipeline/test_graph.py`:
```python
from datetime import date
from unittest.mock import MagicMock

from morningbrief.pipeline.graph import build_graph
from morningbrief.pipeline.state import PipelineState
from morningbrief.agents.fundamental import FundamentalResult
from morningbrief.agents.risk import RiskResult
from morningbrief.agents.debate import BullCase, BearCase, Verdict


def test_graph_runs_end_to_end_with_stub_agents(monkeypatch):
    # Stub each agent function to deterministic outputs
    def fake_fund(llm, ticker, financials, last_close):
        return FundamentalResult(ticker, score=80 if ticker == "NVDA" else 50, summary="f", key_metrics={})

    def fake_risk(llm, ticker, prices):
        return RiskResult(ticker, score=70 if ticker == "NVDA" else 40, summary="r",
                          metrics={"volatility_pct": 30, "max_drawdown_pct": -10, "sharpe_naive": 1.0})

    def fake_bull(llm, ticker, f, r):
        return BullCase(ticker, "bull thesis", ["m"], "rebut", 75)

    def fake_bear(llm, ticker, f, r):
        return BearCase(ticker, "bear thesis", ["m"], "rebut", 50)

    def fake_super(llm, ticker, f, r, b, br):
        return Verdict(ticker, "BUY", 78, "verdict thesis", "what changes")

    monkeypatch.setattr("morningbrief.pipeline.graph.analyze_fundamental", fake_fund)
    monkeypatch.setattr("morningbrief.pipeline.graph.analyze_risk", fake_risk)
    monkeypatch.setattr("morningbrief.pipeline.graph.bull_case", fake_bull)
    monkeypatch.setattr("morningbrief.pipeline.graph.bear_case", fake_bear)
    monkeypatch.setattr("morningbrief.pipeline.graph.supervisor", fake_super)

    universe = {
        t: {"financials": [{"period": "2026Q1", "revenue": 1.0}], "prices": [{"close": 100 + i} for i in range(60)]}
        for t in ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AVGO", "ORCL", "NFLX"]
    }

    initial: PipelineState = {
        "report_date": date(2026, 5, 1),
        "universe": universe,
        "fundamentals": {},
        "risks": {},
        "top3": [],
        "bulls": {},
        "bears": {},
        "verdicts": {},
        "signals": [],
    }

    graph = build_graph(llm=MagicMock())
    final = graph.invoke(initial)

    assert len(final["fundamentals"]) == 10
    assert len(final["risks"]) == 10
    assert "NVDA" in final["top3"]
    assert len(final["top3"]) == 3
    assert len(final["bulls"]) == 3
    assert len(final["bears"]) == 3
    assert len(final["verdicts"]) == 3
    assert len(final["signals"]) == 10
    # Top picks have is_top_pick=True
    nvda_signal = next(s for s in final["signals"] if s["ticker"] == "NVDA")
    assert nvda_signal["is_top_pick"] is True
    assert nvda_signal["signal"] == "BUY"
    # Non-top has is_top_pick=False and HOLD as default (no debate)
    aapl_signal = next(s for s in final["signals"] if s["ticker"] == "AAPL")
    assert aapl_signal["is_top_pick"] is False
```

- [ ] **Step 2: RED**

```
.venv/Scripts/python.exe -m pytest tests/pipeline/test_graph.py -v
```

- [ ] **Step 3: Write state**

`apps/agent/src/morningbrief/pipeline/__init__.py`: empty.

`apps/agent/src/morningbrief/pipeline/state.py`:
```python
from datetime import date
from typing import TypedDict

from morningbrief.agents.fundamental import FundamentalResult
from morningbrief.agents.risk import RiskResult
from morningbrief.agents.debate import BullCase, BearCase, Verdict


class TickerInputs(TypedDict):
    financials: list[dict]
    prices: list[dict]


class PipelineState(TypedDict):
    report_date: date
    universe: dict[str, TickerInputs]
    fundamentals: dict[str, FundamentalResult]
    risks: dict[str, RiskResult]
    top3: list[str]
    bulls: dict[str, BullCase]
    bears: dict[str, BearCase]
    verdicts: dict[str, Verdict]
    signals: list[dict]
```

- [ ] **Step 4: Write graph**

`apps/agent/src/morningbrief/pipeline/graph.py`:
```python
from typing import Any

from langgraph.graph import StateGraph, END

from morningbrief.agents.fundamental import analyze_fundamental
from morningbrief.agents.risk import analyze_risk
from morningbrief.agents.scoring import top_picks
from morningbrief.agents.debate import bull_case, bear_case, supervisor
from morningbrief.llm.base import LLM
from morningbrief.pipeline.state import PipelineState


def _node_analyze_universe(state: PipelineState, llm: LLM) -> dict:
    fundamentals = {}
    risks = {}
    for ticker, inputs in state["universe"].items():
        last_close = inputs["prices"][-1]["close"] if inputs["prices"] else 0.0
        fundamentals[ticker] = analyze_fundamental(
            llm=llm, ticker=ticker, financials=inputs["financials"], last_close=last_close
        )
        risks[ticker] = analyze_risk(llm=llm, ticker=ticker, prices=inputs["prices"])
    return {"fundamentals": fundamentals, "risks": risks}


def _node_select_top3(state: PipelineState) -> dict:
    return {"top3": top_picks(state["fundamentals"], state["risks"], n=3)}


def _node_debate_top3(state: PipelineState, llm: LLM) -> dict:
    bulls, bears, verdicts = {}, {}, {}
    for ticker in state["top3"]:
        f = state["fundamentals"][ticker]
        r = state["risks"][ticker]
        b = bull_case(llm, ticker, f, r)
        br = bear_case(llm, ticker, f, r)
        v = supervisor(llm, ticker, f, r, b, br)
        bulls[ticker] = b
        bears[ticker] = br
        verdicts[ticker] = v
    return {"bulls": bulls, "bears": bears, "verdicts": verdicts}


def _node_assemble_signals(state: PipelineState) -> dict:
    signals = []
    for ticker, f in state["fundamentals"].items():
        if ticker in state["verdicts"]:
            v = state["verdicts"][ticker]
            signals.append({
                "ticker": ticker,
                "signal": v.signal,
                "confidence": v.confidence,
                "thesis": v.thesis,
                "is_top_pick": True,
            })
        else:
            # Non-top: derive simple signal from combined score
            r = state["risks"][ticker]
            combined = 0.6 * f.score + 0.4 * r.score
            if combined >= 70:
                sig, conf = "BUY", int(combined)
            elif combined <= 35:
                sig, conf = "SELL", int(100 - combined)
            else:
                sig, conf = "HOLD", int(50 + abs(combined - 50) / 2)
            signals.append({
                "ticker": ticker,
                "signal": sig,
                "confidence": conf,
                "thesis": f.summary,
                "is_top_pick": False,
            })
    return {"signals": signals}


def build_graph(llm: LLM) -> Any:
    g = StateGraph(PipelineState)
    g.add_node("analyze_universe", lambda s: _node_analyze_universe(s, llm))
    g.add_node("select_top3", _node_select_top3)
    g.add_node("debate_top3", lambda s: _node_debate_top3(s, llm))
    g.add_node("assemble_signals", _node_assemble_signals)
    g.set_entry_point("analyze_universe")
    g.add_edge("analyze_universe", "select_top3")
    g.add_edge("select_top3", "debate_top3")
    g.add_edge("debate_top3", "assemble_signals")
    g.add_edge("assemble_signals", END)
    return g.compile()
```

- [ ] **Step 5: GREEN**

```
.venv/Scripts/python.exe -m pytest tests/pipeline/test_graph.py -v
```
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git -c user.email=djgnfj3795@gmail.com -c user.name="djgnfj3795" commit -m "feat(agent): add LangGraph state and graph wiring"
```

---

## Task 9: Markdown report renderer

**Files:**
- Create: `apps/agent/src/morningbrief/pipeline/render.py`
- Create: `apps/agent/tests/pipeline/test_render.py`

Renders the body shown in `docs/superpowers/specs/sample-report.md`. Inputs: `PipelineState` post-graph + an outcomes summary list (1-day prior outcomes for the auto-verification block).

- [ ] **Step 1: Failing test**

`apps/agent/tests/pipeline/test_render.py`:
```python
from datetime import date

from morningbrief.pipeline.render import render_report
from morningbrief.agents.fundamental import FundamentalResult
from morningbrief.agents.risk import RiskResult
from morningbrief.agents.debate import BullCase, BearCase, Verdict


def _state():
    return {
        "report_date": date(2026, 5, 1),
        "universe": {t: {"financials": [], "prices": [{"close": 100.0}]} for t in [
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AVGO", "ORCL", "NFLX"]},
        "fundamentals": {t: FundamentalResult(t, 60, f"{t} fund", {}) for t in [
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AVGO", "ORCL", "NFLX"]},
        "risks": {t: RiskResult(t, 50, f"{t} risk", {"volatility_pct": 30, "max_drawdown_pct": -10}) for t in [
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AVGO", "ORCL", "NFLX"]},
        "top3": ["NVDA", "MSFT", "AVGO"],
        "bulls": {
            "NVDA": BullCase("NVDA", "Bull NVDA", ["m"], "rebut", 78),
            "MSFT": BullCase("MSFT", "Bull MSFT", ["m"], "rebut", 65),
            "AVGO": BullCase("AVGO", "Bull AVGO", ["m"], "rebut", 71),
        },
        "bears": {
            "NVDA": BearCase("NVDA", "Bear NVDA", ["m"], "rebut", 60),
            "MSFT": BearCase("MSFT", "Bear MSFT", ["m"], "rebut", 55),
            "AVGO": BearCase("AVGO", "Bear AVGO", ["m"], "rebut", 50),
        },
        "verdicts": {
            "NVDA": Verdict("NVDA", "BUY", 78, "Verdict NVDA", "Catalyst X"),
            "MSFT": Verdict("MSFT", "BUY", 65, "Verdict MSFT", "Catalyst Y"),
            "AVGO": Verdict("AVGO", "HOLD", 58, "Verdict AVGO", "Catalyst Z"),
        },
        "signals": [
            {"ticker": "NVDA", "signal": "BUY", "confidence": 78, "thesis": "Verdict NVDA", "is_top_pick": True},
            {"ticker": "MSFT", "signal": "BUY", "confidence": 65, "thesis": "Verdict MSFT", "is_top_pick": True},
            {"ticker": "AVGO", "signal": "HOLD", "confidence": 58, "thesis": "Verdict AVGO", "is_top_pick": True},
            {"ticker": "AAPL", "signal": "HOLD", "confidence": 55, "thesis": "AAPL fund", "is_top_pick": False},
            {"ticker": "GOOGL", "signal": "HOLD", "confidence": 50, "thesis": "GOOGL fund", "is_top_pick": False},
            {"ticker": "AMZN", "signal": "HOLD", "confidence": 50, "thesis": "AMZN fund", "is_top_pick": False},
            {"ticker": "META", "signal": "HOLD", "confidence": 50, "thesis": "META fund", "is_top_pick": False},
            {"ticker": "TSLA", "signal": "HOLD", "confidence": 50, "thesis": "TSLA fund", "is_top_pick": False},
            {"ticker": "ORCL", "signal": "HOLD", "confidence": 50, "thesis": "ORCL fund", "is_top_pick": False},
            {"ticker": "NFLX", "signal": "HOLD", "confidence": 50, "thesis": "NFLX fund", "is_top_pick": False},
        ],
    }


def test_render_has_header_and_top3_sections():
    md = render_report(_state(), prior_outcomes=[])
    assert "MorningBrief — 2026-05-01" in md
    assert "## 🎯 오늘의 Top 3" in md
    assert "### 1. NVDA" in md
    assert "Bull Researcher" in md
    assert "Bear Researcher" in md
    assert "Supervisor" in md
    assert "What would change my mind" in md


def test_render_has_remaining_seven_table():
    md = render_report(_state(), prior_outcomes=[])
    assert "## 📊 나머지 7종 요약" in md
    for t in ["AAPL", "GOOGL", "AMZN", "META", "TSLA", "ORCL", "NFLX"]:
        assert f"| {t} " in md


def test_render_includes_outcomes_block_when_provided():
    outs = [
        {"ticker": "NVDA", "signal": "BUY", "return_1d": 2.1, "spy_return_1d": -0.8},
        {"ticker": "AAPL", "signal": "HOLD", "return_1d": 0.3, "spy_return_1d": -0.8},
    ]
    md = render_report(_state(), prior_outcomes=outs)
    assert "## 📈 어제 시그널 결과" in md
    assert "+2.1%" in md or "2.1%" in md


def test_render_skips_outcomes_block_when_empty():
    md = render_report(_state(), prior_outcomes=[])
    assert "## 📈 어제 시그널 결과" not in md
```

- [ ] **Step 2: RED**

```
.venv/Scripts/python.exe -m pytest tests/pipeline/test_render.py -v
```

- [ ] **Step 3: Implementation**

`apps/agent/src/morningbrief/pipeline/render.py`:
```python
from morningbrief.pipeline.state import PipelineState


def _format_top_section(state: PipelineState, ticker: str, idx: int) -> str:
    f = state["fundamentals"][ticker]
    r = state["risks"][ticker]
    bull = state["bulls"][ticker]
    bear = state["bears"][ticker]
    v = state["verdicts"][ticker]
    last_close = state["universe"][ticker]["prices"][-1]["close"] if state["universe"][ticker]["prices"] else 0.0

    return (
        f"### {idx}. {ticker} — **{v.signal}** (Confidence {v.confidence})\n\n"
        f"> 어제 종가 ${last_close:.2f} · 변동성 {r.metrics.get('volatility_pct', 0):.1f}% · "
        f"MDD {r.metrics.get('max_drawdown_pct', 0):.1f}%\n\n"
        f"**🐂 Bull Researcher**\n> {bull.thesis}\n>\n> {bull.rebuttal}\n\n"
        f"**🐻 Bear Researcher**\n> {bear.thesis}\n>\n> {bear.rebuttal}\n\n"
        f"**🎯 Supervisor 결정 — {v.signal} (Confidence {v.confidence})**\n\n"
        f"{v.thesis}\n\n"
        f"> **What would change my mind**: {v.what_would_change_my_mind}\n\n"
        f"---\n"
    )


def _format_remaining_table(state: PipelineState) -> str:
    rows = ["| 종목 | 시그널 | 신뢰도 | 한 줄 |", "|---|---|---|---|"]
    for s in state["signals"]:
        if s["is_top_pick"]:
            continue
        thesis = s["thesis"][:60].replace("|", " ")
        rows.append(f"| {s['ticker']} | {s['signal']} | {s['confidence']} | {thesis} |")
    return "\n".join(rows)


def _format_outcomes(outcomes: list[dict]) -> str:
    rows = ["| 종목 | 시그널 | 1일 수익률 | vs SPY |", "|---|---|---|---|"]
    for o in outcomes:
        r1 = o.get("return_1d")
        rspy = o.get("spy_return_1d", 0.0)
        if r1 is None:
            continue
        excess = r1 - rspy
        sign = "+" if r1 >= 0 else ""
        rows.append(
            f"| {o['ticker']} | {o['signal']} | **{sign}{r1:.1f}%** | "
            f"{'+' if excess >= 0 else ''}{excess:.1f}%p |"
        )
    return "\n".join(rows)


def render_report(state: PipelineState, prior_outcomes: list[dict]) -> str:
    parts: list[str] = []
    d = state["report_date"]
    parts.append(f"# 📈 MorningBrief — {d.isoformat()}\n")
    parts.append("## 🎯 오늘의 Top 3\n")
    for i, t in enumerate(state["top3"], start=1):
        parts.append(_format_top_section(state, t, i))
    parts.append("## 📊 나머지 7종 요약\n")
    parts.append(_format_remaining_table(state))
    parts.append("\n")
    if prior_outcomes:
        parts.append("## 📈 어제 시그널 결과\n")
        parts.append(_format_outcomes(prior_outcomes))
        parts.append("\n")
    parts.append("---\n")
    parts.append("> 본 메일은 정보 제공 목적이며 투자 자문이 아닙니다. 데이터: SEC EDGAR, Yahoo Finance.\n")
    return "\n".join(parts)
```

- [ ] **Step 4: GREEN**

```
.venv/Scripts/python.exe -m pytest tests/pipeline/test_render.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git -c user.email=djgnfj3795@gmail.com -c user.name="djgnfj3795" commit -m "feat(agent): add markdown report renderer"
```

---

## Task 10: Outcomes updater (1d/7d returns)

**Files:**
- Create: `apps/agent/src/morningbrief/pipeline/outcomes.py`
- Create: `apps/agent/tests/pipeline/test_outcomes.py`

For each `signal` whose corresponding `outcomes` row is missing `return_1d` or `return_7d`, look up `prices[ticker]` for the relevant trading days and compute close-to-close returns.

- [ ] **Step 1: Failing test**

`apps/agent/tests/pipeline/test_outcomes.py`:
```python
from datetime import date
from unittest.mock import MagicMock

from morningbrief.pipeline.outcomes import update_outcomes


def test_update_outcomes_writes_1d_return_when_one_trading_day_passed():
    """A signal from 2 trading days ago can have its 1d return filled."""
    mock_client = MagicMock()
    # Signals from 2 days ago, each with prices available
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "sig1", "ticker": "NVDA", "report_id": "r1", "signal": "BUY"},
    ]

    # prices_by_ticker_date stub: NVDA close on signal date = 100, +1 trading day = 102
    def fake_load_close(client, ticker, on_date):
        return {("NVDA", date(2026, 4, 28)): 100.0,
                ("NVDA", date(2026, 4, 29)): 102.0}.get((ticker, on_date))

    # Patch in the module
    import morningbrief.pipeline.outcomes as outcomes_mod
    outcomes_mod._load_close = fake_load_close  # monkey

    # We need: signal date = 2026-04-28, today = 2026-04-30 -> 1d trading day passed (29)
    n_updated = update_outcomes(
        mock_client,
        signals_with_dates=[("sig1", "NVDA", date(2026, 4, 28))],
        today=date(2026, 4, 30),
    )

    assert n_updated == 1
    # outcomes upsert called with computed return
    upsert_payload = mock_client.table.return_value.upsert.call_args[0][0]
    assert upsert_payload[0]["signal_id"] == "sig1"
    assert upsert_payload[0]["price_at_report"] == 100.0
    assert upsert_payload[0]["price_1d"] == 102.0
    assert round(upsert_payload[0]["return_1d"], 2) == 2.0  # +2%


def test_update_outcomes_skips_when_prices_not_yet_available():
    mock_client = MagicMock()

    import morningbrief.pipeline.outcomes as outcomes_mod
    outcomes_mod._load_close = lambda c, t, d: None  # no prices yet

    n = update_outcomes(
        mock_client,
        signals_with_dates=[("sig1", "NVDA", date(2026, 4, 29))],
        today=date(2026, 4, 30),
    )
    assert n == 0
    mock_client.table.return_value.upsert.assert_not_called()
```

- [ ] **Step 2: RED**

```
.venv/Scripts/python.exe -m pytest tests/pipeline/test_outcomes.py -v
```

- [ ] **Step 3: Implementation**

`apps/agent/src/morningbrief/pipeline/outcomes.py`:
```python
from datetime import date

from morningbrief.data.calendar import last_trading_day


def _load_close(client, ticker: str, on_date: date) -> float | None:
    resp = (
        client.table("prices")
        .select("close")
        .eq("ticker", ticker)
        .eq("date", on_date.isoformat())
        .execute()
    )
    if not resp.data:
        return None
    return float(resp.data[0]["close"])


def _next_trading_day(from_date: date, n: int) -> date:
    """Return the trading day exactly `n` sessions after `from_date`."""
    cur = from_date
    for _ in range(n):
        # Use last_trading_day on (cur+2) iteratively — but we need *next*, so step day-by-day
        cur = _step_to_next_session(cur)
    return cur


def _step_to_next_session(d: date) -> date:
    from datetime import timedelta
    from morningbrief.data.calendar import is_trading_day
    cur = d + timedelta(days=1)
    while not is_trading_day(cur):
        cur += timedelta(days=1)
    return cur


def update_outcomes(
    client,
    signals_with_dates: list[tuple[str, str, date]],  # (signal_id, ticker, signal_date)
    today: date,
) -> int:
    """For each signal, attempt to fill price_1d/return_1d (and price_7d/return_7d if 7 sessions passed)."""
    payloads = []
    for signal_id, ticker, signal_date in signals_with_dates:
        p0 = _load_close(client, ticker, signal_date)
        if p0 is None:
            continue
        row: dict = {"signal_id": signal_id, "price_at_report": p0}

        d1 = _step_to_next_session(signal_date)
        if d1 < today:
            p1 = _load_close(client, ticker, d1)
            if p1 is not None:
                row["price_1d"] = p1
                row["return_1d"] = round((p1 / p0 - 1.0) * 100.0, 4)

        d7 = signal_date
        for _ in range(7):
            d7 = _step_to_next_session(d7)
        if d7 < today:
            p7 = _load_close(client, ticker, d7)
            if p7 is not None:
                row["price_7d"] = p7
                row["return_7d"] = round((p7 / p0 - 1.0) * 100.0, 4)

        # Only upsert if we actually have a return to write
        if "return_1d" in row or "return_7d" in row:
            payloads.append(row)

    if payloads:
        client.table("outcomes").upsert(payloads).execute()
    return len(payloads)
```

- [ ] **Step 4: GREEN**

```
.venv/Scripts/python.exe -m pytest tests/pipeline/test_outcomes.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git -c user.email=djgnfj3795@gmail.com -c user.name="djgnfj3795" commit -m "feat(agent): add outcomes updater (1d/7d returns)"
```

---

## Task 11: Orchestrator (entry point)

**Files:**
- Create: `apps/agent/src/morningbrief/pipeline/orchestrator.py`
- Create: `apps/agent/tests/pipeline/test_orchestrator.py`

The orchestrator is the public entry point: load data → run graph → render → save. Send is Plan 3.

- [ ] **Step 1: Failing test**

`apps/agent/tests/pipeline/test_orchestrator.py`:
```python
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
```

- [ ] **Step 2: RED**

```
.venv/Scripts/python.exe -m pytest tests/pipeline/test_orchestrator.py -v
```

- [ ] **Step 3: Implementation**

`apps/agent/src/morningbrief/pipeline/orchestrator.py`:
```python
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

    body_md = render_report(final, prior_outcomes=[])  # outcomes injection: Plan 3 wires this

    report = {
        "date": report_date.isoformat(),
        "body_md": body_md,
        "trace_url": None,
        "cost_usd": 0.0,
    }
    return save_report_with_signals(client, report, final["signals"])
```

- [ ] **Step 4: GREEN + full suite**

```
.venv/Scripts/python.exe -m pytest tests/pipeline/test_orchestrator.py -v
.venv/Scripts/python.exe -m pytest -v
```
Expected: orchestrator 1 passed, full suite all green.

- [ ] **Step 5: Commit**

```bash
git -c user.email=djgnfj3795@gmail.com -c user.name="djgnfj3795" commit -m "feat(agent): add pipeline orchestrator entry point"
```

---

## Task 12: Real end-to-end smoke test

This is a manual verification that the pipeline works against real data with real OpenAI.

- [ ] **Step 1: Add OPENAI_API_KEY to `.env`**

Edit repo-root `.env`:
```
OPENAI_API_KEY=sk-...
```

- [ ] **Step 2: Create a tiny driver script**

`scripts/run_today.py`:
```python
"""Manual driver for end-to-end pipeline run."""
from __future__ import annotations

import logging
from datetime import date

from dotenv import load_dotenv

from morningbrief.pipeline.orchestrator import run_for_date

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

if __name__ == "__main__":
    load_dotenv()
    rid = run_for_date(date.today())
    print(f"Saved report: {rid}")
```

- [ ] **Step 3: Run**

```bash
PYTHONPATH=apps/agent/src apps/agent/.venv/Scripts/python.exe -m scripts.run_today
```

Expected runtime: ~2-3 minutes (10 fund + 10 risk on cheap, 3 bull + 3 bear + 3 supervisor on premium). Cost: ~$0.05.

- [ ] **Step 4: Verify in Supabase**

Use the supabase MCP to inspect:
```sql
SELECT id, date, length(body_md) FROM reports ORDER BY created_at DESC LIMIT 1;
SELECT ticker, signal, confidence, is_top_pick FROM signals
  WHERE report_id = (SELECT id FROM reports ORDER BY created_at DESC LIMIT 1)
  ORDER BY is_top_pick DESC, confidence DESC;
```

Expected:
- 1 report row with body_md > 1000 characters
- 10 signal rows, exactly 3 with `is_top_pick=true`

- [ ] **Step 5: Commit driver script**

```bash
git -c user.email=djgnfj3795@gmail.com -c user.name="djgnfj3795" commit -m "feat: add manual end-to-end driver script"
```

---

## Self-Review

**Spec coverage:**
- ✅ §5 LangGraph: Tasks 4-8
- ✅ §5.4 Top-3 scoring: Task 6
- ✅ §6 Markdown report: Task 9
- ✅ §9 LLM adapter: Task 3
- ✅ Outcomes updater: Task 10
- ✅ EDGAR fix: Task 1
- ⏭ Send (Resend): Plan 3
- ⏭ Astro frontend: Plan 3
- ⏭ GitHub Actions: Plan 3

**Type consistency:** `FundamentalResult`, `RiskResult`, `BullCase`, `BearCase`, `Verdict`, `PipelineState` used consistently across tasks.

**Placeholders:** None.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-30-plan2-agent-pipeline.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task with reviews
**2. Inline Execution** — execute in this session

Which approach?
