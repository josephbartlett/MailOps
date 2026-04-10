"""Date helpers."""

from __future__ import annotations

import re

_RELATIVE_DAYS_RE = re.compile(r"^(?P<count>\d+)d$")


def parse_relative_days(value: str) -> int:
    """Parse a compact relative day string such as `3d`."""

    match = _RELATIVE_DAYS_RE.match(value.strip())
    if not match:
        raise ValueError("expected relative day window like '3d'")
    return int(match.group("count"))

