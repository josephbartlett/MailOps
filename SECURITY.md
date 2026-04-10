# Security Policy

MailOps handles email metadata and may create reviewed provider drafts. Treat local state, logs, and exports as sensitive.

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 0.1.x   | Yes       |

## Reporting

Before a public issue is filed for a security concern, contact the maintainer through the repository security channel once the public remote is configured.

Do not include mailbox contents, Bridge passwords, OAuth tokens, authorization headers, or raw message bodies in public reports.

## Credential Handling

- Do not commit `.mailops/`, `.env`, logs, local SQLite databases, or Bridge credentials.
- Saved Proton profiles intentionally do not persist passwords.
- Use `MAILOPS_PROTON_PASSWORD` as a runtime-only environment variable for live Proton validation.
- Rotate any Bridge password that was pasted into chat, terminal history, or logs.

## Current Safety Boundaries

- MailOps can create reviewed Proton drafts.
- MailOps cannot send mail.
- MailOps cannot delete mail.
- MailOps cannot apply provider rules.
- Rule generation is preview-only.
