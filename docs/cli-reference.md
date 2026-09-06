# CLI Reference

## Stable commands

- `mailops doctor`
- `mailops connect`
- `mailops demo`
- `mailops draft`
- `mailops sync`
- `mailops status`
- `mailops search`
- `mailops inspect`
- `mailops triage`
- `mailops ask`
- `mailops review`
- `mailops rules`
- `mailops apply`
- `mailops rollback`
- `mailops export`

## Current behavior

The CLI now supports the first concrete Proton operator loop:

- `doctor` validates local state and reports Proton Bridge reachability, including WSL-to-Windows host candidates.
- `connect proton` resolves Bridge settings, lists folders, and saves non-secret Proton profiles.
- `demo seed` creates a local-only deterministic mailbox fixture for contributor testing.
- `draft create` creates an explicit custom outbound draft proposal as a pending review batch.
- `sync` indexes bounded Proton Bridge mailbox slices into SQLite.
- `status`, `search`, `inspect`, and `triage` read local indexed state.
- `search` returns local thread and message IDs for follow-up inspection.
- `inspect thread` and `inspect message` show bounded local email context without contacting providers.
- `ask` compiles natural-language requests into explicit local actions or queries.
- `review` inspects persisted review batches and local draft proposals.
- `apply` approves batches and materializes Proton drafts through Bridge IMAP when credentials are available.
- `review batch sync-drafts` resolves executed Proton draft refs back to provider metadata and records local audit snapshots.
- `rules propose` generates review-only Proton Sieve text and preview metadata without applying provider rules.
- `rollback` removes local draft artifacts only before provider-side execution exists.
- `export audit` emits markdown audit history.

Gmail commands remain placeholders until the Gmail API adapter is implemented.

## Design rule

Natural-language entry through `ask` must compile into explicit actions, queries, or review items. It should never be a hidden destructive shortcut.

## Safety rule

MailOps may create reviewed Proton drafts. It must not send mail, delete mail, bulk mutate mail, or apply provider rules without explicit future policy support and review gates.

## Custom Drafts

Create custom outbound draft proposals from any local context without sending:

```powershell
mailops draft create --from-account operator@example.com --to stakeholder@example.com --subject "Project update" --body-file draft.md --context-ref repo:current
mailops review batch show <batch_id>
mailops apply <batch_id>
mailops review batch sync-drafts <batch_id>
```

`draft create` records To, Cc, Bcc, subject, body, and context refs in local state. `review batch show` displays that envelope before apply. `apply` may materialize that proposal as a Proton Draft after review; it does not send the message.

Generated reply proposals also freeze their recipients and account at creation.
`apply` rejects legacy proposals without reviewed recipients. If an action has an
interrupted or uncertain provider attempt, the batch requires attention, apply
returns nonzero, and automatic retry/local rollback are blocked. Inspect Proton
Drafts and the audit trail before any manual recovery.
