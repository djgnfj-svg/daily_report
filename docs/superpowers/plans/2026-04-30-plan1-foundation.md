# MorningBrief Plan 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bootstrap monorepo, provision Supabase schema, build data-source wrappers (yfinance, SEC EDGAR, NYSE calendar), and ship a `backfill.py` script that seeds 90 days of prices and the latest 4 quarters of financials for 10 tickers.

**Architecture:** Python `src/` layout under `apps/agent`. Thin pure-function wrappers around `yfinance` (prices), `sec-edgar-api`/raw HTTP (financials, filings), and `pandas-market-calendars` (trading days). Database access via `supabase-py` client. Backfill orchestrates wrappers and upserts into Supabase. TDD throughout — network calls mocked with `responses`/`pytest-mock`.

**Tech Stack:** Python 3.11, `uv` for package management (fast, modern), `pytest`, `yfinance`, `requests`, `pandas-market-calendars`, `supabase-py`, Supabase Postgres.

---

## Prerequisite: Supabase Project (one-time, manual)

Before Task 2, the user must create a Supabase project (free tier).

- [ ] **Create Supabase project**
  1. Go to https://supabase.com/dashboard, sign in, create new project
  2. Name: `morningbrief`, region: closest, password: store securely
  3. Wait for provisioning (~2 min)
  4. Settings → API → copy `Project URL` and `service_role` key (NOT anon key)
  5. Save these as local-only env values (used in Task 8 onward); they will become GitHub Actions secrets in Plan 3.

---

## File Structure

```
daily_report/
├── .gitignore                         # NEW
├── README.md                          # NEW (skeleton)
├── apps/
│   └── agent/
│       ├── pyproject.toml             # NEW
│       ├── README.md                  # NEW (per-app)
│       ├── src/
│       │   └── morningbrief/
│       │       ├── __init__.py
│       │       └── data/
│       │           ├── __init__.py
│       │           ├── tickers.py     # 10종 상수
│       │           ├── supabase_client.py
│       │           ├── yf.py          # yfinance 래퍼
│       │           ├── edgar.py       # SEC EDGAR 래퍼
│       │           └── calendar.py    # NYSE 캘린더
│       └── tests/
│           └── data/
│               ├── conftest.py
│               ├── test_tickers.py
│               ├── test_yf.py
│               ├── test_edgar.py
│               └── test_calendar.py
├── scripts/
│   └── backfill.py                    # NEW
└── supabase/
    └── migrations/
        └── 0001_init.sql              # NEW (7 tables)
```

Each file has one clear responsibility:
- `tickers.py` — single source of truth for the 10-ticker preset
- `supabase_client.py` — get a configured client, expose typed upsert helpers (later tasks)
- `yf.py` — `fetch_prices(ticker, start, end) -> list[PriceRow]`
- `edgar.py` — `fetch_quarterly_financials(ticker, n=4) -> list[FinancialRow]`, `fetch_recent_filings(ticker, since) -> list[FilingRow]`
- `calendar.py` — `is_trading_day(date)`, `last_trading_day(ref)`
- `backfill.py` — orchestration only, no business logic

---

## Task 1: Repo bootstrap (.gitignore + root README)

**Files:**
- Create: `.gitignore`
- Create: `README.md`

- [ ] **Step 1: Write `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.pytest_cache/
.coverage
htmlcov/

# Env / secrets
.env
.env.local
.env.*.local

# Node / Astro
node_modules/
dist/
.astro/
.vercel/

# OS
.DS_Store
Thumbs.db

# Editor
.idea/
.vscode/
*.swp

# Data dumps
*.csv
*.parquet
!apps/agent/tests/**/*.csv
```

- [ ] **Step 2: Write `README.md` skeleton**

```markdown
# MorningBrief

매일 아침 6시(KST), AI 멀티 에이전트가 분석한 미국 빅테크 10종 뉴스레터.

- Spec: [docs/superpowers/specs/2026-04-30-morningbrief-design.md](docs/superpowers/specs/2026-04-30-morningbrief-design.md)
- Sample report: [docs/superpowers/specs/sample-report.md](docs/superpowers/specs/sample-report.md)

## Monorepo

| Path | Purpose |
|---|---|
| `apps/agent` | Python LangGraph pipeline (Plan 2) |
| `apps/site` | Astro frontend + API routes (Plan 3) |
| `scripts/` | One-off scripts (backfill, backtest) |
| `supabase/migrations/` | DB schema |

Status: **Plan 1 in progress** (Foundation).
```

- [ ] **Step 3: Commit**

```bash
git add .gitignore README.md
git commit -m "chore: bootstrap repo with gitignore and README"
```

---

## Task 2: Supabase schema migration

**Files:**
- Create: `supabase/migrations/0001_init.sql`

- [ ] **Step 1: Write the migration SQL**

```sql
-- supabase/migrations/0001_init.sql
-- MorningBrief initial schema

CREATE TABLE prices (
  ticker TEXT NOT NULL,
  date DATE NOT NULL,
  open NUMERIC,
  high NUMERIC,
  low NUMERIC,
  close NUMERIC,
  volume BIGINT,
  PRIMARY KEY (ticker, date)
);

CREATE TABLE financials (
  ticker TEXT NOT NULL,
  period TEXT NOT NULL,
  revenue NUMERIC,
  net_income NUMERIC,
  eps NUMERIC,
  fcf NUMERIC,
  total_debt NUMERIC,
  total_equity NUMERIC,
  source TEXT,
  filed_at DATE,
  PRIMARY KEY (ticker, period)
);

CREATE TABLE filings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker TEXT NOT NULL,
  form_type TEXT,
  filed_at TIMESTAMPTZ,
  url TEXT,
  summary TEXT
);
CREATE INDEX ON filings(ticker, filed_at DESC);

CREATE TABLE reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  date DATE NOT NULL UNIQUE,
  body_md TEXT,
  trace_url TEXT,
  cost_usd NUMERIC(10,4),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE signals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  report_id UUID REFERENCES reports(id) ON DELETE CASCADE,
  ticker TEXT NOT NULL,
  signal TEXT CHECK(signal IN ('BUY','HOLD','SELL')),
  confidence INT,
  thesis TEXT,
  is_top_pick BOOLEAN DEFAULT FALSE
);
CREATE INDEX ON signals(report_id);
CREATE INDEX ON signals(ticker);

CREATE TABLE outcomes (
  signal_id UUID PRIMARY KEY REFERENCES signals(id) ON DELETE CASCADE,
  price_at_report NUMERIC,
  price_1d NUMERIC,
  price_7d NUMERIC,
  return_1d NUMERIC,
  return_7d NUMERIC
);

CREATE TABLE subscribers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('pending','confirmed','unsubscribed')),
  confirm_token TEXT UNIQUE,
  unsub_token TEXT UNIQUE NOT NULL,
  confirmed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ON subscribers(status);

-- RLS: lock everything; service_role bypasses RLS automatically.
ALTER TABLE prices       ENABLE ROW LEVEL SECURITY;
ALTER TABLE financials   ENABLE ROW LEVEL SECURITY;
ALTER TABLE filings      ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports      ENABLE ROW LEVEL SECURITY;
ALTER TABLE signals      ENABLE ROW LEVEL SECURITY;
ALTER TABLE outcomes     ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscribers  ENABLE ROW LEVEL SECURITY;
```

- [ ] **Step 2: Apply migration (manual, one-time)**

In Supabase Dashboard → SQL Editor → paste the file contents → Run.

Verify in Table Editor that all 7 tables exist.

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/0001_init.sql
git commit -m "feat(db): add initial schema with 7 tables and RLS"
```

---

## Task 3: Python project setup (pyproject.toml + pytest)

**Files:**
- Create: `apps/agent/pyproject.toml`
- Create: `apps/agent/README.md`
- Create: `apps/agent/src/morningbrief/__init__.py`
- Create: `apps/agent/src/morningbrief/data/__init__.py`
- Create: `apps/agent/tests/__init__.py`
- Create: `apps/agent/tests/data/__init__.py`

- [ ] **Step 1: Write `apps/agent/pyproject.toml`**

```toml
[project]
name = "morningbrief"
version = "0.1.0"
description = "MorningBrief AI newsletter agent pipeline"
requires-python = ">=3.11"
dependencies = [
  "yfinance>=0.2.40",
  "requests>=2.31",
  "pandas>=2.2",
  "pandas-market-calendars>=4.4",
  "supabase>=2.5",
  "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0",
  "pytest-mock>=3.12",
  "responses>=0.25",
  "ruff>=0.4",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/morningbrief"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]

[tool.ruff]
line-length = 100
target-version = "py311"
```

- [ ] **Step 2: Write empty `__init__.py` files**

Create all four with empty content:
- `apps/agent/src/morningbrief/__init__.py`
- `apps/agent/src/morningbrief/data/__init__.py`
- `apps/agent/tests/__init__.py`
- `apps/agent/tests/data/__init__.py`

- [ ] **Step 3: Write `apps/agent/README.md`**

```markdown
# apps/agent

Python LangGraph pipeline.

## Setup

```bash
cd apps/agent
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Copy `.env.example` to `.env` (created in later tasks).

## Test

```bash
pytest -v
```
```

- [ ] **Step 4: Install dependencies and verify pytest discovers nothing yet**

Run (from `apps/agent`):
```bash
python -m venv .venv
.venv\Scripts\activate    # Windows
pip install -e ".[dev]"
pytest -v
```

Expected: `no tests ran in 0.XXs` (no failures, just empty).

- [ ] **Step 5: Commit**

```bash
git add apps/agent/pyproject.toml apps/agent/README.md apps/agent/src apps/agent/tests
git commit -m "chore(agent): scaffold python project with pytest"
```

---

## Task 4: `tickers.py` constant

**Files:**
- Create: `apps/agent/src/morningbrief/data/tickers.py`
- Test: `apps/agent/tests/data/test_tickers.py`

- [ ] **Step 1: Write the failing test**

`apps/agent/tests/data/test_tickers.py`:
```python
from morningbrief.data.tickers import TICKERS

def test_tickers_are_the_ten_big_techs():
    assert TICKERS == [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META",
        "NVDA", "TSLA", "AVGO", "ORCL", "NFLX",
    ]

def test_tickers_are_unique():
    assert len(TICKERS) == len(set(TICKERS))
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/data/test_tickers.py -v
```
Expected: ImportError / ModuleNotFoundError on `morningbrief.data.tickers`.

- [ ] **Step 3: Write the implementation**

`apps/agent/src/morningbrief/data/tickers.py`:
```python
TICKERS: list[str] = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META",
    "NVDA", "TSLA", "AVGO", "ORCL", "NFLX",
]
```

- [ ] **Step 4: Run tests, expect PASS**

```bash
pytest tests/data/test_tickers.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/agent/src/morningbrief/data/tickers.py apps/agent/tests/data/test_tickers.py
git commit -m "feat(agent): add 10-ticker preset constant"
```

---

## Task 5: NYSE trading-day calendar

**Files:**
- Create: `apps/agent/src/morningbrief/data/calendar.py`
- Test: `apps/agent/tests/data/test_calendar.py`

- [ ] **Step 1: Write the failing test**

`apps/agent/tests/data/test_calendar.py`:
```python
from datetime import date
from morningbrief.data.calendar import is_trading_day, last_trading_day

def test_christmas_2025_is_not_trading_day():
    assert is_trading_day(date(2025, 12, 25)) is False

def test_normal_weekday_is_trading_day():
    # 2025-12-22 was a Monday, normal trading day
    assert is_trading_day(date(2025, 12, 22)) is True

def test_saturday_is_not_trading_day():
    # 2025-12-20 was Saturday
    assert is_trading_day(date(2025, 12, 20)) is False

def test_last_trading_day_skips_weekend():
    # Sunday 2025-12-21 → previous Friday 2025-12-19
    assert last_trading_day(date(2025, 12, 21)) == date(2025, 12, 19)

def test_last_trading_day_skips_christmas():
    # 2025-12-26 (Friday after Christmas) → Wednesday 2025-12-24 (early close, still trading) — actually NYSE half-day on 12/24 still counts.
    # Use a clearer case: day after Christmas should return 12/24 (half-day).
    assert last_trading_day(date(2025, 12, 26)) == date(2025, 12, 24)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/data/test_calendar.py -v
```
Expected: ImportError on `morningbrief.data.calendar`.

- [ ] **Step 3: Write the implementation**

`apps/agent/src/morningbrief/data/calendar.py`:
```python
from datetime import date, timedelta
from functools import lru_cache

import pandas_market_calendars as mcal

_NYSE = mcal.get_calendar("NYSE")


@lru_cache(maxsize=1024)
def _trading_days_set(year: int) -> frozenset[date]:
    schedule = _NYSE.schedule(start_date=f"{year}-01-01", end_date=f"{year}-12-31")
    return frozenset(d.date() for d in schedule.index)


def is_trading_day(d: date) -> bool:
    return d in _trading_days_set(d.year)


def last_trading_day(ref: date) -> date:
    """Return the most recent trading day strictly on or before `ref` minus one day.

    i.e. last_trading_day(today) = the previous session's date.
    """
    candidate = ref - timedelta(days=1)
    while not is_trading_day(candidate):
        candidate -= timedelta(days=1)
    return candidate
```

- [ ] **Step 4: Run tests, expect PASS**

```bash
pytest tests/data/test_calendar.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/agent/src/morningbrief/data/calendar.py apps/agent/tests/data/test_calendar.py
git commit -m "feat(agent): add NYSE trading-day calendar helpers"
```

---

## Task 6: yfinance price wrapper

**Files:**
- Create: `apps/agent/src/morningbrief/data/yf.py`
- Test: `apps/agent/tests/data/test_yf.py`
- Create: `apps/agent/tests/data/conftest.py`

The wrapper exposes `fetch_prices(ticker, start, end) -> list[PriceRow]`. We test against a stub `yfinance.Ticker` injected via monkeypatch (no network).

- [ ] **Step 1: Write the failing test**

`apps/agent/tests/data/conftest.py`:
```python
import pandas as pd
import pytest


@pytest.fixture
def fake_yf_history():
    """Returns a factory that builds a yfinance-shaped DataFrame."""
    def _make(rows):
        # rows: list[(date_str, open, high, low, close, volume)]
        df = pd.DataFrame(
            [{"Open": o, "High": h, "Low": l, "Close": c, "Volume": v} for _, o, h, l, c, v in rows],
            index=pd.DatetimeIndex([d for d, *_ in rows], name="Date"),
        )
        return df
    return _make
```

`apps/agent/tests/data/test_yf.py`:
```python
from datetime import date
from morningbrief.data.yf import fetch_prices, PriceRow


def test_fetch_prices_returns_rows(monkeypatch, fake_yf_history):
    df = fake_yf_history([
        ("2026-04-28", 100.0, 102.0, 99.0, 101.0, 1_000_000),
        ("2026-04-29", 101.0, 103.0, 100.5, 102.5, 1_200_000),
    ])

    class FakeTicker:
        def __init__(self, sym): self.sym = sym
        def history(self, start, end, auto_adjust=False):
            return df

    monkeypatch.setattr("morningbrief.data.yf.yf.Ticker", FakeTicker)

    rows = fetch_prices("NVDA", date(2026, 4, 28), date(2026, 4, 30))

    assert rows == [
        PriceRow(ticker="NVDA", date=date(2026, 4, 28),
                 open=100.0, high=102.0, low=99.0, close=101.0, volume=1_000_000),
        PriceRow(ticker="NVDA", date=date(2026, 4, 29),
                 open=101.0, high=103.0, low=100.5, close=102.5, volume=1_200_000),
    ]


def test_fetch_prices_empty_returns_empty_list(monkeypatch, fake_yf_history):
    df = fake_yf_history([])

    class FakeTicker:
        def __init__(self, sym): pass
        def history(self, **kw): return df

    monkeypatch.setattr("morningbrief.data.yf.yf.Ticker", FakeTicker)
    assert fetch_prices("XXXX", date(2026, 4, 28), date(2026, 4, 30)) == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/data/test_yf.py -v
```
Expected: ImportError on `morningbrief.data.yf`.

- [ ] **Step 3: Write the implementation**

`apps/agent/src/morningbrief/data/yf.py`:
```python
from dataclasses import dataclass
from datetime import date

import yfinance as yf


@dataclass(frozen=True)
class PriceRow:
    ticker: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


def fetch_prices(ticker: str, start: date, end: date) -> list[PriceRow]:
    """Fetch daily OHLCV bars [start, end) inclusive of start, exclusive of end (yfinance convention).

    Returns empty list if yfinance returns no rows.
    """
    df = yf.Ticker(ticker).history(start=start.isoformat(), end=end.isoformat(), auto_adjust=False)
    rows: list[PriceRow] = []
    for ts, r in df.iterrows():
        rows.append(PriceRow(
            ticker=ticker,
            date=ts.date() if hasattr(ts, "date") else ts,
            open=float(r["Open"]),
            high=float(r["High"]),
            low=float(r["Low"]),
            close=float(r["Close"]),
            volume=int(r["Volume"]),
        ))
    return rows
```

- [ ] **Step 4: Run tests, expect PASS**

```bash
pytest tests/data/test_yf.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/agent/src/morningbrief/data/yf.py apps/agent/tests/data/test_yf.py apps/agent/tests/data/conftest.py
git commit -m "feat(agent): add yfinance price wrapper"
```

---

## Task 7: SEC EDGAR financials wrapper

The financials endpoint we use is `https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{tag}.json`. For MVP we fetch revenue, net income, EPS, total debt, total equity per quarter via `companyfacts`. We mock all HTTP via `responses`.

A simpler approach: use SEC's `/api/xbrl/companyfacts/CIK{cik}.json` (single call returns all tags), parse the latest 4 quarters of needed concepts.

**Files:**
- Create: `apps/agent/src/morningbrief/data/edgar.py`
- Test: `apps/agent/tests/data/test_edgar.py`
- Create: `apps/agent/tests/data/fixtures/edgar_aapl_facts.json` (small fixture)

- [ ] **Step 1: Create the fixture**

Save `apps/agent/tests/data/fixtures/edgar_aapl_facts.json` (a minimal stub — the real file is huge; we only need the tags we use):

```json
{
  "cik": 320193,
  "entityName": "Apple Inc.",
  "facts": {
    "us-gaap": {
      "Revenues": {
        "units": {
          "USD": [
            {"end": "2025-12-28", "val": 124300000000, "fp": "Q1", "fy": 2026, "form": "10-Q", "filed": "2026-01-30"},
            {"end": "2025-09-28", "val": 119000000000, "fp": "FY", "fy": 2025, "form": "10-K", "filed": "2025-10-31"},
            {"end": "2025-06-29", "val": 95000000000,  "fp": "Q3", "fy": 2025, "form": "10-Q", "filed": "2025-07-31"},
            {"end": "2025-03-30", "val": 90000000000,  "fp": "Q2", "fy": 2025, "form": "10-Q", "filed": "2025-04-30"},
            {"end": "2024-12-28", "val": 117000000000, "fp": "Q1", "fy": 2025, "form": "10-Q", "filed": "2025-01-31"}
          ]
        }
      },
      "NetIncomeLoss": {
        "units": {
          "USD": [
            {"end": "2025-12-28", "val": 36000000000, "fp": "Q1", "fy": 2026, "form": "10-Q", "filed": "2026-01-30"},
            {"end": "2025-09-28", "val": 30000000000, "fp": "FY", "fy": 2025, "form": "10-K", "filed": "2025-10-31"},
            {"end": "2025-06-29", "val": 22000000000, "fp": "Q3", "fy": 2025, "form": "10-Q", "filed": "2025-07-31"},
            {"end": "2025-03-30", "val": 20000000000, "fp": "Q2", "fy": 2025, "form": "10-Q", "filed": "2025-04-30"}
          ]
        }
      },
      "EarningsPerShareBasic": {
        "units": {
          "USD/shares": [
            {"end": "2025-12-28", "val": 2.40, "fp": "Q1", "fy": 2026, "form": "10-Q", "filed": "2026-01-30"},
            {"end": "2025-09-28", "val": 2.00, "fp": "FY", "fy": 2025, "form": "10-K", "filed": "2025-10-31"},
            {"end": "2025-06-29", "val": 1.45, "fp": "Q3", "fy": 2025, "form": "10-Q", "filed": "2025-07-31"},
            {"end": "2025-03-30", "val": 1.30, "fp": "Q2", "fy": 2025, "form": "10-Q", "filed": "2025-04-30"}
          ]
        }
      },
      "LongTermDebt": {
        "units": {
          "USD": [
            {"end": "2025-12-28", "val": 95000000000, "fp": "Q1", "fy": 2026, "form": "10-Q", "filed": "2026-01-30"}
          ]
        }
      },
      "StockholdersEquity": {
        "units": {
          "USD": [
            {"end": "2025-12-28", "val": 65000000000, "fp": "Q1", "fy": 2026, "form": "10-Q", "filed": "2026-01-30"}
          ]
        }
      }
    }
  }
}
```

- [ ] **Step 2: Write the failing test**

`apps/agent/tests/data/test_edgar.py`:
```python
import json
from datetime import date
from pathlib import Path

import pytest
import responses

from morningbrief.data.edgar import (
    fetch_quarterly_financials,
    FinancialRow,
    TICKER_TO_CIK,
)


FIXTURE = Path(__file__).parent / "fixtures" / "edgar_aapl_facts.json"


@responses.activate
def test_fetch_quarterly_financials_returns_recent_quarters():
    cik_padded = str(TICKER_TO_CIK["AAPL"]).zfill(10)
    responses.add(
        responses.GET,
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json",
        json=json.loads(FIXTURE.read_text()),
        status=200,
    )

    rows = fetch_quarterly_financials("AAPL", n=4)

    assert len(rows) == 4
    # Most recent first
    assert rows[0] == FinancialRow(
        ticker="AAPL",
        period="2026Q1",
        revenue=124_300_000_000,
        net_income=36_000_000_000,
        eps=2.40,
        fcf=None,                   # we don't compute FCF in MVP fixture
        total_debt=95_000_000_000,
        total_equity=65_000_000_000,
        source="10-Q",
        filed_at=date(2026, 1, 30),
    )
    # Order check
    assert [r.period for r in rows] == ["2026Q1", "2025FY", "2025Q3", "2025Q2"]


def test_ticker_to_cik_covers_all_ten():
    expected = {"AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AVGO", "ORCL", "NFLX"}
    assert expected.issubset(TICKER_TO_CIK.keys())
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/data/test_edgar.py -v
```
Expected: ImportError on `morningbrief.data.edgar`.

- [ ] **Step 4: Write the implementation**

`apps/agent/src/morningbrief/data/edgar.py`:
```python
from dataclasses import dataclass
from datetime import date
from typing import Any

import requests

# CIK numbers from https://www.sec.gov/cgi-bin/browse-edgar (verified 2026)
TICKER_TO_CIK: dict[str, int] = {
    "AAPL":  320193,
    "MSFT":  789019,
    "GOOGL": 1652044,
    "AMZN":  1018724,
    "META":  1326801,
    "NVDA":  1045810,
    "TSLA":  1318605,
    "AVGO":  1730168,
    "ORCL":  1341439,
    "NFLX":  1065280,
}

USER_AGENT = "MorningBrief research bot contact@reseeall.com"


@dataclass(frozen=True)
class FinancialRow:
    ticker: str
    period: str           # '2026Q1' or '2025FY'
    revenue: float | None
    net_income: float | None
    eps: float | None
    fcf: float | None
    total_debt: float | None
    total_equity: float | None
    source: str           # '10-Q' or '10-K'
    filed_at: date


def _fetch_company_facts(cik: int) -> dict[str, Any]:
    cik_padded = str(cik).zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _period_label(fp: str, fy: int) -> str:
    return f"{fy}{fp}" if fp == "FY" else f"{fy}{fp}"


def _index_concept(facts: dict, tag: str, unit: str) -> dict[str, dict]:
    """Return {period_label: entry} keyed by FY+FP."""
    entries = facts.get("facts", {}).get("us-gaap", {}).get(tag, {}).get("units", {}).get(unit, [])
    out: dict[str, dict] = {}
    for e in entries:
        label = _period_label(e["fp"], e["fy"])
        # Keep latest filing per period
        if label not in out or e["filed"] > out[label]["filed"]:
            out[label] = e
    return out


def fetch_quarterly_financials(ticker: str, n: int = 4) -> list[FinancialRow]:
    """Return the most recent `n` quarterly/annual periods, newest first."""
    if ticker not in TICKER_TO_CIK:
        raise ValueError(f"Unknown ticker: {ticker}")
    facts = _fetch_company_facts(TICKER_TO_CIK[ticker])

    revenue = _index_concept(facts, "Revenues", "USD")
    net_income = _index_concept(facts, "NetIncomeLoss", "USD")
    eps = _index_concept(facts, "EarningsPerShareBasic", "USD/shares")
    debt = _index_concept(facts, "LongTermDebt", "USD")
    equity = _index_concept(facts, "StockholdersEquity", "USD")

    # Period universe = revenue keys (most reliable)
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

- [ ] **Step 5: Run tests, expect PASS**

```bash
pytest tests/data/test_edgar.py -v
```
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add apps/agent/src/morningbrief/data/edgar.py apps/agent/tests/data/test_edgar.py apps/agent/tests/data/fixtures/edgar_aapl_facts.json
git commit -m "feat(agent): add SEC EDGAR quarterly financials wrapper"
```

---

## Task 8: SEC EDGAR filings (8-K) wrapper

Endpoint: `https://data.sec.gov/submissions/CIK{cik}.json` returns recent filings list.

**Files:**
- Modify: `apps/agent/src/morningbrief/data/edgar.py` (add `fetch_recent_filings` + `FilingRow`)
- Modify: `apps/agent/tests/data/test_edgar.py` (add tests)
- Create: `apps/agent/tests/data/fixtures/edgar_aapl_submissions.json`

- [ ] **Step 1: Create the fixture**

`apps/agent/tests/data/fixtures/edgar_aapl_submissions.json`:
```json
{
  "cik": "320193",
  "name": "Apple Inc.",
  "filings": {
    "recent": {
      "accessionNumber": ["0000320193-26-000010", "0000320193-26-000009", "0000320193-26-000008"],
      "filingDate":      ["2026-04-29",            "2026-04-15",            "2026-01-30"],
      "form":            ["8-K",                   "8-K",                   "10-Q"],
      "primaryDocument": ["aapl_8k_20260429.htm",  "aapl_8k_20260415.htm",  "aapl_10q_20260130.htm"],
      "primaryDocDescription": ["Current report",  "Current report",        "Quarterly report"]
    }
  }
}
```

- [ ] **Step 2: Write the failing test**

Append to `apps/agent/tests/data/test_edgar.py`:
```python
from datetime import datetime, timezone

from morningbrief.data.edgar import fetch_recent_filings, FilingRow


SUBM_FIXTURE = Path(__file__).parent / "fixtures" / "edgar_aapl_submissions.json"


@responses.activate
def test_fetch_recent_filings_8k_only():
    cik_padded = str(TICKER_TO_CIK["AAPL"]).zfill(10)
    responses.add(
        responses.GET,
        f"https://data.sec.gov/submissions/CIK{cik_padded}.json",
        json=json.loads(SUBM_FIXTURE.read_text()),
        status=200,
    )

    since = date(2026, 4, 1)
    rows = fetch_recent_filings("AAPL", since=since, form_types=("8-K",))

    assert len(rows) == 2
    assert rows[0].ticker == "AAPL"
    assert rows[0].form_type == "8-K"
    assert rows[0].filed_at.date() == date(2026, 4, 29)
    assert "aapl_8k_20260429.htm" in rows[0].url


@responses.activate
def test_fetch_recent_filings_filters_by_since():
    cik_padded = str(TICKER_TO_CIK["AAPL"]).zfill(10)
    responses.add(
        responses.GET,
        f"https://data.sec.gov/submissions/CIK{cik_padded}.json",
        json=json.loads(SUBM_FIXTURE.read_text()),
        status=200,
    )

    rows = fetch_recent_filings("AAPL", since=date(2026, 4, 20), form_types=("8-K",))
    assert len(rows) == 1
    assert rows[0].filed_at.date() == date(2026, 4, 29)
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/data/test_edgar.py -v
```
Expected: 2 new tests fail with ImportError on `fetch_recent_filings`/`FilingRow`.

- [ ] **Step 4: Add the implementation**

Append to `apps/agent/src/morningbrief/data/edgar.py`:
```python
from datetime import datetime


@dataclass(frozen=True)
class FilingRow:
    ticker: str
    form_type: str
    filed_at: datetime
    url: str


def _fetch_submissions(cik: int) -> dict[str, Any]:
    cik_padded = str(cik).zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
    resp.raise_for_status()
    return resp.json()


def fetch_recent_filings(
    ticker: str,
    since: date,
    form_types: tuple[str, ...] = ("8-K",),
) -> list[FilingRow]:
    """Return filings of given form types filed on/after `since`, newest first."""
    if ticker not in TICKER_TO_CIK:
        raise ValueError(f"Unknown ticker: {ticker}")
    cik = TICKER_TO_CIK[ticker]
    data = _fetch_submissions(cik)
    recent = data["filings"]["recent"]

    rows: list[FilingRow] = []
    for i, form in enumerate(recent["form"]):
        if form not in form_types:
            continue
        filed = date.fromisoformat(recent["filingDate"][i])
        if filed < since:
            continue
        accession = recent["accessionNumber"][i].replace("-", "")
        primary = recent["primaryDocument"][i]
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{primary}"
        rows.append(FilingRow(
            ticker=ticker,
            form_type=form,
            filed_at=datetime(filed.year, filed.month, filed.day, tzinfo=timezone.utc),
            url=url,
        ))
    return rows
```

Also add at top of `edgar.py`: `from datetime import datetime, timezone` (merge with existing date import).

- [ ] **Step 5: Run tests, expect PASS**

```bash
pytest tests/data/test_edgar.py -v
```
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add apps/agent/src/morningbrief/data/edgar.py apps/agent/tests/data/test_edgar.py apps/agent/tests/data/fixtures/edgar_aapl_submissions.json
git commit -m "feat(agent): add SEC EDGAR 8-K filings wrapper"
```

---

## Task 9: Supabase client + typed upserts

**Files:**
- Create: `apps/agent/src/morningbrief/data/supabase_client.py`
- Test: `apps/agent/tests/data/test_supabase_client.py`
- Create: `apps/agent/.env.example`

- [ ] **Step 1: Create `.env.example`**

`apps/agent/.env.example`:
```
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_KEY=eyJ...service_role_key_NOT_anon
```

Tell user to copy `.env.example` to `.env` and fill values from the project they created in the prerequisite step. `.env` is already gitignored.

- [ ] **Step 2: Write the failing test**

`apps/agent/tests/data/test_supabase_client.py`:
```python
from datetime import date
from unittest.mock import MagicMock

from morningbrief.data.supabase_client import upsert_prices, upsert_financials
from morningbrief.data.yf import PriceRow
from morningbrief.data.edgar import FinancialRow


def test_upsert_prices_calls_supabase_with_correct_payload():
    mock_client = MagicMock()
    rows = [
        PriceRow(ticker="NVDA", date=date(2026, 4, 28),
                 open=100.0, high=102.0, low=99.0, close=101.0, volume=1_000_000),
    ]

    upsert_prices(mock_client, rows)

    mock_client.table.assert_called_once_with("prices")
    upsert_call = mock_client.table.return_value.upsert
    payload = upsert_call.call_args[0][0]
    assert payload == [{
        "ticker": "NVDA",
        "date": "2026-04-28",
        "open": 100.0,
        "high": 102.0,
        "low": 99.0,
        "close": 101.0,
        "volume": 1_000_000,
    }]
    upsert_call.return_value.execute.assert_called_once()


def test_upsert_prices_empty_list_is_noop():
    mock_client = MagicMock()
    upsert_prices(mock_client, [])
    mock_client.table.assert_not_called()


def test_upsert_financials_serializes_dates():
    mock_client = MagicMock()
    rows = [
        FinancialRow(ticker="AAPL", period="2026Q1",
                     revenue=124e9, net_income=36e9, eps=2.40, fcf=None,
                     total_debt=95e9, total_equity=65e9,
                     source="10-Q", filed_at=date(2026, 1, 30)),
    ]
    upsert_financials(mock_client, rows)
    payload = mock_client.table.return_value.upsert.call_args[0][0]
    assert payload[0]["filed_at"] == "2026-01-30"
    assert payload[0]["period"] == "2026Q1"
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/data/test_supabase_client.py -v
```
Expected: ImportError on `morningbrief.data.supabase_client`.

- [ ] **Step 4: Write the implementation**

`apps/agent/src/morningbrief/data/supabase_client.py`:
```python
import os
from dataclasses import asdict
from datetime import date, datetime
from typing import Any

from supabase import create_client, Client

from morningbrief.data.yf import PriceRow
from morningbrief.data.edgar import FinancialRow, FilingRow


def get_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _row_to_dict(row: Any) -> dict:
    return {k: _serialize(v) for k, v in asdict(row).items()}


def upsert_prices(client: Client, rows: list[PriceRow]) -> None:
    if not rows:
        return
    payload = [_row_to_dict(r) for r in rows]
    client.table("prices").upsert(payload).execute()


def upsert_financials(client: Client, rows: list[FinancialRow]) -> None:
    if not rows:
        return
    payload = [_row_to_dict(r) for r in rows]
    client.table("financials").upsert(payload).execute()


def insert_filings(client: Client, rows: list[FilingRow]) -> None:
    if not rows:
        return
    payload = [_row_to_dict(r) for r in rows]
    # No PK on natural key, but accession URL is unique enough — for MVP use plain insert
    # and rely on upstream caller to skip already-seen ones (Plan 2 will track last_seen).
    client.table("filings").insert(payload).execute()
```

- [ ] **Step 5: Run tests, expect PASS**

```bash
pytest tests/data/test_supabase_client.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add apps/agent/src/morningbrief/data/supabase_client.py apps/agent/tests/data/test_supabase_client.py apps/agent/.env.example
git commit -m "feat(agent): add Supabase client and typed upsert helpers"
```

---

## Task 10: `scripts/backfill.py`

Orchestrates: for each of the 10 tickers, fetch 90 days of prices and the latest 4 quarters of financials, upsert into Supabase.

**Files:**
- Create: `scripts/backfill.py`
- Test: `apps/agent/tests/test_backfill.py`

The script is thin orchestration. Test by patching `fetch_prices`, `fetch_quarterly_financials`, and the Supabase client.

- [ ] **Step 1: Write the failing test**

`apps/agent/tests/test_backfill.py`:
```python
from datetime import date
from unittest.mock import MagicMock, patch

from morningbrief.data.yf import PriceRow
from morningbrief.data.edgar import FinancialRow


def test_backfill_runs_for_all_tickers():
    fake_prices = [PriceRow("X", date(2026, 4, 1), 1, 1, 1, 1, 100)]
    fake_fin = [FinancialRow("X", "2026Q1", 1, 1, 1, None, 1, 1, "10-Q", date(2026, 4, 1))]

    with patch("scripts.backfill.fetch_prices", return_value=fake_prices) as mp, \
         patch("scripts.backfill.fetch_quarterly_financials", return_value=fake_fin) as mf, \
         patch("scripts.backfill.upsert_prices") as up, \
         patch("scripts.backfill.upsert_financials") as uf, \
         patch("scripts.backfill.get_client") as gc:

        gc.return_value = MagicMock()
        from scripts.backfill import main
        main(today=date(2026, 4, 30))

        # Called once per ticker (10)
        assert mp.call_count == 10
        assert mf.call_count == 10
        assert up.call_count == 10
        assert uf.call_count == 10

        # Price window: 90 days before today
        first_call_args = mp.call_args_list[0]
        ticker_arg, start_arg, end_arg = first_call_args.args
        assert (end_arg - start_arg).days == 90
        assert end_arg == date(2026, 4, 30)
```

To make `scripts.backfill` importable, add to `pytest.ini_options.pythonpath`:

Modify `apps/agent/pyproject.toml` `[tool.pytest.ini_options]`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src", "../.."]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_backfill.py -v
```
Expected: ImportError on `scripts.backfill`.

- [ ] **Step 3: Create `scripts/__init__.py`**

Empty file at `scripts/__init__.py` so it's importable as a package.

- [ ] **Step 4: Write the implementation**

`scripts/backfill.py`:
```python
"""One-off seed: 90 days of prices + latest 4 quarters of financials for the 10-ticker preset.

Run from repo root:
    cd apps/agent && python -m scripts.backfill
or:
    python -m scripts.backfill   (with PYTHONPATH set)
"""
from __future__ import annotations

from datetime import date, timedelta
import logging
import sys

from dotenv import load_dotenv

from morningbrief.data.tickers import TICKERS
from morningbrief.data.yf import fetch_prices
from morningbrief.data.edgar import fetch_quarterly_financials
from morningbrief.data.supabase_client import (
    get_client,
    upsert_prices,
    upsert_financials,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill")


def main(today: date | None = None) -> None:
    today = today or date.today()
    start = today - timedelta(days=90)
    client = get_client()

    for ticker in TICKERS:
        log.info("Backfilling %s prices [%s, %s)", ticker, start, today)
        prices = fetch_prices(ticker, start, today)
        upsert_prices(client, prices)
        log.info("  %d price rows", len(prices))

        log.info("Backfilling %s financials (last 4 quarters)", ticker)
        fins = fetch_quarterly_financials(ticker, n=4)
        upsert_financials(client, fins)
        log.info("  %d financial rows", len(fins))

    log.info("Backfill complete.")


if __name__ == "__main__":
    load_dotenv()
    try:
        main()
    except Exception:
        log.exception("Backfill failed")
        sys.exit(1)
```

- [ ] **Step 5: Run tests, expect PASS**

```bash
pytest tests/test_backfill.py -v
```
Expected: 1 passed.

- [ ] **Step 6: Run full test suite to verify no regressions**

```bash
pytest -v
```
Expected: all tests pass (12+ tests).

- [ ] **Step 7: Commit**

```bash
git add scripts/backfill.py scripts/__init__.py apps/agent/tests/test_backfill.py apps/agent/pyproject.toml
git commit -m "feat: add backfill script for 90d prices and quarterly financials"
```

---

## Task 11: Real backfill execution (manual smoke test)

This is a one-time manual verification that the wiring works against real Supabase + real APIs.

- [ ] **Step 1: Verify `.env` is populated**

In `apps/agent/.env`, confirm `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are set (from the prerequisite Supabase project).

- [ ] **Step 2: Run the backfill**

From `apps/agent/`:
```bash
.venv\Scripts\activate
cd ../..
PYTHONPATH=apps/agent/src python -m scripts.backfill
```

(On Windows PowerShell: `$env:PYTHONPATH="apps/agent/src"; python -m scripts.backfill`)

Expected: ~10 tickers, each logging price rows (~60-65 trading days in 90 calendar days) and 4 financial rows. Total runtime ~30-60s. SEC EDGAR has a 10 req/sec limit; we're well under.

- [ ] **Step 3: Verify in Supabase Dashboard**

In SQL Editor:
```sql
SELECT ticker, COUNT(*) FROM prices GROUP BY ticker ORDER BY ticker;
SELECT ticker, COUNT(*) FROM financials GROUP BY ticker ORDER BY ticker;
```

Expected:
- `prices`: 10 rows, each with ~60-65 count
- `financials`: 10 rows, each with 4 count

- [ ] **Step 4: No commit needed (data only)**

---

## Self-Review

**Spec coverage check:**
- ✅ §1 결정사항 (10 tickers): Task 4
- ✅ §3 schema (7 tables incl. subscribers): Task 2
- ✅ §3 RLS: Task 2
- ✅ Data sources (yfinance, SEC EDGAR): Tasks 6, 7, 8
- ✅ Calendar/holidays foundation: Task 5
- ✅ Backfill (시드 데이터): Tasks 10, 11
- ⏭ LangGraph agents → Plan 2
- ⏭ Frontend, Resend, GitHub Actions → Plan 3

No placeholders found. Type names consistent (`PriceRow`, `FinancialRow`, `FilingRow`) across tasks.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-30-plan1-foundation.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task with two-stage review

**2. Inline Execution** — execute tasks in this session with batched checkpoints

Which approach?
