# Contributing

MailOps is local-first and review-first. Contributions should preserve the operator loop:

```text
sync -> inspect -> triage -> draft -> review -> apply -> audit
```

## Setup

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

Use the demo mailbox for local development that does not require Proton Bridge:

```bash
mailops demo seed
mailops status
mailops search "invoice"
mailops triage --since 0d
```

## Product Boundaries

- Keep MailOps local-first by default.
- Preserve provider-specific behavior.
- Route risky actions through explicit review primitives.
- Do not add silent send, delete, bulk archive, or auto-rule-application paths.
- Do not log credentials, auth headers, or raw mailbox content casually.

## Validation

Before closing a change:

```bash
python -m pytest
PYTHONPATH=src python -m mailops.cli.main --help
```

If Proton behavior changed, also verify Bridge discovery/listing from an environment where Proton Bridge is reachable.

## Versioning and Changelog

MailOps follows Semantic Versioning. Update `CHANGELOG.md` for user-visible fixes, features, safety-boundary changes, packaging changes, and release-process changes.

Before publishing a release, follow `docs/release-process.md` and `docs/release-checklist.md`. Do not commit, push, tag, publish, change remotes, or change repository visibility unless the operator explicitly approves that exact action.
