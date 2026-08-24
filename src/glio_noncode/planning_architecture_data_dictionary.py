"""D13 field-level data dictionary."""

from __future__ import annotations

from typing import Any


def planning_architecture_data_dictionary() -> tuple[dict[str, Any], ...]:
    rows = (
        (
            "fixture_id",
            "string",
            "aggregate fixture identity",
            True,
            "planning-architecture-public-aggregate-001",
        ),
        (
            "version",
            "string",
            "typed D13 contract version",
            True,
            "2026.08.d13-planning-architecture.v1",
        ),
        ("boundary", "string", "public aggregate boundary", True, "public_aggregate_non_patient"),
        (
            "context_key",
            "string",
            "aggregate context envelope",
            True,
            "multi_context_public_aggregate",
        ),
        (
            "family_contexts",
            "object",
            "exact context retained per delegate family",
            True,
            "four non-empty entries",
        ),
        (
            "source_id",
            "string",
            "prefixed public source receipt identity",
            True,
            "D13 family source key",
        ),
        (
            "delegate_source_id",
            "string",
            "source identity in the family fixture",
            True,
            "family-local source key",
        ),
        ("operation_id", "string", "D13 operation identity", True, "D13-C01 through D13-C16"),
        (
            "capability_id",
            "string",
            "capability registry identity",
            True,
            "GNC-D13-C01 through GNC-D13-C16",
        ),
        (
            "delegate_operation",
            "string",
            "family evaluator operation",
            True,
            "family operation enum value",
        ),
        (
            "dependencies",
            "array",
            "earlier operation dependencies",
            True,
            "zero or more D13 operation IDs",
        ),
        ("case_id", "string", "aggregate case identity", True, "D13-Cxx-POS/CTRL-xxx"),
        (
            "scenario",
            "string",
            "positive or balanced control role",
            True,
            "positive/control_a/control_b/control_c",
        ),
        (
            "delegate_fixture_id",
            "string",
            "family fixture identity",
            True,
            "public aggregate fixture ID",
        ),
        ("delegate_record_id", "string", "family record identity", True, "family-local record ID"),
        (
            "aggregate_context_key",
            "string",
            "D13 envelope context",
            True,
            "multi_context_public_aggregate",
        ),
        (
            "delegate_context_key",
            "string",
            "family exact context or held control context",
            True,
            "context receipt",
        ),
        (
            "payload",
            "object",
            "sanitized synthetic planning input",
            True,
            "public aggregate mapping",
        ),
        (
            "expected_state",
            "string",
            "delegate-backed observed state",
            True,
            "ready, routed, designed, held, or updated",
        ),
        (
            "expected_issue_codes",
            "array",
            "delegate issue vocabulary",
            True,
            "empty or explicit issue codes",
        ),
        (
            "expected_counts",
            "object",
            "bounded count invariants",
            True,
            "source/payload/output/issue counts",
        ),
        (
            "content_address",
            "string",
            "deterministic SHA-256-style address",
            True,
            "sha256-prefixed receipt",
        ),
    )
    return tuple(
        {
            "field": field,
            "type": field_type,
            "description": description,
            "required": required,
            "example": example,
        }
        for field, field_type, description, required, example in rows
    )


def planning_architecture_data_dictionary_summary() -> dict[str, object]:
    rows = planning_architecture_data_dictionary()
    return {
        "field_count": len(rows),
        "required_count": sum(item["required"] for item in rows),
        "types": sorted({item["type"] for item in rows}),
        "fields": [item["field"] for item in rows],
    }


__all__ = [
    "planning_architecture_data_dictionary",
    "planning_architecture_data_dictionary_summary",
]
