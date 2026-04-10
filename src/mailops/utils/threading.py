"""Email subject and threading helpers."""

from __future__ import annotations

import re

_REPLY_PREFIX_RE = re.compile(r"^(re|fw|fwd):\s*", re.IGNORECASE)


def normalize_subject(subject: str) -> str:
    """Strip common reply and forward prefixes from a subject."""

    value = subject.strip()
    while True:
        updated = _REPLY_PREFIX_RE.sub("", value)
        if updated == value:
            return updated
        value = updated.strip()
