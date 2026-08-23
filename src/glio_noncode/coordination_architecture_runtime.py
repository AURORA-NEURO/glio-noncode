"""End-to-end D16 coordination architecture runtime."""

from __future__ import annotations

from .coordination_architecture_contracts import (
    CoordinationFixture,
    CoordinationRuntime,
    CoordinationRuntimeStage,
    CoordinationState,
    addressed,
)
from .coordination_architecture_deployment import (
    build_coordination_assignments,
    build_coordination_deployment_artifacts,
)
from .coordination_architecture_ledger import build_coordination_ledger
from .coordination_architecture_monitoring import build_coordination_observations
from .coordination_architecture_operations import evaluate_coordination_fixture
from .coordination_architecture_plan import compile_coordination_plan
from .coordination_architecture_policy import evaluate_coordination_policy
from .coordination_architecture_public_data import default_coordination_fixture
from .coordination_architecture_public_data import audit_coordination_data
from .coordination_architecture_registries import (
    build_coordination_compute_registry,
    build_coordination_reference_registry,
)
from .coordination_architecture_release import build_coordination_release
from .coordination_architecture_review import build_coordination_review_queue
from .coordination_architecture_sandbox import execute_coordination_sandbox
from .coordination_architecture_scheduler import schedule_coordination_plan
from .coordination_architecture_security import evaluate_coordination_security
from .coordination_architecture_tools import build_coordination_tool_registry


def _stage(stage_id: str, ordinal: int, state: CoordinationState, input_value: object, output_value: object, detail: str) -> CoordinationRuntimeStage:
    body = {
        "stage_id": stage_id,
        "ordinal": ordinal,
        "state": state,
        "input_address": addressed(input_value, "coordination-stage-input"),
        "output_address": addressed(output_value, "coordination-stage-output"),
        "detail": detail,
    }
    return CoordinationRuntimeStage(**body, content_address=addressed(body, "coordination-stage"))


def run_coordination_architecture(
    fixture: CoordinationFixture | None = None,
    *,
    run_id: str = "coordination-architecture-runtime",
) -> CoordinationRuntime:
    value = fixture or default_coordination_fixture()
    stages: list[CoordinationRuntimeStage] = []
    stages.append(_stage("fixture-loaded", 1, CoordinationState.ACCEPTED, {}, value.to_dict(), "load public aggregate coordination fixture"))
    data = audit_coordination_data(value)
    stages.append(_stage("public-boundary-audited", 2, CoordinationState.ACCEPTED if data.accepted else CoordinationState.REVIEW, value.to_dict(), data.to_dict(), "audit HTTPS sources and aggregate payload scope"))
    plan = compile_coordination_plan(value)
    stages.append(_stage("workflow-compiled", 3, CoordinationState.ACCEPTED if plan.accepted else CoordinationState.REVIEW, value.to_dict(), plan.to_dict(), "compile dependencies and detect cycles"))
    tools = build_coordination_tool_registry(value)
    stages.append(_stage("typed-tools-registered", 4, CoordinationState.ACCEPTED if tools.accepted else CoordinationState.REVIEW, plan.to_dict(), tools.to_dict(), "close input and output tool contracts"))
    schedule = schedule_coordination_plan(plan)
    stages.append(_stage("resources-scheduled", 5, CoordinationState.ACCEPTED if schedule.accepted else CoordinationState.REVIEW, plan.to_dict(), schedule.to_dict(), "admit deterministic work within budget"))
    evaluation = evaluate_coordination_fixture(value)
    stages.append(_stage("cases-evaluated", 6, CoordinationState.ACCEPTED if evaluation.accepted else CoordinationState.REVIEW, value.to_dict(), evaluation.to_dict(), "execute positive and control scenarios"))
    spec_by_id = {item.operation_id: item for item in value.operations}
    tool_by_id = {item.operation_id: item for item in tools.tools}
    positive_sandbox = tuple(
        execute_coordination_sandbox(case, spec_by_id[case.operation_id], tool_by_id[case.operation_id])
        for case in value.positive_cases
    )
    sandbox_state = CoordinationState.ACCEPTED if all(item.state is CoordinationState.ACCEPTED for item in positive_sandbox) else CoordinationState.REVIEW
    stages.append(_stage("sandbox-admitted", 7, sandbox_state, evaluation.to_dict(), tuple(item.to_dict() for item in positive_sandbox), "admit only registered local aggregate tools"))
    positive_policy = tuple(evaluate_coordination_policy(case, spec_by_id[case.operation_id]) for case in value.positive_cases)
    policy_state = CoordinationState.ACCEPTED if all(item.allowed for item in positive_policy) else CoordinationState.REVIEW
    stages.append(_stage("claim-policy-gated", 8, policy_state, evaluation.to_dict(), tuple(item.to_dict() for item in positive_policy), "apply bounded claim and context policy"))
    review_queue = build_coordination_review_queue(evaluation.executions)
    stages.append(_stage("review-routed", 9, CoordinationState.ACCEPTED if len(review_queue) == len(value.control_cases) else CoordinationState.REVIEW, evaluation.to_dict(), tuple(item.to_dict() for item in review_queue), "route every held control to review"))
    ledger = build_coordination_ledger(evaluation.executions)
    stages.append(_stage("event-ledgered", 10, CoordinationState.ACCEPTED, evaluation.to_dict(), ledger.to_dict(), "append addressed case events"))
    compute_registry = build_coordination_compute_registry(value)
    stages.append(_stage("compute-registered", 11, CoordinationState.ACCEPTED if compute_registry.accepted else CoordinationState.REVIEW, {}, compute_registry.to_dict(), "register bounded compute profiles"))
    reference_registry = build_coordination_reference_registry(value)
    stages.append(_stage("references-registered", 12, CoordinationState.ACCEPTED if reference_registry.accepted else CoordinationState.REVIEW, {}, reference_registry.to_dict(), "register public reference receipts"))
    observations = build_coordination_observations(value)
    stages.append(_stage("drift-monitored", 13, CoordinationState.ACCEPTED, reference_registry.to_dict(), tuple(item.to_dict() for item in observations), "monitor exact-context support and drift"))
    security = tuple(evaluate_coordination_security(case) for case in value.positive_cases)
    stages.append(_stage("security-gated", 14, CoordinationState.ACCEPTED if all(item.state is CoordinationState.ACCEPTED for item in security) else CoordinationState.REVIEW, tuple(item.to_dict() for item in security), {}, "deny private and network paths"))
    artifacts = build_coordination_deployment_artifacts(value)
    stages.append(_stage("bundle-materialized", 15, CoordinationState.ACCEPTED, {}, tuple(item.to_dict() for item in artifacts), "materialize offline bundle artifacts"))
    assignments = build_coordination_assignments(value)
    stages.append(_stage("federation-assigned", 16, CoordinationState.ACCEPTED, {}, tuple(item.to_dict() for item in assignments), "retain site-local public assignments"))
    release = build_coordination_release(artifacts)
    stages.append(_stage("release-gated", 17, release.state, tuple(item.to_dict() for item in artifacts), release.to_dict(), "apply release and rollback gates"))
    stages.append(_stage("ledger-closed", 18, CoordinationState.ACCEPTED, ledger.to_dict(), {"events": len(ledger.events)}, "verify event denominator and links"))
    stages.append(_stage("control-boundary-retained", 19, CoordinationState.ACCEPTED if all(item.observed_state is not CoordinationState.ACCEPTED for item in evaluation.executions if item.scenario.value != "positive") else CoordinationState.REVIEW, evaluation.to_dict(), {"review_cases": len(review_queue)}, "keep all controls held"))
    final_state = CoordinationState.ACCEPTED if all(item.state is CoordinationState.ACCEPTED for item in stages) else CoordinationState.REVIEW
    stages.append(_stage("runtime-finalized", 20, final_state, {"stage_count": len(stages)}, {"state": final_state}, "finalize addressed coordination runtime"))
    body = {
        "run_id": run_id,
        "stages": tuple(stages),
        "state": final_state,
        "fixture_id": value.fixture_id,
        "evaluation": evaluation,
        "plan": plan,
        "tools": tools,
        "schedule": schedule,
        "ledger": ledger,
        "compute_registry": compute_registry,
        "reference_registry": reference_registry,
        "observations": observations,
        "security": security,
        "deployment_artifacts": artifacts,
        "assignments": assignments,
        "release": release,
    }
    return CoordinationRuntime(**body, content_address=addressed(body, "coordination-runtime"))


__all__ = ["run_coordination_architecture"]
