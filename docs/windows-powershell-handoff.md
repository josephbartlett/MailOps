# Windows PowerShell continuation

Start with [AGENTS.md](../AGENTS.md) and [the validation guide](harness-engineering.md).
This is a runbook, not a snapshot of current accounts, Bridge reachability, or test
counts. Inspect current state before choosing any live operation.

## Development validation

```powershell
cd C:\Users\decoy\MailOps
.\.venv\Scripts\python.exe scripts/validate.py
```

The runner uses synthetic temporary state. A successful test suite does not prove
Bridge connectivity or authorize a real provider write.

## Select the operational mailbox

Preserve the original `MAILOPS_HOME` setting, then set it to the established absolute
mailbox-store path. Run `status`, `review batch list`, and `connect proton --list-profiles`
to select the actual account/profile. These commands may initialize/migrate local
state; take a protected backup before using a schema-changing version operationally.
Never assume example profile names or old mailbox counts apply to the current host.

Plain `connect proton` performs discovery without folder listing or synchronization.
`doctor` performs network reachability probes. Use the selected profile with
`connect proton --profile <profile> --list-folders` only when live inspection is part
of the task. Native Windows usually reaches a running Bridge on loopback; verify
the current host. See [WSL networking](wsl-windows-bridge.md) for that topology.

## Runtime credentials

Use Bridge-generated credentials, not the Proton account password. Read the password
through a secure prompt; never paste it in commands, chat, config, or logs.

```powershell
$secure = Read-Host "Proton Bridge password" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $env:MAILOPS_PROTON_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}
```

Clear the transient password when the authorized operation finishes and restore the
previous `MAILOPS_HOME` setting. Never print the environment or saved credential data.

## Live work

Sync only the selected account, folder, and bounded limit required by the task.
Read paths are distinct from creating a real draft. When the operator has authorized
materializing an exact reviewed batch, inspect its full account, To/Cc/Bcc, subject,
and body with `review batch show <batch_id>`, then use `apply <batch_id>`.
Follow with `review batch sync-drafts <batch_id>` and a private audit export.
Do not apply an existing batch merely to test the harness.

Sending, deletion, and provider rule application remain unimplemented. Rollback is
local-only and blocked after a provider attempt exists. If an action is `executing`
or `uncertain`, inspect Proton Drafts and its audit history; automatic retry and
rollback are blocked because the provider may already have accepted it.

Continue from [quality.md](quality.md) and [roadmap.md](roadmap.md), with no commit,
push, tag, publication, or remote changes unless explicitly authorized.
