"""Text normalization helpers."""

from __future__ import annotations

from typing import Any
import unicodedata

from rich.console import Console
from rich.text import Text


def compact_whitespace(value: str) -> str:
    """Collapse repeated whitespace into single spaces."""

    return " ".join(value.split())


def safe_console_text(value: object, console: Console) -> str:
    """Expose terminal controls and unsupported characters as visible escapes."""

    text = "".join(
        character.encode("unicode_escape").decode("ascii")
        if unicodedata.category(character) in {"Cc", "Cf"} and character not in "\n\t"
        else character
        for character in str(value)
    )
    encoding = getattr(console.file, "encoding", None) or "utf-8"
    return text.encode(encoding, errors="backslashreplace").decode(encoding)


class LiteralConsole(Console):
    """Render CLI string data literally while retaining explicit table styles."""

    def render_str(self, text: str, **kwargs: Any) -> Text:
        kwargs.update(markup=False, emoji=False, highlight=False)
        return super().render_str(safe_console_text(text, self), **kwargs)
