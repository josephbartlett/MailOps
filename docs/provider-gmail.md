# Gmail Provider Notes

MailOps will use the Gmail API directly rather than forcing Gmail into an IMAP-first abstraction.

## Planned adapter scope

- OAuth account connection
- message and thread access
- label management
- draft creation
- sending with explicit user approval
- incremental sync support

## Design notes

- preserve Gmail label semantics
- keep scopes narrow and explainable
- treat API-specific metadata as a capability, not a nuisance

## Current status

The Gmail adapter modules in this scaffold are placeholders intended to receive the first OAuth and sync implementation in a later milestone.

