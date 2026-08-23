"""Deep quality gate for D01 runtime, controls, provenance, and release."""

from __future__ import annotations

from typing import Any

from .intake_architecture_bundle import verify_intake_architecture_release
from .intake_architecture_contracts import (
    IntakeArchitectureCheckKind,
    IntakeArchitectureQualityCheck,
    IntakeArchitectureQualityReport,
    IntakeArchitectureRuntime,
    IntakeArchitectureScenario,
    IntakeArchitectureState,
    addressed,
)
from .intake_architecture_plan import audit_intake_architecture_plan
from .intake_architecture_provenance import verify_intake_architecture_ledger
from .intake_architecture_schema import validate_intake_architecture_schema
from .intake_architecture_invariants import intake_architecture_invariants


def _check(check_id: str, kind: IntakeArchitectureCheckKind, passed: bool, observed: Any, required: Any, detail: str) -> IntakeArchitectureQualityCheck:
    body = {"check_id": check_id, "kind": kind, "passed": bool(passed), "observed": observed, "required": required, "detail": detail}
    return IntakeArchitectureQualityCheck(**body, content_address=addressed(body, "intake-quality-check"))


def run_intake_architecture_quality_gate(runtime: IntakeArchitectureRuntime) -> IntakeArchitectureQualityReport:
    positives = tuple(item for item in runtime.evaluation.results if item.scenario is IntakeArchitectureScenario.POSITIVE)
    controls = tuple(item for item in runtime.evaluation.results if item.scenario is not IntakeArchitectureScenario.POSITIVE)
    plan_issues = audit_intake_architecture_plan(runtime.plan)
    ledger_issues = verify_intake_architecture_ledger(runtime.ledger)
    schema_issues = validate_intake_architecture_schema()
    invariant_issues = intake_architecture_invariants(runtime)
    release_issues = verify_intake_architecture_release(runtime.release)
    checks = (
        _check("runtime-accepted", IntakeArchitectureCheckKind.INTEGRITY, runtime.state is IntakeArchitectureState.ACCEPTED, runtime.state, IntakeArchitectureState.ACCEPTED, "all twenty runtime stages are accepted"),
        _check("stage-count", IntakeArchitectureCheckKind.INTEGRITY, len(runtime.stages) == 20, len(runtime.stages), 20, "runtime denominator is closed"),
        _check("case-cardinality", IntakeArchitectureCheckKind.OPERATION, len(runtime.evaluation.results) == 64, len(runtime.evaluation.results), 64, "all cases execute"),
        _check("evaluation-reconciled", IntakeArchitectureCheckKind.OPERATION, runtime.evaluation.accepted, runtime.evaluation.failed_cases, 0, "expected states and issue codes reconcile"),
        _check("positive-acceptance", IntakeArchitectureCheckKind.OPERATION, all(item.observed_state is IntakeArchitectureState.ACCEPTED for item in positives), len(positives), 16, "all positive cases are accepted"),
        _check("control-holds", IntakeArchitectureCheckKind.POLICY, all(item.observed_state is not IntakeArchitectureState.ACCEPTED for item in controls), len(controls), 48, "all controls remain held"),
        _check("plan-closed", IntakeArchitectureCheckKind.OPERATION, not plan_issues, plan_issues, (), "dependency plan is closed"),
        _check("review-closed", IntakeArchitectureCheckKind.POLICY, len(runtime.review_queue.items) == 48, len(runtime.review_queue.items), 48, "held controls have review routes"),
        _check("ledger-closed", IntakeArchitectureCheckKind.PROVENANCE, not ledger_issues, ledger_issues, (), "custody ledger is contiguous"),
        _check("artifact-count", IntakeArchitectureCheckKind.RELEASE, len(runtime.artifacts) == 5, len(runtime.artifacts), 5, "five offline artifacts are present"),
        _check("release-closed", IntakeArchitectureCheckKind.RELEASE, not release_issues and runtime.release.state is IntakeArchitectureState.ACCEPTED, release_issues, (), "release and rollback data are complete"),
        _check("schema-closed", IntakeArchitectureCheckKind.INTEGRITY, not schema_issues, schema_issues, (), "schema privacy and denominator are closed"),
        _check("invariants-closed", IntakeArchitectureCheckKind.INTEGRITY, not invariant_issues, invariant_issues, (), "runtime invariants hold"),
        _check("addressed-results", IntakeArchitectureCheckKind.INTEGRITY, all(":" in item.content_address for item in runtime.evaluation.results), len(runtime.evaluation.results), 64, "every result has an address"),
        _check("receipt-links", IntakeArchitectureCheckKind.PROVENANCE, all(item.receipt_addresses for item in positives), sum(bool(item.receipt_addresses) for item in positives), 16, "positive primitive receipts are retained"),
        _check("context-boundary", IntakeArchitectureCheckKind.POLICY, all(item.output.get("claim_boundary") == "public aggregate intake identity only" for item in runtime.evaluation.results), True, True, "claim boundary is explicit"),
        _check("validation-denominator", IntakeArchitectureCheckKind.INTEGRITY, len(runtime.stages) == 20, len(runtime.stages), 20, "runtime stage evidence is present"),
        _check("rollback-pointer", IntakeArchitectureCheckKind.RELEASE, bool(runtime.release.rollback_version), runtime.release.rollback_version, "non-empty", "rollback pointer is retained"),
    )
    passed = sum(item.passed for item in checks)
    body = {"fixture_id": runtime.fixture_id, "checks": checks, "accepted": passed == len(checks), "passed_checks": passed, "failed_checks": len(checks) - passed}
    return IntakeArchitectureQualityReport(runtime.fixture_id, checks, passed == len(checks), passed, len(checks) - passed, addressed(body, "intake-quality"))


__all__ = ["run_intake_architecture_quality_gate"]
