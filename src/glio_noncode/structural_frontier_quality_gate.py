"""Cross-surface quality gate for Domain 02 C13-C16."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .structural_frontier_contracts import default_structural_frontier_contract_registry
from .structural_frontier_fixture_eval import evaluate_structural_frontier_fixture
from .structural_frontier_lineage import (
    audit_structural_frontier_lineage,
    build_structural_frontier_lineage,
)
from .structural_frontier_public_data import (
    STRUCTURAL_FRONTIER_CONTROL_FLOOR,
    STRUCTURAL_FRONTIER_OPERATION_FLOOR,
    StructuralFrontierFixtureCatalog,
    StructuralFrontierFixtureState,
    StructuralFrontierOperation,
    audit_structural_frontier_fixture,
)
from .structural_frontier_replay import (
    StructuralFrontierReplayCase,
    StructuralFrontierReplayExpectation,
    StructuralFrontierReplayReport,
)
from .structural_frontier_scenario_matrix import evaluate_structural_frontier_scenarios


@dataclass(frozen=True, slots=True)
class StructuralFrontierQualityCheck:
    """One named quality-gate assertion."""

    check_id: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralFrontierQualityGateReport:
    """Reconciled C13-C16 quality result."""

    fixture_id: str
    context_key: str
    state: StructuralFrontierFixtureState
    checks: tuple[StructuralFrontierQualityCheck, ...]
    evaluation_address: str
    replay_address: str
    scenario_address: str
    lineage_address: str
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == StructuralFrontierFixtureState.ACCEPTED and all(
            check.passed for check in self.checks
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed": self.passed,
            "check_count": len(self.checks),
            "failed_check_ids": tuple(check.check_id for check in self.checks if not check.passed),
        }


def evaluate_structural_frontier_quality_gate(
    fixture: StructuralFrontierFixtureCatalog | str,
) -> StructuralFrontierQualityGateReport:
    """Reconcile data, execution, replay, scenarios, contracts, and lineage."""

    catalog = StructuralFrontierFixtureCatalog.from_file(fixture) if isinstance(fixture, str) else fixture
    audit = audit_structural_frontier_fixture(catalog)
    evaluation = evaluate_structural_frontier_fixture(catalog)
    expectation = StructuralFrontierReplayExpectation(
        fixture_id=catalog.fixture_id,
        context_key=catalog.context_key,
        source_ids=catalog.source_ids,
        minimum_checks=40,
        minimum_positive_records=STRUCTURAL_FRONTIER_OPERATION_FLOOR,
        minimum_control_records=STRUCTURAL_FRONTIER_CONTROL_FLOOR,
    )
    replay = _replay_catalog(catalog, expectation)
    scenarios = evaluate_structural_frontier_scenarios(catalog)
    contracts = default_structural_frontier_contract_registry()
    lineage = build_structural_frontier_lineage(catalog, evaluation=evaluation)
    lineage_audit = audit_structural_frontier_lineage(lineage)
    checks = (
        StructuralFrontierQualityCheck("data-audit", audit.accepted, f"data audit state={audit.state.value}"),
        StructuralFrontierQualityCheck("fixture-evaluation", evaluation.passed, f"fixture checks={len(evaluation.checks)}"),
        StructuralFrontierQualityCheck("check-floor", len(evaluation.checks) >= 40, f"check count={len(evaluation.checks)}"),
        StructuralFrontierQualityCheck("replay", replay.passed, f"replay cases={len(replay.cases)}"),
        StructuralFrontierQualityCheck("scenarios", scenarios.passed, f"scenario count={len(scenarios.scenarios)}"),
        StructuralFrontierQualityCheck("positive-floor", len(catalog.positives) >= STRUCTURAL_FRONTIER_OPERATION_FLOOR, f"positive count={len(catalog.positives)}"),
        StructuralFrontierQualityCheck("control-floor", len(catalog.controls) >= STRUCTURAL_FRONTIER_CONTROL_FLOOR, f"control count={len(catalog.controls)}"),
        StructuralFrontierQualityCheck("operation-coverage", set(catalog.operation_ids) == {item.value for item in StructuralFrontierOperation}, f"operations={catalog.operation_ids}"),
        StructuralFrontierQualityCheck("contract-floor", len(contracts.contracts) == 4 and set(item.operation.value for item in contracts.contracts) == set(catalog.operation_ids), f"contract count={len(contracts.contracts)}"),
        StructuralFrontierQualityCheck(
            "context-agreement",
            catalog.context_key == evaluation.context_key == audit.context_key == lineage.context_key
            and all(
                record.context_key == catalog.context_key
                for record in catalog.positives + catalog.controls
            ),
            "catalog, records, evaluation, audit, and lineage contexts agree",
        ),
        StructuralFrontierQualityCheck("source-agreement", audit.source_ids == catalog.source_ids == lineage.source_ids, "source IDs agree across catalog, audit, and lineage"),
        StructuralFrontierQualityCheck("deterministic-evaluation", evaluation.content_address == evaluate_structural_frontier_fixture(catalog).content_address, "evaluation address is stable"),
        StructuralFrontierQualityCheck("fixture-identity", bool(catalog.fixture_id) and catalog.content_address.startswith("sha256:"), "fixture identity and address are present"),
        StructuralFrontierQualityCheck("aggregate-scope", not catalog.patient_level and all(not source.patient_level for source in catalog.sources), "fixture and sources are aggregate"),
        StructuralFrontierQualityCheck("address-floor", len(evaluation.receipts) == 12 and all(receipt.output_address.startswith("sha256:") for receipt in evaluation.receipts), "all operation receipts are addressed"),
        StructuralFrontierQualityCheck("contract-state-coverage", _contract_states_match(catalog, evaluation, contracts), "observed states fit declared operation contracts"),
        StructuralFrontierQualityCheck("sanitized-boundary", _sanitized_evaluation(evaluation), "evaluation output excludes raw payload markers"),
        StructuralFrontierQualityCheck("receipt-identity", len(evaluation.receipts) == len({receipt.record_id for receipt in evaluation.receipts}) == 12, "receipt IDs are unique and complete"),
        StructuralFrontierQualityCheck("lineage-audit", lineage_audit.passed, f"lineage issues={lineage_audit.issue_codes}"),
        StructuralFrontierQualityCheck("lineage-shape", len(lineage.nodes) == 29 and len(lineage.edges) == 36, f"lineage nodes={len(lineage.nodes)} edges={len(lineage.edges)}"),
    )
    state = StructuralFrontierFixtureState.ACCEPTED if all(check.passed for check in checks) else StructuralFrontierFixtureState.REVIEW
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
    return StructuralFrontierQualityGateReport(
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
    catalog: StructuralFrontierFixtureCatalog,
    expectation: StructuralFrontierReplayExpectation,
):
    """Replay an in-memory catalog without requiring a temporary file."""

    evaluation = evaluate_structural_frontier_fixture(catalog)
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
    case = StructuralFrontierReplayCase(
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
    body = {"fixture_id": expectation.fixture_id, "required_context_key": expectation.context_key, "cases": (case,), "passed": not issues}
    return StructuralFrontierReplayReport(expectation.fixture_id, expectation.context_key, (case,), not issues, content_hash(body))


def _contract_states_match(catalog, evaluation, contracts) -> bool:
    for receipt in evaluation.receipts:
        contract = contracts.get(receipt.operation)
        if receipt.expected_state == StructuralFrontierFixtureState.ACCEPTED:
            if not contract.accepts(receipt.observed_result_state):
                return False
        elif not (contract.accepts(receipt.observed_result_state) or contract.reviews(receipt.observed_result_state)):
            return False
    return True


def _sanitized_evaluation(evaluation) -> bool:
    serialized = json.dumps(evaluation.to_dict(), sort_keys=True)
    return all(marker not in serialized for marker in ("raw_record", "patient_id", "subject_id", "sequence"))


__all__ = [
    "StructuralFrontierQualityCheck",
    "StructuralFrontierQualityGateReport",
    "evaluate_structural_frontier_quality_gate",
]
