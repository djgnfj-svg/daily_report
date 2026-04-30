"""Manual driver for end-to-end pipeline run.

Run from repo root:
    PYTHONPATH=apps/agent/src apps/agent/.venv/Scripts/python.exe -m scripts.run_today
"""
from __future__ import annotations

import logging
from datetime import date

from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

if __name__ == "__main__":
    load_dotenv()
    from morningbrief.pipeline.orchestrator import run_for_date

    rid = run_for_date(date.today())
    print(f"\n>>> Saved report: {rid}\n")
