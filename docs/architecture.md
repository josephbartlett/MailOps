# MailOps Architecture

MailOps is organized as a local-first operator stack with explicit boundaries between data access, local state, policy, and interfaces.

## Runtime layers

### Provider adapters

- `proton_bridge`
- `gmail_api`

Adapters own provider-specific connectivity, capabilities, and translation into MailOps models. They are not flattened into a fake universal protocol.

### Local state and index

SQLite is the first storage target. The index owns normalized mailbox metadata, searchable thread state, pending actions, and audit events.

### Policy and execution engine

The policy layer determines what may auto-execute, what requires review, and what is blocked entirely.

### Interfaces

- CLI
- optional TUI
- Codex-facing `ask` planner
- audit exports

## Current scaffold

The current repository includes:

- typed domain models
- config and logging primitives
- SQLite bootstrap helpers
- Proton Bridge discovery, profile registry, folder listing, folder capability detection, sync, and draft materialization
- WSL-to-Windows Bridge diagnostics and host fallback
- local search and thread triage
- local draft proposal generation
- review batches, apply/rollback state transitions, and audit export
- provider draft syncback snapshots
- review-only Proton Sieve rule previews
- seeded local demo mailbox data
- Gmail adapter placeholders for a later milestone

## Current execution flow

1. `sync` indexes selected Proton folders into local SQLite.
2. `triage` refreshes thread-level follow-up state and importance scores.
3. `ask` turns supported natural-language requests into local queries or draft review batches.
4. `review` shows exact proposed actions and local draft content.
5. `apply` approves eligible batches and creates provider-side Proton drafts when Bridge credentials are available.
6. `review batch sync-drafts` records provider-visible draft metadata after execution.
7. `rules propose` previews Proton Sieve text without applying provider rules.
8. `export audit` records proposal, approval, execution, syncback, and rollback events.

## Planned evolution

1. configurable triage heuristics
2. explicit Bridge profile health checks
3. richer audit export and release feedback hardening
