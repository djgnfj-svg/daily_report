"""풀 E2E 드라이버: ingest → analyze(LLM) → render → save → send.

사용 전 점검 + 본인 이메일을 subscribers에 등록하는 헬퍼 포함.

실행:
    apps/agent/.venv/Scripts/python.exe -m scripts.smoke_e2e --check
        키/구독자/도메인 사전 점검만

    apps/agent/.venv/Scripts/python.exe -m scripts.smoke_e2e --add-me djgnfj3795@gmail.com
        해당 이메일을 confirmed 구독자로 등록 (멱등)

    apps/agent/.venv/Scripts/python.exe -m scripts.smoke_e2e --run
        실제 파이프라인 실행 + 발송 (~$0.05, 1~2분)
"""
from __future__ import annotations

import argparse
import logging
import os
import secrets
import sys
from datetime import date

from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("e2e")


def cmd_check():
    keys = ["SUPABASE_URL", "SUPABASE_SERVICE_KEY", "OPENAI_API_KEY", "RESEND_API_KEY"]
    missing = [k for k in keys if not os.environ.get(k)]
    print("--- env ---")
    for k in keys:
        v = os.environ.get(k, "")
        print(f"  {k}: {'OK' if v else 'MISSING'} ({len(v)} chars)")
    if missing:
        print(f"[FAIL] missing env: {missing}")
        return 1

    from morningbrief.data.supabase_client import get_client
    client = get_client()

    print("\n--- subscribers ---")
    resp = client.table("subscribers").select("email,status").execute()
    rows = resp.data or []
    confirmed = [r for r in rows if r["status"] == "confirmed"]
    for r in rows:
        print(f"  {r['email']:<40} {r['status']}")
    print(f"  total={len(rows)} confirmed={len(confirmed)}")
    if not confirmed:
        print("  [WARN] no confirmed subscribers — send will be a no-op")

    print("\n--- resend domain ---")
    try:
        import resend
        resend.api_key = os.environ["RESEND_API_KEY"]
        domains = resend.Domains.list()
        for d in (domains.get("data") if isinstance(domains, dict) else domains) or []:
            print(f"  {d.get('name'):<25} status={d.get('status')}")
    except Exception as e:
        print(f"  [WARN] could not list domains: {e}")

    print("\n[PASS] check complete")
    return 0


def cmd_add_me(email: str):
    from morningbrief.data.supabase_client import get_client
    client = get_client()

    existing = client.table("subscribers").select("*").eq("email", email).execute().data
    if existing:
        client.table("subscribers").update({"status": "confirmed"}).eq("email", email).execute()
        print(f"[PASS] {email} updated to confirmed")
    else:
        client.table("subscribers").insert({
            "email": email,
            "status": "confirmed",
            "unsub_token": secrets.token_urlsafe(24),
            "confirm_token": secrets.token_urlsafe(24),
        }).execute()
        print(f"[PASS] {email} inserted as confirmed")
    return 0


DEFAULT_TEST_TO = "djgnfj3795@gmail.com"


def cmd_run(only_to: str | None):
    from morningbrief.pipeline.orchestrator import run_for_date
    if only_to:
        print(f"[INFO] sending TEST email to {only_to} only (DB subscribers untouched)")
    else:
        print("[WARN] --all-subscribers: real cron mode, every confirmed subscriber will be emailed")
    rid = run_for_date(date.today(), send=True, only_to=only_to)
    print(f"\n[PASS] report saved id={rid}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--add-me", metavar="EMAIL")
    g.add_argument("--run", action="store_true",
                   help=f"테스트 발송: 기본 {DEFAULT_TEST_TO} 한 명에게만")
    ap.add_argument("--to", metavar="EMAIL", default=None,
                    help="테스트 수신자 변경 (기본: %s)" % DEFAULT_TEST_TO)
    ap.add_argument("--all-subscribers", action="store_true",
                    help="DB confirmed 구독자 전원 발송 (운영 cron과 동일)")
    args = ap.parse_args()

    load_dotenv()

    if args.check:
        sys.exit(cmd_check())
    elif args.add_me:
        sys.exit(cmd_add_me(args.add_me))
    elif args.run:
        only_to = None if args.all_subscribers else (args.to or DEFAULT_TEST_TO)
        sys.exit(cmd_run(only_to))


if __name__ == "__main__":
    main()
