from __future__ import annotations

from datetime import datetime, timezone

from mailops.index.triage import ThreadMessageSnapshot, assess_thread


def _message(
    *,
    sender: str,
    to_recipients: list[str],
    received_at: str,
    flags: list[str] | None = None,
    body_text: str = "",
    cc_recipients: list[str] | None = None,
) -> ThreadMessageSnapshot:
    return ThreadMessageSnapshot(
        sender=sender,
        to_recipients=to_recipients,
        cc_recipients=cc_recipients or [],
        bcc_recipients=[],
        sent_at=None,
        received_at=datetime.fromisoformat(received_at).replace(tzinfo=timezone.utc),
        snippet=body_text,
        body_text=body_text,
        flags=flags or [],
    )


def test_assess_thread_marks_external_unread_question_as_waiting_on_me() -> None:
    assessment = assess_thread(
        subject="Invoice review needed",
        account_aliases={"ops@example.com"},
        messages=[
            _message(
                sender="client@example.com",
                to_recipients=["ops@example.com"],
                received_at="2026-04-06T12:00:00",
                body_text="Can you review this invoice today?",
            )
        ],
        now=datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert assessment.followup_state == "waiting_on_me"
    assert assessment.unread_count == 1
    assert assessment.importance_score >= 0.9
    assert "direct to you" in assessment.classification_tags
    assert "finance-related" in assessment.classification_tags


def test_assess_thread_marks_last_reply_from_me_as_waiting_on_them() -> None:
    assessment = assess_thread(
        subject="Project update",
        account_aliases={"ops@example.com"},
        messages=[
            _message(
                sender="client@example.com",
                to_recipients=["ops@example.com"],
                received_at="2026-04-07T09:00:00",
                body_text="Can you send the updated proposal?",
            ),
            _message(
                sender="ops@example.com",
                to_recipients=["client@example.com"],
                received_at="2026-04-07T10:00:00",
                flags=["\\Seen"],
                body_text="Proposal sent. Let me know if you want changes.",
            ),
        ],
        now=datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert assessment.followup_state == "waiting_on_them"
    assert assessment.importance_score >= 0.3
    assert "latest message from you" in assessment.classification_tags


def test_assess_thread_marks_acknowledgement_as_resolved() -> None:
    assessment = assess_thread(
        subject="Meeting confirmed",
        account_aliases={"ops@example.com"},
        messages=[
            _message(
                sender="ops@example.com",
                to_recipients=["client@example.com"],
                received_at="2026-04-08T08:00:00",
                flags=["\\Seen"],
                body_text="See you then.",
            ),
            _message(
                sender="client@example.com",
                to_recipients=["ops@example.com"],
                received_at="2026-04-08T09:00:00",
                flags=["\\Seen"],
                body_text="Thanks, sounds good.",
            ),
        ],
        now=datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert assessment.followup_state == "resolved"
    assert assessment.importance_score <= 0.2
    assert "closure language" in assessment.classification_tags


def test_assess_thread_marks_notifications_as_ambiguous() -> None:
    assessment = assess_thread(
        subject="[GitHub] Daily digest",
        account_aliases={"ops@example.com"},
        messages=[
            _message(
                sender="notifications@github.com",
                to_recipients=["ops@example.com"],
                received_at="2026-04-08T09:00:00",
                body_text="Your daily digest is ready.",
            )
        ],
        now=datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert assessment.followup_state == "ambiguous"
    assert assessment.importance_score <= 0.45
    assert "automated sender" in assessment.classification_tags


def test_assess_thread_marks_passive_submission_update_as_waiting_on_them() -> None:
    assessment = assess_thread(
        subject="314e Submission Confirmation!",
        account_aliases={"ops@example.com"},
        messages=[
            _message(
                sender="recruiter@example.com",
                to_recipients=["ops@example.com"],
                received_at="2026-04-08T09:00:00",
                flags=["\\Seen"],
                body_text="Thank you for your time. We are submitting your resume to the hiring manager and will be in touch once we hear feedback.",
            )
        ],
        now=datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert assessment.followup_state == "waiting_on_them"
    assert "passive status update" in assessment.classification_tags


def test_assess_thread_ignores_quoted_reply_chain_when_scoring_latest_message() -> None:
    assessment = assess_thread(
        subject="Re: 314e Submission Confirmation!",
        account_aliases={"ops@example.com"},
        messages=[
            _message(
                sender="recruiter@example.com",
                to_recipients=["ops@example.com"],
                received_at="2026-04-08T09:00:00",
                flags=["\\Seen"],
                body_text=(
                    "Thanks, Joe. Have a great day ahead!\n\n"
                    "On Wed, 16 Jul 2025 at 5:35 PM, Joe wrote:\n"
                    "Can you share the attached document?"
                ),
            )
        ],
        now=datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert assessment.followup_state in {"resolved", "waiting_on_them"}
    assert "explicit question" not in assessment.classification_tags


def test_assess_thread_marks_cold_outreach_as_ambiguous() -> None:
    assessment = assess_thread(
        subject="Re: LM Consulting Group new clients",
        account_aliases={"ops@example.com"},
        messages=[
            _message(
                sender="seller@example.com",
                to_recipients=["ops@example.com"],
                received_at="2026-04-08T09:00:00",
                body_text="Worth a chat? I came across your business and wanted to reach out. If you don't want to hear from me again, please let me know.",
            )
        ],
        now=datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert assessment.followup_state == "ambiguous"
    assert "cold outreach" in assessment.classification_tags
    assert assessment.importance_score <= 0.45


def test_assess_thread_marks_unengaged_recruiter_outreach_as_ambiguous() -> None:
    assessment = assess_thread(
        subject="Open Role for Epic Bridges Analyst",
        account_aliases={"ops@example.com"},
        messages=[
            _message(
                sender="rina@clindcast.com",
                to_recipients=["ops@example.com"],
                received_at="2026-04-08T09:00:00",
                body_text=(
                    "Hi Joseph, We have an open position for an Epic Bridges Analyst. "
                    "Please let me know if you are interested and share your updated resume."
                ),
            )
        ],
        now=datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert assessment.followup_state == "ambiguous"
    assert "recruiter outreach" in assessment.classification_tags
    assert assessment.importance_score <= 0.45


def test_assess_thread_marks_recruiting_process_thread_as_waiting_on_me() -> None:
    assessment = assess_thread(
        subject="314e Submission Confirmation!",
        account_aliases={"ops@example.com"},
        messages=[
            _message(
                sender="pratibha.bordoloi@314ecorp.com",
                to_recipients=["ops@example.com"],
                received_at="2026-04-08T09:00:00",
                body_text=(
                    "Hi Joseph, I am confirming your submission to the hiring manager. "
                    "Please share your updated resume and reply confirming you agree to the submission details. "
                    "Regards, Recruiter"
                ),
            )
        ],
        now=datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert assessment.followup_state == "waiting_on_me"
    assert "recruiting process" in assessment.classification_tags
    assert assessment.importance_score < 0.9


def test_assess_thread_marks_calendar_invite_as_ambiguous_without_request() -> None:
    assessment = assess_thread(
        subject="Invitation: Joe <> Harrison @ Sat Aug 9, 2025 10am - 10:30am",
        account_aliases={"ops@example.com"},
        messages=[
            _message(
                sender="calendar@example.com",
                to_recipients=["ops@example.com"],
                received_at="2026-04-08T09:00:00",
                flags=["\\Seen"],
                body_text="Calendar invitation details and organizer metadata.",
            )
        ],
        now=datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert assessment.followup_state == "ambiguous"
    assert "calendar invite" in assessment.classification_tags


def test_assess_thread_marks_dormant_single_inbound_question_as_ambiguous() -> None:
    assessment = assess_thread(
        subject="Moving forward!",
        account_aliases={"ops@example.com"},
        messages=[
            _message(
                sender="founder@example.com",
                to_recipients=["ops@example.com"],
                received_at="2025-08-12T09:00:00",
                flags=["\\Seen"],
                body_text="We would love to move forward. When would you be able to get started?",
            )
        ],
        now=datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert assessment.followup_state == "ambiguous"
    assert "dormant one-off thread" in assessment.classification_tags
    assert assessment.importance_score <= 0.2


def test_assess_thread_marks_logistics_request_as_lower_priority_waiting_on_me() -> None:
    assessment = assess_thread(
        subject="FW: IT Equipment Return",
        account_aliases={"ops@example.com"},
        messages=[
            _message(
                sender="cbartich@teksystems.com",
                to_recipients=["ops@example.com"],
                received_at="2026-04-08T09:00:00",
                body_text="Hey Joe, Here is the shipping label to return your laptop.",
            )
        ],
        now=datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert assessment.followup_state == "waiting_on_me"
    assert "logistics request" in assessment.classification_tags
    assert assessment.importance_score < 0.75


def test_assess_thread_does_not_treat_promotional_subject_question_as_human_followup() -> None:
    assessment = assess_thread(
        subject="What Happens in an Audit?, and more | May 2025",
        account_aliases={"ops@example.com"},
        messages=[
            _message(
                sender="newsletter@example.com",
                to_recipients=["ops@example.com"],
                received_at="2026-04-08T09:00:00",
                body_text="Monthly resources and updates.",
            )
        ],
        now=datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert assessment.followup_state == "ambiguous"
    assert "broadcast-style message" in assessment.classification_tags
