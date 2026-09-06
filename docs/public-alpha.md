# Public Alpha Guide

MailOps **0.2.1** is a local-first email CLI for Proton Mail Bridge. Search and
triage multiple accounts, prepare reviewed drafts, and export an audit trail.
The mailbox index and audit history stay in local SQLite state; optional
[Codex skills](codex-skills.md) use the same CLI workflows.

**Alpha software. Sending and Gmail support are not implemented.** The
[0.2.1 release notes](releases/v0.2.1.md) cover this documentation and discovery
update. The [0.2.0 notes](releases/v0.2.0.md) cover the preceding safety fixes and
store migration.

## Install and upgrade

Use **Python 3.10+** and a virtual environment. Download the wheel attached to the
[GitHub release](https://github.com/josephbartlett/MailOps/releases/tag/v0.2.1),
then run:

```text
python -m pip install ./mailops-0.2.1-py3-none-any.whl
mailops --help
```

The [README installation steps](../README.md#install-the-release) show virtual
environment setup and direct release installation for PowerShell and Bash. PyPI
availability is separate from GitHub publication.

Before upgrading an operational store, stop MailOps operations and back up the
established `MAILOPS_HOME`. Most state-using commands initialize/migrate the
database. Use an absolute home path when invoking MailOps from another repository.
Version 0.2.1 adds no schema changes, but upgrades from 0.1.0 must follow the
[0.2.0 migration instructions](releases/v0.2.0.md#upgrade-instructions). Existing
overwritten mail cannot be reconstructed by migration; old proposals without
reviewed recipients must be recreated and reviewed.

## Try the local demo

The [README demo steps](../README.md#try-the-synthetic-demo) create a new temporary
`MAILOPS_HOME` and restore your previous setting in both PowerShell and Bash.
They run local seed, status, search, inspection, and triage commands without
credentials or provider connections. Never seed demo data into an operational
mailbox store.

The demo account uses provider `demo_local`; it does not simulate live Proton
acceptance. See [the synthetic terminal demonstration](demo.md) for actual CLI
output and reproduction details.

## Work with Proton

Follow [the Windows continuation guide](windows-powershell-handoff.md),
[WSL setup](wsl-windows-bridge.md), or [provider notes](provider-proton.md).
Set the intended existing absolute `MAILOPS_HOME`, verify the account/profile,
and select a bounded sync scope. The default `.mailops` is relative to the current
directory; an empty newly initialized store is not evidence of an empty mailbox.
Use Bridge-generated credentials through transient secure input, never password
arguments or persisted config.

Inspect every proposal's complete account, recipients, subject, and body before
authorizing its creation in Proton Drafts. Apply never sends mail. An interrupted
or uncertain provider attempt blocks retry and local rollback until the operator
inspects Proton Drafts and audit history. Legacy UID-only references are unverified.
The [CLI reference](cli-reference.md) documents commands and review behavior.

## Alpha limitations

| Area | Limit |
| --- | --- |
| Providers and actions | Gmail runtime, sending, deletion, bulk archive/move, and rule application are unimplemented. Sieve output is preview-only. |
| Index and triage | Threading and triage are heuristic. Bounded sync is not a complete mirror of existing flags and deletions. |
| Draft reconciliation | Provider snapshots contain headers, not full draft bodies in the index. |
| Local privacy | State and exports are plaintext; protect them with host permissions, encryption, and backups. |
| Validation | Automated tests use synthetic data and provider fakes. They do not establish live Bridge acceptance for an operator's account. |

See the [security policy](../SECURITY.md), [threat model](threat-model.md), and
[quality report](quality.md) for privacy guidance, audit evidence, and remaining work.

## Contribute

For development, install `.[dev]` into a virtual environment and run
`python scripts/validate.py`. The command includes a synthetic demo in temporary
state. See [the harness guide](harness-engineering.md) and
[release checklist](release-checklist.md) for validation details.
