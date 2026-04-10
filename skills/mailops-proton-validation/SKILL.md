---
name: mailops-proton-validation
description: Validate MailOps Proton Bridge workflows, including Windows/WSL Bridge reachability, saved profiles, bounded sync, review-first draft materialization, provider draft syncback, and audit export. Use when testing live Proton behavior without leaking credentials or sending mail.
---

# MailOps Proton Validation

Use this skill for live or simulated Proton Bridge validation. Never persist Bridge passwords.

## Safety Rules

- Use the Proton Bridge-generated IMAP password, not the Proton account password.
- Set credentials only as a runtime environment variable or transient `--password`.
- Do not write credentials into `.env`, TOML config, docs, logs, shell scripts, or shell history.
- Do not send mail, delete mail, bulk archive, bulk move, or apply provider rules.
- Apply only reviewed `create_draft` actions whose exact scope was inspected.

## Baseline

From the MailOps repo:

```powershell
$env:PYTHONPATH = "src"
py -m pytest
py -m mailops.cli.main doctor
py -m mailops.cli.main status
py -m mailops.cli.main review batch list
```

On Windows, `doctor` should report Proton IMAP `127.0.0.1:1143` and SMTP `127.0.0.1:1025` reachable when Bridge is running. In WSL, inspect `docs/wsl-windows-bridge.md` and prefer Windows PowerShell for live write-path validation if WSL cannot reach Bridge.

## Runtime Password Pattern

Use a prompt instead of a literal command:

```powershell
$secure = Read-Host "Proton Bridge password" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $env:MAILOPS_PROTON_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}
```

Clear it when done:

```powershell
Remove-Item Env:MAILOPS_PROTON_PASSWORD
```

## Read Path

```powershell
py -m mailops.cli.main connect proton --list-profiles
py -m mailops.cli.main connect proton --profile lm-main --list-folders
py -m mailops.cli.main sync --profile lm-main --folder INBOX --limit 10
py -m mailops.cli.main status
py -m mailops.cli.main triage --since 3d
```

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

3. Apply only if every action is a safe `create_draft` action:

   ```powershell
   py -m mailops.cli.main apply <batch_id>
   ```

4. Reconcile provider draft metadata:

   ```powershell
   py -m mailops.cli.main review batch sync-drafts <batch_id>
   py -m mailops.cli.main review batch show <batch_id>
   py -m mailops.cli.main export audit --format markdown
   ```

Expected result: provider refs such as `Drafts:uid:<n>`, provider draft snapshots with status `present`, no sent mail, and audit events for approval, materialization, syncback, and execution.
