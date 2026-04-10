"""Text normalization helpers."""

from __future__ import annotations

from rich.console import Console


def compact_whitespace(value: str) -> str:
    """Collapse repeated whitespace into single spaces."""

    return " ".join(value.split())


def safe_console_text(value: object, console: Console) -> str:
    """Render text safely for terminals with limited encodings."""

    text = str(value)
    encoding = getattr(console.file, "encoding", None) or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding, errors="replace")
