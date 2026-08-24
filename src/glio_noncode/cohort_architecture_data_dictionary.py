"""D12 field-level data dictionary."""

from __future__ import annotations


def cohort_architecture_data_dictionary() -> dict[str, object]:
    return {
        "fixture": {
            "fixture_id": "stable public aggregate identity",
            "boundary": "public aggregate research boundary",
            "context_key": "aggregate envelope context",
            "family_contexts": "exact context key retained for each cohort family",
            "sources": "prefixed source receipts joined to delegate receipts",
            "operations": "sixteen semantic cohort contracts",
            "cases": "positive and three control scenarios per operation",
            "content_address": "canonical aggregate address",
        },
        "source": {
            "delegate_source_id": "family source identifier",
            "delegate_fixture_id": "family fixture identity",
            "source_context_key": "family context used by the source",
            "public_aggregate": "public aggregate visibility flag",
            "delegate_content_address": "family receipt address",
        },
        "case": {
            "delegate_fixture_id": "family fixture identity",
            "delegate_record_id": "family record identity",
            "delegate_class": "positive or declared control class",
            "delegate_context_key": "exact family context retained",
            "expected_state": "family evaluator state expected by the aggregate",
            "expected_issue_codes": "family issue and control vocabulary",
            "expected_counts": "source, payload, and row accounting",
            "payload": "bounded public delegate input and output projection",
        },
        "release": {
            "artifact_ids": "six review-safe outputs",
            "limitations": "descriptive cohort claim ceiling",
        },
    }


__all__ = ["cohort_architecture_data_dictionary"]
