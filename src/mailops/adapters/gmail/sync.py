"""Gmail sync placeholder."""

from __future__ import annotations

from pydantic import BaseModel


class GmailSyncCursor(BaseModel):
    history_id: str | None = None

