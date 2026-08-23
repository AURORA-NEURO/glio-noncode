"""Functional adapters for the eight Domain 16 control/runtime operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .control_beta import (
    BudgetResourceScheduler,
    BudgetWorkItem,
    ControlBetaState,
    DeterministicFallbackRouter,
    FallbackCandidate,
    FallbackRequest,
    HumanReviewQueueRouter,
)
from .control_frontier_contracts import (
    CONTROL_FRONTIER_CONTEXT_KEY,
    ControlFrontierOperation,
    ControlFrontierState,
)
from .errors import ValidationError
from .platform_alpha import (
    DataReferenceRegistry,
    DriftAndOODMonitor,
    EventSourcedExecutionLedger,
    ModelRegistry,
    RuntimeAlphaState,
)
from .serialization import content_hash, jsonable, require_non_empty
from .workflow import ResourceEnvelope


@dataclass(frozen=True, slots=True)
class ControlFrontierOperationResult:
    """Normalized result returned by every operation adapter."""

    operation: ControlFrontierOperation
    state: ControlFrontierState
    issue_codes: tuple[str, ...]
    output: Mapping[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


_CLAIM_RANK = {"observation": 0, "evidence": 1, "hypothesis": 2, "research_release": 3}


def _result(operation: ControlFrontierOperation, state: ControlFrontierState, issues: list[str], output: Mapping[str, Any]) -> ControlFrontierOperationResult:
    normalized = tuple(dict.fromkeys(str(item) for item in issues))
    body = {"operation": operation, "state": state, "issue_codes": normalized, "output": output}
    return ControlFrontierOperationResult(operation, state, normalized, dict(output), content_hash(body))


def _policy(payload: Mapping[str, Any]) -> ControlFrontierOperationResult:
    issues: list[str] = []
    if payload.get("context_key", CONTROL_FRONTIER_CONTEXT_KEY) != CONTROL_FRONTIER_CONTEXT_KEY:
        issues.append("context_mismatch")
    if payload.get("sensitive_paths"):
        issues.append("sensitive_input")
    source_gap = sorted(set(payload.get("request_source_ids", ())) - set(payload.get("allowed_source_ids", ())))
    if source_gap:
        issues.append("source_allowlist_gap")
    if payload.get("mutation_scope", "none") not in set(payload.get("allowed_mutations", ("none",))):
        issues.append("mutation_scope_denied")
    mission_rank = _CLAIM_RANK.get(str(payload.get("mission_ceiling", "observation")), -1)
    request_rank = _CLAIM_RANK.get(str(payload.get("claim_ceiling", "observation")), -1)
    if request_rank < 0 or mission_rank < 0 or request_rank > mission_rank:
        issues.append("claim_ceiling_exceeded")
    if payload.get("network_requested") and not payload.get("allowed_source_ids"):
        issues.append("network_source_missing")
    state = ControlFrontierState.SUPPORTED if not issues else ControlFrontierState.BLOCKED
    output = {
        "request_id": str(payload.get("request_id", "unknown")),
        "role_id": str(payload.get("role_id", "unknown")),
        "tool_id": str(payload.get("tool_id", "unknown")),
        "allowed": not issues,
        "claim_ceiling": payload.get("claim_ceiling"),
        "source_gap": source_gap,
        "sensitive_paths": list(payload.get("sensitive_paths", ())),
        "violations": list(issues),
        "policy_version": "control-frontier-policy-v1",
        "research_use_only": True,
    }
    return _result(ControlFrontierOperation.POLICY_CLAIM_GATE, state, issues, output)


def _resource(value: Mapping[str, Any]) -> ResourceEnvelope:
    return ResourceEnvelope(
        cpu=float(value.get("cpu", 1.0)),
        memory_gb=float(value.get("memory_gb", 1.0)),
        gpu_count=int(value.get("gpu_count", 0)),
        storage_gb=float(value.get("storage_gb", 1.0)),
        network_egress=bool(value.get("network_egress", False)),
        max_seconds=int(value.get("max_seconds", 300)),
    )


def _budget(payload: Mapping[str, Any]) -> ControlFrontierOperationResult:
    try:
        items = tuple(BudgetWorkItem.from_mapping(value) for value in payload.get("items", ()))
        limits = payload.get("limits", {})
        capacity = _resource(payload.get("capacity", {}))
        result = BudgetResourceScheduler().schedule(
            items,
            max_invocations=int(limits.get("max_invocations", 1)),
            max_network_requests=int(limits.get("max_network_requests", 0)),
            max_seconds=int(limits.get("max_seconds", 1)),
            max_cost_units=float(limits.get("max_cost_units", 1.0)),
            capacity=capacity,
            schedule_id=str(payload.get("schedule_id", "control-frontier-schedule")),
        )
    except ValidationError as exc:
        code = "dependency_cycle" if "cycle" in str(exc).lower() else "invalid_schedule"
        return _result(ControlFrontierOperation.BUDGET_RESOURCE_SCHEDULER, ControlFrontierState.BLOCKED, [code], {"error": str(exc), "schedule_id": payload.get("schedule_id")})
    issues: list[str] = []
    network_item_ids = {str(item.get("item_id", item.get("id", ""))) for item in payload.get("items", ()) if item.get("network_egress")}
    for item_id, reason in result.reasons.items():
        lower = reason.lower()
        if item_id in network_item_ids or "network" in lower:
            issues.append("network_limit")
        elif "capacity" in lower or "resource" in lower:
            issues.append("capacity_exceeded")
        elif "dependency" in lower:
            issues.append("dependency_unresolved")
    if result.deferred_item_ids and not issues:
        issues.append("budget_deferred")
    state = {
        ControlBetaState.READY: ControlFrontierState.READY,
        ControlBetaState.PARTIAL: ControlFrontierState.PARTIAL,
        ControlBetaState.BLOCKED: ControlFrontierState.BLOCKED,
    }.get(result.state, ControlFrontierState.PARTIAL)
    return _result(ControlFrontierOperation.BUDGET_RESOURCE_SCHEDULER, state, issues, result.to_dict())


def _fallback(payload: Mapping[str, Any]) -> ControlFrontierOperationResult:
    request = FallbackRequest.from_mapping(payload.get("request", {}))
    candidates = tuple(FallbackCandidate.from_mapping(item) for item in payload.get("candidates", ()))
    route = DeterministicFallbackRouter().route(request, candidates)
    if route.state is ControlBetaState.SELECTED:
        state = ControlFrontierState.SELECTED
        issues: list[str] = []
    elif not request.retryable:
        state = ControlFrontierState.BLOCKED
        issues = ["non_retryable_failure"]
    else:
        state = ControlFrontierState.ABSTAINED
        issues = ["no_eligible_candidate"]
    return _result(ControlFrontierOperation.DETERMINISTIC_FALLBACK, state, issues, route.to_dict())


def _review(payload: Mapping[str, Any]) -> ControlFrontierOperationResult:
    result = HumanReviewQueueRouter().route(
        payload.get("items", ()),
        required_roles=tuple(str(item) for item in payload.get("required_roles", ())),
        max_review_candidates=int(payload.get("max_review_candidates", 100)),
        queue_id=str(payload.get("queue_id", "control-frontier-queue")),
    )
    issues: list[str] = []
    if result.state is ControlBetaState.BLOCKED:
        issues.append("review_blocker")
    if result.omitted_item_ids:
        issues.append("queue_bounded")
    if result.state is ControlBetaState.EMPTY:
        issues.append("no_review_items")
    state = {
        ControlBetaState.READY: ControlFrontierState.READY,
        ControlBetaState.BLOCKED: ControlFrontierState.BLOCKED,
        ControlBetaState.PARTIAL: ControlFrontierState.PARTIAL,
        ControlBetaState.EMPTY: ControlFrontierState.EMPTY,
    }.get(result.state, ControlFrontierState.PARTIAL)
    return _result(ControlFrontierOperation.HUMAN_REVIEW_ROUTER, state, issues, result.to_dict())


def _ledger(payload: Mapping[str, Any]) -> ControlFrontierOperationResult:
    ledger = EventSourcedExecutionLedger().replay(
        payload.get("events", ()),
        execution_id=str(payload.get("execution_id", "control-frontier-execution")),
        context_key=str(payload.get("context_key", CONTROL_FRONTIER_CONTEXT_KEY)),
    )
    state = {
        RuntimeAlphaState.COMPLETED: ControlFrontierState.COMPLETED,
        RuntimeAlphaState.BLOCKED: ControlFrontierState.BLOCKED,
        RuntimeAlphaState.OUT_OF_DOMAIN: ControlFrontierState.OUT_OF_DOMAIN,
        RuntimeAlphaState.PARTIAL: ControlFrontierState.PARTIAL,
        RuntimeAlphaState.FAILED: ControlFrontierState.FAILED,
        RuntimeAlphaState.REJECTED: ControlFrontierState.REJECTED,
    }.get(ledger.state, ControlFrontierState.PARTIAL)
    issues = [item.code for item in ledger.issues]
    if "context_mismatch" in issues:
        issues = ["context_mismatch"]
        state = ControlFrontierState.OUT_OF_DOMAIN
    return _result(ControlFrontierOperation.EXECUTION_LEDGER, state, issues, ledger.to_dict())


def _model(payload: Mapping[str, Any]) -> ControlFrontierOperationResult:
    query = payload.get("query", {})
    resolution = ModelRegistry.from_mappings(payload.get("records", ())).snapshot.resolve(
        str(query.get("model_id", "")),
        context_key=str(query.get("context_key", CONTROL_FRONTIER_CONTEXT_KEY)),
        version=query.get("version"),
        input_contract=query.get("input_contract"),
        output_contract=query.get("output_contract"),
    )
    state = {
        "compatible": ControlFrontierState.COMPATIBLE,
        "out_of_domain": ControlFrontierState.OUT_OF_DOMAIN,
        "blocked": ControlFrontierState.BLOCKED,
        "partial": ControlFrontierState.PARTIAL,
        "abstained": ControlFrontierState.ABSTAINED,
    }[resolution.state.value]
    return _result(ControlFrontierOperation.MODEL_REGISTRY, state, list(resolution.blockers), resolution.to_dict())


def _reference(payload: Mapping[str, Any]) -> ControlFrontierOperationResult:
    query = payload.get("query", {})
    resolution = DataReferenceRegistry.from_mappings(payload.get("records", ())).snapshot.resolve(
        str(query.get("dataset_id", "")),
        context_key=str(query.get("context_key", CONTROL_FRONTIER_CONTEXT_KEY)),
        version=query.get("version"),
        coordinate_system=query.get("coordinate_system"),
        license_id=query.get("license_id"),
    )
    state = {
        "compatible": ControlFrontierState.COMPATIBLE,
        "out_of_domain": ControlFrontierState.OUT_OF_DOMAIN,
        "blocked": ControlFrontierState.BLOCKED,
        "review_required": ControlFrontierState.REVIEW_REQUIRED,
        "abstained": ControlFrontierState.ABSTAINED,
    }[resolution.state.value]
    return _result(ControlFrontierOperation.DATA_REFERENCE_REGISTRY, state, list(resolution.blockers), resolution.to_dict())


def _drift(payload: Mapping[str, Any]) -> ControlFrontierOperationResult:
    report = DriftAndOODMonitor().evaluate(
        payload.get("observations", ()),
        monitor_id=str(payload.get("monitor_id", "control-frontier-monitor")),
        context_key=str(payload.get("context_key", CONTROL_FRONTIER_CONTEXT_KEY)),
    )
    states = {
        RuntimeAlphaState.READY_FOR_REVIEW: ControlFrontierState.READY,
        RuntimeAlphaState.WATCH: ControlFrontierState.WATCH,
        RuntimeAlphaState.DRIFT: ControlFrontierState.DRIFT,
        RuntimeAlphaState.OUT_OF_DOMAIN: ControlFrontierState.OUT_OF_DOMAIN,
        RuntimeAlphaState.PARTIAL: ControlFrontierState.PARTIAL,
        RuntimeAlphaState.ABSTAINED: ControlFrontierState.ABSTAINED,
    }
    issues = [reason for finding in report.findings for reason in finding.reasons]
    issues.extend(item.code for item in report.issues)
    return _result(ControlFrontierOperation.DRIFT_OOD_MONITOR, states.get(report.state, ControlFrontierState.PARTIAL), issues, report.to_dict())


def run_control_frontier_operation(operation: ControlFrontierOperation | str, payload: Mapping[str, Any]) -> ControlFrontierOperationResult:
    """Dispatch one operation without reading the fixture's expected state."""

    selected = operation if isinstance(operation, ControlFrontierOperation) else ControlFrontierOperation(str(operation))
    require_non_empty(str(selected), "control frontier operation")
    return {
        ControlFrontierOperation.POLICY_CLAIM_GATE: _policy,
        ControlFrontierOperation.BUDGET_RESOURCE_SCHEDULER: _budget,
        ControlFrontierOperation.DETERMINISTIC_FALLBACK: _fallback,
        ControlFrontierOperation.HUMAN_REVIEW_ROUTER: _review,
        ControlFrontierOperation.EXECUTION_LEDGER: _ledger,
        ControlFrontierOperation.MODEL_REGISTRY: _model,
        ControlFrontierOperation.DATA_REFERENCE_REGISTRY: _reference,
        ControlFrontierOperation.DRIFT_OOD_MONITOR: _drift,
    }[selected](payload)


__all__ = ["ControlFrontierOperationResult", "run_control_frontier_operation"]
