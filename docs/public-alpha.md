# Public Alpha Guide

MailOps v0.1.0 is a local-first, review-first inbox operations harness. It is ready for a public alpha when the release checklist in [release-checklist.md](release-checklist.md) is complete and the operator explicitly approves the release source-control actions.

## What Works

- Local SQLite runtime bootstrap and diagnostics
- Proton Bridge discovery on Windows, Linux desktop, and supported WSL-to-Windows topologies
- Saved non-secret Proton profiles
- Proton folder listing with role and capability detection
- Bounded Proton sync into local state
- Search over synced local messages
- Read-only local thread/message inspection
- Thread triage and follow-up classification
- Natural-language requests compiled into explicit actions or local queries
- Local draft proposal batches
- Custom outbound draft proposal batches from explicit operator context
- Review-first Proton draft materialization through IMAP `APPEND`
- Provider draft syncback snapshots for executed draft refs
- Review-only Proton Sieve previews
- Markdown audit export
- Local-only demo mailbox fixture for contributors without Proton Bridge

## What Does Not Work Yet

- Gmail OAuth, sync, labels, and draft operations are placeholders.
- SMTP send is not implemented.
- Delete, bulk archive, bulk move, and provider rule application are not implemented.
- Proton draft syncback records provider-visible draft metadata but does not yet import full provider draft bodies into the normal message index.
- Triage heuristics are useful but still heuristic; they are not a substitute for operator review.
- Live provider validation currently assumes Proton Bridge is already installed and running.

## Safety Model

MailOps keeps risky provider mutations review-first. In v0.1.0, the only provider write path is creating reviewed Proton drafts. The system does not send mail, delete mail, bulk archive, bulk move, or apply provider rules.

Secrets are intentionally runtime-only. Saved Proton profiles store host, port, username, account email, and canonical email metadata, but not Bridge passwords. Use `MAILOPS_PROTON_PASSWORD` or a transient `--password` override for live Bridge operations.

## Install

```bash
python -m pip install -e ".[dev]"
```

For a packaged install after release:

```bash
python -m pip install mailops
```

## Demo Workflow

The local demo path does not require Proton Bridge:

```bash
mailops demo seed
mailops status
mailops search "invoice"
mailops inspect thread demo-thread-finance
mailops triage --since 0d
mailops ask "show unanswered finance threads"
mailops rules propose "filter future messages from vendor.example to label Finance"
mailops export audit --format markdown
```

## Proton Workflow

Use the Proton Bridge-generated IMAP username and password, not the Proton account password.

```powershell
mailops doctor
mailops connect proton --username operator@example.com --account-email operator@example.com --save-profile work
$secure = Read-Host "Proton Bridge password" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
$env:MAILOPS_PROTON_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
mailops connect proton --profile work --list-folders
mailops sync --profile work --folder INBOX --limit 25
mailops search "project update"
mailops inspect thread <thread_id>
mailops triage --since 3d
mailops ask "draft replies for scheduling emails from this week"
mailops draft create --from-account operator@example.com --to stakeholder@example.com --subject "Project update" --body-file draft.md --context-ref repo:current
mailops review batch list
mailops review batch show batch_xxxxxxxx
mailops apply batch_xxxxxxxx
mailops review batch sync-drafts batch_xxxxxxxx
mailops export audit --format markdown
```

Clear the password after the live session:

```powershell
Remove-Item Env:MAILOPS_PROTON_PASSWORD
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
```

## Release Notes Summary

v0.1.0 proves the MailOps operator loop for Proton:

```text
sync -> inspect -> triage -> draft -> review -> apply -> audit
```

The release remains intentionally narrow. Proton is the validated provider; Gmail stays out of scope until the Proton loop is stable in public use.
