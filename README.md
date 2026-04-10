# MailOps

MailOps is a local-first, provider-aware inbox operations harness for people who manage serious email workloads across multiple accounts.

It is not a generic AI email client. MailOps is an execution layer between mail providers, a local indexed mailbox state, guarded actions, and an agentic workflow such as Codex CLI.

## Why MailOps

Operators buried in newsletters, invoices, client threads, and scheduling noise need:

- cross-account triage
- follow-up detection
- safe reviewed batch work
- explainable automation
- local control
- auditability

MailOps is designed to provide those capabilities without giving an LLM silent, unrestricted control over email.

## Current status

The repository now includes a working CLI, local SQLite bootstrap, Proton Bridge discovery, folder listing with capability detection, bounded recent-message sync, ranked thread triage, role-aware follow-up filtering, local draft proposal generation, custom outbound draft proposals, provider-backed Proton draft materialization, provider draft syncback snapshots, review batches, review-only Proton Sieve previews, a seeded local demo mailbox, and markdown audit export. Gmail remains intentionally unimplemented in this milestone.

## Product loop

MailOps is being built around one disciplined operator loop:

1. sync
2. inspect
3. triage
4. draft
5. review
6. apply
7. audit

That loop is the product.

## Quickstart

### Prerequisites

- Python 3.10+
- `uv` recommended, or `pip`

### Install for development

```bash
uv pip install -e ".[dev]"
```

Or with `pip`:

```bash
python -m pip install -e ".[dev]"
```

### Run the CLI

```bash
mailops --help
mailops doctor
mailops demo seed
mailops connect proton --list-folders
mailops sync --folder INBOX
mailops status
mailops search "invoice"
mailops inspect thread <thread_id>
mailops triage --since 3d
mailops ask "draft replies for scheduling emails from this week"
mailops draft create --from-account operator@example.com --to stakeholder@example.com --subject "Project update" --body-file draft.md --context-ref repo:current
mailops review batch list
mailops ask "show unanswered client threads older than 2 days"
# Set MAILOPS_PROTON_PASSWORD only in the current shell before live Bridge writes.
mailops review batch show batch_001
mailops apply batch_001
mailops review batch sync-drafts batch_001
mailops rules propose "filter future messages from vendor.example to label Finance"
mailops export audit --format markdown
```

`mailops ask` follow-up queries now honor prompt intent for common operator phrases like `client threads`, `finance`, and `scheduling`, so recruiter, logistics, and other low-signal thread types stop crowding the shortlist.
Approved draft batches can now materialize real Proton drafts through Bridge-backed IMAP. If Bridge credentials are not available, `mailops apply` leaves those actions pending instead of pretending execution succeeded. After apply, `mailops review batch sync-drafts` resolves stored provider refs back to Proton Drafts metadata and records a local audit snapshot.

## Command surface

```bash
mailops doctor
mailops demo seed
mailops connect proton --list-folders
mailops connect proton --profile profile-name --list-folders
# Set MAILOPS_PROTON_PASSWORD only in the current shell before live Bridge sync.
mailops sync --provider proton --profile all --folder "All Mail" --limit 50
mailops sync --provider proton --folder INBOX
mailops status
mailops search "invoice"
mailops inspect thread <thread_id>
mailops inspect message <message_id>
mailops triage --since 3d
mailops ask "draft replies for all scheduling messages from this week"
mailops draft create --from-account operator@example.com --to stakeholder@example.com --subject "Project update" --body-file draft.md --context-ref repo:current
mailops review
mailops review batch list
mailops review batch show batch_001
mailops apply batch_001
mailops review batch sync-drafts batch_001
mailops rules propose "filter future messages from vendor.example to label Finance"
mailops rollback batch_001
mailops export audit --format markdown
```

## Local Demo Workflow

Contributors without Proton Bridge can seed a deterministic local-only mailbox:

```bash
mailops demo seed
mailops status
mailops search "invoice"
mailops triage --since 0d
mailops ask "show unanswered finance threads"
```

The demo account uses provider `demo_local`, so it is useful for local search and triage behavior without pretending to be Proton or Gmail.

## Codex Skills

MailOps includes reusable Codex Skills in `skills/`. The operator-facing skills let Codex use MailOps from any repository to search local email context, inspect a thread or message, draft email from the current repo/session context, and move approved draft batches through review/apply/audit. Contributor-facing skills cover MailOps product development, Proton validation, and public alpha release work.

See [docs/codex-skills.md](docs/codex-skills.md) for installation and validation.

## Rule Preview Workflow

Rule generation is preview-only in this milestone:

```bash
mailops rules propose "filter future messages from vendor.example to label Finance"
mailops ask "create a sieve rule for messages from vendor.example to label Finance"
```

MailOps generates Proton Sieve text and a structured preview, but it does not apply provider rules.

## Architecture

The repository is organized around a few concrete runtime layers:

- `mailops-core`: config, models, policies, actions, logging, exceptions
- `mailops-adapter-proton`: Proton Bridge connectivity and Sieve artifacts
- `mailops-adapter-gmail`: placeholder package for future Gmail API work
- `mailops-index`: local SQLite state and query helpers
- `mailops-cli`: operator-facing CLI
- `mailops-agent`: natural-language planning into explicit actions
- `mailops-review`: review batches, previews, and rollback primitives

See [docs/architecture.md](docs/architecture.md) for the current implementation-oriented view.

## Safety stance

- Local-first by default
- Review-first for anything risky
- Provider-aware instead of flattened abstraction
- Auditable actions with explicit reasons
- LLM assistance as an optional layer, not the only layer

High-risk actions such as send, delete, bulk archive, and provider rule application are intentionally blocked by default in the current milestone.

## Proton profile workflow

MailOps can persist non-secret Proton Bridge settings for each mailbox under `.mailops/config/proton_accounts.json`.

```bash
mailops connect proton --username operator@example.com --account-email operator@example.com --save-profile work
mailops connect proton --username alias@example.com --account-email alias@example.com --canonical-email operator@example.com --save-profile alias
mailops connect proton --list-profiles
mailops sync --provider proton --profile all --folder "All Mail" --limit 50
```

Passwords are intentionally not persisted. Use `MAILOPS_PROTON_PASSWORD` or `--password` only as transient runtime input when syncing saved profiles or materializing reviewed drafts.

### WSL and Windows Bridge

MailOps supports running inside WSL while Proton Mail Bridge runs on Windows. The Proton adapter tries `127.0.0.1` first, then falls back to the Windows host IP when WSL networking requires it.

Run `mailops doctor` to see which Bridge hosts and ports are reachable. See [docs/wsl-windows-bridge.md](docs/wsl-windows-bridge.md) for the supported setup and troubleshooting notes.

For continuing live Proton validation from Windows PowerShell, use [docs/windows-powershell-handoff.md](docs/windows-powershell-handoff.md).

## Local Draft Workflow

Draft requests stay local first. MailOps generates local proposal artifacts, bundles them into a review batch, and records the lifecycle in the audit log. Drafts can come from indexed mailbox threads or from explicit operator-provided context such as a repo/session summary.

```bash
mailops ask "draft replies for scheduling emails from this week"
mailops draft create --from-account operator@example.com --to stakeholder@example.com --subject "Project update" --body-file draft.md --context-ref repo:current
mailops review batch list
mailops review batch show batch_xxxxxxxx
mailops apply batch_xxxxxxxx
mailops review batch sync-drafts batch_xxxxxxxx
mailops rollback batch_xxxxxxxx
mailops export audit --format markdown
```

## License

MailOps is released under the MIT license. See [LICENSE](LICENSE).

## Repository layout

```text
mailops/
├── docs/
├── examples/
├── scripts/
├── skills/
├── src/mailops/
└── tests/
```

The full intended layout is reflected in the source tree and mirrored in the docs for contributors.

## Near-term roadmap

- harden public alpha feedback, triage heuristics, and provider-specific docs
- keep Gmail out of scope until the Proton review/apply/audit loop is stable in public use

## Versioning and releases

MailOps follows Semantic Versioning. Release history is tracked in [CHANGELOG.md](CHANGELOG.md), and release procedure is documented in [docs/release-process.md](docs/release-process.md).

See [docs/public-alpha.md](docs/public-alpha.md), [docs/release-checklist.md](docs/release-checklist.md), [docs/release-process.md](docs/release-process.md), and [docs/roadmap.md](docs/roadmap.md).
