"""Higher-level query helpers."""

from __future__ import annotations

from mailops.core.config import AppConfig
from mailops.index.triage import list_triage_threads


def list_unanswered_threads(config: AppConfig, *, older_than_days: int, account_id: str) -> list[dict[str, str]]:
    """Return threads likely waiting on the operator."""

    rows = list_triage_threads(
        config,
        older_than_days=older_than_days,
        account_id=account_id,
        states=("waiting_on_me",),
        limit=100,
    )
    return [
        {
            "id": str(row["id"]),
            "account_id": str(row["account_id"]),
            "subject": str(row["subject"]),
            "last_message_at": str(row["last_message_at"]),
            "unread_count": str(row["unread_count"]),
            "importance_score": f"{float(row['importance_score']):.2f}",
            "classification_tags": ", ".join(list(row["classification_tags"])[:4]),
            "followup_state": str(row["followup_state"]),
        }
        for row in rows
    ]
