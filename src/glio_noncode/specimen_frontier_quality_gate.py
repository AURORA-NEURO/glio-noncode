"""Cross-surface quality gate for Domain 03 C01-C04."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .specimen_frontier_contracts import default_specimen_frontier_contract_registry
from .specimen_frontier_fixture_eval import evaluate_specimen_frontier_fixture
from .specimen_frontier_lineage import (
    audit_specimen_frontier_lineage,
    build_specimen_frontier_lineage,
)
from .specimen_frontier_public_data import (
    SPECIMEN_FRONTIER_CONTROL_FLOOR,
    SPECIMEN_FRONTIER_OPERATION_FLOOR,
    SpecimenFrontierFixtureCatalog,
    SpecimenFrontierFixtureState,
    SpecimenFrontierOperation,
    audit_specimen_frontier_fixture,
)
from .specimen_frontier_replay import (
    SpecimenFrontierReplayCase,
    SpecimenFrontierReplayExpectation,
    SpecimenFrontierReplayReport,
)
from .specimen_frontier_scenario_matrix import evaluate_specimen_frontier_scenarios


@dataclass(frozen=True, slots=True)
class SpecimenFrontierQualityCheck:
    """One named quality-gate assertion."""

    check_id: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenFrontierQualityGateReport:
    """Reconciled C01-C04 quality result."""

    fixture_id: str
    context_key: str
    state: SpecimenFrontierFixtureState
    checks: tuple[SpecimenFrontierQualityCheck, ...]
    evaluation_address: str
    replay_address: str
    scenario_address: str
    lineage_address: str
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == SpecimenFrontierFixtureState.ACCEPTED and all(
            check.passed for check in self.checks
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed": self.passed,
            "check_count": len(self.checks),
            "failed_check_ids": tuple(check.check_id for check in self.checks if not check.passed),
        }


def evaluate_specimen_frontier_quality_gate(
    fixture: SpecimenFrontierFixtureCatalog | str,
) -> SpecimenFrontierQualityGateReport:
    """Reconcile data, execution, replay, scenarios, contracts, and lineage."""

    catalog = (
        SpecimenFrontierFixtureCatalog.from_file(fixture) if isinstance(fixture, str) else fixture
    )
    audit = audit_specimen_frontier_fixture(catalog)
    evaluation = evaluate_specimen_frontier_fixture(catalog)
    expectation = SpecimenFrontierReplayExpectation(
        fixture_id=catalog.fixture_id,
        context_key=catalog.context_key,
        source_ids=catalog.source_ids,
        minimum_checks=40,
        minimum_positive_records=SPECIMEN_FRONTIER_OPERATION_FLOOR,
        minimum_control_records=SPECIMEN_FRONTIER_CONTROL_FLOOR,
    )
    replay = _replay_catalog(catalog, expectation)
    scenarios = evaluate_specimen_frontier_scenarios(catalog)
    contracts = default_specimen_frontier_contract_registry()
    lineage = build_specimen_frontier_lineage(catalog, evaluation=evaluation)
    lineage_audit = audit_specimen_frontier_lineage(lineage)
    checks = (
        SpecimenFrontierQualityCheck(
            "data-audit",
            audit.accepted,
            f"data audit state={audit.state.value}",
        ),
        SpecimenFrontierQualityCheck(
            "fixture-evaluation",
            evaluation.passed,
            f"fixture checks={len(evaluation.checks)}",
        ),
        SpecimenFrontierQualityCheck(
            "check-floor",
            len(evaluation.checks) >= 40,
            f"check count={len(evaluation.checks)}",
        ),
        SpecimenFrontierQualityCheck(
            "replay",
            replay.passed,
            f"replay cases={len(replay.cases)}",
        ),
        SpecimenFrontierQualityCheck(
            "scenarios",
            scenarios.passed,
            f"scenario count={len(scenarios.scenarios)}",
        ),
        SpecimenFrontierQualityCheck(
            "positive-floor",
            len(catalog.positives) >= SPECIMEN_FRONTIER_OPERATION_FLOOR,
            f"positive count={len(catalog.positives)}",
        ),
        SpecimenFrontierQualityCheck(
            "control-floor",
            len(catalog.controls) >= SPECIMEN_FRONTIER_CONTROL_FLOOR,
            f"control count={len(catalog.controls)}",
        ),
        SpecimenFrontierQualityCheck(
            "operation-coverage",
            set(catalog.operation_ids) == {item.value for item in SpecimenFrontierOperation},
            f"operations={catalog.operation_ids}",
        ),
        SpecimenFrontierQualityCheck(
            "contract-floor",
            len(contracts.contracts) == 4
            and set(item.operation.value for item in contracts.contracts)
            == set(catalog.operation_ids),
            f"contract count={len(contracts.contracts)}",
        ),
        SpecimenFrontierQualityCheck(
            "context-agreement",
            catalog.context_key == evaluation.context_key == lineage.context_key
            and all(
                record.context_key == catalog.context_key
                for record in catalog.positives + catalog.controls
            ),
            "catalog, records, evaluation, and lineage contexts agree",
        ),
        SpecimenFrontierQualityCheck(
            "source-agreement",
            audit.source_ids == catalog.source_ids == lineage.source_ids,
            "source IDs agree across catalog, audit, and lineage",
        ),
        SpecimenFrontierQualityCheck(
            "deterministic-evaluation",
            evaluation.content_address
            == evaluate_specimen_frontier_fixture(catalog).content_address,
            "evaluation address is stable",
        ),
        SpecimenFrontierQualityCheck(
            "fixture-identity",
            bool(catalog.fixture_id) and catalog.content_address.startswith("sha256:"),
            "fixture identity and address are present",
        ),
        SpecimenFrontierQualityCheck(
            "aggregate-scope",
            catalog.aggregate_only and all(source.aggregate_only for source in catalog.sources),
            "fixture and sources are aggregate",
        ),
        SpecimenFrontierQualityCheck(
            "address-floor",
            len(evaluation.receipts) == 12
            and all(
                receipt.output_address.startswith("sha256:") for receipt in evaluation.receipts
            ),
            "all operation receipts are addressed",
        ),
        SpecimenFrontierQualityCheck(
            "contract-state-coverage",
            _contract_states_match(evaluation, contracts),
            "observed states fit declared operation contracts",
        ),
        SpecimenFrontierQualityCheck(
            "sanitized-boundary",
            _sanitized_evaluation(evaluation),
            "evaluation output excludes raw payload markers",
        ),
        SpecimenFrontierQualityCheck(
            "receipt-identity",
            len(evaluation.receipts)
            == len({receipt.record_id for receipt in evaluation.receipts})
            == 12,
            "receipt IDs are unique and complete",
        ),
        SpecimenFrontierQualityCheck(
            "issue-control-coverage",
            _issue_controls_match(catalog, evaluation),
            "fixture issue controls match their declared review codes",
        ),
        SpecimenFrontierQualityCheck(
            "lineage-audit",
            lineage_audit.passed,
            f"lineage issues={lineage_audit.issue_codes}",
        ),
        SpecimenFrontierQualityCheck(
            "lineage-shape",
            len(lineage.nodes) == 29 and len(lineage.edges) == 36,
            f"lineage nodes={len(lineage.nodes)} edges={len(lineage.edges)}",
        ),
    )
    state = (
        SpecimenFrontierFixtureState.ACCEPTED
        if all(check.passed for check in checks)
        else SpecimenFrontierFixtureState.REVIEW
    )
    body = {
        "fixture_id": catalog.fixture_id,
        "context_key": catalog.context_key,
        "state": state,
        "checks": checks,
        "evaluation_address": evaluation.content_address,
        "replay_address": replay.content_address,
        "scenario_address": scenarios.content_address,
        "lineage_address": lineage.content_address,
    }
    return SpecimenFrontierQualityGateReport(
        fixture_id=catalog.fixture_id,
        context_key=catalog.context_key,
        state=state,
        checks=checks,
        evaluation_address=evaluation.content_address,
        replay_address=replay.content_address,
        scenario_address=scenarios.content_address,
        lineage_address=lineage.content_address,
        content_address=content_hash(body),
    )


def _replay_catalog(
    catalog: SpecimenFrontierFixtureCatalog,
    expectation: SpecimenFrontierReplayExpectation,
) -> SpecimenFrontierReplayReport:
    evaluation = evaluate_specimen_frontier_fixture(catalog)
    issues: set[str] = set()
    if catalog.fixture_id != expectation.fixture_id:
        issues.add("fixture_id_mismatch")
    if catalog.context_key != expectation.context_key:
        issues.add("context_mismatch")
    if catalog.source_ids != tuple(sorted(expectation.source_ids)):
        issues.add("source_set_mismatch")
    if len(evaluation.checks) < expectation.minimum_checks:
        issues.add("check_floor")
    if len(catalog.positives) < expectation.minimum_positive_records:
        issues.add("positive_floor")
    if len(catalog.controls) < expectation.minimum_control_records:
        issues.add("control_floor")
    addresses = [receipt.output_address for receipt in evaluation.receipts]
    if len(addresses) != len(set(addresses)):
        issues.add("duplicate_output_address")
    if len(catalog.record_ids) != len(set(catalog.record_ids)):
        issues.add("duplicate_record_id")
    if not evaluation.passed:
        issues.add("evaluation_failed")
    case = SpecimenFrontierReplayCase(
        path="<in-memory>",
        fixture_id=catalog.fixture_id,
        context_key=catalog.context_key,
        source_ids=catalog.source_ids,
        check_count=len(evaluation.checks),
        positive_count=len(catalog.positives),
        control_count=len(catalog.controls),
        evaluation_address=evaluation.content_address,
        passed=not issues,
        issue_codes=tuple(sorted(issues)),
    )
    body = {
        "fixture_id": expectation.fixture_id,
        "required_context_key": expectation.context_key,
        "cases": (case,),
        "passed": not issues,
    }
    return SpecimenFrontierReplayReport(
        fixture_id=expectation.fixture_id,
        required_context_key=expectation.context_key,
        cases=(case,),
        passed=not issues,
        content_address=content_hash(body),
    )


def _contract_states_match(evaluation: Any, contracts: Any) -> bool:
    for receipt in evaluation.receipts:
        contract = contracts.get(receipt.operation)
        if receipt.expected_state == SpecimenFrontierFixtureState.ACCEPTED:
            if not contract.accepts(receipt.observed_result_state):
                return False
        elif not (
            contract.accepts(receipt.observed_result_state)
            or contract.reviews(receipt.observed_result_state)
        ):
            return False
    return True


def _issue_controls_match(catalog: Any, evaluation: Any) -> bool:
    expected_by_id = {
        record.record_id: tuple(
            sorted(str(item) for item in record.parameters.get("required_issue_codes", ()))
        )
        for record in catalog.positives + catalog.controls
    }
    return all(
        receipt.issue_codes == expected_by_id.get(receipt.record_id, ())
        for receipt in evaluation.receipts
    )


def _sanitized_evaluation(evaluation: Any) -> bool:
    serialized = json.dumps(evaluation.to_dict(), sort_keys=True)
    return all(
        marker not in serialized
        for marker in ("raw_record", "patient_id", "subject_id", "medical_record_number")
    )


__all__ = [
    "SpecimenFrontierQualityCheck",
    "SpecimenFrontierQualityGateReport",
    "evaluate_specimen_frontier_quality_gate",
]
