# Proton Provider Notes

MailOps is Proton-first for the MVP because the local-first story is strongest when paired with Proton Mail Bridge.

## Implemented in the current milestone

- discovery from `.mailops/config/config.toml`, Proton-specific env vars, or explicit CLI overrides
- saved non-secret Proton Bridge profiles under `.mailops/config/proton_accounts.json`
- local IMAP folder listing through Proton Mail Bridge with provider-aware role/capability detection
- bounded initial sync of recent messages from selected folders
- UID-based incremental sync after the initial cursor is established
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
