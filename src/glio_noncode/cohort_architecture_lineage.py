"""D12 source, operation, and case lineage projections."""

from __future__ import annotations

from typing import Any

from .cohort_architecture_contracts import CohortArchitectureFixture, addressed


def build_cohort_architecture_lineage(
    fixture: CohortArchitectureFixture,
) -> dict[str, Any]:
    family_sources = {
        family.value: tuple(item.source_id for item in fixture.sources if item.family is family)
        for family in fixture.family_set
    }
    source_operations = {
        source.source_id: tuple(
            operation.operation_id
            for operation in fixture.operations
            if source.source_id in operation.source_ids
        )
        for source in fixture.sources
    }
    operation_cases = {
        operation.operation_id: tuple(
            item.case_id for item in fixture.cases if item.operation_id == operation.operation_id
        )
        for operation in fixture.operations
    }
    edges = tuple(
        {
            "source_id": source_id,
            "operation_ids": operation_ids,
        }
        for source_id, operation_ids in sorted(source_operations.items())
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "family_sources": family_sources,
        "source_operations": source_operations,
        "operation_cases": operation_cases,
        "edges": edges,
    }
    return body | {"content_address": addressed(body, "cohort-lineage")}


def cohort_architecture_lineage_gaps(
    fixture: CohortArchitectureFixture,
) -> tuple[str, ...]:
    lineage = build_cohort_architecture_lineage(fixture)
    gaps = []
    for source_id, operation_ids in lineage["source_operations"].items():
        if not operation_ids:
            gaps.append(f"source:{source_id}")
    for operation_id, case_ids in lineage["operation_cases"].items():
        if len(case_ids) != 4:
            gaps.append(f"operation:{operation_id}")
    return tuple(gaps)


__all__ = ["build_cohort_architecture_lineage", "cohort_architecture_lineage_gaps"]
