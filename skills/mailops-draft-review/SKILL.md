---
name: mailops-draft-review
description: "Review, apply, reconcile, and audit MailOps draft batches from any Codex repo or session. Use when the user asks to inspect a proposed email batch, create Proton Drafts after approval, verify that no mail was sent, sync provider draft metadata, or export the audit trail."
---

# MailOps Draft Review

Use this skill to move an existing MailOps draft batch through review, safe materialization, provider syncback, and audit. Batches may contain thread replies or custom outbound drafts created with `mailops draft create`.

## Safety Rules

- Apply only batches the user has explicitly reviewed and approved.
- Apply only safe `create_draft` actions. Do not send, delete, archive, bulk move, or apply provider rules.
- Use Proton Bridge credentials only as transient runtime input.
- If the batch scope, action type, recipient, subject, or body is unclear, stop and show the exact batch instead of applying.
- Resolve the intended existing absolute `MAILOPS_HOME` before using these commands. The default `.mailops` is relative to the current directory; do not create a fresh store while trying to inspect an existing batch.

## Inspect

```powershell
mailops review batch list
mailops review batch show <batch_id>
```

Confirm:

- `highest_risk` is acceptable for a draft action
- every action type is `create_draft`
- draft account, To, Cc, Bcc, subject, and body are expected
- batch status is `pending` for a new application; inspect action execution states before any recovery attempt
- no action resembles send, delete, archive, bulk move, or rule application

## Apply

Apply only after user approval of the exact batch. Reuse existing approval when the account, content, recipients and scope have not changed:

```powershell
mailops apply <batch_id>
```

If Proton Bridge credentials are required, set them only for the current shell session. Prefer a secure prompt rather than a literal password command.

## Sync Provider Drafts

After apply, reconcile provider-visible draft metadata:

```powershell
mailops review batch sync-drafts <batch_id>
mailops review batch show <batch_id>
```

Expected provider refs look like `Drafts:uid:<n>` or `Drafts:message-id:<id>`. Provider draft snapshots should report status `present`.

## Audit

Export the audit trail:

```powershell
mailops export audit --format markdown
```

Report whether:

- provider draft materialization succeeded
- provider draft syncback succeeded
- no send path was invoked
- any actions remain pending or failed

If anything fails, inspect local execution state and provider syncback before a retry. An interrupted or uncertain IMAP append may already have created a draft. Do not recreate the batch or retry blindly; report an unresolved provider result when reconciliation cannot establish it. Never infer that no mail was sent solely from a draft being present; report the operations actually observed.
