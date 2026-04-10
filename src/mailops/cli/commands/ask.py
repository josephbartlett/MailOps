"""Implementation of `mailops ask`."""

import re

import typer

from rich.table import Table

from mailops.agent.drafts import create_draft_review_batch
from mailops.agent.planner import compile_request
from mailops.agent.tools import explain_plan
from mailops.adapters.proton_bridge.sieve import generate_sieve_rule_proposal
from mailops.cli.commands.rules import render_rule_proposal
from mailops.cli.runtime import build_runtime
from mailops.index.triage import list_triage_threads, refresh_thread_triage
from mailops.utils.text import safe_console_text

_OLDER_THAN_DAYS_RE = re.compile(r"older than (?P<count>\d+) days?", re.IGNORECASE)
_CLIENT_EXCLUDE_TAGS = {
    "recruiter outreach",
    "recruiting process",
    "logistics request",
    "cold outreach",
    "calendar invite",
    "broadcast-style message",
    "automated sender",
    "informational security notice",
}
_FINANCE_INCLUDE_TAGS = {"finance-related"}
_SCHEDULING_INCLUDE_TAGS = {"scheduling-related", "calendar invite"}
_PERSONAL_INCLUDE_TAGS = {"direct to you"}


def ask_command(prompt: str = typer.Argument(..., help="Natural-language operator request.")) -> None:
    """Compile a natural-language request into explicit actions or queries."""

    runtime = build_runtime()
    plan = compile_request(prompt)

    runtime.console.print(f"Intent: {plan.intent}")
    runtime.console.print(plan.summary)

    table = Table(title="Compiled Actions")
    table.add_column("Type")
    table.add_column("Risk")
    table.add_column("Reason")

    for action in plan.actions:
        table.add_row(action.type.value, action.risk_level.value, action.reason)

    if not plan.actions:
        table.add_row("none", "low", "No action generated from the prompt.")

    runtime.console.print(table)
    for line in explain_plan(plan):
        runtime.console.print(f"- {line}")

    if plan.intent == "draft_queue":
        result = create_draft_review_batch(runtime.config, prompt)
        runtime.console.print(result.reason)
        if result.batch_id is not None:
            runtime.console.print(
                f"Created review batch `{result.batch_id}` with {result.proposals_created} local draft proposal(s)."
            )
            runtime.console.print(f"Inspect it with `mailops review batch show {result.batch_id}`.")
        return

    if plan.intent == "followup_analysis":
        refresh_thread_triage(runtime.config)
        rows = list_triage_threads(
            runtime.config,
            older_than_days=_older_than_days_from_prompt(prompt),
            account_id="all",
            states=("waiting_on_me",),
            limit=50,
        )
        rows = _filter_followup_rows(rows, prompt)[:10]
        followup_table = Table(title="Follow-up Candidates")
        followup_table.add_column("Account")
        followup_table.add_column("Subject")
        followup_table.add_column("Score")
        if not rows:
            followup_table.add_row("(none)", "No waiting-on-me threads matched the prompt.", "-")
        else:
            for row in rows:
                followup_table.add_row(
                    safe_console_text(str(row["account_id"]), runtime.console),
                    safe_console_text(str(row["subject"]), runtime.console),
                    safe_console_text(f"{float(row['importance_score']):.0%}", runtime.console),
                )
        runtime.console.print(followup_table)
        return

    if plan.intent == "rule_generation":
        proposal = generate_sieve_rule_proposal(prompt)
        render_rule_proposal(runtime.console, proposal)


def _older_than_days_from_prompt(prompt: str) -> int:
    lowered = prompt.lower()
    explicit = _OLDER_THAN_DAYS_RE.search(lowered)
    if explicit is not None:
        return int(explicit.group("count"))
    if "this week" in lowered:
        return 7
    for token in lowered.split():
        if token.endswith("d") and token[:-1].isdigit():
            return int(token[:-1])
    return 3


def _filter_followup_rows(rows: list[dict[str, object]], prompt: str) -> list[dict[str, object]]:
    lowered = prompt.lower()
    filtered = list(rows)
    if any(token in lowered for token in ("client", "customer")):
        filtered = [row for row in filtered if not _has_any_tag(row, _CLIENT_EXCLUDE_TAGS)]
    if any(token in lowered for token in ("finance", "invoice", "payment", "billing")):
        filtered = [row for row in filtered if _has_any_tag(row, _FINANCE_INCLUDE_TAGS)]
    if any(token in lowered for token in ("schedule", "scheduling", "meeting", "availability", "calendar")):
        filtered = [row for row in filtered if _has_any_tag(row, _SCHEDULING_INCLUDE_TAGS)]
    if "personally" in lowered:
        filtered = [row for row in filtered if _has_any_tag(row, _PERSONAL_INCLUDE_TAGS)]
    return filtered


def _has_any_tag(row: dict[str, object], target_tags: set[str]) -> bool:
    raw_tags = row.get("classification_tags", [])
    if not isinstance(raw_tags, list):
        return False
    tags = {str(tag).strip().lower() for tag in raw_tags if str(tag).strip()}
    return bool(tags & target_tags)
