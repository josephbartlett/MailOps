# Windows PowerShell Handoff

This handoff is for continuing MailOps development from Windows PowerShell with Proton Mail Bridge already running on Windows.

## Where We Are Leaving Off

MailOps has a working local-first Proton MVP:

- Proton Bridge discovery, profile storage, folder listing, and bounded sync
- local SQLite mailbox state
- search and ranked triage
- role-aware follow-up filtering
- local draft proposal generation
- review batches and audit export
- provider-backed Proton draft materialization through IMAP `APPEND`
- WSL diagnostics and Windows host fallback for Bridge discovery

The WSL session can read the repo and local SQLite state, but it cannot currently reach Windows Proton Bridge ports.

Latest WSL `mailops doctor` result:

```text
wsl: detected
proton_bridge_hosts: 127.0.0.1, 10.255.255.254, 172.25.96.1
proton_imap:127.0.0.1: connection refused
proton_smtp:127.0.0.1: connection refused
proton_imap:10.255.255.254: connection refused
proton_smtp:10.255.255.254: connection refused
proton_imap:172.25.96.1: timed out
proton_smtp:172.25.96.1: timed out
```

Latest local MailOps state:

```text
accounts: 2
account_aliases: 2
folders: 2
threads: 29
messages: 50
folder_links: 50
review_batches: 0
pending_action_proposals: 0
```

Saved Proton profiles currently visible from WSL:

```text
lm-main -> primary Proton Bridge profile
lm-info -> secondary Proton Bridge profile
```

There are no pending review batches. A new draft batch must be created before testing `mailops apply`.

WSL `git status` currently reports this directory is not inside a Git repository. Check from Windows PowerShell before making release-oriented assumptions:

```powershell
git status --short
```

## Planned Work After Live Validation

The current roadmap is tracked in [roadmap.md](roadmap.md). The most important next slices are:

1. Validate live Proton draft materialization from Windows PowerShell.
2. Add draft syncback or provider draft lookup so local state can show richer context for created Proton drafts.
3. Improve Proton folder capability detection for Drafts, Sent, Archive, Trash, and All Mail.
4. Add Proton Sieve rule proposal generation and preview.
5. Add configurable sender-role heuristics and allow/block lists for triage.
6. Add a seeded demo mailbox dataset for contributors without Proton Bridge.
7. Prepare public alpha docs: setup, safety model, known limitations, and release checklist.

Do not start Gmail until the Proton operator loop is validated end to end.

## PowerShell Setup

From Windows PowerShell:

```powershell
cd C:\Users\decoy\MailOps
py -m pip install -e ".[dev]"
$env:PYTHONPATH = "src"
py -m pytest
```

Expected result:

```text
55 passed
```

Run the local status checks:

```powershell
py -m mailops.cli.main doctor
py -m mailops.cli.main status
py -m mailops.cli.main review batch list
```

On Windows, `doctor` should show Proton Bridge IMAP and SMTP reachable on `127.0.0.1` if Bridge is running and exposing the default ports.

## Proton Bridge Credentials

Use the Proton Bridge-generated IMAP username and password from the Bridge app, not the Proton account password.

Do not store the Bridge password in repo config. Pass it at runtime:

```powershell
$secure = Read-Host "Proton Bridge password" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $env:MAILOPS_PROTON_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}
```

Rotate the Bridge password after testing if it has been pasted into chat or logs.

## Live Read-Path Validation

Verify that Windows PowerShell can reach Bridge:

```powershell
py -m mailops.cli.main connect proton --profile lm-main --list-folders
```

If profile names need checking:

```powershell
py -m mailops.cli.main connect proton --list-profiles
```

If needed, run a bounded sync:

```powershell
py -m mailops.cli.main sync --provider proton --profile all --folder "All Mail" --limit 50
py -m mailops.cli.main status
py -m mailops.cli.main triage --since 3d
```

## First Live Write-Path Test

This creates a real Proton draft, not a sent email.

Create a local draft batch:

```powershell
py -m mailops.cli.main ask "draft replies for scheduling emails from this week"
py -m mailops.cli.main review batch list
```

Inspect the batch:

```powershell
py -m mailops.cli.main review batch show batch_xxxxxxxx
```

Apply the batch:

```powershell
py -m mailops.cli.main apply batch_xxxxxxxx
```

Expected result:

- the batch status becomes `executed`
- each `create_draft` action has `execution_status=executed`
- each executed action has a `provider_ref` such as `Drafts:uid:<number>`
- the draft appears in Proton Drafts
- no email is sent

Confirm locally:

```powershell
py -m mailops.cli.main review batch show batch_xxxxxxxx
py -m mailops.cli.main export audit --format markdown
```

Do not run rollback after provider drafts are materialized. MailOps intentionally blocks local rollback once provider-side state exists.

## Codex Handoff Prompt

```text
You are continuing MailOps from Windows PowerShell.

Repo:
C:\Users\decoy\MailOps

Goal:
Validate the Proton Bridge live write path from Windows, where Bridge is reachable on Windows localhost.

Context:
- MailOps is a local-first inbox operations harness.
- Proton Bridge is installed and running on Windows.
- WSL could sync local state earlier but cannot currently reach Windows Bridge ports.
- Current local state has 2 accounts, 29 threads, 50 messages, and 0 review batches.
- Provider-backed draft materialization is implemented via IMAP APPEND into Proton Drafts.
- Sending is not implemented and must not be added for this validation.
- Rollback is blocked once provider-side drafts exist.

Start:
1. cd C:\Users\decoy\MailOps
2. py -m pip install -e ".[dev]"
3. $env:PYTHONPATH = "src"
4. py -m pytest
5. py -m mailops.cli.main doctor
6. py -m mailops.cli.main connect proton --list-profiles
7. Set $env:MAILOPS_PROTON_PASSWORD to the Bridge-generated password.
8. py -m mailops.cli.main connect proton --profile lm-main --list-folders

Then:
1. Create a review batch with `py -m mailops.cli.main ask "draft replies for scheduling emails from this week"`.
2. Inspect it with `py -m mailops.cli.main review batch list` and `py -m mailops.cli.main review batch show <batch_id>`.
3. Apply it with `py -m mailops.cli.main apply <batch_id>`.
4. Verify the batch status is executed and the action has a provider_ref.
5. Confirm the draft appears in Proton Drafts.
6. Export audit with `py -m mailops.cli.main export audit --format markdown`.

Safety:
- Do not send mail.
- Do not delete mail.
- Do not auto-apply rules.
- Do not persist Bridge passwords.
- Keep any follow-up fixes covered by tests.

After live validation:
- Continue with `docs/roadmap.md`.
- Prioritize Proton draft syncback, Proton folder capability detection, and Sieve rule proposals before Gmail.
```
