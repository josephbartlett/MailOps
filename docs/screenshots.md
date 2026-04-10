# CLI Captures

These text captures are safe for public alpha docs because they use the local `demo_local` dataset, not real mailbox content.

## Help

```text
Usage: python -m mailops.cli.main [OPTIONS] COMMAND [ARGS]...

MailOps: local-first inbox operations harness for serious workflows.

Commands:
  doctor     Validate the local MailOps runtime and print a concise report.
  connect    Inspect provider connection state and optionally verify Proton Bridge access.
  sync       Sync mailbox data for the selected provider into the local index.
  status     Show the current local MailOps state.
  search     Search synced local mailbox state.
  triage     Show threads likely waiting on the operator.
  ask        Compile a natural-language request into explicit actions or queries.
  apply      Apply a review batch and materialize provider-side drafts when possible.
  rollback   Describe rollback behavior without faking reversible provider state.
  demo       Seed local-only demo data.
  review     Inspect pending review work.
  rules      Preview provider-native rules without applying them.
  export     Export local MailOps artifacts.
```

## Demo Seed And Status

```text
Seeded local demo mailbox 'demo@example.com' with 5 threads and 6 messages.

MailOps Status
environment               development
default_provider          proton_bridge
accounts                  1
folders                   2
threads                   5
messages                  6
provider_drafts           0
review_batches            0
pending_action_proposals  0
```

## Demo Triage

```text
Triage
account          all
window           0d
waiting_on_me    2
waiting_on_them  1
resolved         1
ambiguous        1
ranked_results   2

Waiting On Me
demo@example.com  Invoice approval needed             95%
demo@example.com  Scheduling implementation review    93%
```

## Rule Preview

```text
Rule Proposal
provider         proton_bridge
intent           filter future messages from vendor.example to label Finance
target_mailbox   Labels/Finance
risk             medium
apply_supported  false

Structured Conditions
from_domain  is  vendor.example

require ["fileinto"];

if address :domain :is "From" "vendor.example" {
    fileinto "Labels/Finance";
    stop;
}
```
