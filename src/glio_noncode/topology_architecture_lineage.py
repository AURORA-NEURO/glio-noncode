"""Source, operation, and case lineage for D09."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .topology_architecture_contracts import TopologyArchitectureFixture, addressed


def build_topology_architecture_lineage(fixture: TopologyArchitectureFixture) -> dict[str, Any]:
    family_sources: dict[str, list[str]] = defaultdict(list)
    source_operations: dict[str, list[str]] = defaultdict(list)
    operation_cases: dict[str, list[str]] = defaultdict(list)
    for source in fixture.sources:
        family_sources[source.family.value].append(source.source_id)
    for operation in fixture.operations:
        for source_id in operation.source_ids:
            source_operations[source_id].append(operation.operation_id)
    for case in fixture.cases:
        operation_cases[case.operation_id].append(case.case_id)
    body = {
        "fixture_id": fixture.fixture_id,
        "family_sources": {key: sorted(value) for key, value in sorted(family_sources.items())},
        "source_operations": {
            key: sorted(value) for key, value in sorted(source_operations.items())
        },
        "operation_cases": {key: sorted(value) for key, value in sorted(operation_cases.items())},
    }
    return body | {"content_address": addressed(body, "topology-lineage")}


def topology_architecture_lineage_gaps(fixture: TopologyArchitectureFixture) -> tuple[str, ...]:
    source_ids = {item.source_id for item in fixture.sources}
    operation_ids = {item.operation_id for item in fixture.operations}
    return tuple(
        sorted(
            {
                source_id
                for item in fixture.operations
                for source_id in item.source_ids
                if source_id not in source_ids
            }
            | {
                item.operation_id
                for item in fixture.cases
                if item.operation_id not in operation_ids
            }
        )
    )


__all__ = ["build_topology_architecture_lineage", "topology_architecture_lineage_gaps"]
