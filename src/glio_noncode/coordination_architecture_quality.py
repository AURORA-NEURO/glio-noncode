"""Cross-plane quality gate for the coordination architecture."""

from __future__ import annotations

from typing import Any

from .coordination_architecture_contracts import (
    COORDINATION_CASE_COUNT,
    CoordinationCheck,
    CoordinationCheckKind,
    CoordinationQualityReport,
    CoordinationRuntime,
    CoordinationScenario,
    CoordinationState,
    addressed,
)
from .coordination_architecture_deployment import audit_coordination_deployment
from .coordination_architecture_ledger import verify_coordination_ledger
from .coordination_architecture_monitoring import audit_coordination_observations
from .coordination_architecture_plan import audit_coordination_plan
from .coordination_architecture_registries import validate_coordination_registry
from .coordination_architecture_release import verify_coordination_release
from .coordination_architecture_tools import validate_coordination_tool_registry


def _check(check_id: str, kind: CoordinationCheckKind, passed: bool, observed: Any, required: Any, detail: str) -> CoordinationCheck:
    body = {"check_id": check_id, "kind": kind, "passed": bool(passed), "observed": observed, "required": required, "detail": detail}
    return CoordinationCheck(**body, content_address=addressed(body, "coordination-quality-check"))


def run_coordination_quality_gate(runtime: CoordinationRuntime) -> CoordinationQualityReport:
    controls = tuple(item for item in runtime.evaluation.executions if item.scenario is not CoordinationScenario.POSITIVE)
    positive = tuple(item for item in runtime.evaluation.executions if item.scenario is CoordinationScenario.POSITIVE)
    plan_issues = audit_coordination_plan(runtime.plan)
    tool_issues = validate_coordination_tool_registry(runtime.tools)
    ledger_issues = verify_coordination_ledger(runtime.ledger)
    compute_issues = validate_coordination_registry(runtime.compute_registry)
    reference_issues = validate_coordination_registry(runtime.reference_registry)
    observation_issues = audit_coordination_observations(runtime.observations)
    deployment_issues = audit_coordination_deployment(runtime.deployment_artifacts, runtime.assignments)
    checks = (
        _check("runtime-accepted", CoordinationCheckKind.INTEGRITY, runtime.state is CoordinationState.ACCEPTED, runtime.state, CoordinationState.ACCEPTED, "all runtime stages are accepted"),
        _check("stage-count", CoordinationCheckKind.INTEGRITY, len(runtime.stages) == 20, len(runtime.stages), 20, "runtime stage denominator is closed"),
        _check("evaluation-cardinality", CoordinationCheckKind.OPERATION, len(runtime.evaluation.executions) == COORDINATION_CASE_COUNT, len(runtime.evaluation.executions), COORDINATION_CASE_COUNT, "all fixture cases executed"),
        _check("evaluation-accepted", CoordinationCheckKind.OPERATION, runtime.evaluation.accepted, runtime.evaluation.failed_cases, 0, "expected positive and control states reconcile"),
        _check("positive-acceptance", CoordinationCheckKind.POLICY, all(item.observed_state is CoordinationState.ACCEPTED for item in positive), sum(item.observed_state is CoordinationState.ACCEPTED for item in positive), 16, "positive cases are accepted"),
        _check("control-holds", CoordinationCheckKind.REVIEW, all(item.observed_state is not CoordinationState.ACCEPTED for item in controls), sum(item.observed_state is not CoordinationState.ACCEPTED for item in controls), 48, "controls remain held"),
        _check("plan-closed", CoordinationCheckKind.PLAN, not plan_issues, plan_issues, (), "plan dependencies and ordinals are closed"),
        _check("tools-closed", CoordinationCheckKind.TOOL, not tool_issues, tool_issues, (), "typed tools are deterministic and offline"),
        _check("schedule-closed", CoordinationCheckKind.RESOURCE, runtime.schedule.accepted, runtime.schedule.issues, (), "budget schedule is admitted"),
        _check("review-queue-closed", CoordinationCheckKind.REVIEW, len(runtime.evaluation.executions) - len(positive) == 48, len(controls), 48, "held cases have review routes"),
        _check("ledger-closed", CoordinationCheckKind.LEDGER, not ledger_issues, ledger_issues, (), "event chain is contiguous"),
        _check("compute-registry-closed", CoordinationCheckKind.REGISTRY, not compute_issues, compute_issues, (), "compute registry entries are addressed"),
        _check("reference-registry-closed", CoordinationCheckKind.REGISTRY, not reference_issues, reference_issues, (), "reference registry entries are addressed"),
        _check("monitoring-closed", CoordinationCheckKind.MONITORING, not observation_issues, observation_issues, (), "observations remain in exact context"),
        _check("security-closed", CoordinationCheckKind.SECURITY, all(item.state is CoordinationState.ACCEPTED for item in runtime.security), len(runtime.security), 16, "positive security decisions are accepted"),
        _check("deployment-closed", CoordinationCheckKind.DEPLOYMENT, len(runtime.release.artifact_addresses) == 5 and not deployment_issues, len(runtime.release.artifact_addresses), 5, "offline deployment artifacts are retained"),
        _check("release-closed", CoordinationCheckKind.RELEASE, not verify_coordination_release(runtime.release) and runtime.release.state is CoordinationState.ACCEPTED, runtime.release.state, CoordinationState.ACCEPTED, "release and rollback metadata are complete"),
        _check("assignment-closed", CoordinationCheckKind.RELEASE, len(runtime.assignments) == 16 and all(item.eligible for item in runtime.assignments), len(runtime.assignments), 16, "federated assignments remain eligible"),
    )
    passed = sum(item.passed for item in checks)
    failed = len(checks) - passed
    body = {"fixture_id": runtime.fixture_id, "checks": checks, "accepted": failed == 0, "passed_checks": passed, "failed_checks": failed}
    return CoordinationQualityReport(runtime.fixture_id, checks, failed == 0, passed, failed, addressed(body, "coordination-quality"))


__all__ = ["run_coordination_quality_gate"]
