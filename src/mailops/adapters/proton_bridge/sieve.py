"""Sieve proposal helpers for Proton."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field


class SieveCondition(BaseModel):
    field: str
    match_type: str
    value: str


class SieveRuleProposal(BaseModel):
    intent: str
    structured_conditions: list[SieveCondition] = Field(default_factory=list)
    target_mailbox: str
    generated_rule_text: str
    explanation: str
    preview: str


_EMAIL_RE = re.compile(r"[\w.!#$%&'*+/=?^_`{|}~-]+@[\w.-]+\.[a-z]{2,}", re.IGNORECASE)
_DOMAIN_RE = re.compile(r"\bfrom\s+(?P<domain>[a-z0-9.-]+\.[a-z]{2,})\b", re.IGNORECASE)
_SUBJECT_CONTAINS_RE = re.compile(r"\bsubject\s+(?:contains|has|includes)\s+(?P<value>[^,.;]+)", re.IGNORECASE)
_TO_MAILBOX_RE = re.compile(r"\b(?:to|into)\s+(?:folder|label|mailbox)?\s*['\"]?(?P<mailbox>[a-z0-9][\w &/.-]{1,80})['\"]?", re.IGNORECASE)
_NOISE_WORDS = {
    "archive",
    "filter",
    "from",
    "future",
    "messages",
    "move",
    "proton",
    "rule",
    "sieve",
}


def generate_sieve_rule_proposal(prompt: str) -> SieveRuleProposal:
    """Generate a Proton Sieve preview from a constrained natural-language prompt."""

    conditions = _extract_conditions(prompt)
    target_mailbox = _target_mailbox(prompt)
    if not conditions:
        conditions.append(SieveCondition(field="subject", match_type="contains", value=_topic_fallback(prompt)))

    require_extensions = ['"fileinto"']
    test = _render_test(conditions)
    generated_rule_text = "\n".join(
        [
            f"require [{', '.join(require_extensions)}];",
            "",
            f"if {test} {{",
            f"    fileinto {_sieve_string(target_mailbox)};",
            "    stop;",
            "}",
        ]
    )
    readable_conditions = ", ".join(
        f"{condition.field} {condition.match_type} {_quote(condition.value)}" for condition in conditions
    )
    return SieveRuleProposal(
        intent=prompt,
        structured_conditions=conditions,
        target_mailbox=target_mailbox,
        generated_rule_text=generated_rule_text,
        explanation=(
            "Review-only Proton Sieve proposal. It matches future messages where "
            f"{readable_conditions} and files them into {_quote(target_mailbox)}."
        ),
        preview=(
            "Would affect future matching Proton messages only. MailOps does not apply this rule; "
            "copy it into Proton after manual review if it is correct."
        ),
    )


def _extract_conditions(prompt: str) -> list[SieveCondition]:
    conditions: list[SieveCondition] = []
    email_match = _EMAIL_RE.search(prompt)
    if email_match is not None:
        conditions.append(SieveCondition(field="from", match_type="is", value=email_match.group(0).lower()))
    else:
        domain_match = _DOMAIN_RE.search(prompt)
        if domain_match is not None:
            conditions.append(SieveCondition(field="from_domain", match_type="is", value=domain_match.group("domain").lower()))

    subject_match = _SUBJECT_CONTAINS_RE.search(prompt)
    if subject_match is not None:
        subject_value = _clean_value(subject_match.group("value"))
        if subject_value:
            conditions.append(SieveCondition(field="subject", match_type="contains", value=subject_value))
    return conditions


def _target_mailbox(prompt: str) -> str:
    lowered = prompt.lower()
    if "archive" in lowered:
        return "Archive"
    match = _TO_MAILBOX_RE.search(prompt)
    if match is None:
        return "Archive"
    mailbox = _clean_value(match.group("mailbox"))
    if not mailbox:
        return "Archive"
    if "/" in mailbox:
        return mailbox
    if any(token in lowered for token in ("label", "labels")):
        return f"Labels/{mailbox}"
    if any(token in lowered for token in ("folder", "folders")):
        return f"Folders/{mailbox}"
    return mailbox


def _topic_fallback(prompt: str) -> str:
    tokens = [
        token
        for token in re.findall(r"[a-z0-9_-]+", prompt.lower())
        if len(token) > 2 and token not in _NOISE_WORDS
    ]
    if not tokens:
        return "review"
    return " ".join(tokens[:4])


def _render_test(conditions: list[SieveCondition]) -> str:
    rendered = [_render_condition(condition) for condition in conditions]
    if len(rendered) == 1:
        return rendered[0]
    return f"allof ({', '.join(rendered)})"


def _render_condition(condition: SieveCondition) -> str:
    if condition.field == "from":
        return f'address :is "From" {_sieve_string(condition.value)}'
    if condition.field == "from_domain":
        return f'address :domain :is "From" {_sieve_string(condition.value)}'
    return f'header :contains "Subject" {_sieve_string(condition.value)}'


def _clean_value(value: str) -> str:
    cleaned = value.strip().strip("'\"")
    for separator in (" to ", " into ", " then ", " and "):
        if separator in cleaned.lower():
            cleaned = cleaned[: cleaned.lower().index(separator)].strip()
    return cleaned.strip(" .,:;")


def _sieve_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _quote(value: str) -> str:
    return f"'{value}'"
