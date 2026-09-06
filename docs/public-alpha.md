# Public Alpha Guide

MailOps 0.2.0 is a local-first, provider-aware inbox operations harness. It supports
Proton Bridge discovery, bounded indexing, search, inspection, heuristic triage,
local draft proposals, reviewed Proton draft creation, reconciliation, and audit
export. The [release notes](releases/v0.2.0.md) describe the changes and migration.

## Install and upgrade

Use the wheel attached to the [GitHub release](https://github.com/josephbartlett/MailOps/releases/tag/v0.2.0):

```text
python -m pip install ./mailops-0.2.0-py3-none-any.whl
```

For development, install `.[dev]` into a virtual environment and run
`python scripts/validate.py`. See [the harness guide](harness-engineering.md).
PyPI availability is separate from GitHub publication.

Before upgrading an operational store, stop MailOps operations and back up the
established `MAILOPS_HOME`. The first state-using command performs schema migration.
Use an absolute home path when invoking MailOps from another repository. Existing
overwritten mail cannot be reconstructed by migration; old proposals without
reviewed recipients must be recreated and reviewed.

## Try the local demo

The shared validation command runs a synthetic demo in temporary state. For an
interactive demo, select a new temporary `MAILOPS_HOME` and restore the previous
setting afterward. Never seed demo data into an operational mailbox store.

Once an isolated home is selected, `mailops demo seed`, `mailops search invoice`,
`mailops inspect thread demo-thread-finance`, and `mailops triage --since 0d` show
the local workflow without Bridge credentials.

## Work with Proton

Follow [the Windows continuation guide](windows-powershell-handoff.md) or
[provider notes](provider-proton.md). Select the correct account/profile and a
bounded sync scope. Use Bridge-generated credentials through transient secure
input, never password arguments or persisted config.

Inspect every proposal's complete account, recipients, subject, and body before
authorizing its creation in Proton Drafts. Apply never sends mail. An interrupted
or uncertain provider attempt blocks retry and local rollback until the operator
inspects Proton Drafts and audit history. Legacy UID-only references are unverified.

## Alpha limitations

- Gmail runtime, sending, deletion, bulk archive/move, and rule application are
  unimplemented. Sieve output is preview-only.
- Threading and triage are heuristic; the bounded index is not a complete mirror
  of existing message flags and deletions.
- Provider-draft reconciliation records headers, not full draft bodies in the index.
- Local state and exports are plaintext; protect them with host permissions,
  encryption, and backups.
- Automated tests use synthetic data and provider fakes. They do not establish
  live Bridge acceptance for an operator's account.

See [quality.md](quality.md) for audit evidence and remaining work, and
[release-checklist.md](release-checklist.md) for release validation.
