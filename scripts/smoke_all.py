"""전체 스모크 러너: 단위 → ingest → indicators → llm → (옵션)e2e.

각 단계 PASS/FAIL을 모아 마지막에 요약. 한 단계 실패해도 나머지 계속 진행.

실행:
    apps/agent/.venv/Scripts/python.exe -m scripts.smoke_all
        e2e 발송 제외 (단위+ingest+indicators+llm)

    apps/agent/.venv/Scripts/python.exe -m scripts.smoke_all --with-e2e
        풀 E2E + 발송까지 (~$0.05, 1-2분 추가)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = str(ROOT / "apps/agent/.venv/Scripts/python.exe")
ENV = {"PYTHONPATH": "apps/agent/src"}


def run_step(name: str, cmd: list[str]) -> tuple[bool, float]:
    print(f"\n{'='*70}\n>>> {name}\n{'='*70}")
    t0 = time.time()
    import os
    env = {**os.environ, **ENV}
    rc = subprocess.call(cmd, cwd=ROOT, env=env)
    dt = time.time() - t0
    ok = rc == 0
    print(f"\n--> {name}: {'PASS' if ok else 'FAIL'} ({dt:.1f}s, exit={rc})")
    return ok, dt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-e2e", action="store_true", help="run full E2E with email send")
    args = ap.parse_args()

    steps = [
        ("1. unit tests", [PY, "-m", "pytest", "apps/agent/tests/", "-q"]),
        ("2. smoke_ingest (live AAPL)", [PY, "-m", "scripts.smoke_ingest"]),
        ("3. smoke_indicators (DB 10 tickers)", [PY, "-m", "scripts.smoke_indicators"]),
        ("4. smoke_llm (1 ticker, ~$0.001)", [PY, "-m", "scripts.smoke_llm"]),
    ]
    if args.with_e2e:
        steps.append(("5. smoke_e2e --run (full pipeline + email, ~$0.05)",
                      [PY, "-m", "scripts.smoke_e2e", "--run"]))

    results: list[tuple[str, bool, float]] = []
    for name, cmd in steps:
        ok, dt = run_step(name, cmd)
        results.append((name, ok, dt))

    print(f"\n{'='*70}\n SUMMARY\n{'='*70}")
    total = 0.0
    for name, ok, dt in results:
        mark = "[PASS]" if ok else "[FAIL]"
        print(f"  {mark}  {name:<55} {dt:6.1f}s")
        total += dt
    print(f"  total: {total:.1f}s")

    failed = [n for n, ok, _ in results if not ok]
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
