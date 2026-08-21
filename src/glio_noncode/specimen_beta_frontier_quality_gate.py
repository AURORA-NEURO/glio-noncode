"""Composite quality gate for the specimen beta frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .specimen_beta_frontier_contracts import default_specimen_beta_frontier_contracts
from .specimen_beta_frontier_fixture_eval import evaluate_specimen_beta_frontier_fixture
from .specimen_beta_frontier_public_data import (
    SPECIMEN_BETA_FRONTIER_CONTROL_FLOOR,
    SPECIMEN_BETA_FRONTIER_OPERATION_FLOOR,
    SpecimenBetaFrontierFixtureCatalog,
    SpecimenBetaFrontierFixtureState,
    SpecimenBetaFrontierOperation,
    audit_specimen_beta_frontier_fixture,
)
from .specimen_beta_frontier_replay import SpecimenBetaFrontierReplayExpectation
from .specimen_beta_frontier_scenario_matrix import evaluate_specimen_beta_frontier_scenarios


@dataclass(frozen=True, slots=True)
class SpecimenBetaFrontierQualityCheck:
    """One release-level quality assertion."""

    check_id: str
    passed: bool
    observed: Any
    expected: Any
    message: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenBetaFrontierQualityGateReport:
    """All quality assertions and their deterministic addresses."""

    fixture_id: str
    state: str
    checks: tuple[SpecimenBetaFrontierQualityCheck, ...]
    positive_count: int
    control_count: int
    operation_count: int
    evaluation_address: str
    scenario_address: str
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


class SpecimenBetaFrontierQualityGate:
    """Combine source, execution, replay, scenario, contract, and lineage checks."""

    def evaluate(
        self,
        catalog: SpecimenBetaFrontierFixtureCatalog,
    ) -> SpecimenBetaFrontierQualityGateReport:
        audit = audit_specimen_beta_frontier_fixture(catalog)
        evaluation = evaluate_specimen_beta_frontier_fixture(catalog)
        second_evaluation = evaluate_specimen_beta_frontier_fixture(catalog)
        scenarios = evaluate_specimen_beta_frontier_scenarios(catalog)
        contracts = default_specimen_beta_frontier_contracts()
        expectation = SpecimenBetaFrontierReplayExpectation(
            fixture_id=catalog.fixture_id,
            context_key=catalog.context_key,
            source_ids=catalog.source_ids,
            minimum_checks=72,
            minimum_positive_records=SPECIMEN_BETA_FRONTIER_OPERATION_FLOOR,
            minimum_control_records=SPECIMEN_BETA_FRONTIER_CONTROL_FLOOR,
        )
        from .specimen_beta_frontier_lineage import (
            audit_specimen_beta_frontier_lineage,
            build_specimen_beta_frontier_lineage,
        )

        lineage = build_specimen_beta_frontier_lineage(catalog)
        lineage_audit = audit_specimen_beta_frontier_lineage(lineage)
        checks = (
            _check("data-audit", audit.accepted, audit.issue_codes, ()),
            _check("fixture-evaluation", evaluation.passed, evaluation.failed_check_ids, ()),
            _check(
                "check-floor",
                len(evaluation.checks) >= expectation.minimum_checks,
                len(evaluation.checks),
                72,
            ),
            _check(
                "replay-identity",
                catalog.fixture_id == expectation.fixture_id,
                catalog.fixture_id,
                expectation.fixture_id,
            ),
            _check("scenario-matrix", scenarios.passed, scenarios.passed, True),
            _check(
                "positive-floor",
                len(catalog.positives) >= expectation.minimum_positive_records,
                len(catalog.positives),
                4,
            ),
            _check(
                "control-floor",
                len(catalog.controls) >= expectation.minimum_control_records,
                len(catalog.controls),
                8,
            ),
            _check(
                "operation-coverage",
                set(catalog.operation_ids)
                == {item.value for item in SpecimenBetaFrontierOperation},
                catalog.operation_ids,
                tuple(item.value for item in SpecimenBetaFrontierOperation),
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
                bool(catalog.fixture_id and catalog.content_address.startswith("sha256:")),
                True,
                True,
            ),
            _check(
                "aggregate-scope",
                catalog.aggregate_only and all(source.aggregate_only for source in catalog.sources),
                True,
                True,
            ),
            _check(
                "address-floor",
                len(evaluation.receipts) == 12
                and all(
                    receipt.output_address.startswith("sha256:") for receipt in evaluation.receipts
                ),
                len(evaluation.receipts),
                12,
            ),
            _check(
                "contract-state-coverage", _contract_states_covered(catalog, contracts), True, True
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
            _check(
                "receipt-identity",
                len({receipt.record_id for receipt in evaluation.receipts}) == 12,
                12,
                12,
            ),
            _check(
                "issue-control-coverage",
                all(
                    record.expected_fixture_state == SpecimenBetaFrontierFixtureState.REVIEW
                    for record in catalog.controls
                ),
                True,
                True,
            ),
            _check("lineage-audit", lineage_audit.passed, lineage_audit.issue_codes, ()),
            _check(
                "lineage-shape",
                len(lineage.nodes) == 29 and len(lineage.edges) == 36,
                (len(lineage.nodes), len(lineage.edges)),
                (29, 36),
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
        }
        return SpecimenBetaFrontierQualityGateReport(
            fixture_id=catalog.fixture_id,
            state=state,
            checks=checks,
            positive_count=len(catalog.positives),
            control_count=len(catalog.controls),
            operation_count=len(catalog.operation_ids),
            evaluation_address=evaluation.content_address,
            scenario_address=scenarios.content_address,
            content_address=content_hash(body),
        )


def _contract_states_covered(catalog: SpecimenBetaFrontierFixtureCatalog, contracts: Any) -> bool:
    return all(
        contracts.get(record.operation).accepts_result_state(record.expected_result_state)
        for record in catalog.records
    )


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    expected: Any,
) -> SpecimenBetaFrontierQualityCheck:
    return SpecimenBetaFrontierQualityCheck(
        check_id=check_id,
        passed=bool(passed),
        observed=observed,
        expected=expected,
        message="passed" if passed else f"{check_id} failed",
    )


def evaluate_specimen_beta_frontier_quality_gate(
    catalog: SpecimenBetaFrontierFixtureCatalog,
) -> SpecimenBetaFrontierQualityGateReport:
    """Convenience entry point for release commands."""

    return SpecimenBetaFrontierQualityGate().evaluate(catalog)


__all__ = [
    "SpecimenBetaFrontierQualityCheck",
    "SpecimenBetaFrontierQualityGate",
    "SpecimenBetaFrontierQualityGateReport",
    "evaluate_specimen_beta_frontier_quality_gate",
]
