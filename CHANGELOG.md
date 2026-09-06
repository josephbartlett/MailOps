# Changelog

MailOps follows Semantic Versioning. See `docs/release-process.md` for versioning and release rules.

## Unreleased

- No unreleased changes.

## 0.2.0 - 2026-09-06

### Fixed

- Account-scoped message identity with a transactional migration preserving local IDs and content.
- UIDVALIDITY-bound Proton sync, returned UID validation, bounded retry correctness, and PEEK fetches.
- Draft references bind Message-ID and UIDVALIDITY; legacy UID-only references report unverified instead of claiming unrelated drafts.
- Frozen reply envelopes, action risk floors, reviewed profile/account binding, and per-action approval checks.
- Durable draft execution claims and explicit uncertain states to prevent duplicate retries and unsafe rollback.
- Standard TOML parsing and validation; credential/traceback redaction and reliable SQLite/log handle closure.
- Literal terminal rendering prevents untrusted mail markup or control characters from hiding reviewed content.
- Relative demo timestamps and date-independent review tests.
- Corrected cross-repository state targeting, credentials, installation, and release guidance in all six Codex skills.

### Added

- Isolated validation runner, architectural/documentation invariants, focused lint, private-package checks, and Windows/Linux CI.
- Repository harness guide and a quality/debt record separating tested behavior from live operational validation.
- Test isolation from operator settings and real network connections.

### Changed

- Development dependencies include patched pytest (9.0.3+) and repeatable lint/build/advisory tools.
- Updated Rich and Twine compatibility so validation accepts current wheel metadata (2.5).
- CI refreshes vulnerable preinstalled setuptools and uses pinned current checkout/setup Actions.
- Python 3.10 uses `tomli` for Proton configuration; later versions use the standard library.
- Removed the obsolete demo-seeding placeholder script; use `mailops demo seed`.
- Legacy drafts without reviewed recipient envelopes require recreation; ambiguous provider attempts require inspection before recovery.

### Upgrade notes

- Back up the operational MailOps home before running this version. The next state-using command performs a transactional schema migration; content already lost to older cross-account collisions cannot be reconstructed by migration.
- Legacy draft proposals without reviewed recipients require recreation. Legacy UID-only draft references report `unverified`; uncertain provider attempts require manual inspection before recovery.
- Live Bridge acceptance remains separate from the automated release checks. Sending, deletion, bulk mutation, provider rules, and Gmail runtime remain unimplemented.

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
