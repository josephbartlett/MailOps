# Rule Engine Notes

MailOps distinguishes between:

- provider-neutral local classification logic
- provider-native rule artifacts that users may review and apply

## v1 focus

The first rule work focuses on review-only Proton Sieve proposals because that is where provider-aware automation can be both powerful and explainable.

## Requirements

- show the natural-language intent
- show structured conditions
- show generated provider-native rule text
- explain why the rule matches
- preview impact where possible
- never auto-apply rules without approval

## Current command

```bash
mailops rules propose "filter future messages from vendor.example to label Finance"
```

The command emits structured conditions, Proton Sieve text, and a preview. It does not persist or apply provider rules.
