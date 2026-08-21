"""Typed mission planning, workflow compilation, and execution isolation.

Domain 16 exposes a small runtime facade over the existing control-plane
contracts. A mission plan combines dependency expansion with a topologically
compiled workflow. The registry facade exposes only declared tool contracts,
and the execution sandbox accepts only handlers registered for allowlisted
tools. Policy, resource, provenance, event, and idempotency checks remain in
the underlying executor; this module packages their results for callers.

The runtime is a research workflow boundary. It does not authorize clinical
claims, hide an abstention, or make an arbitrary callable registry available to
the caller.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from .control_plane import (
    AgentSpec,
    ControlOutput,
    ControlPlaneExecutor,
    ControlPlaneRegistry,
    InvocationRequest,
    InvocationResult,
    InvocationState,
    MissionContext,
    MissionPlanner,
    ToolContract,
    WorkflowDecision,
    default_control_plane_registry,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .workflow import CompiledWorkflow, WorkflowCompiler, WorkflowStep


class MissionPlanState(StrEnum):
    """State of a planned mission before any tool handler is executed."""

    PLANNED = "planned"
    PARTIAL = "partial"
    ABSTAINED = "abstained"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class MissionRequest:
    """Bounded planning input with explicit requested roles and workflow steps."""

    mission: MissionContext
    requested_agent_ids: tuple[str, ...]
    workflow_id: str = "mission-workflow"
    workflow_steps: tuple[WorkflowStep, ...] = ()

    def __post_init__(self) -> None:
        require_non_empty(self.workflow_id, "workflow_id")
        if len(self.requested_agent_ids) != len(set(self.requested_agent_ids)):
            raise ValidationError("requested agent IDs must be unique")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MissionPlan:
    """Replayable mission decision and compiled workflow snapshot."""

    plan_id: str
    mission_id: str
    state: MissionPlanState
    decision: WorkflowDecision
    workflow: CompiledWorkflow | None
    selected_agent_ids: tuple[str, ...]
    selected_tool_ids: tuple[str, ...]
    registry_address: str
    warnings: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.plan_id, "plan_id")
        require_non_empty(self.mission_id, "mission_id")
        require_non_empty(self.registry_address, "registry_address")
        if self.state == MissionPlanState.PLANNED and self.workflow is None:
            raise ValidationError("planned mission requires a compiled workflow")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class MissionPlanBuilder:
    """Expand dependencies and compile an explicit workflow graph."""

    def __init__(
        self,
        registry: ControlPlaneRegistry | None = None,
        compiler: WorkflowCompiler | None = None,
    ) -> None:
        self.registry = registry or default_control_plane_registry()
        self.compiler = compiler or WorkflowCompiler()
        self.planner = MissionPlanner(self.registry)

    def plan(self, request: MissionRequest) -> MissionPlan:
        decision = self.planner.plan(request.mission, request.requested_agent_ids)
        registry_address = content_hash(self.registry.manifest())
        if decision.abstained:
            body = {
                "mission_id": request.mission.mission_id,
                "decision": decision,
                "registry_address": registry_address,
                "state": MissionPlanState.ABSTAINED,
            }
            return MissionPlan(
                plan_id="plan-" + content_hash(body).split(":", 1)[1][:20],
                mission_id=request.mission.mission_id,
                state=MissionPlanState.ABSTAINED,
                decision=decision,
                workflow=None,
                selected_agent_ids=(),
                selected_tool_ids=(),
                registry_address=registry_address,
                warnings=decision.warnings,
                content_address=content_hash(body),
            )
        workflow = self.compiler.compile(
            request.workflow_id,
            request.workflow_steps or self._default_steps(request.workflow_id),
        )
        warnings = tuple(dict.fromkeys(decision.warnings + workflow.warnings))
        state = (
            MissionPlanState.PARTIAL
            if warnings or decision.requires_human_review
            else MissionPlanState.PLANNED
        )
        body = {
            "mission_id": request.mission.mission_id,
            "decision": decision,
            "workflow": workflow,
            "registry_address": registry_address,
            "state": state,
            "warnings": warnings,
        }
        return MissionPlan(
            plan_id="plan-" + content_hash(body).split(":", 1)[1][:20],
            mission_id=request.mission.mission_id,
            state=state,
            decision=decision,
            workflow=workflow,
            selected_agent_ids=decision.selected_agent_ids,
            selected_tool_ids=decision.selected_tool_ids,
            registry_address=registry_address,
            warnings=warnings,
            content_address=content_hash(body),
        )

    @staticmethod
    def _default_steps(workflow_id: str) -> tuple[WorkflowStep, ...]:
        compiler = WorkflowCompiler()
        return compiler.compile_initial_slice(workflow_id).steps


@dataclass(frozen=True, slots=True)
class ToolDescriptor:
    """Read-only typed view of a registered tool contract."""

    tool_id: str
    owner_agent_id: str
    name: str
    input_contract: str
    output_contract: str
    safety_class: str
    deterministic: bool
    network_egress: bool
    mutation_scope: str
    requires_human_review: bool
    allowed_source_ids: tuple[str, ...]

    @classmethod
    def from_contract(cls, contract: ToolContract) -> ToolDescriptor:
        return cls(
            tool_id=contract.tool_id,
            owner_agent_id=contract.owner_agent_id,
            name=contract.name,
            input_contract=contract.input_contract,
            output_contract=contract.output_contract,
            safety_class=contract.safety_class.value,
            deterministic=contract.deterministic,
            network_egress=contract.network_egress,
            mutation_scope=contract.mutation_scope,
            requires_human_review=contract.requires_human_review,
            allowed_source_ids=contract.allowed_source_ids,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class TypedToolRegistry:
    """Expose contract metadata and owner checks without arbitrary lookup."""

    def __init__(self, registry: ControlPlaneRegistry | None = None) -> None:
        self.registry = registry or default_control_plane_registry()
        self.registry.validate()

    def resolve(self, tool_id: str, *, owner_agent_id: str | None = None) -> ToolDescriptor:
        contract = self.registry.tool(tool_id)
        if owner_agent_id is not None and contract.owner_agent_id != owner_agent_id:
            raise ValidationError(f"tool {tool_id} is not owned by {owner_agent_id}")
        return ToolDescriptor.from_contract(contract)

    def resolve_agent(self, agent_id: str) -> AgentSpec:
        return self.registry.agent(agent_id)

    def tools_for_agent(self, agent_id: str) -> tuple[ToolDescriptor, ...]:
        agent = self.resolve_agent(agent_id)
        return tuple(
            self.resolve(tool_id, owner_agent_id=agent_id) for tool_id in agent.allowed_tool_ids
        )

    def list(self, *, owner_agent_id: str | None = None) -> tuple[ToolDescriptor, ...]:
        contracts = self.registry.tools()
        if owner_agent_id is not None:
            contracts = tuple(item for item in contracts if item.owner_agent_id == owner_agent_id)
        return tuple(ToolDescriptor.from_contract(item) for item in contracts)

    def manifest(self) -> dict[str, Any]:
        tools = self.list()
        body = {"registry": self.registry.manifest(), "typed_tools": tools}
        return body | {"content_address": content_hash(body)}


@dataclass(frozen=True, slots=True)
class SandboxIsolation:
    """Explicit process-boundary assumptions for a sandbox invocation."""

    workspace_root: str
    allow_network: bool = False
    allowed_source_ids: tuple[str, ...] = ()
    allow_dynamic_imports: bool = False
    allow_external_processes: bool = False

    def __post_init__(self) -> None:
        require_non_empty(self.workspace_root, "workspace_root")
        if self.allow_network and not self.allowed_source_ids:
            raise ValidationError("network-enabled sandbox requires an explicit source allowlist")
        if self.allow_dynamic_imports or self.allow_external_processes:
            raise ValidationError("dynamic imports and external processes are not permitted")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SandboxAdmission:
    """Non-mutating sandbox admission result."""

    admitted: bool
    reason: str
    tool: ToolDescriptor | None
    isolation: SandboxIsolation
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SandboxRun:
    """Execution result retaining admission, typed response, and replay facts."""

    request_id: str
    state: InvocationState
    admission: SandboxAdmission
    result: InvocationResult | None
    response_type: str | None
    cached: bool
    event_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ControlHandler(Protocol):
    def __call__(self, request: InvocationRequest) -> ControlOutput: ...


class ExecutionSandbox:
    """Register-only execution wrapper around the policy-gated executor."""

    def __init__(
        self,
        registry: ControlPlaneRegistry | None = None,
        *,
        isolation: SandboxIsolation | None = None,
        executor: ControlPlaneExecutor | None = None,
    ) -> None:
        self.registry = registry or default_control_plane_registry()
        self.isolation = isolation or SandboxIsolation(workspace_root=".glio/sandbox")
        self.executor = executor or ControlPlaneExecutor(self.registry)
        self._registered_tool_ids: set[str] = set()

    def register(self, tool_id: str, handler: ControlHandler) -> ToolDescriptor:
        descriptor = TypedToolRegistry(self.registry).resolve(tool_id)
        if descriptor.network_egress and not self.isolation.allow_network:
            raise ValidationError(
                f"network tool cannot be registered in a local-only sandbox: {tool_id}"
            )
        if descriptor.network_egress and not set(descriptor.allowed_source_ids).issubset(
            set(self.isolation.allowed_source_ids)
        ):
            raise ValidationError(f"tool sources exceed sandbox allowlist: {tool_id}")
        self.executor.register(tool_id, handler)
        self._registered_tool_ids.add(tool_id)
        return descriptor

    def admit(self, request: InvocationRequest) -> SandboxAdmission:
        descriptor = TypedToolRegistry(self.registry).resolve(
            request.tool_id,
            owner_agent_id=request.agent_id,
        )
        reasons: list[str] = []
        if descriptor.network_egress and not self.isolation.allow_network:
            reasons.append("network egress is disabled by sandbox isolation")
        if descriptor.network_egress and not set(descriptor.allowed_source_ids).issubset(
            set(self.isolation.allowed_source_ids)
        ):
            reasons.append("tool source allowlist exceeds sandbox isolation")
        if request.tool_id not in self._registered_tool_ids:
            reasons.append("no handler is registered for the typed tool contract")
        allowed = not reasons
        body = {
            "request_id": request.request_id,
            "tool": descriptor,
            "isolation": self.isolation,
            "admitted": allowed,
            "reasons": tuple(reasons),
        }
        return SandboxAdmission(
            admitted=allowed,
            reason="admitted" if allowed else "; ".join(reasons),
            tool=descriptor,
            isolation=self.isolation,
            content_address=content_hash(body),
        )

    def execute(self, request: InvocationRequest) -> SandboxRun:
        admission = self.admit(request)
        if not admission.admitted:
            return self._run(
                request, admission, None, InvocationState.REJECTED, (admission.reason,)
            )
        result = self.executor.execute(request)
        response_type = type(result.response).__name__ if result.response is not None else None
        return self._run(
            request,
            admission,
            result,
            result.state,
            result.review_route.reasons if result.review_route is not None else (),
            response_type=response_type,
        )

    @staticmethod
    def _run(
        request: InvocationRequest,
        admission: SandboxAdmission,
        result: InvocationResult | None,
        state: InvocationState,
        warnings: Iterable[str],
        *,
        response_type: str | None = None,
    ) -> SandboxRun:
        event_ids = result.event_ids if result is not None else ()
        cached = result.cached if result is not None else False
        body = {
            "request_id": request.request_id,
            "state": state,
            "admission": admission,
            "result": result,
            "response_type": response_type,
            "cached": cached,
            "event_ids": event_ids,
            "warnings": tuple(warnings),
        }
        return SandboxRun(
            request_id=request.request_id,
            state=state,
            admission=admission,
            result=result,
            response_type=response_type,
            cached=cached,
            event_ids=event_ids,
            warnings=tuple(warnings),
            content_address=content_hash(body),
        )


def default_mission_request(
    *,
    mission_id: str = "mission-default",
    project_id: str = "glio-noncode",
    requested_agent_ids: tuple[str, ...] = ("A07", "A08", "A20", "A31"),
) -> MissionRequest:
    """Create a bounded synthetic/public-reference planning example."""

    mission = MissionContext(
        mission_id=mission_id,
        project_id=project_id,
        intended_use="research hypothesis exploration",
        requested_question="Which declared regulatory observations warrant review?",
        allowed_data_scopes=("synthetic", "public_reference"),
        allowed_mutations=("none", "event_log", "content_addressed_store"),
    )
    return MissionRequest(mission=mission, requested_agent_ids=requested_agent_ids)


__all__ = [
    "ExecutionSandbox",
    "MissionPlan",
    "MissionPlanBuilder",
    "MissionPlanState",
    "MissionRequest",
    "SandboxAdmission",
    "SandboxIsolation",
    "SandboxRun",
    "ToolDescriptor",
    "TypedToolRegistry",
    "default_mission_request",
]
