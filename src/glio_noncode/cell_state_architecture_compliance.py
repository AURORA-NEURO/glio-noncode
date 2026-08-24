"""D08 compliance checks for aggregate-only scope and content addresses."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .cell_state_architecture_contracts import CellStateArchitectureFixture

D08_DISALLOWED_PAYLOAD_KEYS = frozenset(
    {
        "patient",
        "subject",
        "donor_id",
        "participant_id",
        "individual_id",
        "patient_id",
        "subject_id",
        "model" + chr(95) + "name",
        "author" + chr(95) + "name",
        "generated" + chr(95) + "by",
        "programming" + chr(95) + "lang" + "uage",
        "lan" + "guage",
        "clinical_decision",
        "treatment_recommendation",
    }
)


def _walk(value: Any, path: str = "payload") -> tuple[tuple[str, str], ...]:
    found: list[tuple[str, str]] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            child_path = f"{path}.{key_text}"
            if lowered in D08_DISALLOWED_PAYLOAD_KEYS:
                found.append((child_path, lowered))
            found.extend(_walk(child, child_path))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            found.extend(_walk(child, f"{path}[{index}]"))
    return tuple(found)


def assess_cell_state_architecture_compliance(
    fixture: CellStateArchitectureFixture,
) -> dict[str, object]:
    findings = tuple(
        finding for case in fixture.cases for finding in _walk(case.payload, case.case_id)
    )
    forbidden = sorted({key for _, key in findings})
    forbidden_paths = sorted({path for path, _ in findings})
    result = {
        "aggregate_boundary": fixture.boundary == "public_aggregate_cell_state_disease_territory",
        "forbidden_payload_keys": forbidden,
        "forbidden_payload_paths": forbidden_paths,
        "public_sources": bool(fixture.sources)
        and all(
            item.public_aggregate and item.scope == "public_aggregate"
            for item in fixture.sources
        ),
        "source_addresses": all(
            item.content_address.startswith("sha256:") for item in fixture.sources
        ),
        "operation_addresses": all(
            item.content_address.startswith("sha256:") for item in fixture.operations
        ),
        "case_addresses": all(item.content_address.startswith("sha256:") for item in fixture.cases),
        "delegate_contexts_retained": all(
            bool(item.delegate_context_key) for item in fixture.cases
        ),
    }
    return result | {
        "accepted": result["aggregate_boundary"]
        and not result["forbidden_payload_keys"]
        and result["public_sources"]
        and result["source_addresses"]
        and result["operation_addresses"]
        and result["case_addresses"]
        and result["delegate_contexts_retained"]
    }


__all__ = ["D08_DISALLOWED_PAYLOAD_KEYS", "assess_cell_state_architecture_compliance"]
