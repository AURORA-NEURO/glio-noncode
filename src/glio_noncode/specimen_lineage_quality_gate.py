"""Composite release quality gate for Domain 03 C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .specimen_lineage_contracts import default_specimen_lineage_contracts
from .specimen_lineage_fixture_eval import evaluate_specimen_lineage_fixture
from .specimen_lineage_lineage import (
    audit_specimen_lineage_lineage,
    build_specimen_lineage_lineage,
)
from .specimen_lineage_public_data import (
    SPECIMEN_LINEAGE_CONTROL_FLOOR,
    SPECIMEN_LINEAGE_OPERATION_FLOOR,
    SpecimenLineageFixtureCatalog,
    SpecimenLineageFixtureState,
    SpecimenLineageOperation,
    audit_specimen_lineage_fixture,
)
from .specimen_lineage_reconciliation import (
    audit_specimen_lineage_receipt_index,
    build_specimen_lineage_receipt_index,
)
from .specimen_lineage_scenario_matrix import evaluate_specimen_lineage_scenarios


@dataclass(frozen=True, slots=True)
class SpecimenLineageQualityCheck:
    """One cross-surface release assertion."""

    check_id: str
    passed: bool
    observed: Any
    expected: Any
    message: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenLineageQualityGateReport:
    """All release assertions and their stable addresses."""

    fixture_id: str
    state: str
    checks: tuple[SpecimenLineageQualityCheck, ...]
    positive_count: int
    control_count: int
    operation_count: int
    evaluation_address: str
    scenario_address: str
    lineage_address: str
    receipt_index_address: str
    receipt_reconciliation_address: str
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == "accepted" and all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed": self.passed,
            "failed_check_ids": self.failed_check_ids,
        }


class SpecimenLineageQualityGate:
    """Reconcile source, execution, replay-like, scenario, and graph evidence."""

    def evaluate(
        self,
        catalog: SpecimenLineageFixtureCatalog,
    ) -> SpecimenLineageQualityGateReport:
        audit = audit_specimen_lineage_fixture(catalog)
        evaluation = evaluate_specimen_lineage_fixture(catalog)
        second_evaluation = evaluate_specimen_lineage_fixture(catalog)
        scenarios = evaluate_specimen_lineage_scenarios(catalog)
        contracts = default_specimen_lineage_contracts()
        graph = build_specimen_lineage_lineage(catalog)
        graph_audit = audit_specimen_lineage_lineage(graph)
        receipt_index = build_specimen_lineage_receipt_index(catalog)
        receipt_reconciliation = audit_specimen_lineage_receipt_index(catalog, receipt_index)
        expected_minimum_checks = 159
        checks = (
            _check("data-audit", audit.accepted, audit.issue_codes, ()),
            _check("fixture-evaluation", evaluation.passed, evaluation.failed_check_ids, ()),
            _check(
                "check-floor",
                len(evaluation.checks) >= expected_minimum_checks,
                len(evaluation.checks),
                expected_minimum_checks,
            ),
            _check("scenario-matrix", scenarios.passed, scenarios.passed, True),
            _check(
                "positive-floor",
                len(catalog.positives) >= SPECIMEN_LINEAGE_OPERATION_FLOOR,
                len(catalog.positives),
                SPECIMEN_LINEAGE_OPERATION_FLOOR,
            ),
            _check(
                "control-floor",
                len(catalog.controls) >= SPECIMEN_LINEAGE_CONTROL_FLOOR,
                len(catalog.controls),
                SPECIMEN_LINEAGE_CONTROL_FLOOR,
            ),
            _check(
                "operation-coverage",
                set(catalog.operation_ids) == {item.value for item in SpecimenLineageOperation},
                catalog.operation_ids,
                tuple(item.value for item in SpecimenLineageOperation),
            ),
            _check("contract-floor", len(contracts.contracts) == 4, len(contracts.contracts), 4),
            _check(
                "context-agreement",
                all(record.context_key == catalog.context_key for record in catalog.records),
                True,
                True,
            ),
            _check(
                "source-agreement",
                all(
                    set(record.source_ids).issubset(set(catalog.source_ids))
                    for record in catalog.records
                ),
                True,
                True,
            ),
            _check(
                "deterministic-evaluation",
                evaluation.content_address == second_evaluation.content_address,
                evaluation.content_address,
                second_evaluation.content_address,
            ),
            _check(
                "fixture-identity",
                catalog.fixture_id.startswith("specimen-lineage-")
                and catalog.content_address.startswith("sha256:"),
                catalog.fixture_id,
                "specimen-lineage-* with sha256 address",
            ),
            _check(
                "aggregate-scope",
                catalog.aggregate_only and all(source.aggregate_only for source in catalog.sources),
                True,
                True,
            ),
            _check(
                "receipt-identity",
                len(evaluation.receipts) == len(catalog.records)
                and len({receipt.record_id for receipt in evaluation.receipts})
                == len(catalog.records),
                len(evaluation.receipts),
                len(catalog.records),
            ),
            _check(
                "positive-role",
                all(
                    record.expected_fixture_state == SpecimenLineageFixtureState.ACCEPTED
                    for record in catalog.positives
                ),
                True,
                True,
            ),
            _check(
                "control-role",
                all(
                    record.expected_fixture_state == SpecimenLineageFixtureState.REVIEW
                    for record in catalog.controls
                ),
                True,
                True,
            ),
            _check(
                "control-state-coverage",
                _contract_states_covered(catalog, contracts),
                True,
                True,
            ),
            _check(
                "sanitized-boundary",
                all(
                    check.check_id.endswith("sanitized-output")
                    and check.passed
                    or not check.check_id.endswith("sanitized-output")
                    for check in evaluation.checks
                ),
                True,
                True,
            ),
            _check("lineage-audit", graph_audit.passed, graph_audit.issue_codes, ()),
            _check(
                "receipt-reconciliation",
                receipt_reconciliation.passed,
                receipt_reconciliation.failed_check_ids,
                (),
            ),
            _check(
                "lineage-shape",
                len(graph.nodes) == 29 and len(graph.edges) == 28,
                (len(graph.nodes), len(graph.edges)),
                (29, 28),
            ),
            _check(
                "lineage-address",
                graph.content_address.startswith("sha256:"),
                graph.content_address,
                "sha256:<digest>",
            ),
        )
        state = "accepted" if all(check.passed for check in checks) else "review"
        body = {
            "fixture_id": catalog.fixture_id,
            "state": state,
            "checks": checks,
            "positive_count": len(catalog.positives),
            "control_count": len(catalog.controls),
            "operation_count": len(catalog.operation_ids),
            "evaluation_address": evaluation.content_address,
            "scenario_address": scenarios.content_address,
            "lineage_address": graph.content_address,
            "receipt_index_address": receipt_index.content_address,
            "receipt_reconciliation_address": receipt_reconciliation.content_address,
        }
        return SpecimenLineageQualityGateReport(
            fixture_id=catalog.fixture_id,
            state=state,
            checks=checks,
            positive_count=len(catalog.positives),
            control_count=len(catalog.controls),
            operation_count=len(catalog.operation_ids),
            evaluation_address=evaluation.content_address,
            scenario_address=scenarios.content_address,
            lineage_address=graph.content_address,
            receipt_index_address=receipt_index.content_address,
            receipt_reconciliation_address=receipt_reconciliation.content_address,
            content_address=content_hash(body),
        )


def _contract_states_covered(catalog: SpecimenLineageFixtureCatalog, contracts: Any) -> bool:
    return all(
        contracts.get(record.operation).accepts_result_state(record.expected_result_state)
        for record in catalog.records
    )


def _check(
    check_id: str, passed: bool, observed: Any, expected: Any
) -> SpecimenLineageQualityCheck:
    return SpecimenLineageQualityCheck(
        check_id=check_id,
        passed=bool(passed),
        observed=observed,
        expected=expected,
        message=f"{check_id} release assertion",
    )


def evaluate_specimen_lineage_quality_gate(
    catalog: SpecimenLineageFixtureCatalog,
) -> SpecimenLineageQualityGateReport:
    """Evaluate the complete release gate."""

    return SpecimenLineageQualityGate().evaluate(catalog)


__all__ = [
    "SpecimenLineageQualityCheck",
    "SpecimenLineageQualityGate",
    "SpecimenLineageQualityGateReport",
    "evaluate_specimen_lineage_quality_gate",
]
