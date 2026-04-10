# Roadmap

## Current status

The repo has moved past the original scaffold. These v0.1 pieces are implemented and covered by tests:

- CLI scaffold and local config bootstrap
- SQLite schema, migrations, and table-count diagnostics
- Proton Bridge discovery, saved non-secret profiles, folder listing, folder capability detection, bounded sync, and UID cursors
- canonical account alias consolidation for Proton profiles
- local search over indexed message bodies
- thread-level triage scoring and follow-up classification
- role-aware follow-up filtering for prompts such as `client threads`, `finance`, and `scheduling`
- local draft proposal generation
- review batches, apply/rollback state transitions, and markdown audit export
- provider-backed Proton draft materialization through IMAP `APPEND`
- provider draft syncback snapshots for executed Proton draft refs
- review-only Proton Sieve proposal generation and preview
- seeded local demo mailbox dataset for contributors without Proton Bridge
- WSL-to-Windows Bridge diagnostics and host fallback

The live Windows-side Proton draft materialization path has been validated against Proton Bridge. WSL can read local state but may still be unable to reach Windows Bridge ports on this machine, so live provider validation should happen from Windows PowerShell unless networking changes.

## v0.1 milestone plan

### Milestone A: Foundations

- repo bootstrap
- config system
- SQLite bootstrap
- logging and audit primitives
- policy engine shell
- CLI skeleton

### Milestone B: Proton connectivity

- Bridge discovery and config
- IMAP folder listing
- sync pipeline for selected folders
- normalized thread and message persistence

### Milestone C: Operator workflows

- search command
- triage scoring
- follow-up classifier heuristics
- draft proposal pipeline

### Milestone D: Review and safety

- review batches
- apply and rollback primitives
- audit export
- log redaction

### Milestone E: Polish

- contributor docs
- fixtures
- sample data
- release preparation

## Immediate next work

1. Tighten docs around setup, safety model, and known limitations for a public alpha.
2. Add configurable sender-role heuristics and allow/block lists for triage.
3. Add explicit Bridge profile health checks.

## Next implementation slices

### Proton polish

- explicit Bridge profile health checks

### Operator workflows

- better sender-role classification with configurable allow/block lists
- higher precision follow-up recovery for `waiting_on_them`
- batch creation for low-risk archive/label proposals without automatic mutation
- richer audit export grouped by batch lifecycle

### Safety and policy

- central policy gate for action execution
- action thresholds for bulk archive/move/delete proposals
- explicit dry-run/preview output for every provider mutation
- redacted bug-report export

### Provider expansion

- Gmail OAuth connection
- Gmail labels, drafts, send, and thread actions
- provider capability matrix in docs

### Contributor experience

- fixture mailbox dataset
- integration tests that do not require a live provider
- release checklist and public alpha docs
