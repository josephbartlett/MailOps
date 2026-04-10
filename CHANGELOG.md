# Changelog

MailOps follows Semantic Versioning. See `docs/release-process.md` for versioning and release rules.

## Unreleased

- No unreleased changes.

## 0.1.0 - 2026-04-10

Initial public alpha.

### Added

- Local-first MailOps CLI with Typer and Rich.
- SQLite state bootstrap, diagnostics, and audit export.
- Proton Bridge discovery, saved non-secret profiles, folder listing, and bounded sync.
- Proton folder role and capability detection.
- Local search and triage over indexed mailbox state.
- Read-only local thread/message inspection.
- Natural-language planning into explicit structured actions and local queries.
- Review-first local draft proposal batches.
- Review-first custom outbound draft proposal batches from explicit operator context.
- Proton draft materialization through IMAP `APPEND` after review.
- Provider draft syncback snapshots for executed draft refs.
- Review-only Proton Sieve previews.
- Local `demo_local` mailbox seeding for contributor workflows without Proton Bridge.
- Codex Skills for MailOps email context, contextual drafting, draft review, product development, Proton validation, and public release checks.

### Fixed

- Review previews now include full draft envelopes, including account, To, Cc, Bcc, subject, and body before apply.
- `triage --since` now behaves as a lookback window while explicit "older than" prompts remain supported.
- Proton sync cursors no longer advance past failed UID fetches.
- Gmail placeholder capabilities no longer advertise unsupported runtime behavior.
- CLI failure paths return non-zero exit codes for invalid draft/apply/sync/connect operations.

### Safety Boundaries

- SMTP send is not implemented.
- Delete, bulk archive, bulk move, and provider rule application are not implemented.
- Gmail remains a placeholder for a later milestone.
- Proton Bridge passwords are runtime-only and are not persisted by saved profiles.
