"""Scenario matrix and family/plane summaries for D06."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_architecture_contracts import (
    SequenceArchitectureCase,
    SequenceArchitectureCheck,
    SequenceArchitectureCheckKind,
    SequenceArchitectureEvaluation,
    SequenceArchitectureFixture,
    SequenceArchitectureScenario,
    SequenceArchitectureState,
    addressed,
)
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class SequenceArchitectureScenarioRow:
    case_id: str
    operation_id: str
    family: str
    plane: str
    scenario: SequenceArchitectureScenario
    expected_state: SequenceArchitectureState
    observed_state: SequenceArchitectureState
    expected_result_state: str
    observed_result_state: str
    issue_codes: tuple[str, ...]
    passed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceArchitectureScenarioMatrix:
    fixture_id: str
    rows: tuple[SequenceArchitectureScenarioRow, ...]
    checks: tuple[SequenceArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"row_count": len(self.rows), "check_count": len(self.checks)}


def build_sequence_architecture_scenario_matrix(
    fixture: SequenceArchitectureFixture, evaluation: SequenceArchitectureEvaluation
) -> SequenceArchitectureScenarioMatrix:
    cases = {item.case_id: item for item in fixture.cases}
    operations = {item.operation_id: item for item in fixture.operations}
    rows = tuple(
        _row(cases[item.case_id], operations[item.operation_id], item)
        for item in evaluation.receipts
    )
    checks = (
        _check(
            "scenario-row-count", len(rows) == 64, len(rows), 64, "all receipts have scenario rows"
        ),
        _check(
            "scenario-case-join",
            {item.case_id for item in rows} == set(cases),
            len({item.case_id for item in rows}),
            64,
            "scenario rows join cases",
        ),
        _check(
            "scenario-operation-join",
            {item.operation_id for item in rows} == set(operations),
            len({item.operation_id for item in rows}),
            16,
            "scenario rows join operations",
        ),
        _check(
            "scenario-positive-balance",
            sum(item.scenario is SequenceArchitectureScenario.POSITIVE for item in rows) == 16,
            sum(item.scenario is SequenceArchitectureScenario.POSITIVE for item in rows),
            16,
            "one positive path per operation",
        ),
        _check(
            "scenario-control-balance",
            sum(item.scenario is not SequenceArchitectureScenario.POSITIVE for item in rows) == 48,
            sum(item.scenario is not SequenceArchitectureScenario.POSITIVE for item in rows),
            48,
            "three controls per operation",
        ),
        _check(
            "scenario-receipt-pass",
            all(item.passed for item in rows),
            sum(item.passed for item in rows),
            64,
            "every scenario receipt passes",
        ),
        _check(
            "scenario-addresses",
            all(item.content_address.startswith("sha256:") for item in rows),
            sum(item.content_address.startswith("sha256:") for item in rows),
            64,
            "every scenario row is addressed",
        ),
    )
    body = {"fixture_id": fixture.fixture_id, "rows": rows, "checks": checks}
    return SequenceArchitectureScenarioMatrix(
        fixture_id=fixture.fixture_id,
        rows=rows,
        checks=checks,
        accepted=all(item.passed for item in checks),
        content_address=addressed(body, "sequence-scenario-matrix"),
    )


def sequence_architecture_scenario_summary(
    matrix: SequenceArchitectureScenarioMatrix,
) -> dict[str, Any]:
    def count(predicate: Any) -> int:
        return sum(bool(predicate(item)) for item in matrix.rows)

    return {
        "fixture_id": matrix.fixture_id,
        "accepted": matrix.accepted,
        "scenario_counts": {
            scenario.value: count(lambda item, scenario=scenario: item.scenario is scenario)
            for scenario in SequenceArchitectureScenario
        },
        "state_counts": {
            state.value: count(lambda item, state=state: item.observed_state is state)
            for state in (SequenceArchitectureState.ACCEPTED, SequenceArchitectureState.REVIEW)
        },
        "family_counts": {
            family: count(lambda item, family=family: item.family == family)
            for family in sorted({item.family for item in matrix.rows})
        },
        "plane_counts": {
            plane: count(lambda item, plane=plane: item.plane == plane)
            for plane in sorted({item.plane for item in matrix.rows})
        },
        "failed_case_ids": [item.case_id for item in matrix.rows if not item.passed],
        "content_address": addressed(matrix.to_dict(), "sequence-scenario-summary"),
    }


def _row(
    case: SequenceArchitectureCase, operation: Any, receipt: Any
) -> SequenceArchitectureScenarioRow:
    body = {
        "case_id": case.case_id,
        "operation_id": operation.operation_id,
        "family": operation.family.value,
        "plane": operation.plane.value,
        "scenario": case.scenario,
        "expected_state": receipt.expected_state,
        "observed_state": receipt.observed_state,
        "expected_result_state": receipt.expected_result_state,
        "observed_result_state": receipt.observed_result_state,
        "issue_codes": receipt.observed_issue_codes,
        "passed": receipt.passed,
    }
    return SequenceArchitectureScenarioRow(
        **body, content_address=addressed(body, "sequence-scenario-row")
    )


def _check(
    check_id: str, passed: bool, observed: Any, required: Any, detail: str
) -> SequenceArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": SequenceArchitectureCheckKind.OPERATION,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return SequenceArchitectureCheck(
        check_id=check_id,
        kind=SequenceArchitectureCheckKind.OPERATION,
        passed=passed,
        observed=observed,
        required=required,
        detail=detail,
        content_address=addressed(body, "sequence-scenario-check"),
    )


__all__ = [
    "SequenceArchitectureScenarioMatrix",
    "SequenceArchitectureScenarioRow",
    "build_sequence_architecture_scenario_matrix",
    "sequence_architecture_scenario_summary",
]
