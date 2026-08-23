"""D08 compliance checks for aggregate-only scope and content addresses."""

from __future__ import annotations

from .cell_state_architecture_contracts import CellStateArchitectureFixture

D08_DISALLOWED_PAYLOAD_KEYS = frozenset(
    {"patient", "subject", "donor_id", "participant_id", "individual_id"}
)


def assess_cell_state_architecture_compliance(
    fixture: CellStateArchitectureFixture,
) -> dict[str, object]:
    payload_keys = {str(key).lower() for case in fixture.cases for key in case.payload}
    forbidden = sorted(payload_keys & D08_DISALLOWED_PAYLOAD_KEYS)
    result = {
        "aggregate_boundary": fixture.boundary == "public_aggregate_cell_state_disease_territory",
        "forbidden_payload_keys": forbidden,
        "source_addresses": all(
            item.content_address.startswith("sha256:") for item in fixture.sources
        ),
        "operation_addresses": all(
            item.content_address.startswith("sha256:") for item in fixture.operations
        ),
        "case_addresses": all(item.content_address.startswith("sha256:") for item in fixture.cases),
    }
    return result | {
        "accepted": not forbidden
        and all(value for key, value in result.items() if key != "forbidden_payload_keys")
    }


__all__ = ["D08_DISALLOWED_PAYLOAD_KEYS", "assess_cell_state_architecture_compliance"]
