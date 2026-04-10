from __future__ import annotations

from mailops.core.config import AppConfig
from mailops.index.db import get_table_counts, list_tables


def test_database_bootstrap_creates_expected_tables(tmp_path) -> None:
    config = AppConfig(home_dir=tmp_path / ".mailops")
    config.ensure_directories()

    tables = list_tables(config)
    counts = get_table_counts(config)

    assert tables == [
        "account_aliases",
        "accounts",
        "action_proposals",
        "audit_events",
        "draft_proposals",
        "folder_messages",
        "folders",
        "messages",
        "provider_drafts",
        "review_batches",
        "threads",
    ]
    assert counts["accounts"] == 0
    assert counts["account_aliases"] == 0
    assert counts["folders"] == 0
    assert counts["messages"] == 0
    assert counts["provider_drafts"] == 0
    assert counts["review_batches"] == 0
