"""Source-to-operation-to-case lineage for D13."""

from __future__ import annotations

from typing import Any

from .planning_architecture_contracts import PlanningArchitectureFixture, addressed
from .planning_architecture_public_data import default_planning_architecture_fixture


def planning_architecture_lineage_rows(
    fixture: PlanningArchitectureFixture | None = None,
) -> tuple[dict[str, Any], ...]:
    selected = fixture or default_planning_architecture_fixture()
    source_by_id = {item.source_id: item for item in selected.sources}
    operation_by_id = {item.operation_id: item for item in selected.operations}
    rows: list[dict[str, Any]] = []
    for case in selected.cases:
        operation = operation_by_id[case.operation_id]
        for source_id in case.source_ids:
            source = source_by_id[source_id]
            body = {
                "source_id": source_id,
                "delegate_source_id": source.delegate_source_id,
                "family": case.family,
                "operation_id": case.operation_id,
                "capability_id": operation.capability_id,
                "case_id": case.case_id,
                "scenario": case.scenario,
                "delegate_fixture_id": case.delegate_fixture_id,
                "delegate_record_id": case.delegate_record_id,
                "aggregate_context_key": case.aggregate_context_key,
                "delegate_context_key": case.delegate_context_key,
                "source_content_address": source.content_address,
                "case_content_address": case.content_address,
            }
            rows.append(body | {"lineage_address": addressed(body, "planning-lineage")})
    return tuple(rows)


def planning_architecture_lineage_gaps(
    fixture: PlanningArchitectureFixture | None = None,
) -> tuple[str, ...]:
    selected = fixture or default_planning_architecture_fixture()
    source_ids = {item.source_id for item in selected.sources}
    operation_ids = {item.operation_id for item in selected.operations}
    gaps: list[str] = []
    for case in selected.cases:
        if case.operation_id not in operation_ids:
            gaps.append(f"case:{case.case_id}:operation")
        if not set(case.source_ids) <= source_ids:
            gaps.append(f"case:{case.case_id}:source")
        if not case.delegate_fixture_id or not case.delegate_record_id:
            gaps.append(f"case:{case.case_id}:delegate")
        if not case.delegate_context_key:
            gaps.append(f"case:{case.case_id}:context")
    return tuple(gaps)


def planning_architecture_lineage_summary(
    fixture: PlanningArchitectureFixture | None = None,
) -> dict[str, object]:
    selected = fixture or default_planning_architecture_fixture()
    rows = planning_architecture_lineage_rows(selected)
    return {
        "fixture_id": selected.fixture_id,
        "row_count": len(rows),
        "source_count": len({row["source_id"] for row in rows}),
        "case_count": len({row["case_id"] for row in rows}),
        "gap_count": len(planning_architecture_lineage_gaps(selected)),
        "families": sorted({row["family"].value for row in rows}),
    }


__all__ = [
    "planning_architecture_lineage_gaps",
    "planning_architecture_lineage_rows",
    "planning_architecture_lineage_summary",
]
