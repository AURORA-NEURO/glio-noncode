"""D11 field-level data dictionary."""

from __future__ import annotations


def causal_architecture_data_dictionary() -> dict[str, object]:
    return {
        "fixture": {
            "fixture_id": "stable public aggregate identifier",
            "boundary": "research-use public boundary",
            "context_key": "genome, disease, age, cell state, territory, treatment tuple",
            "sources": "public source receipts",
            "operations": "ordered causal evidence contracts",
            "cases": "positive and control records",
            "content_address": "canonical address",
        },
        "case": {
            "delegate_fixture_id": "family fixture identity",
            "delegate_record_id": "family record identity",
            "delegate_context_key": "family context retained",
            "expected_state": "aggregate release state",
            "expected_result_state": "family result state",
            "expected_issue_codes": "family issue vocabulary",
            "payload": "bounded delegate summary",
        },
        "release": {
            "artifact_ids": "six sanitized outputs",
            "limitations": "research-only and non-clinical boundaries",
        },
    }


__all__ = ["causal_architecture_data_dictionary"]
