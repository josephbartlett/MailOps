from __future__ import annotations

import sqlite3

import pytest

from mailops.core.config import AppConfig
from mailops.index.db import SCHEMA_STATEMENTS, connect_db, get_table_counts, initialize_database, list_tables


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


def _legacy_database(config, *, orphan=False):
    config.ensure_directories()
    with connect_db(config.db_path) as connection:
        for statement in SCHEMA_STATEMENTS:
            if "CREATE TABLE IF NOT EXISTS messages (" in statement:
                statement = statement.replace("        account_id TEXT NOT NULL,\n", "").replace(
                    "UNIQUE(account_id, provider_message_id)", "UNIQUE(provider_message_id)"
                )
            connection.execute(statement)
        connection.execute(
            "INSERT INTO threads (id, account_id, provider_thread_id, subject) VALUES ('thread-1', 'ops@example.com', 't-1', 'Test')"
        )
        connection.execute(
            "INSERT INTO messages (id, thread_id, provider_message_id, sender, body_text) VALUES (?, ?, ?, ?, ?)",
            ("retained-id", "missing" if orphan else "thread-1", "<same@example.com>", "sender@example.com", "Preserve this local body"),
        )
        connection.execute(
            "INSERT INTO folder_messages (folder_id, message_id, uid) VALUES ('folder-1', 'retained-id', 1)"
        )


def test_message_identity_migration_preserves_ids_bodies_and_links(tmp_path):
    config = AppConfig(home_dir=tmp_path / ".mailops")
    _legacy_database(config)
    with connect_db(config.db_path) as connection:
        connection.execute("CREATE TABLE migration_trigger_receipts (message_id TEXT)")
        connection.execute(
            """CREATE TRIGGER record_message_update AFTER UPDATE ON messages
            BEGIN INSERT INTO migration_trigger_receipts (message_id) VALUES (new.id); END"""
        )
    initialize_database(config)
    initialize_database(config)
    with connect_db(config.db_path) as connection:
        message = connection.execute("SELECT id, account_id, body_text FROM messages").fetchone()
        assert tuple(message) == ("retained-id", "ops@example.com", "Preserve this local body")
        assert connection.execute("SELECT message_id FROM folder_messages").fetchone()[0] == "retained-id"
        connection.execute(
            """INSERT INTO messages (id, account_id, thread_id, provider_message_id, sender)
            VALUES ('new-id', 'second@example.com', 'thread-2', '<same@example.com>', 'sender@example.com')"""
        )
        assert connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 2
        connection.execute("DELETE FROM migration_trigger_receipts")
        connection.execute("UPDATE messages SET snippet = 'updated' WHERE id = 'retained-id'")
        assert connection.execute("SELECT message_id FROM migration_trigger_receipts").fetchone()[0] == "retained-id"


def test_orphaned_legacy_message_blocks_migration_without_data_loss(tmp_path):
    config = AppConfig(home_dir=tmp_path / ".mailops")
    _legacy_database(config, orphan=True)
    with pytest.raises(sqlite3.IntegrityError, match="existing account thread"):
        initialize_database(config)
    with connect_db(config.db_path) as connection:
        assert connection.execute("SELECT body_text FROM messages").fetchone()[0] == "Preserve this local body"
        assert "account_id" not in {row["name"] for row in connection.execute("PRAGMA table_info(messages)")}
        assert connection.execute("SELECT name FROM sqlite_master WHERE name = 'messages_account_scoped'").fetchone() is None


def test_database_context_closes_connection(tmp_path):
    with connect_db(tmp_path / "test.db") as connection:
        connection.execute("CREATE TABLE sample (id INTEGER)")
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connection.execute("SELECT 1")
