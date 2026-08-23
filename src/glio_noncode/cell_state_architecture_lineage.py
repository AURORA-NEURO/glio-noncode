"""Source-to-operation-to-case lineage for D08 traceability."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .cell_state_architecture_contracts import CellStateArchitectureFixture, addressed


def build_cell_state_architecture_lineage(fixture: CellStateArchitectureFixture) -> dict[str, Any]:
    source_to_operations: dict[str, list[str]] = defaultdict(list)
    operation_to_cases: dict[str, list[str]] = defaultdict(list)
    family_to_sources: dict[str, list[str]] = defaultdict(list)
    for source in fixture.sources:
        family_to_sources[source.family.value].append(source.source_id)
    for operation in fixture.operations:
        for source_id in operation.source_ids:
            source_to_operations[source_id].append(operation.operation_id)
    for case in fixture.cases:
        operation_to_cases[case.operation_id].append(case.case_id)
    lineage = {
        "fixture_id": fixture.fixture_id,
        "family_to_sources": {
            key: sorted(value) for key, value in sorted(family_to_sources.items())
        },
        "source_to_operations": {
            key: sorted(value) for key, value in sorted(source_to_operations.items())
        },
        "operation_to_cases": {
            key: sorted(value) for key, value in sorted(operation_to_cases.items())
        },
        "case_count": len(fixture.cases),
    }
    return lineage | {"content_address": addressed(lineage, "cell-state-lineage")}


def lineage_gaps(fixture: CellStateArchitectureFixture) -> tuple[str, ...]:
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


__all__ = ["build_cell_state_architecture_lineage", "lineage_gaps"]
