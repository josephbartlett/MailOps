"""Search helpers."""

from __future__ import annotations

from pydantic import BaseModel

from mailops.core.config import AppConfig
from mailops.index.db import connect_db, initialize_database


class SearchRequest(BaseModel):
    query: str
    account_id: str | None = None
    limit: int = 20


def search_messages(config: AppConfig, request: SearchRequest) -> list[dict[str, str]]:
    """Query the local SQLite index for matching messages."""

    initialize_database(config)
    if not request.query.strip():
        return []

    pattern = f"%{request.query.strip().lower()}%"
    sql = """
        SELECT
            messages.id AS message_id,
            threads.id AS thread_id,
            threads.account_id AS account_id,
            threads.subject AS subject,
            messages.sender AS sender,
            messages.snippet AS snippet,
            COALESCE(messages.received_at, messages.sent_at, '') AS sort_time
        FROM messages
        JOIN threads ON threads.id = messages.thread_id
        WHERE (
            LOWER(threads.subject) LIKE ?
            OR LOWER(messages.sender) LIKE ?
            OR LOWER(messages.snippet) LIKE ?
            OR LOWER(messages.body_text) LIKE ?
        )
    """
    parameters: list[object] = [pattern, pattern, pattern, pattern]
    if request.account_id:
        sql += " AND threads.account_id = ?"
        parameters.append(request.account_id)
    sql += " ORDER BY sort_time DESC LIMIT ?"
    parameters.append(request.limit)

    with connect_db(config.db_path) as connection:
        rows = connection.execute(sql, tuple(parameters)).fetchall()

    return [
        {
            "message_id": str(row["message_id"]),
            "thread_id": str(row["thread_id"]),
            "account_id": str(row["account_id"]),
            "subject": str(row["subject"]),
            "sender": str(row["sender"]),
            "snippet": str(row["snippet"]),
            "sort_time": str(row["sort_time"]),
        }
        for row in rows
    ]
