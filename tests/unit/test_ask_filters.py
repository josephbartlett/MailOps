from __future__ import annotations

from mailops.cli.commands.ask import _filter_followup_rows, _older_than_days_from_prompt


def test_filter_followup_rows_excludes_recruiter_and_logistics_for_client_prompt() -> None:
    rows = [
        {
            "subject": "Open Role for Epic Bridges Analyst",
            "classification_tags": ["recruiter outreach", "direct to you"],
        },
        {
            "subject": "Shipping Label",
            "classification_tags": ["logistics request", "direct to you"],
        },
        {
            "subject": "Client kickoff",
            "classification_tags": ["direct to you", "explicit question"],
        },
    ]

    filtered = _filter_followup_rows(rows, "show unanswered client threads older than 2 days")

    assert [row["subject"] for row in filtered] == ["Client kickoff"]


def test_filter_followup_rows_keeps_only_finance_threads_for_finance_prompt() -> None:
    rows = [
        {
            "subject": "Invoice review needed",
            "classification_tags": ["finance-related", "direct to you"],
        },
        {
            "subject": "Client kickoff",
            "classification_tags": ["direct to you", "explicit question"],
        },
    ]

    filtered = _filter_followup_rows(rows, "show unpaid finance threads")

    assert [row["subject"] for row in filtered] == ["Invoice review needed"]


def test_filter_followup_rows_keeps_only_scheduling_threads_for_scheduling_prompt() -> None:
    rows = [
        {
            "subject": "Reschedule next week",
            "classification_tags": ["scheduling-related", "direct to you"],
        },
        {
            "subject": "Project kickoff",
            "classification_tags": ["direct to you", "explicit question"],
        },
    ]

    filtered = _filter_followup_rows(rows, "show scheduling follow-ups")

    assert [row["subject"] for row in filtered] == ["Reschedule next week"]


def test_older_than_days_from_prompt_supports_explicit_days() -> None:
    assert _older_than_days_from_prompt("show unanswered threads older than 14 days") == 14
