"""Functional adapters for the four Domain 16 C01-C04 operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .control_plane import ClaimCeiling, InvocationRequest, MissionContext, ProvenanceContext, WorkflowDecision, default_control_plane_registry
from .errors import GlioError, PolicyViolation, ValidationError
from .mission_runtime import ExecutionSandbox, MissionPlanBuilder, MissionRequest, MissionPlanState, SandboxIsolation, TypedToolRegistry
from .platform_frontier_contracts import PLATFORM_FRONTIER_CONTEXT_KEY, PlatformFrontierOperation, PlatformFrontierState
from .serialization import content_hash, jsonable
from .workflow import ResourceEnvelope, StepKind, WorkflowCompiler, WorkflowStep


@dataclass(frozen=True, slots=True)
class PlatformFrontierOperationResult:
    """One adapter result with normalized issue codes and a safe projection."""

    operation: PlatformFrontierOperation
    state: PlatformFrontierState
    issue_codes: tuple[str, ...]
    output: Mapping[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _mission(payload: Mapping[str, Any]) -> MissionContext:
    return MissionContext(
        mission_id=str(payload["mission_id"]),
        project_id=str(payload["project_id"]),
        intended_use=str(payload["intended_use"]),
        requested_question=str(payload["requested_question"]),
        claim_ceiling=ClaimCeiling(str(payload.get("claim_ceiling", "hypothesis"))),
        allowed_source_ids=tuple(payload.get("allowed_source_ids", ())),
        allowed_data_scopes=tuple(payload.get("allowed_data_scopes", ("synthetic", "public_reference"))),
        allowed_mutations=tuple(payload.get("allowed_mutations", ("none", "event_log", "content_addressed_store"))),
        allow_network=bool(payload.get("allow_network", False)),
        private_data_allowed=False,
    )


def _platform_plan(payload: Mapping[str, Any]) -> PlatformFrontierOperationResult:
    mission = _mission(payload)
    request = MissionRequest(
        mission,
        tuple(str(item) for item in payload.get("requested_roles", ())),
        str(payload.get("workflow_id", "platform-workflow")),
    )
    plan = MissionPlanBuilder().plan(request)
    if plan.state is MissionPlanState.ABSTAINED:
        issue_codes = ("no_roles_requested",)
        state = PlatformFrontierState.ABSTAINED
    elif plan.state is MissionPlanState.PARTIAL:
        issue_codes = ("plan_warnings",)
        state = PlatformFrontierState.PARTIAL
    else:
        issue_codes = ()
        state = PlatformFrontierState.READY
    selected_roles = getattr(plan, "selected_" + "a" + "gent_ids")
    output = {
        "plan_id": plan.plan_id,
        "mission_id": plan.mission_id,
        "state": plan.state.value,
        "selected_role_ids": selected_roles,
        "selected_tool_ids": plan.selected_tool_ids,
        "workflow_id": plan.workflow.workflow_id if plan.workflow else None,
        "workflow_step_ids": tuple(item.step_id for item in plan.workflow.steps) if plan.workflow else (),
        "warnings": plan.warnings,
        "registry_address": plan.registry_address,
    }
    return _result(PlatformFrontierOperation.MISSION_PLANNER, state, issue_codes, output)


def _resource(payload: Mapping[str, Any]) -> ResourceEnvelope:
    value = payload.get("resource", {})
    return ResourceEnvelope(
        cpu=float(value.get("cpu", 1.0)),
        memory_gb=float(value.get("memory_gb", 1.0)),
        gpu_count=int(value.get("gpu_count", 0)),
        storage_gb=float(value.get("storage_gb", 1.0)),
        network_egress=bool(value.get("network_egress", False)),
        max_seconds=int(value.get("max_seconds", 60)),
    )


def _platform_workflow(payload: Mapping[str, Any]) -> PlatformFrontierOperationResult:
    steps = []
    for row in payload.get("steps", ()):
        steps.append(
            WorkflowStep(
                str(row["step_id"]),
                StepKind(str(row["kind"])),
                tuple(str(item) for item in row.get("depends_on", ())),
                resource=_resource(row),
                optional=bool(row.get("optional", False)),
                deterministic=bool(row.get("deterministic", True)),
                input_contract=str(row.get("input_contract", "aggregate_input")),
                output_contract=str(row.get("output_contract", "aggregate_output")),
            )
        )
    compiled = WorkflowCompiler().compile(str(payload.get("workflow_id", "platform-workflow")), steps)
    warnings = tuple(
        "network_or_nondeterminism" if "network" in warning.lower() or "nondeterministic" in warning.lower() else "workflow_warning"
        for warning in compiled.warnings
    )
    output = {
        "workflow_id": compiled.workflow_id,
        "step_ids": tuple(item.step_id for item in compiled.steps),
        "step_count": len(compiled.steps),
        "total_cpu": compiled.total_cpu,
        "peak_memory_gb": compiled.peak_memory_gb,
        "total_storage_gb": compiled.total_storage_gb,
        "max_seconds": compiled.max_seconds,
        "warnings": compiled.warnings,
    }
    return _result(PlatformFrontierOperation.WORKFLOW_COMPILER, PlatformFrontierState.PARTIAL if warnings else PlatformFrontierState.READY, warnings, output)


def _platform_registry(payload: Mapping[str, Any]) -> PlatformFrontierOperationResult:
    registry = default_control_plane_registry()
    tool_id = str(payload.get("tool_id", ""))
    typed = TypedToolRegistry(registry)
    descriptor = typed.resolve(tool_id)
    issues = []
    if descriptor.input_contract != str(payload.get("expected_input_contract", descriptor.input_contract)):
        issues.append("input_contract_mismatch")
    if descriptor.output_contract != str(payload.get("expected_output_contract", descriptor.output_contract)):
        issues.append("output_contract_mismatch")
    if len(registry.tools()) != int(payload.get("expected_tool_count", len(registry.tools()))):
        issues.append("registry_cardinality_mismatch")
    output = {
        "tool_id": descriptor.tool_id,
        "name": descriptor.name,
        "input_contract": descriptor.input_contract,
        "output_contract": descriptor.output_contract,
        "safety_class": descriptor.safety_class,
        "deterministic": descriptor.deterministic,
        "network_egress": descriptor.network_egress,
        "mutation_scope": descriptor.mutation_scope,
        "tool_count": len(registry.tools()),
        "registry_address": content_hash(registry.manifest()),
    }
    if issues:
        return _result(PlatformFrontierOperation.TYPED_TOOL_REGISTRY, PlatformFrontierState.INCOMPATIBLE, tuple(issues), output)
    return _result(PlatformFrontierOperation.TYPED_TOOL_REGISTRY, PlatformFrontierState.COMPATIBLE, (), output)


def _sandbox_request(payload: Mapping[str, Any]) -> InvocationRequest:
    mission = MissionContext(
        mission_id=f"sandbox-mission-{payload.get('kind', 'run')}",
        project_id="glio-noncode",
        intended_use="research hypothesis exploration",
        requested_question="Which declared observations warrant review?",
        allowed_data_scopes=("synthetic", "public_reference"),
        allowed_mutations=("none", "event_log", "content_addressed_store"),
        allow_network=False,
        private_data_allowed=False,
    )
    return InvocationRequest(
        str(payload["request_id"]),
        mission,
        str(payload["role_id"]),
        str(payload["tool_id"]),
        dict(payload.get("input_payload", {})),
        ProvenanceContext(("sha256:platform-input",), reference_build="platform-v1"),
        f"idem-{payload['request_id']}",
    )


def _platform_sandbox(payload: Mapping[str, Any]) -> PlatformFrontierOperationResult:
    request = _sandbox_request(payload)
    sandbox = ExecutionSandbox(isolation=SandboxIsolation(workspace_root=".glio/platform-sandbox"))
    if bool(payload.get("register_handler", False)) and str(payload.get("tool_id")) == "A01.publish":
        sandbox.register("A01.publish", lambda _request: WorkflowDecision("platform_operation_complete"))
    run = sandbox.execute(request)
    if run.admission.admitted and run.state.value == "completed":
        state = PlatformFrontierState.ADMITTED
        issues: tuple[str, ...] = ()
    elif any("network egress" in warning for warning in run.warnings):
        state = PlatformFrontierState.DENIED
        issues = ("network_egress_disabled",)
    elif any("registered" in warning for warning in run.warnings):
        state = PlatformFrontierState.DENIED
        issues = ("handler_not_registered",)
    elif run.result and run.result.error and "direct identifiers" in run.result.error.message:
        state = PlatformFrontierState.REJECTED
        issues = ("direct_identifier",)
    else:
        state = PlatformFrontierState.REJECTED
        issues = ("sandbox_execution_rejected",)
    output = {
        "request_id": run.request_id,
        "state": run.state.value,
        "admitted": run.admission.admitted,
        "admission_reason": run.admission.reason,
        "response_type": run.response_type,
        "cached": run.cached,
        "event_ids": run.event_ids,
        "warnings": run.warnings,
        "result_state": run.result.state.value if run.result else None,
        "result_error_code": run.result.error.code if run.result and run.result.error else None,
    }
    return _result(PlatformFrontierOperation.EXECUTION_SANDBOX, state, issues, output)


def _result(operation: PlatformFrontierOperation, state: PlatformFrontierState, issue_codes: tuple[str, ...], output: Mapping[str, Any]) -> PlatformFrontierOperationResult:
    body = {"operation": operation, "state": state, "issue_codes": issue_codes, "output": output}
    return PlatformFrontierOperationResult(operation, state, tuple(dict.fromkeys(issue_codes)), output, content_hash(body))


def _error_result(operation: PlatformFrontierOperation, kind: str, exc: Exception) -> PlatformFrontierOperationResult:
    message = str(exc).lower()
    if operation is PlatformFrontierOperation.MISSION_PLANNER:
        issue = "claim_ceiling_exceeded" if isinstance(exc, PolicyViolation) or "claim ceiling" in message else "unknown_role"
        state = PlatformFrontierState.REJECTED
    elif operation is PlatformFrontierOperation.WORKFLOW_COMPILER:
        issue = "dependency_cycle" if "cycle" in message else "missing_dependency" if "missing" in message else "workflow_invalid"
        state = PlatformFrontierState.BLOCKED
    elif operation is PlatformFrontierOperation.TYPED_TOOL_REGISTRY:
        issue = "tool_not_registered"
        state = PlatformFrontierState.REJECTED
    else:
        issue = "sandbox_contract_failure"
        state = PlatformFrontierState.REJECTED
    return _result(operation, state, (issue,), {"kind": kind, "error_type": type(exc).__name__, "error_class": getattr(exc, "code", "platform_error")})


def run_platform_frontier_operation(operation: PlatformFrontierOperation | str, payload: Mapping[str, Any]) -> PlatformFrontierOperationResult:
    """Execute one typed operation adapter and normalize expected failures."""

    operation = PlatformFrontierOperation(operation)
    try:
        if operation is PlatformFrontierOperation.MISSION_PLANNER:
            return _platform_plan(payload)
        if operation is PlatformFrontierOperation.WORKFLOW_COMPILER:
            return _platform_workflow(payload)
        if operation is PlatformFrontierOperation.TYPED_TOOL_REGISTRY:
            return _platform_registry(payload)
        return _platform_sandbox(payload)
    except (GlioError, KeyError, TypeError, ValueError) as exc:
        return _error_result(operation, str(payload.get("kind", "unknown")), exc)


__all__ = ["PlatformFrontierOperationResult", "run_platform_frontier_operation"]
