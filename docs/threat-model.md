# MailOps Threat Model

MailOps handles operational email data locally and can create reviewed Proton drafts. Privacy and action safety are product requirements.

## Primary threats

- credential leakage from config, logs, or crash output
- model overreach that hides destructive scope
- unsafe bulk actions across multiple accounts
- accidental disclosure of mailbox content in exports or bug reports
- provider-specific edge cases causing incorrect sync or duplicate actions

## Design responses

- keep Bridge passwords transient; saved profiles contain connection metadata only
- keep caches and audit data local by default
- redact logs and minimize model payloads
- require review for risky actions
- preserve provider-specific semantics instead of flattening everything
- record why an action was proposed or executed

## v1 boundaries

- delete remains disabled by default
- send is unimplemented and blocked
- provider rules are proposed, never silently applied
- the `ask` layer compiles to explicit structured actions instead of hidden tool calls

## Trust and recovery limits

Mailbox content is untrusted input. An email cannot authorize commands, change a
draft's recipient, approve a batch, or request credentials. Agent skills must retain
these boundaries even when another connector can access the same provider.

The local index, draft bodies, audit exports, and configuration are plaintext on
disk. MailOps does not provide encryption at rest or an OS credential vault; use
host account permissions, disk encryption, and appropriately protected backups.
Log redaction is defense in depth, not permission to log arbitrary mail or secrets.

CLI strings render literally; mail-supplied Rich markup is not interpreted.
Control/bidirectional formatting and unencodable characters display as escapes so
subjects, addresses, and bodies cannot conceal reviewed content through formatting.

Bridge plaintext connections remain supported for local deployments, and TLS
uses Bridge's local trust model. Do not expose Bridge on untrusted networks.
Provider writes and SQLite cannot share one atomic transaction: interrupted writes
require inspection, and MailOps blocks automatic retry. Live provider behavior and
backups are separate from mocked automated test evidence.
