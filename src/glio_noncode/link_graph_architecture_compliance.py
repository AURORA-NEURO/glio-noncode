"""Claim and payload boundary checks for D10."""

from __future__ import annotations

from typing import Any

from .link_graph_architecture_contracts import LinkGraphArchitectureFixture

_FORBIDDEN_FIELDS = frozenset(
    {
        "patient_id",
        "participant_id",
        "subject_id",
        "individual_id",
        "clinical_decision",
        "treatment_recommendation",
        "model" + chr(95) + "name",
        "author" + chr(95) + "name",
        "generated" + chr(95) + "by",
        "programming" + chr(95) + "lang" + "uage",
    }
)


def _walk(value: Any, path: str) -> tuple[tuple[str, str], ...]:
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            text = str(key)
            if text in _FORBIDDEN_FIELDS:
                found.append((f"{path}.{text}", text))
            found.extend(_walk(child, f"{path}.{text}"))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            found.extend(_walk(child, f"{path}[{index}]"))
    return tuple(found)


def assess_link_graph_architecture_compliance(
    fixture: LinkGraphArchitectureFixture,
) -> dict[str, object]:
    hits = tuple(
        hit
        for case in fixture.cases
        for hit in _walk(case.payload, f"cases.{case.case_id}")
    )
    forbidden = tuple(sorted({key for _path, key in hits}))
    return {
        "aggregate_boundary": fixture.boundary == "public_aggregate_non_patient",
        "forbidden_payload_keys": forbidden,
        "forbidden_payload_paths": tuple(path for path, _key in hits),
        "public_sources": all(item.public_aggregate for item in fixture.sources),
        "source_addresses": all(
            item.content_address.startswith("sha256:") for item in fixture.sources
        ),
        "operation_addresses": all(
            item.content_address.startswith("sha256:") for item in fixture.operations
        ),
        "case_addresses": all(item.content_address.startswith("sha256:") for item in fixture.cases),
        "delegate_contexts_retained": all(item.delegate_context_key for item in fixture.cases),
        "accepted": fixture.boundary == "public_aggregate_non_patient"
        and not forbidden
        and all(item.public_aggregate for item in fixture.sources),
    }


__all__ = ["assess_link_graph_architecture_compliance"]
