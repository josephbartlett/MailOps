---
name: mailops-product-development
description: "Build, modify, or review MailOps code, tests, schema, CLI behavior, docs, or local workflows while preserving the product boundary: local-first, provider-aware, review-first inbox operations. Use when working in the MailOps repository or porting MailOps patterns to another repo."
---

# MailOps Product Development

Use this skill for MailOps implementation work. Preserve the operator loop:

```text
sync -> inspect -> triage -> draft -> review -> apply -> audit
```

## First Steps

1. Read `AGENTS.md` if it exists in the repository root.
2. Inspect the touched modules before editing.
3. Keep changes scoped to the current workflow and provider boundary.
4. Prefer typed Python and existing MailOps helpers over speculative abstraction.

## Product Rules

- Keep MailOps local-first by default.
- Preserve provider-specific behavior; do not flatten Proton and Gmail into a fake universal transport.
- Keep high-risk actions review-first.
- Do not add silent send, delete, bulk archive, bulk move, or auto-rule-application paths.
- Do not log credentials, auth headers, or raw mailbox content casually.
- Do not commit, push, tag, publish, or change remotes unless the operator explicitly approves that exact source-control action.
- Compile natural-language behavior into explicit structured actions, queries, or review batches.

## Code Patterns

- Local state changes require schema/bootstrap helpers, query/update helpers, models, CLI display, and tests to move together.
- Provider functionality belongs in the provider adapter or provider-specific review orchestration.
- Proton Bridge discovery, sync, draft materialization, and provider draft lookup must stay separate concerns.
- Gmail remains API-first; do not force Gmail through IMAP for symmetry.
- Rule generation may preview provider-native artifacts, but provider rule application must remain unimplemented unless a future reviewed policy gate is added.
- Keep repository guidance concise and link to maintained implementation and workflow docs. Turn observed failures into focused regression coverage or a useful automated check; use independent review when the change warrants it, without fixed reviewer roles or duplicate orchestration systems.

## Testing

Install the repository's development dependencies as documented, then run the shared offline validation entrypoint before closing work:

```bash
python scripts/validate.py
```

The entrypoint runs repository checks, lint, tests and CLI smoke checks against temporary state. For focused test runs, use `python -m pytest <test_path>`. Use the source tree for individual CLI checks; on PowerShell, set `$env:PYTHONPATH = "src"`.

If Proton behavior changed, also verify discovery:

```bash
PYTHONPATH=src python -m mailops.cli.main connect proton
```

Use a unique temporary `MAILOPS_HOME` for CLI smoke checks and `mailops demo seed`; never seed the operator's mailbox store. Restore previous environment values in `finally`. `doctor` actively probes Bridge TCP endpoints, so reserve it for requested connection diagnostics. Read `$mailops-proton-validation` only when live Proton validation is in scope; report skipped live checks honestly.
