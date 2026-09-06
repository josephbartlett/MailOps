"""SQLite bootstrap helpers."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from mailops.core.config import AppConfig

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS accounts (
        id TEXT PRIMARY KEY,
        provider TEXT NOT NULL,
        display_name TEXT NOT NULL,
        email_address TEXT NOT NULL,
        adapter_config_ref TEXT,
        last_sync_at TEXT,
        sync_status TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS folders (
        id TEXT PRIMARY KEY,
        account_id TEXT NOT NULL,
        provider_folder_id TEXT NOT NULL,
        display_name TEXT NOT NULL,
        delimiter TEXT NOT NULL DEFAULT '/',
        attributes TEXT NOT NULL DEFAULT '[]',
        role TEXT NOT NULL DEFAULT 'unknown',
        is_selectable INTEGER NOT NULL DEFAULT 1,
        can_sync INTEGER NOT NULL DEFAULT 1,
        can_create_draft INTEGER NOT NULL DEFAULT 0,
        uid_validity TEXT,
        last_uid INTEGER NOT NULL DEFAULT 0,
        last_sync_at TEXT,
        UNIQUE(account_id, provider_folder_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS account_aliases (
        alias_email TEXT PRIMARY KEY,
        account_id TEXT NOT NULL,
        provider_username TEXT,
        is_primary INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS threads (
        id TEXT PRIMARY KEY,
        account_id TEXT NOT NULL,
        provider_thread_id TEXT NOT NULL,
        subject TEXT NOT NULL,
        participants TEXT NOT NULL DEFAULT '[]',
        last_message_at TEXT,
        unread_count INTEGER NOT NULL DEFAULT 0,
        importance_score REAL NOT NULL DEFAULT 0.0,
        followup_state TEXT NOT NULL DEFAULT 'ambiguous',
        classification_tags TEXT NOT NULL DEFAULT '[]',
        UNIQUE(account_id, provider_thread_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        account_id TEXT NOT NULL,
        thread_id TEXT NOT NULL,
        provider_message_id TEXT NOT NULL,
        sender TEXT NOT NULL,
        to_recipients TEXT NOT NULL DEFAULT '[]',
        cc_recipients TEXT NOT NULL DEFAULT '[]',
        bcc_recipients TEXT NOT NULL DEFAULT '[]',
        sent_at TEXT,
        received_at TEXT,
        snippet TEXT NOT NULL DEFAULT '',
        body_text TEXT NOT NULL DEFAULT '',
        folder_or_label_refs TEXT NOT NULL DEFAULT '[]',
        flags TEXT NOT NULL DEFAULT '[]',
        UNIQUE(account_id, provider_message_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS folder_messages (
        folder_id TEXT NOT NULL,
        message_id TEXT NOT NULL,
        uid INTEGER NOT NULL,
        flags TEXT NOT NULL DEFAULT '[]',
        PRIMARY KEY(folder_id, uid)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS draft_proposals (
        id TEXT PRIMARY KEY,
        thread_id TEXT NOT NULL,
        account_id TEXT,
        to_recipients TEXT NOT NULL DEFAULT '[]',
        cc_recipients TEXT NOT NULL DEFAULT '[]',
        bcc_recipients TEXT NOT NULL DEFAULT '[]',
        in_reply_to TEXT,
        reference_message_ids TEXT NOT NULL DEFAULT '[]',
        context_refs TEXT NOT NULL DEFAULT '[]',
        style_profile TEXT NOT NULL DEFAULT 'default',
        proposed_subject TEXT NOT NULL,
        proposed_body TEXT NOT NULL,
        confidence REAL NOT NULL DEFAULT 0.0,
        rationale TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS action_proposals (
        id TEXT PRIMARY KEY,
        batch_id TEXT NOT NULL,
        type TEXT NOT NULL,
        scope TEXT NOT NULL DEFAULT '[]',
        reason TEXT NOT NULL,
        evidence_refs TEXT NOT NULL DEFAULT '[]',
        draft_proposal_id TEXT,
        provider_ref TEXT,
        risk_level TEXT NOT NULL,
        review_status TEXT NOT NULL,
        execution_status TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS review_batches (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        status TEXT NOT NULL,
        scope_count INTEGER NOT NULL DEFAULT 0,
        highest_risk TEXT NOT NULL,
        reason TEXT NOT NULL,
        rollback_available INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS provider_drafts (
        action_id TEXT PRIMARY KEY,
        batch_id TEXT NOT NULL,
        draft_proposal_id TEXT,
        account_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        provider_ref TEXT NOT NULL,
        mailbox TEXT NOT NULL,
        uid INTEGER,
        provider_message_id TEXT,
        subject TEXT NOT NULL DEFAULT '',
        from_address TEXT NOT NULL DEFAULT '',
        to_recipients TEXT NOT NULL DEFAULT '[]',
        cc_recipients TEXT NOT NULL DEFAULT '[]',
        bcc_recipients TEXT NOT NULL DEFAULT '[]',
        flags TEXT NOT NULL DEFAULT '[]',
        internal_date TEXT,
        synced_at TEXT NOT NULL,
        status TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_events (
        id TEXT PRIMARY KEY,
        actor TEXT NOT NULL,
        action_type TEXT NOT NULL,
        target_ref TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        before_state TEXT,
        after_state TEXT,
        result TEXT NOT NULL
    )
    """,
)

COUNTED_TABLES = (
    "accounts",
    "account_aliases",
    "folders",
    "threads",
    "messages",
    "folder_messages",
    "draft_proposals",
    "action_proposals",
    "provider_drafts",
    "review_batches",
    "audit_events",
)

MIGRATION_COLUMNS: dict[str, tuple[tuple[str, str], ...]] = {
    "accounts": (
        ("adapter_config_ref", "TEXT"),
    ),
    "folders": (
        ("uid_validity", "TEXT"),
        ("role", "TEXT NOT NULL DEFAULT 'unknown'"),
        ("is_selectable", "INTEGER NOT NULL DEFAULT 1"),
        ("can_sync", "INTEGER NOT NULL DEFAULT 1"),
        ("can_create_draft", "INTEGER NOT NULL DEFAULT 0"),
    ),
    "threads": (
        ("participants", "TEXT NOT NULL DEFAULT '[]'"),
        ("importance_score", "REAL NOT NULL DEFAULT 0.0"),
        ("classification_tags", "TEXT NOT NULL DEFAULT '[]'"),
    ),
    "draft_proposals": (
        ("account_id", "TEXT"),
        ("to_recipients", "TEXT NOT NULL DEFAULT '[]'"),
        ("cc_recipients", "TEXT NOT NULL DEFAULT '[]'"),
        ("bcc_recipients", "TEXT NOT NULL DEFAULT '[]'"),
        ("in_reply_to", "TEXT"),
        ("reference_message_ids", "TEXT NOT NULL DEFAULT '[]'"),
        ("context_refs", "TEXT NOT NULL DEFAULT '[]'"),
        ("style_profile", "TEXT NOT NULL DEFAULT 'default'"),
    ),
    "action_proposals": (
        ("batch_id", "TEXT"),
        ("scope", "TEXT NOT NULL DEFAULT '[]'"),
        ("evidence_refs", "TEXT NOT NULL DEFAULT '[]'"),
        ("draft_proposal_id", "TEXT"),
        ("provider_ref", "TEXT"),
        ("created_at", "TEXT"),
    ),
    "audit_events": (
        ("before_state", "TEXT"),
        ("after_state", "TEXT"),
    ),
    "messages": (
        ("account_id", "TEXT"),
        ("to_recipients", "TEXT NOT NULL DEFAULT '[]'"),
        ("cc_recipients", "TEXT NOT NULL DEFAULT '[]'"),
        ("bcc_recipients", "TEXT NOT NULL DEFAULT '[]'"),
        ("folder_or_label_refs", "TEXT NOT NULL DEFAULT '[]'"),
        ("flags", "TEXT NOT NULL DEFAULT '[]'"),
    ),
}

MIGRATION_INDEXES: tuple[str, ...] = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_folders_account_provider_folder ON folders(account_id, provider_folder_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_threads_account_provider_thread ON threads(account_id, provider_thread_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_account_provider_message ON messages(account_id, provider_message_id)",
    "CREATE INDEX IF NOT EXISTS idx_messages_thread_id ON messages(thread_id)",
    "CREATE INDEX IF NOT EXISTS idx_folder_messages_message_id ON folder_messages(message_id)",
    "CREATE INDEX IF NOT EXISTS idx_action_proposals_batch_id ON action_proposals(batch_id)",
    "CREATE INDEX IF NOT EXISTS idx_draft_proposals_thread_id ON draft_proposals(thread_id)",
    "CREATE INDEX IF NOT EXISTS idx_provider_drafts_batch_id ON provider_drafts(batch_id)",
)


class _ClosingConnection(sqlite3.Connection):
    """Commit or roll back a transaction and release its file handle on exit."""

    def __exit__(self, *args: Any) -> bool:
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def connect_db(path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with row access by name."""

    connection = sqlite3.connect(path, factory=_ClosingConnection)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(config: AppConfig) -> None:
    """Ensure the local schema exists."""

    config.ensure_directories()
    with connect_db(config.db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)
        _apply_migrations(connection)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _normalize_address(value: str) -> str:
    return value.strip().lower()


def _apply_migrations(connection: sqlite3.Connection) -> None:
    """Add newly introduced columns to pre-existing SQLite tables."""

    for table_name, columns in MIGRATION_COLUMNS.items():
        existing_columns = {
            str(row["name"])
            for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        for column_name, column_definition in columns:
            if column_name in existing_columns:
                continue
            try:
                connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise
    _migrate_message_identity(connection)
    for statement in MIGRATION_INDEXES:
        connection.execute(statement)
    connection.execute(
        "UPDATE action_proposals SET batch_id = id WHERE batch_id IS NULL OR TRIM(batch_id) = ''"
    )
    connection.execute(
        "UPDATE action_proposals SET created_at = COALESCE(created_at, '1970-01-01T00:00:00+00:00')"
    )
    account_rows = connection.execute("SELECT id, email_address FROM accounts").fetchall()
    for row in account_rows:
        account_id = _normalize_address(str(row["id"]))
        email_address = _normalize_address(str(row["email_address"]))
        if account_id:
            connection.execute(
                """
                INSERT OR IGNORE INTO account_aliases (alias_email, account_id, provider_username, is_primary)
                VALUES (?, ?, ?, ?)
                """,
                (account_id, account_id, None, 1),
            )
        if email_address:
            connection.execute(
                """
                INSERT OR IGNORE INTO account_aliases (alias_email, account_id, provider_username, is_primary)
                VALUES (?, ?, ?, ?)
                """,
                (email_address, account_id or email_address, None, 1 if email_address == account_id else 0),
            )


def _migrate_message_identity(connection: sqlite3.Connection) -> None:
    """Preserve local IDs while replacing the legacy cross-account uniqueness rule."""

    columns = connection.execute("PRAGMA table_info(messages)").fetchall()
    needs_rebuild = any(row["name"] == "account_id" and not row["notnull"] for row in columns)
    if not needs_rebuild:
        return
    connection.execute(
        """
        UPDATE messages SET account_id = (
            SELECT account_id FROM threads WHERE threads.id = messages.thread_id
        ) WHERE account_id IS NULL
        """
    )
    if connection.execute("SELECT 1 FROM messages WHERE account_id IS NULL LIMIT 1").fetchone():
        raise sqlite3.IntegrityError("Message identity migration requires every message to have an existing account thread.")

    schema = next(statement for statement in SCHEMA_STATEMENTS if "CREATE TABLE IF NOT EXISTS messages (" in statement)
    connection.execute(schema.replace("CREATE TABLE IF NOT EXISTS messages (", "CREATE TABLE messages_account_scoped ("))
    new_columns = {str(row["name"]) for row in connection.execute("PRAGMA table_info(messages_account_scoped)")}
    if {str(row["name"]) for row in columns} != new_columns:
        raise sqlite3.IntegrityError("Message identity migration found an unsupported schema; no records were changed.")
    dependent_schema_sql = [
        str(row["sql"])
        for row in connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type IN ('index', 'trigger') AND tbl_name = 'messages'"
        )
        if row["sql"] and row["name"] != "idx_messages_provider_message_id"
    ]
    names = ", ".join('"' + str(row["name"]).replace('"', '""') + '"' for row in columns)
    connection.execute(f"INSERT INTO messages_account_scoped ({names}) SELECT {names} FROM messages")
    connection.execute("DROP TABLE messages")
    connection.execute("ALTER TABLE messages_account_scoped RENAME TO messages")
    for statement in dependent_schema_sql:
        connection.execute(statement)


def list_tables(config: AppConfig) -> list[str]:
    """Return user tables from the local SQLite database."""

    initialize_database(config)
    with connect_db(config.db_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    return [row["name"] for row in rows]


def upsert_account(
    connection: sqlite3.Connection,
    *,
    account_id: str,
    provider: str,
    display_name: str,
    email_address: str,
    adapter_config_ref: str | None = None,
    last_sync_at: str | None = None,
    sync_status: str = "ready",
) -> None:
    """Insert or update an account record."""

    connection.execute(
        """
        INSERT INTO accounts (
            id, provider, display_name, email_address, adapter_config_ref, last_sync_at, sync_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            provider = excluded.provider,
            display_name = excluded.display_name,
            email_address = excluded.email_address,
            adapter_config_ref = excluded.adapter_config_ref,
            last_sync_at = excluded.last_sync_at,
            sync_status = excluded.sync_status
        """,
        (
            account_id,
            provider,
            display_name,
            _normalize_address(email_address),
            adapter_config_ref,
            last_sync_at,
            sync_status,
        ),
    )


def upsert_account_alias(
    connection: sqlite3.Connection,
    *,
    alias_email: str,
    account_id: str,
    provider_username: str | None = None,
    is_primary: bool = False,
) -> None:
    """Insert or update an alias mapping for a canonical account."""

    normalized_alias = _normalize_address(alias_email)
    if not normalized_alias:
        return
    connection.execute(
        """
        INSERT INTO account_aliases (alias_email, account_id, provider_username, is_primary)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(alias_email) DO UPDATE SET
            account_id = excluded.account_id,
            provider_username = excluded.provider_username,
            is_primary = excluded.is_primary
        """,
        (
            normalized_alias,
            account_id,
            _normalize_address(provider_username) if provider_username else None,
            1 if is_primary else 0,
        ),
    )


def upsert_folder(
    connection: sqlite3.Connection,
    *,
    folder_id: str,
    account_id: str,
    provider_folder_id: str,
    display_name: str,
    delimiter: str,
    attributes: list[str],
    role: str = "unknown",
    is_selectable: bool = True,
    can_sync: bool = True,
    can_create_draft: bool = False,
    uid_validity: str | None = None,
    last_uid: int | None = None,
    last_sync_at: str | None = None,
) -> None:
    """Insert or update a folder record without resetting cursor state unintentionally."""

    current = connection.execute("SELECT last_uid, last_sync_at, uid_validity FROM folders WHERE id = ?", (folder_id,)).fetchone()
    effective_last_uid = current["last_uid"] if current is not None and last_uid is None else (last_uid or 0)
    effective_last_sync_at = current["last_sync_at"] if current is not None and last_sync_at is None else last_sync_at
    effective_uid_validity = current["uid_validity"] if current is not None and uid_validity is None else uid_validity

    connection.execute(
        """
        INSERT INTO folders (
            id,
            account_id,
            provider_folder_id,
            display_name,
            delimiter,
            attributes,
            role,
            is_selectable,
            can_sync,
            can_create_draft,
            uid_validity,
            last_uid,
            last_sync_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            account_id = excluded.account_id,
            provider_folder_id = excluded.provider_folder_id,
            display_name = excluded.display_name,
            delimiter = excluded.delimiter,
            attributes = excluded.attributes,
            role = excluded.role,
            is_selectable = excluded.is_selectable,
            can_sync = excluded.can_sync,
            can_create_draft = excluded.can_create_draft,
            uid_validity = excluded.uid_validity,
            last_uid = excluded.last_uid,
            last_sync_at = excluded.last_sync_at
        """,
        (
            folder_id,
            account_id,
            provider_folder_id,
            display_name,
            delimiter,
            _json_dumps(attributes),
            role,
            1 if is_selectable else 0,
            1 if can_sync else 0,
            1 if can_create_draft else 0,
            effective_uid_validity,
            effective_last_uid,
            effective_last_sync_at,
        ),
    )


def get_folder_last_uid(connection: sqlite3.Connection, folder_id: str) -> int:
    """Return the last synced UID for a folder."""

    row = connection.execute("SELECT last_uid FROM folders WHERE id = ?", (folder_id,)).fetchone()
    if row is None:
        return 0
    return int(row["last_uid"])


def get_folder_uid_validity(connection: sqlite3.Connection, folder_id: str) -> str | None:
    row = connection.execute("SELECT uid_validity FROM folders WHERE id = ?", (folder_id,)).fetchone()
    return str(row["uid_validity"]) if row is not None and row["uid_validity"] is not None else None


def reset_folder_uid_state(connection: sqlite3.Connection, folder_id: str, uid_validity: str) -> None:
    """Discard invalid UID links while retaining indexed message history."""

    connection.execute("DELETE FROM folder_messages WHERE folder_id = ?", (folder_id,))
    connection.execute("UPDATE folders SET last_uid = 0, uid_validity = ? WHERE id = ?", (uid_validity, folder_id))


def upsert_thread(
    connection: sqlite3.Connection,
    *,
    thread_id: str,
    account_id: str,
    provider_thread_id: str,
    subject: str,
    participants: list[str],
    last_message_at: str | None,
    unread_count: int,
    importance_score: float,
    followup_state: str,
    classification_tags: list[str],
) -> None:
    """Insert or update a thread record."""

    connection.execute(
        """
        INSERT INTO threads (
            id,
            account_id,
            provider_thread_id,
            subject,
            participants,
            last_message_at,
            unread_count,
            importance_score,
            followup_state,
            classification_tags
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            account_id = excluded.account_id,
            provider_thread_id = excluded.provider_thread_id,
            subject = excluded.subject,
            participants = excluded.participants,
            last_message_at = excluded.last_message_at,
            unread_count = excluded.unread_count,
            importance_score = excluded.importance_score,
            followup_state = excluded.followup_state,
            classification_tags = excluded.classification_tags
        """,
        (
            thread_id,
            account_id,
            provider_thread_id,
            subject,
            _json_dumps(participants),
            last_message_at,
            unread_count,
            importance_score,
            followup_state,
            _json_dumps(classification_tags),
        ),
    )


def upsert_message(
    connection: sqlite3.Connection,
    *,
    message_id: str,
    provider_message_id: str,
    thread_id: str,
    sender: str,
    to_recipients: list[str],
    cc_recipients: list[str],
    bcc_recipients: list[str],
    sent_at: str | None,
    received_at: str | None,
    snippet: str,
    body_text: str,
    folder_or_label_refs: list[str],
    flags: list[str],
) -> bool:
    """Insert or update a message record and report whether it was new."""

    thread = connection.execute("SELECT account_id FROM threads WHERE id = ?", (thread_id,)).fetchone()
    if thread is None:
        raise ValueError("A message must belong to an existing account thread.")
    account_id = str(thread["account_id"])
    existing = connection.execute(
        "SELECT id, folder_or_label_refs FROM messages WHERE account_id = ? AND provider_message_id = ?",
        (account_id, provider_message_id),
    ).fetchone()
    inserted = existing is None
    effective_message_id = message_id if inserted else str(existing["id"])
    if existing is not None:
        folder_or_label_refs = sorted(set(json.loads(existing["folder_or_label_refs"])) | set(folder_or_label_refs))

    connection.execute(
        """
        INSERT INTO messages (
            id,
            account_id,
            thread_id,
            provider_message_id,
            sender,
            to_recipients,
            cc_recipients,
            bcc_recipients,
            sent_at,
            received_at,
            snippet,
            body_text,
            folder_or_label_refs,
            flags
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(account_id, provider_message_id) DO UPDATE SET
            thread_id = excluded.thread_id,
            sender = excluded.sender,
            to_recipients = excluded.to_recipients,
            cc_recipients = excluded.cc_recipients,
            bcc_recipients = excluded.bcc_recipients,
            sent_at = excluded.sent_at,
            received_at = excluded.received_at,
            snippet = excluded.snippet,
            body_text = excluded.body_text,
            folder_or_label_refs = excluded.folder_or_label_refs,
            flags = excluded.flags
        """,
        (
            effective_message_id,
            account_id,
            thread_id,
            provider_message_id,
            _normalize_address(sender),
            _json_dumps([_normalize_address(item) for item in to_recipients]),
            _json_dumps([_normalize_address(item) for item in cc_recipients]),
            _json_dumps([_normalize_address(item) for item in bcc_recipients]),
            sent_at,
            received_at,
            snippet,
            body_text,
            _json_dumps(folder_or_label_refs),
            _json_dumps(flags),
        ),
    )
    return inserted


def link_message_to_folder(
    connection: sqlite3.Connection,
    *,
    folder_id: str,
    provider_message_id: str,
    uid: int,
    flags: list[str],
) -> None:
    """Link a normalized message into a provider folder by UID."""

    row = connection.execute(
        """SELECT messages.id FROM messages
        JOIN folders ON folders.account_id = messages.account_id
        WHERE folders.id = ? AND messages.provider_message_id = ?""",
        (folder_id, provider_message_id),
    ).fetchone()
    if row is None:
        raise ValueError(f"message '{provider_message_id}' must exist before it can be linked to a folder")

    connection.execute(
        """
        INSERT INTO folder_messages (folder_id, message_id, uid, flags)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(folder_id, uid) DO UPDATE SET
            message_id = excluded.message_id,
            flags = excluded.flags
        """,
        (folder_id, row["id"], uid, _json_dumps(flags)),
    )


def get_table_counts(config: AppConfig) -> dict[str, int]:
    """Return record counts for tracked tables."""

    initialize_database(config)
    counts: dict[str, int] = {}
    with connect_db(config.db_path) as connection:
        for table in COUNTED_TABLES:
            row = connection.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
            counts[table] = int(row["count"])
    return counts


def get_pending_action_proposal_count(config: AppConfig) -> int:
    """Return action proposals that still need review or provider execution."""

    initialize_database(config)
    with connect_db(config.db_path) as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM action_proposals
            WHERE review_status = 'pending'
               OR (review_status != 'rejected' AND execution_status IN ('pending', 'executing', 'uncertain', 'failed', 'blocked'))
            """
        ).fetchone()
    return int(row["count"])


def upsert_provider_draft_snapshot(
    connection: sqlite3.Connection,
    *,
    action_id: str,
    batch_id: str,
    draft_proposal_id: str | None,
    account_id: str,
    provider: str,
    provider_ref: str,
    mailbox: str,
    uid: int | None,
    provider_message_id: str | None,
    subject: str,
    from_address: str,
    to_recipients: list[str],
    cc_recipients: list[str],
    bcc_recipients: list[str],
    flags: list[str],
    internal_date: str | None,
    synced_at: str,
    status: str,
) -> None:
    """Persist the latest provider-visible snapshot for a materialized draft."""

    connection.execute(
        """
        INSERT INTO provider_drafts (
            action_id,
            batch_id,
            draft_proposal_id,
            account_id,
            provider,
            provider_ref,
            mailbox,
            uid,
            provider_message_id,
            subject,
            from_address,
            to_recipients,
            cc_recipients,
            bcc_recipients,
            flags,
            internal_date,
            synced_at,
            status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(action_id) DO UPDATE SET
            batch_id = excluded.batch_id,
            draft_proposal_id = excluded.draft_proposal_id,
            account_id = excluded.account_id,
            provider = excluded.provider,
            provider_ref = excluded.provider_ref,
            mailbox = excluded.mailbox,
            uid = excluded.uid,
            provider_message_id = excluded.provider_message_id,
            subject = excluded.subject,
            from_address = excluded.from_address,
            to_recipients = excluded.to_recipients,
            cc_recipients = excluded.cc_recipients,
            bcc_recipients = excluded.bcc_recipients,
            flags = excluded.flags,
            internal_date = excluded.internal_date,
            synced_at = excluded.synced_at,
            status = excluded.status
        """,
        (
            action_id,
            batch_id,
            draft_proposal_id,
            account_id,
            provider,
            provider_ref,
            mailbox,
            uid,
            provider_message_id,
            subject,
            _normalize_address(from_address) if from_address else "",
            _json_dumps([_normalize_address(item) for item in to_recipients]),
            _json_dumps([_normalize_address(item) for item in cc_recipients]),
            _json_dumps([_normalize_address(item) for item in bcc_recipients]),
            _json_dumps(flags),
            internal_date,
            synced_at,
            status,
        ),
    )


def new_identifier(prefix: str) -> str:
    """Create a readable local identifier."""

    return f"{prefix}_{uuid4().hex[:8]}"


def create_draft_proposal(
    connection: sqlite3.Connection,
    *,
    proposal_id: str,
    thread_id: str,
    account_id: str | None = None,
    to_recipients: list[str] | None = None,
    cc_recipients: list[str] | None = None,
    bcc_recipients: list[str] | None = None,
    in_reply_to: str | None = None,
    reference_message_ids: list[str] | None = None,
    context_refs: list[str] | None = None,
    style_profile: str,
    proposed_subject: str,
    proposed_body: str,
    confidence: float,
    rationale: str,
    created_at: str,
) -> None:
    """Persist a local draft proposal."""

    connection.execute(
        """
        INSERT INTO draft_proposals (
            id,
            thread_id,
            account_id,
            to_recipients,
            cc_recipients,
            bcc_recipients,
            in_reply_to,
            reference_message_ids,
            context_refs,
            style_profile,
            proposed_subject,
            proposed_body,
            confidence,
            rationale,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            proposal_id,
            thread_id,
            account_id,
            _json_dumps([_normalize_address(item) for item in (to_recipients or [])]),
            _json_dumps([_normalize_address(item) for item in (cc_recipients or [])]),
            _json_dumps([_normalize_address(item) for item in (bcc_recipients or [])]),
            in_reply_to,
            _json_dumps(reference_message_ids or []),
            _json_dumps(context_refs or []),
            style_profile,
            proposed_subject,
            proposed_body,
            confidence,
            rationale,
            created_at,
        ),
    )


def create_review_batch(
    connection: sqlite3.Connection,
    *,
    batch_id: str,
    batch_type: str,
    status: str,
    scope_count: int,
    highest_risk: str,
    reason: str,
    rollback_available: bool,
    created_at: str,
) -> None:
    """Persist a review batch."""

    connection.execute(
        """
        INSERT INTO review_batches (
            id, type, status, scope_count, highest_risk, reason, rollback_available, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            batch_id,
            batch_type,
            status,
            scope_count,
            highest_risk,
            reason,
            1 if rollback_available else 0,
            created_at,
        ),
    )


def update_review_batch_status(connection: sqlite3.Connection, *, batch_id: str, status: str) -> None:
    """Update review batch lifecycle state."""

    connection.execute("UPDATE review_batches SET status = ? WHERE id = ?", (status, batch_id))


def create_action_proposal(
    connection: sqlite3.Connection,
    *,
    proposal_id: str,
    batch_id: str,
    action_type: str,
    scope: list[str],
    reason: str,
    evidence_refs: list[str],
    draft_proposal_id: str | None,
    risk_level: str,
    review_status: str,
    execution_status: str,
    created_at: str,
    provider_ref: str | None = None,
) -> None:
    """Persist an action proposal."""

    connection.execute(
        """
        INSERT INTO action_proposals (
            id,
            batch_id,
            type,
            scope,
            reason,
            evidence_refs,
            draft_proposal_id,
            provider_ref,
            risk_level,
            review_status,
            execution_status,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            proposal_id,
            batch_id,
            action_type,
            _json_dumps(scope),
            reason,
            _json_dumps(evidence_refs),
            draft_proposal_id,
            provider_ref,
            risk_level,
            review_status,
            execution_status,
            created_at,
        ),
    )


def update_batch_action_statuses(
    connection: sqlite3.Connection,
    *,
    batch_id: str,
    review_status: str | None = None,
    execution_status: str | None = None,
) -> None:
    """Update review and execution status for all actions in a batch."""

    assignments: list[str] = []
    parameters: list[object] = []
    if review_status is not None:
        assignments.append("review_status = ?")
        parameters.append(review_status)
    if execution_status is not None:
        assignments.append("execution_status = ?")
        parameters.append(execution_status)
    if not assignments:
        return
    parameters.append(batch_id)
    connection.execute(
        f"UPDATE action_proposals SET {', '.join(assignments)} WHERE batch_id = ?",
        tuple(parameters),
    )


def update_action_proposal_execution(
    connection: sqlite3.Connection,
    *,
    proposal_id: str,
    execution_status: str,
    provider_ref: str | None = None,
) -> None:
    """Persist execution status for a single action proposal."""

    if provider_ref is None:
        connection.execute(
            "UPDATE action_proposals SET execution_status = ? WHERE id = ?",
            (execution_status, proposal_id),
        )
        return
    connection.execute(
        "UPDATE action_proposals SET execution_status = ?, provider_ref = ? WHERE id = ?",
        (execution_status, provider_ref, proposal_id),
    )


def delete_draft_proposals(connection: sqlite3.Connection, *, proposal_ids: list[str]) -> None:
    """Remove local draft proposals."""

    if not proposal_ids:
        return
    placeholders = ", ".join("?" for _ in proposal_ids)
    connection.execute(f"DELETE FROM draft_proposals WHERE id IN ({placeholders})", tuple(proposal_ids))


def create_audit_event(
    connection: sqlite3.Connection,
    *,
    event_id: str,
    actor: str,
    action_type: str,
    target_ref: str,
    timestamp: str,
    result: str,
    before_state: dict[str, Any] | None = None,
    after_state: dict[str, Any] | None = None,
) -> None:
    """Persist an audit event."""

    connection.execute(
        """
        INSERT INTO audit_events (
            id, actor, action_type, target_ref, timestamp, before_state, after_state, result
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            actor,
            action_type,
            target_ref,
            timestamp,
            _json_dumps(before_state) if before_state is not None else None,
            _json_dumps(after_state) if after_state is not None else None,
            result,
        ),
    )
