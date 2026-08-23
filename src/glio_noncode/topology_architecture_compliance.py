"""Aggregate-only compliance checks for the D09 topology release."""

from __future__ import annotations

from .topology_architecture_contracts import TopologyArchitectureFixture


def assess_topology_architecture_compliance(
    fixture: TopologyArchitectureFixture,
) -> dict[str, object]:
    forbidden = {"patient", "subject", "donor_id", "participant_id", "individual_id"}
    keys = {str(key).lower() for case in fixture.cases for key in case.payload}
    result = {
        "aggregate_boundary": fixture.boundary == "public_aggregate_3d_genome_regulatory_topology",
        "forbidden_payload_keys": sorted(keys & forbidden),
        "source_addresses": all(
            item.content_address.startswith("sha256:") for item in fixture.sources
        ),
        "operation_addresses": all(
            item.content_address.startswith("sha256:") for item in fixture.operations
        ),
        "case_addresses": all(item.content_address.startswith("sha256:") for item in fixture.cases),
    }
    return result | {
        "accepted": not result["forbidden_payload_keys"]
        and all(value for key, value in result.items() if key != "forbidden_payload_keys")
    }


__all__ = ["assess_topology_architecture_compliance"]
