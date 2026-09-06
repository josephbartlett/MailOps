from __future__ import annotations

from typer.testing import CliRunner

from mailops.cli.main import app
from mailops.core.config import AppConfig
from mailops.index.db import connect_db, initialize_database, upsert_account, upsert_message, upsert_thread
from mailops.review.custom_drafts import CustomDraftRequest, create_custom_draft_review_batch


def test_review_and_inspection_show_literal_untrusted_mail_text(tmp_path, monkeypatch):
    config = AppConfig(home_dir=tmp_path / ".mailops")
    monkeypatch.setenv("MAILOPS_HOME", str(config.home_dir))
    monkeypatch.setenv("COLUMNS", "240")
    initialize_database(config)
    subject = "[conceal]private subject[/conceal]"
    body = "[bold]literal body[/bold] :smile: \x1b[2J\u202eend"
    with connect_db(config.db_path) as connection:
        upsert_account(connection, account_id="ops@example.com", provider="proton_bridge",
                       display_name="Ops", email_address="ops@example.com")
        upsert_thread(connection, thread_id="thread", account_id="ops@example.com", provider_thread_id="provider-thread",
                      subject=subject, participants=["client@example.com"], last_message_at=None, unread_count=0,
                      importance_score=0, followup_state="ambiguous", classification_tags=[])
        upsert_message(connection, message_id="message", thread_id="thread", provider_message_id="<message@example.com>",
                       sender="client@example.com", to_recipients=["ops@example.com"], cc_recipients=[], bcc_recipients=[],
                       sent_at=None, received_at=None, snippet=body, body_text=body, folder_or_label_refs=["INBOX"], flags=[])
    result = create_custom_draft_review_batch(config, CustomDraftRequest(
        to_recipients=["[conceal]client@example.com[/conceal]"], subject=subject, body_text=body,
    ))
    runner = CliRunner()
    reviewed = runner.invoke(app, ["review", "batch", "show", result.batch_id])
    assert reviewed.exit_code == 0, reviewed.output
    assert subject in reviewed.output
    assert "[conceal]client@example.com[/conceal]" in reviewed.output
    for command in (["review", "batch", "show", result.batch_id], ["inspect", "message", "message"]):
        rendered = runner.invoke(app, command)
        assert rendered.exit_code == 0, rendered.output
        assert "[bold]literal body[/bold] :smile:" in rendered.output
        assert r"\x1b[2J\u202eend" in rendered.output
        assert "\u202e" not in rendered.output
