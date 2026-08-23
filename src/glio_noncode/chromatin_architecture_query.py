"""Stable query helpers over D07 fixtures and receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_architecture_contracts import (
    ChromatinArchitectureCase,
    ChromatinArchitectureEvaluation,
    ChromatinArchitectureOperation,
    ChromatinArchitectureState,
    addressed,
)
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureQuery:
    operation: ChromatinArchitectureOperation | None = None
    state: ChromatinArchitectureState | None = None
    scenario: str | None = None
    family: str | None = None


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureQueryResult:
    case_ids: tuple[str, ...]
    receipt_ids: tuple[str, ...]
    matched_count: int
    query_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def query_chromatin_architecture(
    cases: tuple[ChromatinArchitectureCase, ...],
    evaluation: ChromatinArchitectureEvaluation,
    query: ChromatinArchitectureQuery,
) -> ChromatinArchitectureQueryResult:
    receipts = {item.case_id: item for item in evaluation.receipts}
    selected: list[str] = []
    for case in cases:
        receipt = receipts.get(case.case_id)
        if receipt is None:
            continue
        if query.operation is not None and case.operation is not query.operation:
            continue
        if query.state is not None and receipt.observed_state is not query.state:
            continue
        if query.scenario is not None and case.scenario.value != query.scenario:
            continue
        if query.family is not None and case.family.value != query.family:
            continue
        selected.append(case.case_id)
    body = {"case_ids": tuple(selected), "query": query}
    return ChromatinArchitectureQueryResult(
        tuple(selected), tuple(selected), len(selected), addressed(body, "chromatin-query")
    )


def chromatin_cases_for_operation(
    cases: tuple[ChromatinArchitectureCase, ...],
    operation: ChromatinArchitectureOperation,
) -> tuple[ChromatinArchitectureCase, ...]:
    return tuple(case for case in cases if case.operation is operation)


def chromatin_receipts_for_state(
    evaluation: ChromatinArchitectureEvaluation,
    state: ChromatinArchitectureState,
) -> tuple[str, ...]:
    return tuple(item.case_id for item in evaluation.receipts if item.observed_state is state)


__all__ = [
    "ChromatinArchitectureQuery",
    "ChromatinArchitectureQueryResult",
    "chromatin_cases_for_operation",
    "chromatin_receipts_for_state",
    "query_chromatin_architecture",
]
