"""Cross-surface quality gate for Domain 02 C09-C12."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .structural_haplotype_contracts import default_structural_haplotype_contract_registry
from .structural_haplotype_fixture_eval import evaluate_structural_haplotype_fixture
from .structural_haplotype_lineage import (
    audit_structural_haplotype_lineage,
    build_structural_haplotype_lineage,
)
from .structural_haplotype_public_data import (
    STRUCTURAL_HAPLOTYPE_CONTROL_FLOOR,
    STRUCTURAL_HAPLOTYPE_OPERATION_FLOOR,
    StructuralHaplotypeFixtureCatalog,
    StructuralHaplotypeFixtureState,
    StructuralHaplotypeOperation,
    audit_structural_haplotype_fixture,
)
from .structural_haplotype_replay import (
    StructuralHaplotypeReplayCase,
    StructuralHaplotypeReplayExpectation,
    StructuralHaplotypeReplayReport,
)
from .structural_haplotype_scenario_matrix import evaluate_structural_haplotype_scenarios


@dataclass(frozen=True, slots=True)
class StructuralHaplotypeQualityCheck:
    """One named quality assertion with expected and observed values."""

    check_id: str
    passed: bool
    expected: Any
    observed: Any
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralHaplotypeQualityGateReport:
    """Reconciled result across data, execution, replay, scenarios, and contracts."""

    fixture_id: str
    context_key: str
    state: StructuralHaplotypeFixtureState
    checks: tuple[StructuralHaplotypeQualityCheck, ...]
    evaluation_address: str
    replay_address: str
    scenario_address: str
    contract_address: str
    lineage_address: str
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == StructuralHaplotypeFixtureState.ACCEPTED and all(check.passed for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed": self.passed, "check_count": len(self.checks)}


def evaluate_structural_haplotype_quality_gate(
    fixture: StructuralHaplotypeFixtureCatalog | str,
) -> StructuralHaplotypeQualityGateReport:
    """Run and reconcile the complete C09-C12 evidence surface."""

    catalog = StructuralHaplotypeFixtureCatalog.from_file(fixture) if isinstance(fixture, str) else fixture
    audit = audit_structural_haplotype_fixture(catalog)
    evaluation = evaluate_structural_haplotype_fixture(catalog)
    scenarios = evaluate_structural_haplotype_scenarios(catalog)
    contracts = default_structural_haplotype_contract_registry()
    expectation = StructuralHaplotypeReplayExpectation(
        fixture_id=catalog.fixture_id,
        context_key=catalog.context_key,
        source_ids=catalog.source_ids,
        minimum_checks=40,
        minimum_positive_records=STRUCTURAL_HAPLOTYPE_OPERATION_FLOOR,
        minimum_control_records=STRUCTURAL_HAPLOTYPE_CONTROL_FLOOR,
    )
    replay = _replay_catalog(catalog, expectation)
    lineage = build_structural_haplotype_lineage(catalog, evaluation=evaluation)
    lineage_audit = audit_structural_haplotype_lineage(lineage)
    deterministic = _deterministic(catalog)
    contract_states = _contract_states_match(catalog, evaluation, contracts)
    sanitized = _sanitized(evaluation)
    address_floor = all(receipt.output_address.startswith("sha256:") for receipt in evaluation.receipts)
    checks = (
        _check("data-audit", audit.accepted, True, audit.accepted, "public aggregate source and payload boundary"),
        _check("fixture-evaluation", evaluation.passed, True, evaluation.passed, "all C09-C12 positives and controls pass"),
        _check("check-floor", len(evaluation.checks) >= 40, 40, len(evaluation.checks), "fixture assertions are substantial"),
        _check("replay", replay.passed, True, replay.passed, "identity, source, context, and address replay"),
        _check("scenario-matrix", scenarios.passed, True, scenarios.passed, "independent state-transition scenarios"),
        _check("positive-floor", len(catalog.positives) >= 4, 4, len(catalog.positives), "one positive per operation"),
        _check("control-floor", len(catalog.controls) >= 8, 8, len(catalog.controls), "two review controls per operation"),
        _check("operation-coverage", set(catalog.operation_ids) == {item.value for item in StructuralHaplotypeOperation}, [item.value for item in StructuralHaplotypeOperation], list(catalog.operation_ids), "all C09-C12 operations represented"),
        _check("contract-floor", len(contracts.contracts) == 4, 4, len(contracts.contracts), "four typed structural haplotype contracts"),
        _check("context-agreement", evaluation.context_key == catalog.context_key == scenarios.context_key, catalog.context_key, (evaluation.context_key, scenarios.context_key), "one exact context across surfaces"),
        _check("source-agreement", set(catalog.source_ids) == set(audit.source_ids), list(catalog.source_ids), list(audit.source_ids), "source receipts preserved"),
        _check("determinism", deterministic, True, deterministic, "repeated evaluation address is stable"),
        _check("positive-identities", _unique(item.record_id for item in catalog.positives), True, _unique(item.record_id for item in catalog.positives), "positive IDs are unique"),
        _check("control-identities", _unique(item.record_id for item in catalog.controls), True, _unique(item.record_id for item in catalog.controls), "control IDs are unique"),
        _check("aggregate-scope", catalog.patient_level is False and all(not source.patient_level for source in catalog.sources), True, catalog.patient_level is False, "all scope flags are aggregate"),
        _check("address-floor", address_floor, True, address_floor, "all operation receipts are addressed"),
        _check("contract-state-coverage", contract_states, True, contract_states, "positive and review states are contract-covered"),
        _check("sanitized-boundary", sanitized, True, sanitized, "published evaluation has no raw payload fields"),
        _check("lineage-audit", lineage_audit.passed, True, lineage_audit.passed, "source-to-result lineage graph is valid"),
        _check("lineage-shape", len(lineage.nodes) == 29 and len(lineage.edges) == 36, (29, 36), (len(lineage.nodes), len(lineage.edges)), "lineage graph covers every source, record, and result"),
    )
    state = StructuralHaplotypeFixtureState.ACCEPTED if all(check.passed for check in checks) else StructuralHaplotypeFixtureState.REVIEW
    body = {
        "fixture_id": catalog.fixture_id,
        "context_key": catalog.context_key,
        "state": state,
        "checks": checks,
        "evaluation": evaluation.content_address,
        "replay": replay.content_address,
        "scenarios": scenarios.content_address,
        "contracts": contracts.manifest()["content_address"],
        "lineage": lineage.content_address,
    }
    return StructuralHaplotypeQualityGateReport(
        fixture_id=catalog.fixture_id,
        context_key=catalog.context_key,
        state=state,
        checks=checks,
        evaluation_address=evaluation.content_address,
        replay_address=replay.content_address,
        scenario_address=scenarios.content_address,
        contract_address=contracts.manifest()["content_address"],
        lineage_address=lineage.content_address,
        content_address=content_hash(body),
    )


def _replay_catalog(
    catalog: StructuralHaplotypeFixtureCatalog,
    expectation: StructuralHaplotypeReplayExpectation,
) -> StructuralHaplotypeReplayReport:
    evaluation = evaluate_structural_haplotype_fixture(catalog)
    issues: set[str] = set()
    if catalog.fixture_id != expectation.fixture_id:
        issues.add("fixture_id_mismatch")
    if catalog.context_key != expectation.context_key:
        issues.add("context_mismatch")
    if catalog.source_ids != tuple(sorted(expectation.source_ids)):
        issues.add("source_set_mismatch")
    if len(evaluation.checks) < expectation.minimum_checks:
        issues.add("check_floor")
    case = StructuralHaplotypeReplayCase(
        path="<in-memory>",
        fixture_id=catalog.fixture_id,
        context_key=catalog.context_key,
        content_address=catalog.content_address,
        evaluation_address=evaluation.content_address,
        passed=not issues and evaluation.passed,
        issue_codes=tuple(sorted(issues | ({"evaluation_failed"} if not evaluation.passed else set()))),
    )
    body = {"cases": (case,), "issues": tuple(sorted(issues))}
    return StructuralHaplotypeReplayReport((case,), tuple(sorted(issues)), content_hash(body))


def _contract_states_match(catalog: StructuralHaplotypeFixtureCatalog, evaluation: Any, contracts: Any) -> bool:
    receipt_by_id = {receipt.record_id: receipt for receipt in evaluation.receipts}
    for record in catalog.positives:
        if not contracts.get(record.operation).accepts(receipt_by_id[record.record_id].observed_result_state):
            return False
    for record in catalog.controls:
        if not contracts.get(record.operation).reviews(receipt_by_id[record.record_id].observed_result_state):
            return False
    return True


def _deterministic(catalog: StructuralHaplotypeFixtureCatalog) -> bool:
    first = evaluate_structural_haplotype_fixture(catalog)
    second = evaluate_structural_haplotype_fixture(catalog)
    return first.content_address == second.content_address


def _sanitized(evaluation: Any) -> bool:
    payload = json.dumps(evaluation.to_dict(), sort_keys=True)
    return all(token not in payload for token in ("raw_record", "patient_id", "subject_id", "sample_patient_id"))


def _unique(values: Any) -> bool:
    items = tuple(values)
    return len(items) == len(set(items))


def _check(check_id: str, passed: bool, expected: Any, observed: Any, detail: str) -> StructuralHaplotypeQualityCheck:
    return StructuralHaplotypeQualityCheck(check_id, passed, expected, observed, detail)


__all__ = [
    "StructuralHaplotypeQualityCheck",
    "StructuralHaplotypeQualityGateReport",
    "evaluate_structural_haplotype_quality_gate",
]
