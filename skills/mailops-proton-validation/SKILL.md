---
name: mailops-proton-validation
description: Validate MailOps Proton Bridge workflows, including Windows/WSL Bridge reachability, saved profiles, bounded sync, review-first draft materialization, provider draft syncback, and audit export. Use when testing live Proton behavior without leaking credentials or sending mail.
---

# MailOps Proton Validation

Use this skill for live or simulated Proton Bridge validation. Never persist Bridge passwords.

## Safety Rules

- Use the Proton Bridge-generated IMAP password, not the Proton account password.
- Set credentials through a secure prompt and a runtime environment variable. Avoid literal passwords and `--password` arguments: command history and process listings can expose them.
- Do not write credentials into `.env`, TOML config, docs, logs, shell scripts, or shell history.
- Do not send mail, delete mail, bulk archive, bulk move, or apply provider rules.
- Apply only `create_draft` actions after the user has approved the exact account, recipients, subject, body and batch scope. A request for an audit or connection test does not authorize creating provider drafts.

## Baseline

Read the repo's `docs/windows-powershell-handoff.md` for Windows setup; treat its machine snapshots and profile names as historical examples. Resolve the intended existing absolute `MAILOPS_HOME` before live checks so a different working directory does not select a different mailbox store.

For local-only code validation, use an isolated temporary home and the repository's tests. For an authorized live connection diagnostic, run from the MailOps repo:

```powershell
$env:PYTHONPATH = "src"
py -m mailops.cli.main doctor
py -m mailops.cli.main status
py -m mailops.cli.main review batch list
```

`doctor` actively probes configured TCP endpoints. Windows defaults are IMAP `127.0.0.1:1143` and SMTP `127.0.0.1:1025`; verify the actual profile instead of assuming defaults. SMTP reachability does not imply a MailOps send capability. In WSL, inspect `docs/wsl-windows-bridge.md` and prefer Windows PowerShell if WSL cannot reach Bridge.

## Runtime Password Pattern

Use a prompt instead of a literal command, restore any existing runtime value afterward, and run only the authorized commands inside the outer `try`:

```powershell
$previousPassword = [Environment]::GetEnvironmentVariable("MAILOPS_PROTON_PASSWORD", "Process")
$secure = Read-Host "Proton Bridge password" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  try {
    $env:MAILOPS_PROTON_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
  } finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    $secure.Dispose()
  }
  # Run the authorized MailOps commands here.
} finally {
  [Environment]::SetEnvironmentVariable("MAILOPS_PROTON_PASSWORD", $previousPassword, "Process")
  $previousPassword = $null
}
```

## Read Path

```powershell
py -m mailops.cli.main connect proton --list-profiles
py -m mailops.cli.main connect proton --profile <profile_name> --list-folders
py -m mailops.cli.main sync --profile <profile_name> --folder INBOX --limit 10
py -m mailops.cli.main status
py -m mailops.cli.main triage --since 3d --account <account_id>
```

Choose the profile and account from the intended mailbox. Omitting the sync target can select every saved profile. Keep the folder and count bounded to the requested validation.

## Write Path

1. Create a low-volume local draft batch:

   ```powershell
   py -m mailops.cli.main ask "draft replies for scheduling messages from this week"
   py -m mailops.cli.main review batch list
   ```

2. Inspect the exact batch:

   ```powershell
   py -m mailops.cli.main review batch show <batch_id>
   ```

3. Once the user has approved the exact displayed batch and every action is `create_draft`, apply it:

   ```powershell
   py -m mailops.cli.main apply <batch_id>
   ```

4. Reconcile provider draft metadata:

   ```powershell
   py -m mailops.cli.main review batch sync-drafts <batch_id>
   py -m mailops.cli.main review batch show <batch_id>
   py -m mailops.cli.main export audit --format markdown
   ```

Expected result: provider refs such as `Drafts:uid:<n>`, provider draft snapshots with status `present`, and audit events for approval, materialization, syncback, and execution. Report that this workflow invoked no send operation; draft presence alone does not establish account-wide absence of sent mail. If append completion is uncertain, inspect execution state and reconcile before any retry rather than creating another batch.
