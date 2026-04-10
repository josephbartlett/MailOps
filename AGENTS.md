# AGENTS.md

This repository is designed to work well with coding agents, but only if they respect the product boundaries.

## Mission

MailOps is a local-first inbox operations harness. It is not a generic AI mail client and it is not an autonomous inbox takeover tool.

Every change should reinforce this operator loop:

1. sync
2. inspect
3. triage
4. draft
5. review
6. apply
7. audit

## Non-negotiable product rules

- Keep the system local-first by default.
- Preserve provider-aware behavior. Do not flatten Proton and Gmail into a fake universal transport.
- High-risk actions stay review-first.
- Do not add silent send, delete, bulk archive, or auto-rule-application paths.
- Do not log credentials, auth headers, or raw mailbox content casually.
- Do not commit, push, tag, publish, change remotes, or otherwise mutate source-control or release state without explicit operator permission for that exact action.

## Current architecture

- `src/mailops/core`: config, models, actions, policies, logging, exceptions
- `src/mailops/adapters/proton_bridge`: Bridge discovery, IMAP sync, draft materialization, WSL networking helpers, future SMTP and Sieve work
- `src/mailops/adapters/gmail`: placeholder for future Gmail API implementation
- `src/mailops/index`: SQLite schema and query helpers
- `src/mailops/cli`: Typer command surface
- `src/mailops/agent`: natural-language planning into explicit actions
- `src/mailops/review`: review batch primitives and provider execution orchestration

## How to work in this repo

- Prefer concrete, typed Python over speculative abstraction.
- If you add provider functionality, keep provider-specific capabilities explicit.
- If you change local state, update SQLite bootstrap, query helpers, and tests together.
- If you add risky actions, route them through policy and review primitives.
- If you add natural-language behavior, compile it into explicit structured actions.

## Proton-specific guidance

- Discovery and sync are separate concerns. Keep them separate.
- Discovery precedence is: explicit CLI overrides, env vars, local config file, then safe defaults.
- Initial sync should stay bounded. Avoid full-mailbox surprises.
- Incremental sync should preserve a reliable cursor and avoid skipping new mail.
- Draft materialization may create Proton Drafts through Bridge IMAP after review approval.
- Do not implement send as a side effect of draft creation or review approval.
- Never print Bridge passwords in CLI output or logs.

## Gmail-specific guidance

- Use the Gmail API directly when implementation starts.
- Do not force Gmail through an IMAP-first design just for symmetry.

## Validation

Run these before closing work:

```bash
python -m pytest
PYTHONPATH=src python -m mailops.cli.main --help
```

If you changed Proton behavior, also verify:

```bash
PYTHONPATH=src python -m mailops.cli.main connect proton
```

For a Windows-side Proton Bridge continuation, start with `docs/windows-powershell-handoff.md`.

## Documentation expectations

- Update `README.md` when the user-visible workflow changes.
- Update `docs/provider-proton.md` or `docs/provider-gmail.md` when adapter behavior changes.
- Keep examples in `.env.example` and `examples/config.example.toml` aligned with the code.

## License

This repository is MIT-licensed. Keep headers, docs, and packaging metadata consistent with that.
