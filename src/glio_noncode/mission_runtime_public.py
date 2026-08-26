"""Public, addressed projections for the typed mission runtime.

The control-plane runtime needs internal routing identifiers to perform owner
and dependency checks. Those identifiers are implementation inputs, not part of
the public mission receipt. This module establishes the separate public
boundary: a caller can inspect mission state, workflow shape, resource
envelopes, decision flags, and content addresses without receiving role,
producer, model, language, identity, or raw request metadata.

The projection is intentionally lossy. It is not a replacement for the typed
internal plan and cannot be used to execute a handler. Its address is computed
from the published fields only, so adding an internal routing field cannot
silently change the public contract.
"""

from __future__ import annotations

import csv
import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from io import StringIO
from typing import Any

from .control_plane import ClaimCeiling, MissionContext
from .errors import ValidationError
from .mission_runtime import MissionPlan, MissionPlanBuilder, MissionRequest
from .module_fabric_support import contains_private_key
from .serialization import canonical_json, content_hash, jsonable
from .workflow import ResourceEnvelope, StepKind, WorkflowCompiler, WorkflowStep


MISSION_PLAN_PUBLIC_VERSION = "mission-plan-public-v1"
MISSION_PLAN_PUBLIC_SCHEMA_VERSION = "mission-plan-public-schema-v1"
MISSION_PLAN_PUBLIC_MAX_STEPS = 256
MISSION_PLAN_PUBLIC_MAX_DEPENDENCIES = 64
MISSION_PLAN_PUBLIC_MAX_WORKFLOW_ID = 128
MISSION_PLAN_PUBLIC_MAX_MISSION_ID = 256

_FORBIDDEN_PUBLIC_KEYS = frozenset(
    {
        "agent",
        "agent_id",
        "agent_ids",
        "assistant",
        "assistant_id",
        "author",
        "author_id",
        "contact",
        "credential",
        "email",
        "generated_by",
        "individual",
        "language",
        "model",
        "model_id",
        "model_version",
        "patient",
        "phone",
        "programming_language",
        "producer",
        "role_id",
        "sample",
        "secret",
        "selected_agent_ids",
        "selected_tool_ids",
        "subject",
        "token",
        "tool_id",
        "tool_ids",
    }
)

_PUBLIC_RESOURCE_KEYS = frozenset(
    {"cpu", "memory_gb", "gpu_count", "storage_gb", "network_egress", "max_seconds"}
)
_PUBLIC_STEP_KEYS = frozenset(
    {
        "step_id",
        "kind",
        "depends_on",
        "resource",
        "optional",
        "deterministic",
        "input_contract",
        "output_contract",
    }
)
_PUBLIC_RECEIPT_KEYS = frozenset(
    {
        "version",
        "plan_id",
        "mission_id",
        "state",
        "accepted",
        "decision",
        "abstained",
        "requires_human_review",
        "workflow_id",
        "steps",
        "step_count",
        "total_cpu",
        "peak_memory_gb",
        "total_storage_gb",
        "max_seconds",
        "selected_role_count",
        "selected_operation_count",
        "registry_address",
        "warning_count",
        "boundary_accepted",
        "content_address",
    }
)


class MissionPublicDecisionState(StrEnum):
    """Stable decision state exposed to public consumers."""

    PLANNED = "planned"
    PARTIAL = "partial"
    ABSTAINED = "abstained"
    REJECTED = "rejected"


def _text(value: Any, field: str, *, maximum: int | None = None) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f"{field} must not be empty")
    if maximum is not None and len(normalized) > maximum:
        raise ValidationError(f"{field} exceeds the maximum length")
    return normalized


def _string_tuple(value: Any, field: str, *, maximum: int = 256) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValidationError(f"{field} must be an array")
    values = tuple(_text(item, f"{field}[]", maximum=maximum) for item in value)
    if len(values) != len(set(values)):
        raise ValidationError(f"{field} must not contain duplicates")
    return values


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return {str(key): item for key, item in value.items()}


def _forbidden_paths(value: Any, path: str = "") -> tuple[str, ...]:
    if isinstance(value, Mapping):
        paths: list[str] = []
        for key, item in value.items():
            key_text = str(key)
            child = f"{path}.{key_text}" if path else key_text
            if key_text.casefold() in _FORBIDDEN_PUBLIC_KEYS:
                paths.append(child)
            paths.extend(_forbidden_paths(item, child))
        return tuple(paths)
    if isinstance(value, (list, tuple)):
        paths: list[str] = []
        for index, item in enumerate(value):
            paths.extend(_forbidden_paths(item, f"{path}[{index}]"))
        return tuple(paths)
    return ()


def _resource_body(resource: ResourceEnvelope) -> dict[str, Any]:
    return {
        "cpu": float(resource.cpu),
        "memory_gb": float(resource.memory_gb),
        "gpu_count": resource.gpu_count,
        "storage_gb": float(resource.storage_gb),
        "network_egress": resource.network_egress,
        "max_seconds": resource.max_seconds,
    }


def _resource_from_mapping(value: Any, field: str) -> ResourceEnvelope:
    body = _mapping(value, field)
    unexpected = set(body) - _PUBLIC_RESOURCE_KEYS
    if unexpected:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unexpected)}")
    try:
        cpu = float(body.get("cpu", 1.0))
        memory_gb = float(body.get("memory_gb", 1.0))
        storage_gb = float(body.get("storage_gb", 1.0))
        gpu_count = int(body.get("gpu_count", 0))
        max_seconds = int(body.get("max_seconds", 300))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} contains an invalid numeric value") from exc
    if not all(math.isfinite(value) for value in (cpu, memory_gb, storage_gb)):
        raise ValidationError(f"{field} contains a non-finite numeric value")
    return ResourceEnvelope(
        cpu=cpu,
        memory_gb=memory_gb,
        gpu_count=gpu_count,
        storage_gb=storage_gb,
        network_egress=bool(body.get("network_egress", False)),
        max_seconds=max_seconds,
    )


@dataclass(frozen=True, slots=True)
class MissionPublicWorkflowStep:
    """Public workflow step with no internal routing identifiers."""

    step_id: str
    kind: str
    depends_on: tuple[str, ...]
    resource: Mapping[str, Any]
    optional: bool
    deterministic: bool
    input_contract: str
    output_contract: str

    def __post_init__(self) -> None:
        _text(self.step_id, "step_id")
        _text(self.kind, "kind")
        _text(self.input_contract, "input_contract")
        _text(self.output_contract, "output_contract")
        if len(self.depends_on) > MISSION_PLAN_PUBLIC_MAX_DEPENDENCIES:
            raise ValidationError("workflow step dependency count exceeds the public bound")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @classmethod
    def from_mapping(cls, value: Any, field: str) -> "MissionPublicWorkflowStep":
        body = _mapping(value, field)
        unexpected = set(body) - _PUBLIC_STEP_KEYS
        if unexpected:
            raise ValidationError(f"{field} contains unsupported fields: {sorted(unexpected)}")
        resource = _resource_body(
            _resource_from_mapping(body.get("resource", {}), f"{field}.resource")
        )
        try:
            kind = StepKind(_text(body.get("kind"), f"{field}.kind")).value
        except ValueError as exc:
            raise ValidationError(f"{field}.kind is invalid") from exc
        return cls(
            step_id=_text(body.get("step_id"), f"{field}.step_id"),
            kind=kind,
            depends_on=_string_tuple(body.get("depends_on", ()), f"{field}.depends_on"),
            resource=resource,
            optional=bool(body.get("optional", False)),
            deterministic=bool(body.get("deterministic", True)),
            input_contract=_text(body.get("input_contract", "unspecified"), f"{field}.input_contract"),
            output_contract=_text(body.get("output_contract", "unspecified"), f"{field}.output_contract"),
        )


@dataclass(frozen=True, slots=True)
class MissionPlanPublicReceipt:
    """Addressable mission receipt safe for published API and CLI output."""

    version: str
    plan_id: str
    mission_id: str
    state: MissionPublicDecisionState
    accepted: bool
    decision: str
    abstained: bool
    requires_human_review: bool
    workflow_id: str | None
    steps: tuple[MissionPublicWorkflowStep, ...]
    step_count: int
    total_cpu: float
    peak_memory_gb: float
    total_storage_gb: float
    max_seconds: int
    selected_role_count: int
    selected_operation_count: int
    registry_address: str
    warning_count: int
    boundary_accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if self.version != MISSION_PLAN_PUBLIC_VERSION:
            raise ValidationError("mission public receipt version is invalid")
        _text(self.plan_id, "plan_id")
        _text(self.mission_id, "mission_id", maximum=MISSION_PLAN_PUBLIC_MAX_MISSION_ID)
        if self.workflow_id is not None:
            _text(self.workflow_id, "workflow_id", maximum=MISSION_PLAN_PUBLIC_MAX_WORKFLOW_ID)
        _text(self.decision, "decision")
        _text(self.registry_address, "registry_address")
        if self.step_count != len(self.steps):
            raise ValidationError("mission public step count does not reconcile")
        if self.step_count > MISSION_PLAN_PUBLIC_MAX_STEPS:
            raise ValidationError("mission public step count exceeds the bound")
        if any(value < 0 for value in (self.total_cpu, self.peak_memory_gb, self.total_storage_gb)):
            raise ValidationError("mission public resource totals must be non-negative")
        if self.max_seconds < 0 or self.selected_role_count < 0 or self.selected_operation_count < 0:
            raise ValidationError("mission public counts must be non-negative")
        if self.warning_count < 0:
            raise ValidationError("mission public warning count must be non-negative")
        if not self.boundary_accepted:
            raise ValidationError("mission public receipt must pass its public boundary")

    def _body(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "plan_id": self.plan_id,
            "mission_id": self.mission_id,
            "state": self.state,
            "accepted": self.accepted,
            "decision": self.decision,
            "abstained": self.abstained,
            "requires_human_review": self.requires_human_review,
            "workflow_id": self.workflow_id,
            "steps": self.steps,
            "step_count": self.step_count,
            "total_cpu": self.total_cpu,
            "peak_memory_gb": self.peak_memory_gb,
            "total_storage_gb": self.total_storage_gb,
            "max_seconds": self.max_seconds,
            "selected_role_count": self.selected_role_count,
            "selected_operation_count": self.selected_operation_count,
            "registry_address": self.registry_address,
            "warning_count": self.warning_count,
            "boundary_accepted": self.boundary_accepted,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MissionPlanPublicReceipt":
        body = _mapping(value, "mission public receipt")
        if _forbidden_paths(body) or contains_private_key(body):
            raise ValidationError("mission public receipt contains restricted metadata")
        unexpected = set(body) - _PUBLIC_RECEIPT_KEYS
        if unexpected:
            raise ValidationError(
                f"mission public receipt contains unsupported fields: {sorted(unexpected)}"
            )
        try:
            state = MissionPublicDecisionState(_text(body.get("state"), "receipt.state"))
        except ValueError as exc:
            raise ValidationError("mission public receipt state is invalid") from exc
        raw_steps = body.get("steps", ())
        if not isinstance(raw_steps, (list, tuple)):
            raise ValidationError("mission public receipt steps must be an array")
        steps = tuple(
            MissionPublicWorkflowStep.from_mapping(item, f"receipt.steps[{index}]")
            for index, item in enumerate(raw_steps)
        )
        values: dict[str, Any] = {
            "version": _text(body.get("version"), "receipt.version"),
            "plan_id": _text(body.get("plan_id"), "receipt.plan_id"),
            "mission_id": _text(body.get("mission_id"), "receipt.mission_id"),
            "state": state,
            "accepted": bool(body.get("accepted")),
            "decision": _text(body.get("decision"), "receipt.decision"),
            "abstained": bool(body.get("abstained")),
            "requires_human_review": bool(body.get("requires_human_review")),
            "workflow_id": None if body.get("workflow_id") in (None, "") else _text(body.get("workflow_id"), "receipt.workflow_id"),
            "steps": steps,
            "step_count": int(body.get("step_count")),
            "total_cpu": float(body.get("total_cpu")),
            "peak_memory_gb": float(body.get("peak_memory_gb")),
            "total_storage_gb": float(body.get("total_storage_gb")),
            "max_seconds": int(body.get("max_seconds")),
            "selected_role_count": int(body.get("selected_role_count")),
            "selected_operation_count": int(body.get("selected_operation_count")),
            "registry_address": _text(body.get("registry_address"), "receipt.registry_address"),
            "warning_count": int(body.get("warning_count")),
            "boundary_accepted": bool(body.get("boundary_accepted")),
        }
        receipt = cls(**values, content_address=_text(body.get("content_address"), "receipt.content_address"))
        if content_hash(receipt._body(), prefix="mission-plan-public") != receipt.content_address:
            raise ValidationError("mission public receipt content address does not reconcile")
        return receipt


def mission_plan_public_projection(plan: MissionPlan) -> MissionPlanPublicReceipt:
    """Project an internal plan into a public, routing-free receipt."""

    if not isinstance(plan, MissionPlan):
        raise ValidationError("mission public projection requires a typed mission plan")
    workflow = plan.workflow
    steps: tuple[MissionPublicWorkflowStep, ...] = ()
    workflow_id = None
    total_cpu = peak_memory_gb = total_storage_gb = 0.0
    max_seconds = 0
    if workflow is not None:
        workflow_id = workflow.workflow_id
        steps = tuple(
            MissionPublicWorkflowStep(
                step_id=step.step_id,
                kind=step.kind.value,
                depends_on=step.depends_on,
                resource=_resource_body(step.resource),
                optional=step.optional,
                deterministic=step.deterministic,
                input_contract=step.input_contract,
                output_contract=step.output_contract,
            )
            for step in workflow.steps
        )
        total_cpu = float(workflow.total_cpu)
        peak_memory_gb = float(workflow.peak_memory_gb)
        total_storage_gb = float(workflow.total_storage_gb)
        max_seconds = workflow.max_seconds
    state = MissionPublicDecisionState(plan.state.value)
    body = {
        "version": MISSION_PLAN_PUBLIC_VERSION,
        "plan_id": plan.plan_id,
        "mission_id": plan.mission_id,
        "state": state,
        "accepted": state is not MissionPublicDecisionState.REJECTED,
        "decision": plan.decision.decision,
        "abstained": plan.decision.abstained,
        "requires_human_review": plan.decision.requires_human_review,
        "workflow_id": workflow_id,
        "steps": steps,
        "step_count": len(steps),
        "total_cpu": total_cpu,
        "peak_memory_gb": peak_memory_gb,
        "total_storage_gb": total_storage_gb,
        "max_seconds": max_seconds,
        "selected_role_count": len(plan.selected_agent_ids),
        "selected_operation_count": len(plan.selected_tool_ids),
        "registry_address": plan.registry_address,
        "warning_count": len(plan.warnings),
        "boundary_accepted": True,
    }
    if _forbidden_paths(jsonable(body)) or contains_private_key(body):
        raise ValidationError("mission public projection failed the public boundary")
    return MissionPlanPublicReceipt(
        **body,
        content_address=content_hash(body, prefix="mission-plan-public"),
    )


def _mission_context_from_mapping(value: Any) -> MissionContext:
    body = _mapping(value, "mission")
    try:
        claim_ceiling = ClaimCeiling(
            _text(body.get("claim_ceiling", ClaimCeiling.HYPOTHESIS.value), "mission.claim_ceiling")
        )
    except ValueError as exc:
        raise ValidationError("mission.claim_ceiling is invalid") from exc
    return MissionContext(
        mission_id=_text(body.get("mission_id", "mission-input"), "mission.mission_id"),
        project_id=_text(body.get("project_id", "glio-noncode"), "mission.project_id"),
        intended_use=_text(body.get("intended_use", "research hypothesis exploration"), "mission.intended_use"),
        requested_question=_text(body.get("requested_question", "bounded research question"), "mission.requested_question"),
        claim_ceiling=claim_ceiling,
        allowed_source_ids=_string_tuple(body.get("allowed_source_ids", ()), "mission.allowed_source_ids"),
        allowed_data_scopes=_string_tuple(
            body.get("allowed_data_scopes", ("synthetic", "public_reference")),
            "mission.allowed_data_scopes",
        ),
        allowed_mutations=_string_tuple(
            body.get("allowed_mutations", ("none", "event_log", "content_addressed_store")),
            "mission.allowed_mutations",
        ),
        research_use_only=bool(body.get("research_use_only", True)),
        allow_network=bool(body.get("allow_network", False)),
        private_data_allowed=bool(body.get("private_data_allowed", False)),
        subject_scope=_text(
            body.get("subject_scope", "pseudonymous_research_subject"),
            "mission.subject_scope",
        ),
    )


def _workflow_steps_from_mapping(value: Any) -> tuple[WorkflowStep, ...]:
    if value in (None, ()):
        return ()
    if not isinstance(value, (list, tuple)):
        raise ValidationError("workflow_steps must be an array")
    if len(value) > MISSION_PLAN_PUBLIC_MAX_STEPS:
        raise ValidationError("workflow_steps exceed the public bound")
    steps: list[WorkflowStep] = []
    for index, item in enumerate(value):
        body = _mapping(item, f"workflow_steps[{index}]")
        try:
            kind = StepKind(_text(body.get("kind"), f"workflow_steps[{index}].kind"))
        except ValueError as exc:
            raise ValidationError(f"workflow_steps[{index}].kind is invalid") from exc
        depends_on = _string_tuple(
            body.get("depends_on", ()),
            f"workflow_steps[{index}].depends_on",
        )
        if len(depends_on) > MISSION_PLAN_PUBLIC_MAX_DEPENDENCIES:
            raise ValidationError("workflow step dependencies exceed the public bound")
        steps.append(
            WorkflowStep(
                step_id=_text(body.get("step_id"), f"workflow_steps[{index}].step_id"),
                kind=kind,
                depends_on=depends_on,
                resource=_resource_from_mapping(
                    body.get("resource", {}),
                    f"workflow_steps[{index}].resource",
                ),
                optional=bool(body.get("optional", False)),
                deterministic=bool(body.get("deterministic", True)),
                input_contract=_text(
                    body.get("input_contract", "unspecified"),
                    f"workflow_steps[{index}].input_contract",
                ),
                output_contract=_text(
                    body.get("output_contract", "unspecified"),
                    f"workflow_steps[{index}].output_contract",
                ),
            )
        )
    WorkflowCompiler().compile("public-input-validation", steps)
    return tuple(steps)


def mission_request_from_mapping(value: Mapping[str, Any]) -> MissionRequest:
    """Parse a mission request while retaining routing fields only internally."""

    body = _mapping(value, "mission request")
    mission = _mission_context_from_mapping(body.get("mission", body))
    requested = _string_tuple(body.get("requested_agent_ids", ()), "requested_agent_ids")
    workflow_id = _text(
        body.get("workflow_id", "mission-workflow"),
        "workflow_id",
        maximum=MISSION_PLAN_PUBLIC_MAX_WORKFLOW_ID,
    )
    return MissionRequest(
        mission=mission,
        requested_agent_ids=requested,
        workflow_id=workflow_id,
        workflow_steps=_workflow_steps_from_mapping(body.get("workflow_steps", ())),
    )


def build_public_mission_plan(
    value: Mapping[str, Any] | MissionRequest,
    *,
    builder: MissionPlanBuilder | None = None,
) -> MissionPlanPublicReceipt:
    """Build a typed mission plan and return only its public receipt."""

    request = value if isinstance(value, MissionRequest) else mission_request_from_mapping(value)
    return mission_plan_public_projection((builder or MissionPlanBuilder()).plan(request))


def mission_plan_public_json(receipt: MissionPlanPublicReceipt) -> str:
    """Render the public receipt as canonical JSON."""

    return canonical_json(receipt.to_dict()) + "\n"


def mission_plan_public_csv(receipt: MissionPlanPublicReceipt) -> str:
    """Render the public workflow steps as deterministic CSV."""

    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "step_id",
            "kind",
            "depends_on",
            "optional",
            "deterministic",
            "input_contract",
            "output_contract",
            "cpu",
            "memory_gb",
            "gpu_count",
            "storage_gb",
            "network_egress",
            "max_seconds",
        )
    )
    for step in receipt.steps:
        resource = step.resource
        writer.writerow(
            (
                step.step_id,
                step.kind,
                "|".join(step.depends_on),
                step.optional,
                step.deterministic,
                step.input_contract,
                step.output_contract,
                resource.get("cpu"),
                resource.get("memory_gb"),
                resource.get("gpu_count"),
                resource.get("storage_gb"),
                resource.get("network_egress"),
                resource.get("max_seconds"),
            )
        )
    return output.getvalue()


def render_mission_plan_public_markdown(receipt: MissionPlanPublicReceipt) -> str:
    """Render a compact public mission plan without internal routing fields."""

    lines = [
        "# Mission plan",
        "",
        f"- State: `{receipt.state.value}`",
        f"- Accepted: `{receipt.accepted}`",
        f"- Decision: `{receipt.decision}`",
        f"- Workflow steps: `{receipt.step_count}`",
        f"- Selected roles: `{receipt.selected_role_count}`",
        f"- Selected operations: `{receipt.selected_operation_count}`",
        f"- Human review required: `{receipt.requires_human_review}`",
        f"- Boundary accepted: `{receipt.boundary_accepted}`",
        "",
        "| Step | Kind | Dependencies | Optional | Deterministic |",
        "| --- | --- | --- | --- | --- |",
    ]
    for step in receipt.steps:
        lines.append(
            f"| `{step.step_id}` | `{step.kind}` | `{', '.join(step.depends_on) or 'none'}` | "
            f"{step.optional} | {step.deterministic} |"
        )
    lines.extend(("", "This is a public planning receipt; internal routing metadata is omitted.", ""))
    return "\n".join(lines)


def mission_plan_public_export_payloads(receipt: MissionPlanPublicReceipt) -> dict[str, str]:
    """Return deterministic public JSON, Markdown, and CSV artifacts."""

    return {
        "mission-plan.json": mission_plan_public_json(receipt),
        "mission-plan.md": render_mission_plan_public_markdown(receipt),
        "mission-plan-steps.csv": mission_plan_public_csv(receipt),
    }


def mission_plan_public_schema() -> dict[str, Any]:
    """Return the public mission-plan schema and boundary contract."""

    return {
        "version": MISSION_PLAN_PUBLIC_SCHEMA_VERSION,
        "contract_version": MISSION_PLAN_PUBLIC_VERSION,
        "type": "object",
        "required": [
            "version",
            "plan_id",
            "mission_id",
            "state",
            "accepted",
            "decision",
            "steps",
            "step_count",
            "registry_address",
            "boundary_accepted",
            "content_address",
        ],
        "properties": {
            "version": {"const": MISSION_PLAN_PUBLIC_VERSION},
            "plan_id": {"type": "string"},
            "mission_id": {"type": "string"},
            "state": {"enum": [item.value for item in MissionPublicDecisionState]},
            "accepted": {"type": "boolean"},
            "decision": {"type": "string"},
            "abstained": {"type": "boolean"},
            "requires_human_review": {"type": "boolean"},
            "workflow_id": {"type": ["string", "null"]},
            "steps": {"type": "array", "maxItems": MISSION_PLAN_PUBLIC_MAX_STEPS},
            "step_count": {"type": "integer", "minimum": 0},
            "total_cpu": {"type": "number", "minimum": 0},
            "peak_memory_gb": {"type": "number", "minimum": 0},
            "total_storage_gb": {"type": "number", "minimum": 0},
            "max_seconds": {"type": "integer", "minimum": 0},
            "selected_role_count": {"type": "integer", "minimum": 0},
            "selected_operation_count": {"type": "integer", "minimum": 0},
            "registry_address": {"type": "string"},
            "warning_count": {"type": "integer", "minimum": 0},
            "boundary_accepted": {"const": True},
            "content_address": {"type": "string"},
        },
        "boundary": {
            "routing_metadata": False,
            "producer_metadata": False,
            "model_metadata": False,
            "programming_language_metadata": False,
            "private_identity": False,
            "raw_request_payload": False,
        },
        "limits": {
            "max_steps": MISSION_PLAN_PUBLIC_MAX_STEPS,
            "max_dependencies_per_step": MISSION_PLAN_PUBLIC_MAX_DEPENDENCIES,
        },
    }


def mission_plan_public_capabilities() -> dict[str, Any]:
    """Return operational capabilities for the public mission surface."""

    return {
        "version": MISSION_PLAN_PUBLIC_VERSION,
        "typed_request_parsing": True,
        "dependency_safe_workflow_compilation": True,
        "resource_envelope_projection": True,
        "role_identifier_redaction": True,
        "operation_identifier_redaction": True,
        "public_boundary_validation": True,
        "content_addressed": True,
        "hydration_and_address_verification": True,
        "json_export": True,
        "markdown_export": True,
        "csv_export": True,
        "cli_surface": True,
        "api_surface": True,
        "read_only": True,
        "research_use_only": True,
    }


__all__ = [
    "MISSION_PLAN_PUBLIC_MAX_DEPENDENCIES",
    "MISSION_PLAN_PUBLIC_MAX_STEPS",
    "MISSION_PLAN_PUBLIC_SCHEMA_VERSION",
    "MISSION_PLAN_PUBLIC_VERSION",
    "MissionPlanPublicReceipt",
    "MissionPublicDecisionState",
    "MissionPublicWorkflowStep",
    "build_public_mission_plan",
    "mission_plan_public_capabilities",
    "mission_plan_public_csv",
    "mission_plan_public_export_payloads",
    "mission_plan_public_json",
    "mission_plan_public_projection",
    "mission_plan_public_schema",
    "mission_request_from_mapping",
    "render_mission_plan_public_markdown",
]
