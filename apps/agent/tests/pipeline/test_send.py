from unittest.mock import MagicMock, patch
from morningbrief.pipeline.send import send_report


def _subscribers():
    return [
        {"email": "a@example.com", "unsub_token": "t1"},
        {"email": "b@example.com", "unsub_token": "t2"},
    ]


@patch("morningbrief.pipeline.send.resend")
def test_send_report_emails_each_confirmed_subscriber(mock_resend):
    mock_client = MagicMock()
    chain = mock_client.table.return_value.select.return_value.eq.return_value.execute
    chain.return_value.data = _subscribers()

    n = send_report(
        client=mock_client,
        site_url="https://reseeall.com",
        report_date="2026-05-01",
        subject="MorningBrief 2026-05-01",
        body_md="# hello",
    )

    assert n == 2
    assert mock_resend.Emails.send.call_count == 2
    first_call = mock_resend.Emails.send.call_args_list[0].args[0]
    assert first_call["to"] == ["a@example.com"]
    assert "https://reseeall.com/api/unsubscribe?token=t1" in first_call["html"]
    assert "List-Unsubscribe" in first_call["headers"]


@patch("morningbrief.pipeline.send.resend")
def test_send_report_returns_zero_when_no_subscribers(mock_resend):
    mock_client = MagicMock()
    chain = mock_client.table.return_value.select.return_value.eq.return_value.execute
    chain.return_value.data = []

    n = send_report(
        client=mock_client, site_url="https://reseeall.com",
        report_date="2026-05-01", subject="s", body_md="b",
    )
    assert n == 0
    mock_resend.Emails.send.assert_not_called()
