# MailOps — local-first email workflows for Proton Mail Bridge

[![CI](https://github.com/josephbartlett/MailOps/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/josephbartlett/MailOps/actions/workflows/ci.yml)
[![Latest release](https://img.shields.io/github/v/release/josephbartlett/MailOps)](https://github.com/josephbartlett/MailOps/releases/latest)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![MIT license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

Search and triage your email, prepare replies, and review drafts before creating
them in Proton Drafts. MailOps keeps its mailbox index and audit history locally
in SQLite and works from your terminal or through optional Codex skills.

**Alpha software. Sending and Gmail support are not implemented.**

[Get started](docs/public-alpha.md) · [Try the synthetic demo](#try-the-synthetic-demo) ·
[Codex skills](docs/codex-skills.md) · [CLI reference](docs/cli-reference.md) ·
[Release notes](docs/releases/v0.2.1.md)

![Selected actual CLI output: search, triage, draft preparation, and review](docs/assets/workflow-demo.svg)

*Synthetic mailbox; selected actual CLI output showing search, triage, draft
preparation, and review. No live account or provider connection is shown.
[Reproduce the demonstration](docs/demo.md).*

## What MailOps does

MailOps follows one operator loop:
**sync → inspect → triage → draft → review → apply → audit**.

| Capability | Current behavior |
| --- | --- |
| Proton Mail Bridge | Discover connections, save non-secret account profiles, and sync bounded mailbox slices through IMAP. |
| Search and triage | Search a local multi-account index, inspect threads, and prioritize follow-ups using heuristics. |
| Drafts and review | Prepare local proposals, inspect their full recipient envelope, then create reviewed Proton drafts. |
| Audit | Record local action history and reconcile MailOps-created drafts with provider headers. |
| Codex | Six optional skills use the CLI for email context, drafting, review, and development. No dedicated plugin or MCP server is required. |
| Sending and mailbox mutations | Sending, deletion, bulk archive/move, and provider rule application are unimplemented. Sieve output is preview-only. |
| Gmail | Disabled placeholder for future API-first work. |

## Install the release

Requires **Python 3.10+**. Install the **0.2.1** wheel from
[GitHub Releases](https://github.com/josephbartlett/MailOps/releases/tag/v0.2.1)
in a virtual environment. This installation does not require Proton Bridge.

**PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install "https://github.com/josephbartlett/MailOps/releases/download/v0.2.1/mailops-0.2.1-py3-none-any.whl"
mailops --help
```

**Bash**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install "https://github.com/josephbartlett/MailOps/releases/download/v0.2.1/mailops-0.2.1-py3-none-any.whl"
mailops --help
```

If PowerShell activation is unavailable, use `.\.venv\Scripts\python.exe` for
installation and `.\.venv\Scripts\python.exe -m mailops.cli.main` in place of
`mailops`. GitHub publication does not imply this version is available on PyPI.

**Upgrading an existing mailbox store?** Stop MailOps operations and back up your
established `MAILOPS_HOME` before using the new version. Read the
[0.2.0 migration guidance](docs/releases/v0.2.0.md#upgrade-instructions), especially
when upgrading from 0.1.0. Version 0.2.1 adds no schema changes.

## Try the synthetic demo

These examples use a new temporary home, restore your previous `MAILOPS_HOME`,
and leave the demo files available for inspection. They need no credentials and
make no provider connections. Never seed demo data into an operational store.

**PowerShell**

```powershell
$mailopsDemoPreviousHome = $env:MAILOPS_HOME
try {
    $mailopsDemoHome = Join-Path ([IO.Path]::GetTempPath()) ("mailops-demo-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $mailopsDemoHome -ErrorAction Stop | Out-Null
    $env:MAILOPS_HOME = $mailopsDemoHome
    mailops demo seed
    mailops status
    mailops search invoice
    mailops inspect thread demo-thread-finance
    mailops triage --since 0d
} finally {
    if ($null -eq $mailopsDemoPreviousHome) {
        Remove-Item Env:\MAILOPS_HOME -ErrorAction SilentlyContinue
    } else {
        $env:MAILOPS_HOME = $mailopsDemoPreviousHome
    }
}
```

**Bash**

```bash
(
    mailopsDemoHome="$(mktemp -d "${TMPDIR:-/tmp}/mailops-demo.XXXXXXXX")" || exit 1
    export MAILOPS_HOME="$mailopsDemoHome"
    mailops demo seed
    mailops status
    mailops search invoice
    mailops inspect thread demo-thread-finance
    mailops triage --since 0d
)
```

The Bash subshell restores the parent environment automatically. The demo uses
the `demo_local` provider; its output demonstrates local behavior only.
See [the demo guide](docs/demo.md) for the captured output and reproduction notes.

## Connect an operational Proton account

Start with the [Public Alpha Guide](docs/public-alpha.md#work-with-proton) and
[Proton provider notes](docs/provider-proton.md). Windows users can use the
[PowerShell continuation guide](docs/windows-powershell-handoff.md); WSL users can
use [WSL and Windows Bridge setup](docs/wsl-windows-bridge.md).

Select the intended account/profile and an explicit, absolute `MAILOPS_HOME`
before syncing. The default `.mailops` is relative to the working directory.
Use Bridge-generated credentials through transient secure input; profiles store
non-secret settings only. Keep the initial folder and message limit bounded.

Inspect the account, To/Cc/Bcc, subject, and body before authorizing creation in
Proton Drafts. **Draft approval never sends mail.** Interrupted or uncertain
provider attempts block automatic retry and local rollback: inspect Proton
Drafts and audit history before recovery. Legacy proposals without reviewed
recipients must be recreated and reviewed.

## Privacy and alpha limits

Mail and audit state stay local by default, but local databases and exports are
**plaintext**. Protect them with host permissions, disk encryption, and backups.
Email content is untrusted input. See [SECURITY.md](SECURITY.md) and the
[threat model](docs/threat-model.md).

Threading and triage are heuristic. Bounded sync is not a complete mirror of
mailbox flags and deletions, and draft reconciliation indexes headers rather than
full provider draft bodies. Tests use synthetic data and provider fakes; they do
not establish live Bridge acceptance for your account. See the
[quality report](docs/quality.md) for evidence and remaining work.

## Develop and contribute

From a source checkout, install development dependencies in a virtual environment:

```text
python -m pip install -e ".[dev]"
python scripts/validate.py
```

Validation checks architecture, documentation links, lint, tests, CLI help, and a
synthetic workflow in temporary state. Read the [agent map](AGENTS.md),
[architecture](docs/architecture.md), and [harness guide](docs/harness-engineering.md).
[Issues](https://github.com/josephbartlett/MailOps/issues) are welcome; use synthetic
examples and omit mailbox content and credentials.

MailOps is [MIT licensed](LICENSE). It follows Semantic Versioning; see the
[changelog](CHANGELOG.md), [release process](docs/release-process.md), and
[roadmap](docs/roadmap.md).
