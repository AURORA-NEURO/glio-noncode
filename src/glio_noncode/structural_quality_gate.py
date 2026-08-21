"""Cross-surface quality gate for the Domain 02 C01-C04 evidence stack."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .structural_contracts import default_structural_contract_registry
from .structural_fixture_eval import evaluate_structural_fixture
from .structural_public_data import (
    STRUCTURAL_CONTROL_FLOOR,
    STRUCTURAL_OPERATION_FLOOR,
    StructuralFixtureCatalog,
    StructuralFixtureState,
    StructuralOperation,
    audit_structural_fixture,
)
from .structural_replay import StructuralReplayExpectation
from .structural_scenario_matrix import evaluate_structural_scenarios


@dataclass(frozen=True, slots=True)
class StructuralQualityCheck:
    """One named quality assertion with expected and observed values."""

    check_id: str
    passed: bool
    expected: Any
    observed: Any
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralQualityGateReport:
    """Reconciled quality result across audit, execution, replay, and scenarios."""

    fixture_id: str
    context_key: str
    state: StructuralFixtureState
    checks: tuple[StructuralQualityCheck, ...]
    evaluation_address: str
    replay_address: str
    scenario_address: str
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == StructuralFixtureState.ACCEPTED and all(
            check.passed for check in self.checks
        )

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["passed"] = self.passed
        result["check_count"] = len(self.checks)
        return result


def evaluate_structural_quality_gate(
    fixture: StructuralFixtureCatalog | str,
) -> StructuralQualityGateReport:
    """Run and reconcile every independent Domain 02 verification surface."""

    catalog = (
        StructuralFixtureCatalog.from_file(fixture)
        if isinstance(fixture, str)
        else fixture
    )
    audit = audit_structural_fixture(catalog)
    evaluation = evaluate_structural_fixture(catalog)
    scenarios = evaluate_structural_scenarios(catalog)
    expectation = StructuralReplayExpectation(
        fixture_id=catalog.fixture_id,
        context_key=catalog.context_key,
        source_ids=catalog.source_ids,
        minimum_checks=30,
        minimum_positive_records=STRUCTURAL_OPERATION_FLOOR,
        minimum_control_records=STRUCTURAL_CONTROL_FLOOR,
    )
    replay = _replay_catalog(catalog, expectation)
    contracts = default_structural_contract_registry()
    checks = (
        _check("data-audit", audit.accepted, True, audit.accepted, "public aggregate source and payload boundary"),
        _check("fixture-evaluation", evaluation.passed, True, evaluation.passed, "all positive and control checks pass"),
        _check("check-floor", len(evaluation.checks) >= 30, 30, len(evaluation.checks), "fixture assertions are substantial"),
        _check("replay", replay.passed, True, replay.passed, "replay identity and addresses are stable"),
        _check("scenario-matrix", scenarios.passed, True, scenarios.passed, "independent scenarios match state contracts"),
        _check("positive-floor", len(catalog.positives) >= STRUCTURAL_OPERATION_FLOOR, 4, len(catalog.positives), "all C01-C04 positives execute"),
        _check("positive-operation-coverage", {item.operation.value for item in catalog.positives} == {item.value for item in StructuralOperation}, [item.value for item in StructuralOperation], sorted({item.operation.value for item in catalog.positives}), "each operation has a positive executable record"),
        _check("control-floor", len(catalog.controls) >= STRUCTURAL_CONTROL_FLOOR, 8, len(catalog.controls), "two review controls per operation"),
        _check("operation-floor", set(catalog.operation_ids) == {item.value for item in StructuralOperation}, [item.value for item in StructuralOperation], list(catalog.operation_ids), "all operation contracts are represented"),
        _check("contract-floor", len(contracts.contracts) == 4, 4, len(contracts.contracts), "four typed contracts are registered"),
        _check("context-agreement", evaluation.context_key == catalog.context_key == scenarios.context_key, catalog.context_key, (evaluation.context_key, scenarios.context_key), "all surfaces use one exact context"),
        _check("source-agreement", set(catalog.source_ids) == set(audit.source_ids), list(catalog.source_ids), list(audit.source_ids), "source receipt set is preserved"),
        _check("determinism", _deterministic(catalog), True, _deterministic(catalog), "repeated execution has the same content address"),
        _check("positive-identity", _unique(item.record_id for item in catalog.positives), True, _unique(item.record_id for item in catalog.positives), "positive record IDs are unique"),
        _check("control-identity", _unique(item.record_id for item in catalog.controls), True, _unique(item.record_id for item in catalog.controls), "control record IDs are unique"),
        _check("aggregate-scope", catalog.patient_level is False and all(not source.patient_level for source in catalog.sources), True, catalog.patient_level is False, "fixture scope is aggregate"),
        _check("address-floor", all(receipt.output_address.startswith("sha256:") for receipt in evaluation.receipts), True, True, "every receipt is addressed"),
    )
    state = StructuralFixtureState.ACCEPTED if all(check.passed for check in checks) else StructuralFixtureState.REVIEW
    body = {
        "fixture_id": catalog.fixture_id,
        "context_key": catalog.context_key,
        "state": state,
        "checks": checks,
        "evaluation": evaluation.content_address,
        "replay": replay.content_address,
        "scenarios": scenarios.content_address,
    }
    return StructuralQualityGateReport(
        fixture_id=catalog.fixture_id,
        context_key=catalog.context_key,
        state=state,
        checks=checks,
        evaluation_address=evaluation.content_address,
        replay_address=replay.content_address,
        scenario_address=scenarios.content_address,
        content_address=content_hash(body),
    )


def _replay_catalog(catalog: StructuralFixtureCatalog, expectation: StructuralReplayExpectation):
    """Replay a catalog without requiring a temporary file on the quality path."""

    # The public replay function intentionally reads paths.  This quality gate
    # uses a small equivalent for in-memory catalogs to avoid writing a source
    # fixture during a test or CI run.
    evaluation = evaluate_structural_fixture(catalog)
    issues: set[str] = set()
    if catalog.fixture_id != expectation.fixture_id:
        issues.add("fixture_id_mismatch")
    if catalog.context_key != expectation.context_key:
        issues.add("context_mismatch")
    if catalog.source_ids != tuple(sorted(expectation.source_ids)):
        issues.add("source_set_mismatch")
    if len(evaluation.checks) < expectation.minimum_checks:
        issues.add("check_floor")
    from .structural_replay import StructuralReplayCase, StructuralReplayReport

    case = StructuralReplayCase(
        path="<in-memory>",
        fixture_id=catalog.fixture_id,
        context_key=catalog.context_key,
        content_address=catalog.content_address,
        evaluation_address=evaluation.content_address,
        passed=not issues and evaluation.passed,
        issue_codes=tuple(sorted(issues | ({"evaluation_failed"} if not evaluation.passed else set()))),
    )
    body = {"cases": (case,), "issues": tuple(sorted(issues))}
    return StructuralReplayReport((case,), tuple(sorted(issues)), content_hash(body))


def _check(check_id: str, passed: bool, expected: Any, observed: Any, detail: str) -> StructuralQualityCheck:
    return StructuralQualityCheck(check_id, passed, expected, observed, detail)


def _deterministic(catalog: StructuralFixtureCatalog) -> bool:
    first = evaluate_structural_fixture(catalog)
    second = evaluate_structural_fixture(catalog)
    return first.content_address == second.content_address


def _unique(values: Any) -> bool:
    items = tuple(values)
    return len(items) == len(set(items))


__all__ = [
    "StructuralQualityCheck",
    "StructuralQualityGateReport",
    "evaluate_structural_quality_gate",
]
