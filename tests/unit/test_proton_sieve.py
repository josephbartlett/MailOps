from __future__ import annotations

from mailops.adapters.proton_bridge.sieve import generate_sieve_rule_proposal


def test_generate_sieve_rule_proposal_uses_sender_domain_and_label_target() -> None:
    proposal = generate_sieve_rule_proposal("filter future messages from vendor.example to label Finance")

    assert proposal.target_mailbox == "Labels/Finance"
    assert proposal.structured_conditions[0].field == "from_domain"
    assert proposal.structured_conditions[0].value == "vendor.example"
    assert 'address :domain :is "From" "vendor.example"' in proposal.generated_rule_text
    assert 'fileinto "Labels/Finance";' in proposal.generated_rule_text
    assert "does not apply this rule" in proposal.preview


def test_generate_sieve_rule_proposal_escapes_sieve_strings() -> None:
    proposal = generate_sieve_rule_proposal('rule subject contains ACME "urgent" to folder Client')

    assert 'header :contains "Subject" "ACME \\"urgent\\""' in proposal.generated_rule_text
    assert 'fileinto "Folders/Client";' in proposal.generated_rule_text
