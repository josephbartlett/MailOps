# MailOps Threat Model

MailOps handles operational email data locally and may eventually execute provider actions. That makes both privacy and action safety first-order concerns.

## Primary threats

- credential leakage from config, logs, or crash output
- model overreach that hides destructive scope
- unsafe bulk actions across multiple accounts
- accidental disclosure of mailbox content in exports or bug reports
- provider-specific edge cases causing incorrect sync or duplicate actions

## Design responses

- store secrets in OS-backed secure storage where possible
- keep caches and audit data local by default
- redact logs and minimize model payloads
- require review for risky actions
- preserve provider-specific semantics instead of flattening everything
- record why an action was proposed or executed

## v1 boundaries

- delete remains disabled by default
- send requires explicit user action
- provider rules are proposed, never silently applied
- the `ask` layer compiles to explicit structured actions instead of hidden tool calls

