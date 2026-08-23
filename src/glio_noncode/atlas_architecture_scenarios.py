"""Scenario-matrix diagnostics for D05 positive and control behavior."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .atlas_architecture_contracts import (
    AtlasArchitectureCase,
    AtlasArchitectureCheck,
    AtlasArchitectureCheckKind,
    AtlasArchitectureEvaluation,
    AtlasArchitectureFixture,
    AtlasArchitectureScenario,
    AtlasArchitectureState,
    addressed,
)
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class AtlasArchitectureScenarioRow:
    operation_id: str
    family: str
    plane: str
    scenario: AtlasArchitectureScenario
    case_id: str
    expected_state: AtlasArchitectureState
    observed_state: AtlasArchitectureState
    expected_result_state: str
    observed_result_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    passed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasArchitectureScenarioMatrix:
    fixture_id: str
    rows: tuple[AtlasArchitectureScenarioRow, ...]
    checks: tuple[AtlasArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "row_count": len(self.rows),
            "check_count": len(self.checks),
        }


def build_atlas_architecture_scenario_matrix(
    fixture: AtlasArchitectureFixture,
    evaluation: AtlasArchitectureEvaluation,
) -> AtlasArchitectureScenarioMatrix:
    """Join every case to its operation plane and receipt outcome."""

    operations = {item.operation_id: item for item in fixture.operations}
    cases = {item.case_id: item for item in fixture.cases}
    receipts = {item.case_id: item for item in evaluation.receipts}
    rows = tuple(
        _row(cases[receipt.case_id], operations[receipt.operation_id], receipt)
        for receipt in evaluation.receipts
    )
    checks = (
        _check(
            "scenario-row-cardinality",
            len(rows) == len(fixture.cases),
            len(rows),
            len(fixture.cases),
            "every case has one scenario row",
        ),
        _check(
            "scenario-case-join",
            {item.case_id for item in rows} == set(cases),
            len({item.case_id for item in rows}),
            len(cases),
            "scenario rows join all case identifiers",
        ),
        _check(
            "scenario-receipt-join",
            {item.case_id for item in rows} == set(receipts),
            len({item.case_id for item in rows}),
            len(receipts),
            "scenario rows join all receipt identifiers",
        ),
        _check(
            "scenario-operation-closure",
            {item.operation_id for item in rows}
            == {item.operation_id for item in fixture.operations},
            len({item.operation_id for item in rows}),
            len(fixture.operations),
            "all operations are represented in the scenario matrix",
        ),
        _check(
            "scenario-positive-count",
            sum(item.scenario is AtlasArchitectureScenario.POSITIVE for item in rows)
            == len(fixture.operations),
            sum(item.scenario is AtlasArchitectureScenario.POSITIVE for item in rows),
            len(fixture.operations),
            "each operation has one positive scenario",
        ),
        _check(
            "scenario-control-count",
            sum(item.scenario is not AtlasArchitectureScenario.POSITIVE for item in rows)
            == len(fixture.operations) * 3,
            sum(item.scenario is not AtlasArchitectureScenario.POSITIVE for item in rows),
            len(fixture.operations) * 3,
            "each operation has three held controls",
        ),
        _check(
            "scenario-result-closure",
            all(item.passed for item in rows),
            sum(item.passed for item in rows),
            len(rows),
            "every scenario receipt passes its expected contract",
        ),
        _check(
            "scenario-address-closure",
            all(item.content_address.startswith("sha256:") for item in rows),
            sum(item.content_address.startswith("sha256:") for item in rows),
            len(rows),
            "every scenario row is addressed",
        ),
    )
    body = {"fixture_id": fixture.fixture_id, "rows": rows, "checks": checks}
    return AtlasArchitectureScenarioMatrix(
        fixture_id=fixture.fixture_id,
        rows=rows,
        checks=checks,
        accepted=all(item.passed for item in checks),
        content_address=addressed(body, "atlas-scenario-matrix"),
    )


def atlas_architecture_scenario_summary(
    matrix: AtlasArchitectureScenarioMatrix,
) -> dict[str, Any]:
    """Return counts grouped by scenario, state, family, and plane."""

    def count(predicate: Any) -> int:
        return sum(bool(predicate(item)) for item in matrix.rows)

    return {
        "fixture_id": matrix.fixture_id,
        "accepted": matrix.accepted,
        "row_count": len(matrix.rows),
        "scenario_counts": {
            scenario.value: count(lambda item, scenario=scenario: item.scenario is scenario)
            for scenario in AtlasArchitectureScenario
        },
        "observed_state_counts": {
            state.value: count(lambda item, state=state: item.observed_state is state)
            for state in (AtlasArchitectureState.ACCEPTED, AtlasArchitectureState.REVIEW)
        },
        "family_counts": {
            family: count(lambda item, family=family: item.family == family)
            for family in sorted({item.family for item in matrix.rows})
        },
        "plane_counts": {
            plane: count(lambda item, plane=plane: item.plane == plane)
            for plane in sorted({item.plane for item in matrix.rows})
        },
        "failed_rows": [item.case_id for item in matrix.rows if not item.passed],
        "content_address": addressed(matrix.to_dict(), "atlas-scenario-summary"),
    }


def _row(case: AtlasArchitectureCase, operation: Any, receipt: Any) -> AtlasArchitectureScenarioRow:
    body = {
        "operation_id": operation.operation_id,
        "family": operation.family.value,
        "plane": operation.plane.value,
        "scenario": case.scenario,
        "case_id": case.case_id,
        "expected_state": receipt.expected_state,
        "observed_state": receipt.observed_state,
        "expected_result_state": receipt.expected_result_state,
        "observed_result_state": receipt.observed_result_state,
        "expected_issue_codes": receipt.expected_issue_codes,
        "observed_issue_codes": receipt.observed_issue_codes,
        "passed": receipt.passed,
    }
    return AtlasArchitectureScenarioRow(
        **body, content_address=addressed(body, "atlas-scenario-row")
    )


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> AtlasArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": AtlasArchitectureCheckKind.OPERATION,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return AtlasArchitectureCheck(
        check_id=check_id,
        kind=AtlasArchitectureCheckKind.OPERATION,
        passed=passed,
        observed=observed,
        required=required,
        detail=detail,
        content_address=addressed(body, "atlas-scenario-check"),
    )


__all__ = [
    "AtlasArchitectureScenarioMatrix",
    "AtlasArchitectureScenarioRow",
    "atlas_architecture_scenario_summary",
    "build_atlas_architecture_scenario_matrix",
]
