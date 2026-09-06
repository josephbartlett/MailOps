from __future__ import annotations

from io import StringIO

from rich.table import Table

from mailops.utils.text import LiteralConsole, safe_console_text


def test_cli_tables_preserve_markup_and_emoji_shaped_mail_text():
    stream = StringIO()
    console = LiteralConsole(file=stream, width=180, force_terminal=True, color_system="truecolor", no_color=False)
    value = "[conceal]hidden@example.com[/conceal] [link=https://example.invalid]recipient[/link] :smile:"
    table = Table()
    table.add_column("Envelope")
    table.add_row(value)
    console.print(table)
    output = stream.getvalue()
    for token in value.split():
        assert token in output
    assert "\x1b[8m" not in output
    assert "\x1b]8;" not in output


def test_cli_plain_strings_expose_terminal_and_bidi_controls():
    stream = StringIO()
    console = LiteralConsole(file=stream, width=180)
    console.print("visible\x1b[2J\b\r\u202ehidden")
    output = stream.getvalue()
    assert r"visible\x1b[2J\x08\r\u202ehidden" in output
    assert "\x1b" not in output
    assert "\u202e" not in output


def test_console_encoding_does_not_replace_distinct_characters_with_question_marks():
    class AsciiStream(StringIO):
        encoding = "ascii"

    console = LiteralConsole(file=AsciiStream())
    assert safe_console_text("caf\u00e9\nnext", console) == "caf\\xe9\nnext"
