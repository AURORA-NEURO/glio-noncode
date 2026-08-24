"""Claim and payload boundary checks for D10."""

from __future__ import annotations

from .link_graph_architecture_contracts import LinkGraphArchitectureFixture


def assess_link_graph_architecture_compliance(
    fixture: LinkGraphArchitectureFixture,
) -> dict[str, object]:
    forbidden = tuple(
        sorted(
            {
                key
                for case in fixture.cases
                for key in case.payload
                if key in {"patient_id", "clinical_decision", "treatment_recommendation"}
            }
        )
    )
    return {
        "aggregate_boundary": fixture.boundary == "public_aggregate_non_patient",
        "forbidden_payload_keys": forbidden,
        "public_sources": all(item.public_aggregate for item in fixture.sources),
        "source_addresses": all(
            item.content_address.startswith("sha256:") for item in fixture.sources
        ),
        "operation_addresses": all(
            item.content_address.startswith("sha256:") for item in fixture.operations
        ),
        "case_addresses": all(item.content_address.startswith("sha256:") for item in fixture.cases),
        "accepted": fixture.boundary == "public_aggregate_non_patient"
        and not forbidden
        and all(item.public_aggregate for item in fixture.sources),
    }


__all__ = ["assess_link_graph_architecture_compliance"]
