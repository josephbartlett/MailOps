# Proton Provider Notes

MailOps is Proton-first for the MVP because the local-first story is strongest when paired with Proton Mail Bridge.

## Implemented in the current milestone

- discovery from `.mailops/config/config.toml`, Proton-specific env vars, or explicit CLI overrides
- saved non-secret Proton Bridge profiles under `.mailops/config/proton_accounts.json`
- local IMAP folder listing through Proton Mail Bridge with provider-aware role/capability detection
- bounded initial sync of recent messages from selected folders
- UID-based incremental sync after the initial cursor is established, with cursor advancement held behind failed fetches
- normalization of accounts, folders, threads, and messages into SQLite
- canonical mailbox consolidation across aliases when `canonical_email` is set
- multi-profile sync in one CLI invocation through `mailops sync --profile all`
- local search and simple waiting-on-me triage over synced data
- provider-side draft materialization through Bridge IMAP `APPEND`
- custom outbound draft materialization after review approval
- provider draft syncback through header-only lookup of executed `Drafts:uid` refs
- review-only Proton Sieve proposal generation and preview
- WSL-to-Windows Bridge host fallback when localhost is not reachable from WSL

## Supported discovery inputs

- config file section: `[providers.proton_bridge]`
- env vars:
  - `MAILOPS_PROTON_HOST`
  - `MAILOPS_PROTON_IMAP_PORT`
  - `MAILOPS_PROTON_SMTP_PORT`
  - `MAILOPS_PROTON_IMAP_SECURITY`
  - `MAILOPS_PROTON_USERNAME`
  - `MAILOPS_PROTON_PASSWORD`
  - `MAILOPS_PROTON_ACCOUNT_EMAIL`
  - `MAILOPS_PROTON_CANONICAL_EMAIL`
  - `MAILOPS_PROTON_CONFIG_FILE`
- CLI overrides on `mailops connect proton` and `mailops sync`

## Assumptions

- Proton Mail Bridge is installed and running on the host OS or on a reachable local network host
- Bridge exposes IMAP and SMTP endpoints locally
- saved profiles store connection metadata but not secrets
- account credentials are managed by Bridge or injected locally by the operator, not by a MailOps cloud service

## Supported local topologies

- Native Windows: Bridge and MailOps both run on Windows.
- Native Linux desktop: Bridge and MailOps both run on the Linux desktop environment supported by Proton.
- WSL on Windows: Bridge runs on Windows, while MailOps runs in WSL and automatically falls back from `127.0.0.1` to the Windows host IP when needed.

See [WSL and Windows Bridge setup](wsl-windows-bridge.md) for the WSL topology.

## Known limitations

- initial sync intentionally caps to a recent window so MailOps does not silently index an entire mailbox
- saved profile sync still requires a runtime password source such as `MAILOPS_PROTON_PASSWORD` or `--password`
- thread identity is derived from message headers and normalized subject fallback rather than provider-native thread ids
- SMTP send remains unimplemented; draft creation is implemented through IMAP append for reviewed thread replies and custom outbound drafts
- provider draft syncback records headers and provider refs for MailOps-created drafts; it does not send or delete mail
- Sieve helpers generate review-only rule text; provider rule application remains unimplemented
- running Proton Bridge itself inside WSL is not a first-class supported mode yet

## Safety notes

- never log Bridge credentials
- do not assume one Bridge layout across platforms
- keep discovery separate from sync so explicit overrides remain possible
- do not auto-send mail or auto-apply rules from the Proton adapter

## Sync and execution integrity

Sync uses read-only mailbox selection and `BODY.PEEK[]`. It validates returned
UIDs and binds each cursor to UIDVALIDITY. An unknown or changed epoch resets the
bounded initial sync window and clears stale folder links while retaining indexed
messages. A failed UID holds the cursor; IMAP range responses at or below the cursor
are ignored. The same Message-ID in different accounts stays separate locally.

Provider draft execution uses the reviewed recipients and account. A saved profile
must identify that account; missing envelopes in legacy proposals require recreation
and review. A durable per-action claim prevents concurrent apply from creating two
drafts. Interrupted or ambiguous provider attempts remain `executing`/`uncertain`;
MailOps does not automatically retry or roll back those actions. Inspect Proton
Drafts and local audit history before recovery. A recovery command that proves
provider absence and safely resets an action is not implemented yet.

Discovery parses real TOML, including quoted `#` characters, and validates ports
and security modes. Python 3.10 uses `tomli`; newer Python uses `tomllib`. Keep
passwords in runtime environment input, away from shell command arguments/config.

New provider references use `proton-draft-v2:` followed by JSON containing mailbox,
Message-ID, and (when available) UID and UIDVALIDITY. Header-only reconciliation
checks message identity and searches by Message-ID after epoch changes. Ambiguous
matches are not reported present. Legacy Message-ID references remain readable;
legacy UID-only references are reported `unverified` because the original identity
cannot be proved, and do not trigger a provider lookup.
