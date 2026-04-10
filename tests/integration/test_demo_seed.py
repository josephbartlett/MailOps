from __future__ import annotations

from typer.testing import CliRunner

from mailops.cli.main import app
from mailops.core.config import AppConfig
from mailops.demo.seed import seed_demo_mailbox
from mailops.index.db import get_table_counts
from mailops.index.search import SearchRequest, search_messages
from mailops.index.triage import summarize_followup_states


runner = CliRunner()


def test_seed_demo_mailbox_is_idempotent_and_queryable(tmp_path) -> None:
    config = AppConfig(home_dir=tmp_path / ".mailops")

    first = seed_demo_mailbox(config)
    second = seed_demo_mailbox(config)

    assert first == second
    counts = get_table_counts(config)
    assert counts["accounts"] == 1
    assert counts["folders"] == 2
    assert counts["threads"] == 5
    assert counts["messages"] == 6
    assert counts["folder_messages"] == 6

    search_results = search_messages(config, SearchRequest(query="invoice"))
    assert len(search_results) == 1
    assert search_results[0]["thread_id"] == "demo-thread-finance"
    assert search_results[0]["message_id"] == "demo-message-finance"

    summary = summarize_followup_states(config, account_id="demo@example.com")
    assert summary["waiting_on_me"] >= 2
    assert summary["waiting_on_them"] >= 1


def test_demo_cli_followup_prompts_return_seeded_recent_finance_thread(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MAILOPS_HOME", str(tmp_path / ".mailops"))

    seed_result = runner.invoke(app, ["demo", "seed"])
    assert seed_result.exit_code == 0, seed_result.output

    triage_result = runner.invoke(app, ["triage", "--since", "3d"])
    assert triage_result.exit_code == 0, triage_result.output
    assert "ranked_results" in triage_result.output
    assert "No waiting-on-me threads matched" not in triage_result.output

    ask_result = runner.invoke(app, ["ask", "show unanswered finance threads"])
    assert ask_result.exit_code == 0, ask_result.output
    assert "Invoice approval needed" in ask_result.output
