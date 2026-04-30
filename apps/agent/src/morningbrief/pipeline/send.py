from __future__ import annotations

import logging
import os

import resend
from markdown import markdown

log = logging.getLogger(__name__)


def _md_to_html(md: str) -> str:
    return markdown(md, extensions=["tables"])


def send_report(
    client,
    site_url: str,
    report_date: str,
    subject: str,
    body_md: str,
) -> int:
    """Send the rendered report to all confirmed subscribers via Resend.

    Returns count of attempted sends. Caller is expected to set RESEND_API_KEY env var.
    """
    resend.api_key = os.environ.get("RESEND_API_KEY", "")

    resp = (
        client.table("subscribers")
        .select("email, unsub_token")
        .eq("status", "confirmed")
        .execute()
    )
    subscribers = resp.data or []
    if not subscribers:
        log.info("No confirmed subscribers, skipping send.")
        return 0

    base_html = _md_to_html(body_md)
    sent = 0
    for sub in subscribers:
        unsub_url = f"{site_url}/api/unsubscribe?token={sub['unsub_token']}"
        html = (
            base_html
            + '<hr><p style="font-size:12px;color:#64748b">'
            + f'수신을 원하지 않으시면 <a href="{unsub_url}">여기를 클릭</a>해 구독을 취소하세요.</p>'
        )
        try:
            resend.Emails.send({
                "from": "MorningBrief <hello@reseeall.com>",
                "to": [sub["email"]],
                "subject": subject,
                "html": html,
                "headers": {
                    "List-Unsubscribe": f"<{unsub_url}>",
                    "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
                },
            })
            sent += 1
        except Exception:
            log.exception("Send failed for %s", sub["email"])
    return sent
