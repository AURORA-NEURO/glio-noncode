"""Deep control-plane beta contracts.

The base control plane admits one invocation at a time. This module provides
the next layer of inspectable planning around that boundary:

* policy audits explain every claim, source, data-scope, and privacy decision;
* budget scheduling plans a dependency-aware batch before any handler runs;
* fallback routing chooses only declared deterministic alternatives and keeps
  every rejected candidate reasoned;
* human-review routing turns outcomes into a stable review queue with reasons,
  blockers, source receipts, and bounded output.

These classes are pure projections and planners. They do not execute tools,
mutate evidence, bypass policy, or convert an abstention into a success.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from typing import Any

from .control_plane import (
    AgentSpec,
    ClaimCeiling,
    InvocationRequest,
    InvocationResult,
    InvocationState,
    PolicyClaimGate,
    ToolContract,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .workflow import ResourceEnvelope


class ControlBetaState(StrEnum):
    """State of a control-plane beta projection."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    SELECTED = "selected"
    ABSTAINED = "abstained"
    READY = "ready"
    EMPTY = "empty"


@dataclass(frozen=True, slots=True)
class PolicyClaimAudit:
    """Explain one policy decision without exposing raw sensitive values."""

    request_id: str
    execution_role_id: str
    tool_id: str
    state: ControlBetaState
    allowed: bool
    mission_claim_ceiling: ClaimCeiling
    role_claim_ceiling: ClaimCeiling
    mutation_scope: str
    declared_data_scope: str | None
    source_allowlist_gap: tuple[str, ...]
    sensitive_paths: tuple[str, ...]
    violations: tuple[str, ...]
    warnings: tuple[str, ...]
    policy_version: str
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "request_id",
            "execution_role_id",
            "tool_id",
            "mutation_scope",
            "policy_version",
        ):
            require_non_empty(getattr(self, name), name)
        if self.allowed != (self.state == ControlBetaState.SUPPORTED):
            raise ValidationError("policy audit state and allowed flag disagree")

    @property
    def releaseable(self) -> bool:
        """Whether the request passed the gate; review may still be required."""

        return self.allowed and not self.sensitive_paths

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class PolicyClaimAuditor:
    """Produce a detailed receipt from the canonical policy gate."""

    def __init__(self, gate: PolicyClaimGate | None = None) -> None:
        self.gate = gate or PolicyClaimGate()

    def audit(
        self,
        request: InvocationRequest,
        execution_role: AgentSpec,
        tool: ToolContract,
    ) -> PolicyClaimAudit:
        decision = self.gate.inspect(request, execution_role, tool)
        sensitive = tuple(sorted(PolicyClaimGate._find_sensitive_keys(request.input_payload)))
        source_gap = tuple(
            sorted(set(tool.allowed_source_ids) - set(request.mission.allowed_source_ids))
        )
        declared_scope = request.input_payload.get("data_scope")
        state = ControlBetaState.SUPPORTED if decision.allowed else ControlBetaState.BLOCKED
        body = {
            "request_id": request.request_id,
            "execution_role_id": execution_role.agent_id,
            "tool_id": tool.tool_id,
            "state": state,
            "allowed": decision.allowed,
            "mission_claim_ceiling": request.mission.claim_ceiling,
            "role_claim_ceiling": execution_role.claim_ceiling,
            "mutation_scope": tool.mutation_scope,
            "declared_data_scope": str(declared_scope) if declared_scope is not None else None,
            "source_allowlist_gap": source_gap,
            "sensitive_paths": sensitive,
            "violations": decision.violations,
            "warnings": decision.warnings,
            "policy_version": decision.policy_version,
        }
        return PolicyClaimAudit(
            request_id=request.request_id,
            execution_role_id=execution_role.agent_id,
            tool_id=tool.tool_id,
            state=state,
            allowed=decision.allowed,
            mission_claim_ceiling=request.mission.claim_ceiling,
            role_claim_ceiling=execution_role.claim_ceiling,
            mutation_scope=tool.mutation_scope,
            declared_data_scope=str(declared_scope) if declared_scope is not None else None,
            source_allowlist_gap=source_gap,
            sensitive_paths=sensitive,
            violations=decision.violations,
            warnings=decision.warnings,
            policy_version=decision.policy_version,
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class BudgetWorkItem:
    """One dependency-aware unit considered by the batch scheduler."""

    item_id: str
    resource: ResourceEnvelope = field(default_factory=ResourceEnvelope)
    cost_units: float = 1.0
    priority: int = 0
    depends_on: tuple[str, ...] = ()
    network_egress: bool = False
    optional: bool = False
    output_contract: str = "unspecified"
    source_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_non_empty(self.item_id, "budget item_id")
        if not isfinite(self.cost_units) or self.cost_units <= 0:
            raise ValidationError("budget item cost_units must be finite and positive")
        if len(self.depends_on) != len(set(self.depends_on)):
            raise ValidationError("budget item dependencies must be unique")
        if self.item_id in self.depends_on:
            raise ValidationError("budget item cannot depend on itself")
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValidationError("budget item source IDs must be unique")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> BudgetWorkItem:
        resource = value.get("resource", {})
        if not isinstance(resource, Mapping):
            raise ValidationError("budget item resource must be a mapping")
        return cls(
            item_id=str(value.get("item_id", value.get("id", ""))),
            resource=ResourceEnvelope(
                cpu=float(resource.get("cpu", 1.0)),
                memory_gb=float(resource.get("memory_gb", 1.0)),
                gpu_count=int(resource.get("gpu_count", 0)),
                storage_gb=float(resource.get("storage_gb", 1.0)),
                network_egress=bool(
                    resource.get("network_egress", value.get("network_egress", False))
                ),
                max_seconds=int(resource.get("max_seconds", 300)),
            ),
            cost_units=float(value.get("cost_units", 1.0)),
            priority=int(value.get("priority", 0)),
            depends_on=tuple(str(item) for item in value.get("depends_on", ())),
            network_egress=bool(value.get("network_egress", False)),
            optional=bool(value.get("optional", False)),
            output_contract=str(value.get("output_contract", "unspecified")),
            source_ids=tuple(str(item) for item in value.get("source_ids", ())),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BudgetScheduleResult:
    """Deterministic batch admission result with consumption accounting."""

    schedule_id: str
    state: ControlBetaState
    admitted_item_ids: tuple[str, ...]
    deferred_item_ids: tuple[str, ...]
    rejected_item_ids: tuple[str, ...]
    reasons: Mapping[str, str]
    total_cost_units: float
    total_seconds: int
    network_requests: int
    peak_resource: ResourceEnvelope
    remaining_invocations: int
    remaining_network_requests: int
    remaining_seconds: int
    remaining_cost_units: float
    warnings: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        all_ids = (
            *self.admitted_item_ids,
            *self.deferred_item_ids,
            *self.rejected_item_ids,
        )
        if len(all_ids) != len(set(all_ids)):
            raise ValidationError("budget schedule item IDs cannot appear in multiple states")
        if (
            min(
                self.remaining_invocations,
                self.remaining_network_requests,
                self.remaining_seconds,
            )
            < 0
        ):
            raise ValidationError("budget schedule remaining counters cannot be negative")
        if self.remaining_cost_units < -1e-9:
            raise ValidationError("budget schedule remaining cost cannot be negative")

    @property
    def complete(self) -> bool:
        return self.state == ControlBetaState.READY and not self.deferred_item_ids

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class BudgetResourceScheduler:
    """Plan a dependency-safe batch against bounded mission resources."""

    def schedule(
        self,
        items: Iterable[BudgetWorkItem | Mapping[str, Any]],
        *,
        max_invocations: int,
        max_network_requests: int,
        max_seconds: int,
        max_cost_units: float,
        capacity: ResourceEnvelope,
        schedule_id: str = "budget-schedule",
    ) -> BudgetScheduleResult:
        require_non_empty(schedule_id, "schedule_id")
        if max_invocations < 1 or max_network_requests < 0 or max_seconds < 1:
            raise ValidationError("budget limits are outside the useful range")
        if not isfinite(max_cost_units) or max_cost_units <= 0:
            raise ValidationError("max_cost_units must be finite and positive")
        values = tuple(
            item if isinstance(item, BudgetWorkItem) else BudgetWorkItem.from_mapping(item)
            for item in items
        )
        if len({item.item_id for item in values}) != len(values):
            raise ValidationError("budget item IDs must be unique")
        by_id = {item.item_id: item for item in values}
        for item in values:
            unknown = tuple(sorted(set(item.depends_on) - set(by_id)))
            if unknown:
                raise ValidationError(
                    f"budget item {item.item_id} depends on unknown item(s): {unknown}"
                )
        order = self._topological_priority_order(values)
        admitted: list[str] = []
        deferred: list[str] = []
        rejected: list[str] = []
        reasons: dict[str, str] = {}
        total_cost = 0.0
        total_seconds = 0
        network_requests = 0
        peak = ResourceEnvelope(
            cpu=0.000001,
            memory_gb=0.000001,
            gpu_count=0,
            storage_gb=0.000001,
            network_egress=False,
            max_seconds=1,
        )
        for item in order:
            failed_dependencies = tuple(
                dependency for dependency in item.depends_on if dependency not in admitted
            )
            if failed_dependencies:
                deferred.append(item.item_id)
                reasons[item.item_id] = "dependency was not admitted: " + ", ".join(
                    failed_dependencies
                )
                continue
            network = item.network_egress or item.resource.network_egress
            if not item.resource.fits(capacity):
                rejected.append(item.item_id)
                reasons[item.item_id] = "resource envelope exceeds declared capacity"
                continue
            if len(admitted) >= max_invocations:
                deferred.append(item.item_id)
                reasons[item.item_id] = "invocation budget exhausted"
                continue
            if network and network_requests >= max_network_requests:
                deferred.append(item.item_id)
                reasons[item.item_id] = "network request budget exhausted"
                continue
            if total_seconds + item.resource.max_seconds > max_seconds:
                deferred.append(item.item_id)
                reasons[item.item_id] = "wall-time budget exhausted"
                continue
            if total_cost + item.cost_units > max_cost_units:
                deferred.append(item.item_id)
                reasons[item.item_id] = "cost budget exhausted"
                continue
            admitted.append(item.item_id)
            total_cost = round(total_cost + item.cost_units, 9)
            total_seconds += item.resource.max_seconds
            network_requests += int(network)
            peak = self._peak(peak, item.resource, network)
        warnings: list[str] = [
            "Budget scheduling is a deterministic plan; admission does not execute any item.",
            "Deferred optional work remains visible and is not treated as a negative result.",
        ]
        if rejected:
            warnings.append("At least one item is permanently rejected by capacity constraints.")
        if deferred:
            warnings.append("At least one item is deferred by dependency or mission budget limits.")
        if not values:
            state = ControlBetaState.ABSTAINED
        elif not admitted:
            state = ControlBetaState.ABSTAINED
        elif rejected or deferred:
            state = ControlBetaState.PARTIAL
        else:
            state = ControlBetaState.READY
        body = {
            "schedule_id": schedule_id,
            "state": state,
            "admitted_item_ids": admitted,
            "deferred_item_ids": deferred,
            "rejected_item_ids": rejected,
            "reasons": reasons,
            "total_cost_units": total_cost,
            "total_seconds": total_seconds,
            "network_requests": network_requests,
            "peak_resource": peak,
            "warnings": warnings,
        }
        return BudgetScheduleResult(
            schedule_id=schedule_id,
            state=state,
            admitted_item_ids=tuple(admitted),
            deferred_item_ids=tuple(deferred),
            rejected_item_ids=tuple(rejected),
            reasons=reasons,
            total_cost_units=total_cost,
            total_seconds=total_seconds,
            network_requests=network_requests,
            peak_resource=peak,
            remaining_invocations=max_invocations - len(admitted),
            remaining_network_requests=max_network_requests - network_requests,
            remaining_seconds=max_seconds - total_seconds,
            remaining_cost_units=round(max_cost_units - total_cost, 9),
            warnings=tuple(dict.fromkeys(warnings)),
            content_address=content_hash(body),
        )

    @staticmethod
    def _topological_priority_order(items: Sequence[BudgetWorkItem]) -> tuple[BudgetWorkItem, ...]:
        by_id = {item.item_id: item for item in items}
        indegree = {item.item_id: len(item.depends_on) for item in items}
        children: dict[str, list[str]] = {item.item_id: [] for item in items}
        for item in items:
            for dependency in item.depends_on:
                children[dependency].append(item.item_id)
        ready = [item for item in items if indegree[item.item_id] == 0]
        ordered: list[BudgetWorkItem] = []
        while ready:
            ready.sort(key=lambda item: (-item.priority, item.item_id))
            current = ready.pop(0)
            ordered.append(current)
            for child_id in sorted(children[current.item_id]):
                indegree[child_id] -= 1
                if indegree[child_id] == 0:
                    ready.append(by_id[child_id])
        if len(ordered) != len(items):
            raise ValidationError("budget item dependencies contain a cycle")
        return tuple(ordered)

    @staticmethod
    def _peak(
        current: ResourceEnvelope,
        item: ResourceEnvelope,
        network: bool,
    ) -> ResourceEnvelope:
        return ResourceEnvelope(
            cpu=max(current.cpu, item.cpu),
            memory_gb=max(current.memory_gb, item.memory_gb),
            gpu_count=max(current.gpu_count, item.gpu_count),
            storage_gb=max(current.storage_gb, item.storage_gb),
            network_egress=current.network_egress or network,
            max_seconds=max(current.max_seconds, item.max_seconds),
        )


@dataclass(frozen=True, slots=True)
class FallbackCandidate:
    """A declared alternate operation eligible for deterministic routing."""

    candidate_id: str
    operation_id: str
    priority: int = 0
    deterministic: bool = True
    network_egress: bool = False
    required_inputs: tuple[str, ...] = ()
    output_contract: str = "unspecified"
    cost_units: float = 1.0
    source_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("candidate_id", "operation_id", "output_contract"):
            require_non_empty(getattr(self, name), name)
        if self.cost_units <= 0 or not isfinite(self.cost_units):
            raise ValidationError("fallback cost_units must be finite and positive")
        if len(self.required_inputs) != len(set(self.required_inputs)):
            raise ValidationError("fallback required inputs must be unique")
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValidationError("fallback source IDs must be unique")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> FallbackCandidate:
        return cls(
            candidate_id=str(value.get("candidate_id", value.get("id", ""))),
            operation_id=str(value.get("operation_id", value.get("operation", ""))),
            priority=int(value.get("priority", 0)),
            deterministic=bool(value.get("deterministic", True)),
            network_egress=bool(value.get("network_egress", False)),
            required_inputs=tuple(str(item) for item in value.get("required_inputs", ())),
            output_contract=str(value.get("output_contract", "unspecified")),
            cost_units=float(value.get("cost_units", 1.0)),
            source_ids=tuple(str(item) for item in value.get("source_ids", ())),
            limitations=tuple(str(item) for item in value.get("limitations", ())),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FallbackRequest:
    """Failure context supplied to the deterministic alternate router."""

    request_id: str
    failed_operation_id: str
    failure_code: str
    retryable: bool
    available_inputs: tuple[str, ...] = ()
    network_allowed: bool = False
    require_deterministic: bool = True
    requested_output_contract: str | None = None
    remaining_cost_units: float = 1_000_000_000.0

    def __post_init__(self) -> None:
        for name in ("request_id", "failed_operation_id", "failure_code"):
            require_non_empty(getattr(self, name), name)
        if self.remaining_cost_units < 0 or not isfinite(self.remaining_cost_units):
            raise ValidationError("fallback remaining_cost_units must be finite and non-negative")
        if len(self.available_inputs) != len(set(self.available_inputs)):
            raise ValidationError("fallback available inputs must be unique")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> FallbackRequest:
        return cls(
            request_id=str(value.get("request_id", "fallback-request")),
            failed_operation_id=str(
                value.get("failed_operation_id", value.get("operation_id", ""))
            ),
            failure_code=str(value.get("failure_code", "failure")),
            retryable=bool(value.get("retryable", False)),
            available_inputs=tuple(str(item) for item in value.get("available_inputs", ())),
            network_allowed=bool(value.get("network_allowed", False)),
            require_deterministic=bool(value.get("require_deterministic", True)),
            requested_output_contract=(
                str(value["requested_output_contract"])
                if value.get("requested_output_contract") is not None
                else None
            ),
            remaining_cost_units=float(value.get("remaining_cost_units", 0.0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FallbackRoute:
    """Selected alternate or explicit review/abstention outcome."""

    request_id: str
    state: ControlBetaState
    selected_candidate_id: str | None
    attempted_candidate_ids: tuple[str, ...]
    rejected_candidates: Mapping[str, str]
    reason: str
    warnings: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.request_id, "fallback route request_id")
        require_non_empty(self.reason, "fallback route reason")
        if (
            self.selected_candidate_id is not None
            and self.selected_candidate_id not in self.attempted_candidate_ids
        ):
            raise ValidationError("selected fallback candidate must be attempted")

    @property
    def requires_review(self) -> bool:
        return self.state in {ControlBetaState.ABSTAINED, ControlBetaState.BLOCKED}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class DeterministicFallbackRouter:
    """Select the first eligible declared alternate in stable order."""

    def route(
        self,
        request: FallbackRequest | Mapping[str, Any],
        candidates: Iterable[FallbackCandidate | Mapping[str, Any]],
    ) -> FallbackRoute:
        request = (
            request
            if isinstance(request, FallbackRequest)
            else FallbackRequest.from_mapping(request)
        )
        values = tuple(
            candidate
            if isinstance(candidate, FallbackCandidate)
            else FallbackCandidate.from_mapping(candidate)
            for candidate in candidates
        )
        if len({candidate.candidate_id for candidate in values}) != len(values):
            raise ValidationError("fallback candidate IDs must be unique")
        ordered = tuple(sorted(values, key=lambda item: (-item.priority, item.candidate_id)))
        attempted = tuple(candidate.candidate_id for candidate in ordered)
        rejected: dict[str, str] = {}
        if not request.retryable:
            warnings = ("Non-retryable failures remain blocked for human review.",)
            return self._result(
                request,
                ControlBetaState.BLOCKED,
                None,
                attempted,
                rejected,
                "failure is not declared retryable; no alternate was selected",
                warnings,
            )
        for candidate in ordered:
            if candidate.operation_id == request.failed_operation_id:
                rejected[candidate.candidate_id] = "candidate repeats the failed operation"
                continue
            if request.require_deterministic and not candidate.deterministic:
                rejected[candidate.candidate_id] = "candidate is not deterministic"
                continue
            if candidate.network_egress and not request.network_allowed:
                rejected[candidate.candidate_id] = "candidate requires network access"
                continue
            missing = tuple(sorted(set(candidate.required_inputs) - set(request.available_inputs)))
            if missing:
                rejected[candidate.candidate_id] = "missing inputs: " + ", ".join(missing)
                continue
            if (
                request.requested_output_contract is not None
                and candidate.output_contract != request.requested_output_contract
            ):
                rejected[candidate.candidate_id] = "output contract does not match request"
                continue
            if candidate.cost_units > request.remaining_cost_units:
                rejected[candidate.candidate_id] = "candidate exceeds remaining cost budget"
                continue
            return self._result(
                request,
                ControlBetaState.SELECTED,
                candidate.candidate_id,
                attempted,
                rejected,
                "highest-priority eligible deterministic alternate selected",
                (
                    "Fallback selection is a declared execution route; it does not repair or "
                    "reinterpret the failed result.",
                ),
            )
        return self._result(
            request,
            ControlBetaState.ABSTAINED,
            None,
            attempted,
            rejected,
            "no declared fallback candidate satisfied the request constraints",
            ("No alternate was selected; collect missing inputs or route the failure for review.",),
        )

    @staticmethod
    def _result(
        request: FallbackRequest,
        state: ControlBetaState,
        selected: str | None,
        attempted: tuple[str, ...],
        rejected: Mapping[str, str],
        reason: str,
        warnings: tuple[str, ...],
    ) -> FallbackRoute:
        body = {
            "request_id": request.request_id,
            "state": state,
            "selected_candidate_id": selected,
            "attempted_candidate_ids": attempted,
            "rejected_candidates": rejected,
            "reason": reason,
            "warnings": warnings,
        }
        return FallbackRoute(
            request_id=request.request_id,
            state=state,
            selected_candidate_id=selected,
            attempted_candidate_ids=attempted,
            rejected_candidates=dict(rejected),
            reason=reason,
            warnings=warnings,
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class ReviewWorkItem:
    """One outcome eligible for a bounded human-review queue."""

    item_id: str
    request_id: str
    execution_role_id: str
    tool_id: str
    state: InvocationState
    reasons: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    reviewer_roles: tuple[str, ...] = ()
    priority: int = 0
    source_ids: tuple[str, ...] = ()
    summary: str = ""
    requires_review: bool = True

    def __post_init__(self) -> None:
        for name in ("item_id", "request_id", "execution_role_id", "tool_id"):
            require_non_empty(getattr(self, name), name)
        if len(self.reasons) != len(set(self.reasons)):
            raise ValidationError("review work item reasons must be unique")
        if len(self.blockers) != len(set(self.blockers)):
            raise ValidationError("review work item blockers must be unique")
        if len(self.reviewer_roles) != len(set(self.reviewer_roles)):
            raise ValidationError("review work item reviewer roles must be unique")
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValidationError("review work item source IDs must be unique")

    @classmethod
    def from_invocation(cls, result: InvocationResult) -> ReviewWorkItem:
        reasons: list[str] = []
        blockers: list[str] = []
        roles: list[str] = []
        if result.review_route is not None:
            reasons.extend(result.review_route.reasons)
            if result.review_route.blocked:
                blockers.append("review_route_blocked")
            if result.review_route.required:
                roles.append("domain_expert")
        if result.error is not None:
            reasons.append(result.error.code)
            if not result.error.retryable:
                blockers.append("non_retryable_error")
        if result.state == InvocationState.ABSTAINED:
            reasons.append("abstention_requires_review")
            blockers.append("abstention")
        if result.state == InvocationState.REJECTED:
            reasons.append("policy_or_resource_rejection")
        return cls(
            item_id=result.request_id,
            request_id=result.request_id,
            execution_role_id=result.agent_id,
            tool_id=result.tool_id,
            state=result.state,
            reasons=tuple(dict.fromkeys(reasons)),
            blockers=tuple(dict.fromkeys(blockers)),
            reviewer_roles=tuple(dict.fromkeys(roles)),
            priority=90 if blockers else 70 if reasons else 10,
            requires_review=bool(reasons or blockers),
            summary=(result.error.message if result.error is not None else "invocation outcome"),
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ReviewWorkItem:
        return cls(
            item_id=str(value.get("item_id", value.get("request_id", ""))),
            request_id=str(value.get("request_id", "")),
            execution_role_id=str(value.get("execution_role_id", value.get("role_id", ""))),
            tool_id=str(value.get("tool_id", "")),
            state=InvocationState(str(value.get("state", InvocationState.ABSTAINED.value))),
            reasons=tuple(str(item) for item in value.get("reasons", ())),
            blockers=tuple(str(item) for item in value.get("blockers", ())),
            reviewer_roles=tuple(str(item) for item in value.get("reviewer_roles", ())),
            priority=int(value.get("priority", 0)),
            source_ids=tuple(str(item) for item in value.get("source_ids", ())),
            summary=str(value.get("summary", "")),
            requires_review=bool(value.get("requires_review", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewAssignment:
    """Stable queue row with explicit role routing and blockers."""

    item_id: str
    request_id: str
    execution_role_id: str
    tool_id: str
    priority: int
    reviewer_roles: tuple[str, ...]
    reasons: tuple[str, ...]
    blockers: tuple[str, ...]
    source_ids: tuple[str, ...]
    summary: str
    state: InvocationState
    blocked: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewQueueResult:
    """Bounded human-review queue projection."""

    queue_id: str
    state: ControlBetaState
    assignments: tuple[ReviewAssignment, ...]
    omitted_item_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        ids = tuple(item.item_id for item in self.assignments)
        if len(ids) != len(set(ids)):
            raise ValidationError("review queue assignment IDs must be unique")

    @property
    def requires_human_action(self) -> bool:
        return bool(self.assignments)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class HumanReviewQueueRouter:
    """Route only declared review-required outcomes into a stable queue."""

    def route(
        self,
        items: Iterable[ReviewWorkItem | Mapping[str, Any]],
        *,
        required_roles: Sequence[str] = (),
        max_review_candidates: int = 100,
        queue_id: str = "human-review-queue",
    ) -> ReviewQueueResult:
        require_non_empty(queue_id, "queue_id")
        if max_review_candidates < 1 or max_review_candidates > 10_000:
            raise ValidationError("max_review_candidates is outside the bounded range")
        roles = tuple(dict.fromkeys(str(role) for role in required_roles))
        if any(not role.strip() for role in roles):
            raise ValidationError("required reviewer roles cannot be blank")
        values = tuple(
            item if isinstance(item, ReviewWorkItem) else ReviewWorkItem.from_mapping(item)
            for item in items
        )
        if len({item.item_id for item in values}) != len(values):
            raise ValidationError("review work item IDs must be unique")
        reviewable = tuple(item for item in values if item.requires_review)
        ordered = tuple(
            sorted(
                reviewable,
                key=lambda item: (-item.priority, item.item_id, item.request_id),
            )
        )
        kept = ordered[:max_review_candidates]
        omitted = tuple(item.item_id for item in ordered[max_review_candidates:])
        assignments = tuple(self._assignment(item, roles) for item in kept)
        warnings: list[str] = [
            "Review routing creates a queue; it does not adjudicate or release a result.",
            "Blocked and abstained outcomes remain blocked until a reviewer records a decision.",
        ]
        if omitted:
            warnings.append(
                "Review queue was bounded; omitted candidates remain in the source ledger."
            )
        if any(assignment.blocked for assignment in assignments):
            warnings.append("At least one queued item has an explicit blocker.")
        state = (
            ControlBetaState.EMPTY
            if not assignments
            else ControlBetaState.BLOCKED
            if any(assignment.blocked for assignment in assignments)
            else ControlBetaState.PARTIAL
            if omitted
            else ControlBetaState.READY
        )
        body = {
            "queue_id": queue_id,
            "state": state,
            "assignments": assignments,
            "omitted_item_ids": omitted,
            "warnings": warnings,
        }
        return ReviewQueueResult(
            queue_id=queue_id,
            state=state,
            assignments=assignments,
            omitted_item_ids=omitted,
            warnings=tuple(dict.fromkeys(warnings)),
            content_address=content_hash(body),
        )

    @staticmethod
    def _assignment(item: ReviewWorkItem, required_roles: Sequence[str]) -> ReviewAssignment:
        roles = tuple(dict.fromkeys((*item.reviewer_roles, *required_roles)))
        if not roles:
            roles = ("domain_expert",)
        reasons = item.reasons or ("explicit_review_required",)
        return ReviewAssignment(
            item_id=item.item_id,
            request_id=item.request_id,
            execution_role_id=item.execution_role_id,
            tool_id=item.tool_id,
            priority=item.priority,
            reviewer_roles=roles,
            reasons=reasons,
            blockers=item.blockers,
            source_ids=item.source_ids,
            summary=item.summary,
            state=item.state,
            blocked=bool(item.blockers),
        )


__all__ = [
    "BudgetResourceScheduler",
    "BudgetScheduleResult",
    "BudgetWorkItem",
    "ControlBetaState",
    "DeterministicFallbackRouter",
    "FallbackCandidate",
    "FallbackRequest",
    "FallbackRoute",
    "HumanReviewQueueRouter",
    "PolicyClaimAudit",
    "PolicyClaimAuditor",
    "ReviewAssignment",
    "ReviewQueueResult",
    "ReviewWorkItem",
]
