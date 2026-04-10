# Changelog

## 0.1.0

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

### Safety Boundaries

- SMTP send is not implemented.
- Delete, bulk archive, bulk move, and provider rule application are not implemented.
- Gmail remains a placeholder for a later milestone.
- Proton Bridge passwords are runtime-only and are not persisted by saved profiles.
