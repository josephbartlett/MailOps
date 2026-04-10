from __future__ import annotations

from mailops.core.config import AppConfig
from mailops.demo.seed import seed_demo_mailbox
from mailops.index.db import get_table_counts
from mailops.index.search import SearchRequest, search_messages
from mailops.index.triage import summarize_followup_states


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
