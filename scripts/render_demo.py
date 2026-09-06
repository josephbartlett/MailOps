"""Record an offline synthetic CLI workflow and render selected output as SVG."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from html import escape
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"
WIDTH = 112


def run_cli(arguments: list[str], *, env: dict[str, str], cwd: Path) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "mailops.cli.main", *arguments],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    if result.stderr.strip():
        raise RuntimeError(f"Unexpected CLI stderr: {result.stderr}")
    return "\n".join(line.rstrip() for line in result.stdout.splitlines()).rstrip()


def command_text(arguments: list[str]) -> str:
    return "mailops " + subprocess.list2cmdline(arguments)


def before_heading(output: str, heading: str) -> str:
    """Keep complete leading tables; omit the later tables explicitly."""
    lines = output.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == heading:
            return "\n".join(lines[:index]).rstrip()
    raise ValueError(f"Expected CLI heading was not found: {heading}")


def review_excerpt(output: str) -> str:
    lines = output.splitlines()
    fields = [line for line in lines if line.startswith(("│ status ", "│ highest_risk "))]
    start = lines.index("Draft refs:")
    stop = next(index for index, line in enumerate(lines) if line.strip() == "Provider Draft Snapshots")
    return "\n".join([*fields, "[other review fields and tables omitted]", *lines[start:stop]]).rstrip()


def render_svg(sections: list[tuple[str, str]]) -> str:
    line_height = 21
    y = 142
    elements = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="HEIGHT" '
        'viewBox="0 0 1440 HEIGHT" role="img" aria-labelledby="title description">',
        '<title id="title">MailOps synthetic local workflow</title>',
        '<desc id="description">Selected actual command output from a temporary synthetic '
        'mailbox: one invoice search result, two threads waiting on the operator, a local '
        'draft proposal, and its pending review. No provider was contacted.</desc>',
        '<rect width="1440" height="HEIGHT" rx="22" fill="#0b1320"/>',
        '<circle cx="39" cy="35" r="6" fill="#ff7975"/>',
        '<circle cx="61" cy="35" r="6" fill="#f4c66b"/>',
        '<circle cx="83" cy="35" r="6" fill="#59d6b2"/>',
        '<text x="115" y="41" fill="#f3f7fc" font-family="sans-serif" '
        'font-size="20" font-weight="700">MailOps</text>',
        '<text x="1400" y="41" text-anchor="end" fill="#78dfc5" '
        'font-family="sans-serif" font-size="16">SYNTHETIC LOCAL DEMO</text>',
        '<text x="32" y="87" fill="#f3f7fc" font-family="sans-serif" '
        'font-size="28" font-weight="700">Search. Triage. Prepare. Review.</text>',
        '<text x="32" y="114" fill="#a8b7ce" font-family="sans-serif" '
        'font-size="16">Recorded CLI output excerpts · example.com fixture · no provider access</text>',
    ]
    for label, output in sections:
        lines = output.splitlines()
        height = 49 + len(lines) * line_height
        elements.append(
            f'<rect x="24" y="{y}" width="1392" height="{height}" rx="10" '
            'fill="#111e30" stroke="#293c55"/>'
        )
        elements.append(
            f'<text x="42" y="{y + 27}" fill="#78dfc5" font-family="monospace" '
            f'font-size="17" font-weight="700">$ {escape(label)}</text>'
        )
        for index, line in enumerate(lines):
            elements.append(
                f'<text x="42" y="{y + 53 + index * line_height}" fill="#e2eaf5" '
                'font-family="Consolas, DejaVu Sans Mono, monospace" font-size="17" '
                f'xml:space="preserve">{escape(line)}</text>'
            )
        y += height + 16
    elements.append(
        f'<text x="32" y="{y + 12}" fill="#a8b7ce" font-family="sans-serif" '
        'font-size="16">Full commands and unabridged output: docs/demo.md · Proposal remains pending.</text>'
    )
    elements.append("</svg>")
    return "\n".join(elements).replace("HEIGHT", str(y + 36)) + "\n"


def main() -> int:
    transcript: list[tuple[list[str], str]] = []
    with TemporaryDirectory(prefix="mailops-demo-") as directory:
        temporary = Path(directory)
        env = {key: value for key, value in os.environ.items() if not key.upper().startswith("MAILOPS_")}
        env.update({
            "MAILOPS_HOME": str(temporary / ".mailops"),
            "PYTHONPATH": str(ROOT / "src"),
            "PYTHONUTF8": "1",
            "COLUMNS": str(WIDTH),
            "NO_COLOR": "1",
            "TERM": "dumb",
        })

        def record(arguments: list[str]) -> str:
            output = run_cli(arguments, env=env, cwd=temporary)
            transcript.append((arguments, output))
            return output

        record(["demo", "seed"])
        record(["status"])
        search = record(["search", "invoice", "--limit", "1"])
        inspected = record(["inspect", "thread", "demo-thread-finance"])
        triage = record(["triage", "--since", "0d"])
        draft = record([
            "draft", "create", "--provider", "demo_local", "--from-account", "demo@example.com",
            "--to", "vendor@example.com", "--subject", "Invoice 1042 follow-up",
            "--body", "I will review invoice 1042 and follow up.",
            "--context-ref", "thread:demo-thread-finance",
        ])
        match = re.search(r"Created review batch `(batch_[a-z0-9]+)`", draft)
        if match is None:
            raise ValueError("Draft command did not return a review batch identifier")
        review = record(["review", "batch", "show", match[1]])
        if "pending" not in review or "vendor@example.com" not in review:
            raise ValueError("The synthetic draft was not available for pending review")

    ASSETS.mkdir(parents=True, exist_ok=True)
    transcript_path = ASSETS / "workflow-demo.txt"
    transcript_path.write_text(
        "MailOps synthetic local demo: complete CLI stdout, with trailing line padding trimmed.\n"
        "Generated by scripts/render_demo.py in temporary state with no provider commands.\n"
        "Dates and generated proposal identifiers vary on each run.\n\n"
        + "\n\n".join(f"$ {command_text(args)}\n{output}" for args, output in transcript)
        + "\n",
        encoding="utf-8",
    )
    image_path = ASSETS / "workflow-demo.svg"
    inspected_lines = inspected.splitlines()
    subject = next(line for line in inspected_lines if line.startswith("│ subject "))
    body_start = inspected_lines.index("Body preview for demo-message-finance:")
    search_excerpt = "\n".join([
        before_heading(search, "Matches"),
        "[matches table omitted; inspected matching thread excerpt below]",
        subject,
        *inspected_lines[body_start:],
    ])
    image_path.write_text(render_svg([
        ("mailops search invoice --limit 1; mailops inspect thread demo-thread-finance", search_excerpt),
        ("mailops triage --since 0d", before_heading(triage, "Waiting On Me")),
        ("mailops draft create --provider demo_local ...", draft),
        (f"mailops review batch show {match[1]}", review_excerpt(review)),
    ]), encoding="utf-8")
    print(f"Recorded {len(transcript)} successful local CLI commands.")
    print(f"Wrote {transcript_path.relative_to(ROOT)} and {image_path.relative_to(ROOT)}.")
    print("Synthetic temporary state removed; no provider calls or apply commands were run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
