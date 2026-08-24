"""Field dictionary for the D10 public aggregate."""

from __future__ import annotations


def link_graph_architecture_data_dictionary() -> dict[str, object]:
    return {
        "fixture": {
            "fixture_id": "stable aggregate identifier",
            "boundary": "public aggregate boundary",
            "context_key": "genome, disease, age, cell state, territory, treatment tuple",
            "sources": "public source receipts",
            "operations": "ordered operation contracts",
            "cases": "positive and control records",
            "content_address": "canonical content address",
        },
        "case": {
            "delegate_fixture_id": "family fixture identity",
            "delegate_record_id": "family record identity",
            "delegate_context_key": "family context retained",
            "expected_state": "aggregate release state",
            "expected_result_state": "family result state",
            "expected_issue_codes": "family issue vocabulary",
            "payload": "review-safe delegate summary",
        },
        "release": {
            "artifact_ids": "six sanitized outputs",
            "limitations": "non-causal and non-clinical boundaries",
        },
    }


__all__ = ["link_graph_architecture_data_dictionary"]
