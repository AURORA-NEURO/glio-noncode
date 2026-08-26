"""Independent conformance and replay for public mission-plan receipts.

The public mission-plan projection is intentionally lossy, but it is still a
real contract.  A downstream consumer needs a way to validate a receipt after
transport, explain each reconciliation decision, and replay the validation
sequence without reopening the typed planner.  This module provides that
independent check plane.

Conformance checks reconstruct only facts present in the public receipt:
content addresses, step counts, dependency order, aggregate resources, and
boundary keys.  Replay records those checks as a timestamp-free sequence.  It
never executes a handler, resolves an owner, selects an agent, reads a raw
request, or infers scientific or clinical meaning.
"""

from __future__ import annotations

import csv
import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from io import StringIO
from typing import Any

from .errors import ValidationError
from .mission_runtime_public import (
    MissionPlanPublicReceipt,
    build_public_mission_plan,
)
from .serialization import canonical_json, content_hash, jsonable


MISSION_PLAN_PUBLIC_CONFORMANCE_VERSION = "mission-plan-public-conformance-v1"
MISSION_PLAN_PUBLIC_CONFORMANCE_SCHEMA_VERSION = "mission-plan-public-conformance-schema-v1"
MISSION_PLAN_PUBLIC_CONFORMANCE_CAPABILITIES_VERSION = "mission-plan-public-conformance-capabilities-v1"
MISSION_PLAN_PUBLIC_CONFORMANCE_MAX_CHECKS = 24
MISSION_PLAN_PUBLIC_REPLAY_VERSION = "mission-plan-public-replay-v1"
MISSION_PLAN_PUBLIC_REPLAY_SCHEMA_VERSION = "mission-plan-public-replay-schema-v1"
MISSION_PLAN_PUBLIC_REPLAY_CAPABILITIES_VERSION = "mission-plan-public-replay-capabilities-v1"
MISSION_PLAN_PUBLIC_REPLAY_MAX_STAGES = 8

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
_PUBLIC_RESOURCE_KEYS = frozenset(
    {"cpu", "memory_gb", "gpu_count", "storage_gb", "network_egress", "max_seconds"}
)
_FORBIDDEN_KEYS = frozenset(
    {
        "agent",
        "agent_id",
        "assistant",
        "author",
        "contact",
        "email",
        "generated_by",
        "identity",
        "individual",
        "language",
        "model",
        "model_id",
        "model_version",
        "patient",
        "producer",
        "programming_language",
        "raw_request",
        "request",
        "secret",
        "subject",
        "token",
        "tool_id",
    }
)


def _text(value: Any, field: str, *, maximum: int = 180) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f"{field} must not be empty")
    if len(normalized) > maximum:
        raise ValidationError(f"{field} exceeds the maximum length")
    return normalized


def _private_paths(value: Any, path: str = "") -> tuple[str, ...]:
    if isinstance(value, Mapping):
        paths: list[str] = []
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}" if path else key_text
            if key_text.casefold() in _FORBIDDEN_KEYS:
                paths.append(child_path)
            paths.extend(_private_paths(child, child_path))
        return tuple(paths)
    if isinstance(value, (list, tuple)):
        paths: list[str] = []
        for index, child in enumerate(value):
            paths.extend(_private_paths(child, f"{path}[{index}]"))
        return tuple(paths)
    return ()


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} must be numeric") from exc
    if not math.isfinite(number) or number < 0:
        raise ValidationError(f"{field} must be finite and non-negative")
    return number


def _int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be an integer")
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} must be an integer") from exc
    if number < 0:
        raise ValidationError(f"{field} must be non-negative")
    return number


class MissionPlanConformanceState(StrEnum):
    """Stable outcome for a conformance check."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ABSTAINED = "abstained"


class MissionPlanPublicReplayStageState(StrEnum):
    """Stable outcome for one replay stage."""

    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class MissionPlanPublicConformanceCheck:
    """One independent public receipt reconciliation."""

    check_id: str
    category: str
    accepted: bool
    observed: Any
    expected: Any
    message: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.check_id, "conformance_check.check_id", maximum=128)
        _text(self.category, "conformance_check.category", maximum=64)
        if not isinstance(self.accepted, bool):
            raise ValidationError("conformance check accepted must be boolean")
        _text(self.message, "conformance_check.message", maximum=400)
        _text(self.content_address, "conformance_check.content_address")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MissionPlanPublicConformanceCheck":
        body = dict(value)
        allowed = {"check_id", "category", "accepted", "observed", "expected", "message", "content_address"}
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"conformance check contains unsupported fields: {sorted(unknown)}")
        return cls(
            check_id=_text(body.get("check_id"), "conformance_check.check_id", maximum=128),
            category=_text(body.get("category"), "conformance_check.category", maximum=64),
            accepted=bool(body.get("accepted")),
            observed=body.get("observed"),
            expected=body.get("expected"),
            message=_text(body.get("message"), "conformance_check.message", maximum=400),
            content_address=_text(body.get("content_address"), "conformance_check.content_address"),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MissionPlanPublicConformance:
    """Addressed conformance report for one public receipt."""

    conformance_version: str
    plan_id: str
    plan_address: str
    state: MissionPlanConformanceState
    checks: tuple[MissionPlanPublicConformanceCheck, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if self.conformance_version != MISSION_PLAN_PUBLIC_CONFORMANCE_VERSION:
            raise ValidationError("conformance version is invalid")
        _text(self.plan_id, "conformance.plan_id")
        _text(self.plan_address, "conformance.plan_address")
        if len(self.checks) > MISSION_PLAN_PUBLIC_CONFORMANCE_MAX_CHECKS:
            raise ValidationError("conformance check count exceeds the bound")
        check_ids = tuple(item.check_id for item in self.checks)
        if len(check_ids) != len(set(check_ids)):
            raise ValidationError("conformance check IDs must be unique")
        _text(self.content_address, "conformance.content_address")

    @property
    def passed_check_count(self) -> int:
        return sum(item.accepted for item in self.checks)

    @property
    def failed_check_count(self) -> int:
        return len(self.checks) - self.passed_check_count

    def to_dict(self) -> dict[str, Any]:
        body = {
            "conformance_version": self.conformance_version,
            "plan_id": self.plan_id,
            "plan_address": self.plan_address,
            "state": self.state,
            "check_count": len(self.checks),
            "passed_check_count": self.passed_check_count,
            "failed_check_count": self.failed_check_count,
            "checks": self.checks,
            "accepted": self.accepted,
        }
        return jsonable(body | {"content_address": self.content_address})


@dataclass(frozen=True, slots=True)
class MissionPlanPublicReplayStage:
    """One timestamp-free public receipt replay stage."""

    ordinal: int
    stage_id: str
    state: MissionPlanPublicReplayStageState
    input_address: str | None
    output_address: str | None
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        if self.ordinal <= 0:
            raise ValidationError("replay stage ordinal must be positive")
        _text(self.stage_id, "replay_stage.stage_id", maximum=96)
        _text(self.detail, "replay_stage.detail", maximum=400)
        _text(self.content_address, "replay_stage.content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MissionPlanPublicReplay:
    """Addressed deterministic replay ledger for public conformance."""

    replay_version: str
    plan_id: str
    plan_address: str
    conformance: MissionPlanPublicConformance
    stages: tuple[MissionPlanPublicReplayStage, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if self.replay_version != MISSION_PLAN_PUBLIC_REPLAY_VERSION:
            raise ValidationError("replay version is invalid")
        _text(self.plan_id, "replay.plan_id")
        _text(self.plan_address, "replay.plan_address")
        if len(self.stages) > MISSION_PLAN_PUBLIC_REPLAY_MAX_STAGES:
            raise ValidationError("replay stage count exceeds the bound")
        ordinals = tuple(item.ordinal for item in self.stages)
        if ordinals != tuple(range(1, len(self.stages) + 1)):
            raise ValidationError("replay stage ordinals must be contiguous")
        _text(self.content_address, "replay.content_address")

    @property
    def completed_stage_count(self) -> int:
        return sum(item.state is MissionPlanPublicReplayStageState.COMPLETED for item in self.stages)

    @property
    def failed_stage_count(self) -> int:
        return sum(item.state is MissionPlanPublicReplayStageState.FAILED for item in self.stages)

    def to_dict(self) -> dict[str, Any]:
        body = {
            "replay_version": self.replay_version,
            "plan_id": self.plan_id,
            "plan_address": self.plan_address,
            "conformance": self.conformance,
            "stage_count": len(self.stages),
            "completed_stage_count": self.completed_stage_count,
            "failed_stage_count": self.failed_stage_count,
            "stages": self.stages,
            "accepted": self.accepted,
        }
        return jsonable(body | {"content_address": self.content_address})


def _receipt_from_value(value: MissionPlanPublicReceipt | Mapping[str, Any]) -> MissionPlanPublicReceipt:
    if isinstance(value, MissionPlanPublicReceipt):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("public conformance input must be a receipt or request object")
    body = dict(value)
    if "content_address" in body:
        return MissionPlanPublicReceipt.from_mapping(body)
    return build_public_mission_plan(body)


def _check(
    check_id: str,
    category: str,
    accepted: bool,
    observed: Any,
    expected: Any,
    message: str,
) -> MissionPlanPublicConformanceCheck:
    body = {
        "check_id": check_id,
        "category": category,
        "accepted": bool(accepted),
        "observed": observed,
        "expected": expected,
        "message": message,
    }
    return MissionPlanPublicConformanceCheck(
        **body,
        content_address=content_hash(body, prefix="mission-plan-public-conformance-check"),
    )


def _resource_totals(receipt: MissionPlanPublicReceipt) -> dict[str, float | int]:
    cpu = 0.0
    memory = 0.0
    storage = 0.0
    max_seconds = 0
    for step in receipt.steps:
        resource = step.resource
        cpu += _number(resource.get("cpu"), f"step {step.step_id}.cpu")
        memory = max(memory, _number(resource.get("memory_gb"), f"step {step.step_id}.memory_gb"))
        storage += _number(resource.get("storage_gb"), f"step {step.step_id}.storage_gb")
        max_seconds += _int(resource.get("max_seconds"), f"step {step.step_id}.max_seconds")
    return {
        "total_cpu": cpu,
        "peak_memory_gb": memory,
        "total_storage_gb": storage,
        "max_seconds": max_seconds,
    }


def _dependency_result(receipt: MissionPlanPublicReceipt) -> tuple[bool, tuple[str, ...], int]:
    seen: set[str] = set()
    depth: dict[str, int] = {}
    violations: list[str] = []
    for step in receipt.steps:
        if step.step_id in seen:
            violations.append(f"duplicate:{step.step_id}")
        missing = tuple(item for item in step.depends_on if item not in seen)
        violations.extend(f"order:{step.step_id}->{item}" for item in missing)
        depth[step.step_id] = 1 + max((depth[item] for item in step.depends_on if item in depth), default=0)
        seen.add(step.step_id)
    return not violations, tuple(violations), max(depth.values(), default=0)


def conform_mission_plan_public(
    value: MissionPlanPublicReceipt | Mapping[str, Any],
    *,
    expected_plan_address: str | None = None,
) -> MissionPlanPublicConformance:
    """Independently reconcile a public receipt and its address."""

    receipt = _receipt_from_value(value)
    receipt_body = receipt.to_dict()
    dependency_accepted, dependency_violations, dependency_depth = _dependency_result(receipt)
    totals = _resource_totals(receipt)
    expected_address = content_hash(receipt._body(), prefix="mission-plan-public")
    expected_plan = expected_plan_address or receipt.content_address
    public_paths = _private_paths(receipt_body)
    checks = (
        _check(
            "receipt.version",
            "identity",
            receipt.version == "mission-plan-public-v1",
            receipt.version,
            "mission-plan-public-v1",
            "The receipt version must match the public contract.",
        ),
        _check(
            "receipt.address",
            "address",
            receipt.content_address == expected_address and receipt.content_address == expected_plan,
            receipt.content_address,
            expected_plan,
            "The content address must reconstruct from published receipt fields.",
        ),
        _check(
            "receipt.boundary",
            "boundary",
            receipt.boundary_accepted and not public_paths,
            list(public_paths),
            "no restricted metadata paths",
            "The receipt must remain inside the public boundary.",
        ),
        _check(
            "workflow.step_count",
            "workflow",
            receipt.step_count == len(receipt.steps),
            {"declared": receipt.step_count, "observed": len(receipt.steps)},
            receipt.step_count,
            "The declared step count must match the published rows.",
        ),
        _check(
            "workflow.dependency_order",
            "workflow",
            dependency_accepted,
            {"violations": list(dependency_violations), "depth": dependency_depth},
            "dependencies precede dependants",
            "Every dependency must be declared before its dependent step.",
        ),
        _check(
            "resources.total_cpu",
            "resources",
            math.isclose(receipt.total_cpu, float(totals["total_cpu"]), rel_tol=0.0, abs_tol=1e-9),
            receipt.total_cpu,
            totals["total_cpu"],
            "Total CPU must reconcile with the public step envelopes.",
        ),
        _check(
            "resources.peak_memory_gb",
            "resources",
            math.isclose(receipt.peak_memory_gb, float(totals["peak_memory_gb"]), rel_tol=0.0, abs_tol=1e-9),
            receipt.peak_memory_gb,
            totals["peak_memory_gb"],
            "Peak memory must reconcile with the public step envelopes.",
        ),
        _check(
            "resources.total_storage_gb",
            "resources",
            math.isclose(receipt.total_storage_gb, float(totals["total_storage_gb"]), rel_tol=0.0, abs_tol=1e-9),
            receipt.total_storage_gb,
            totals["total_storage_gb"],
            "Total storage must reconcile with the public step envelopes.",
        ),
        _check(
            "resources.max_seconds",
            "resources",
            receipt.max_seconds == totals["max_seconds"],
            receipt.max_seconds,
            totals["max_seconds"],
            "Maximum seconds must reconcile with the public step envelopes.",
        ),
        _check(
            "steps.identifier_uniqueness",
            "workflow",
            len({step.step_id for step in receipt.steps}) == receipt.step_count,
            [step.step_id for step in receipt.steps],
            "unique step IDs",
            "Each published workflow step must have a unique identifier.",
        ),
        _check(
            "steps.public_shape",
            "boundary",
            all(set(step.to_dict()) <= _PUBLIC_STEP_KEYS for step in receipt.steps),
            [sorted(set(step.to_dict()) - _PUBLIC_STEP_KEYS) for step in receipt.steps],
            "public step fields only",
            "Every step must contain only public contract fields.",
        ),
        _check(
            "resources.public_shape",
            "boundary",
            all(set(step.resource) <= _PUBLIC_RESOURCE_KEYS for step in receipt.steps),
            [sorted(set(step.resource) - _PUBLIC_RESOURCE_KEYS) for step in receipt.steps],
            "public resource fields only",
            "Every resource envelope must contain only public fields.",
        ),
        _check(
            "receipt.public_shape",
            "boundary",
            set(receipt_body) <= _PUBLIC_RECEIPT_KEYS,
            sorted(set(receipt_body) - _PUBLIC_RECEIPT_KEYS),
            sorted(_PUBLIC_RECEIPT_KEYS),
            "The receipt must contain only declared public fields.",
        ),
        _check(
            "receipt.acceptance_state",
            "decision",
            receipt.accepted or receipt.state.value in {"rejected", "abstained", "partial"},
            {"accepted": receipt.accepted, "state": receipt.state.value},
            "accepted or explicit non-accepted state",
            "A non-accepted receipt must make its state visible.",
        ),
        _check(
            "receipt.warning_count",
            "decision",
            receipt.warning_count >= 0,
            receipt.warning_count,
            "non-negative",
            "Warning counts must be explicit and non-negative.",
        ),
    )
    accepted = all(item.accepted for item in checks)
    state = MissionPlanConformanceState.ACCEPTED if accepted else MissionPlanConformanceState.REJECTED
    body = {
        "conformance_version": MISSION_PLAN_PUBLIC_CONFORMANCE_VERSION,
        "plan_id": receipt.plan_id,
        "plan_address": receipt.content_address,
        "state": state,
        "checks": checks,
        "accepted": accepted,
    }
    return MissionPlanPublicConformance(
        conformance_version=MISSION_PLAN_PUBLIC_CONFORMANCE_VERSION,
        plan_id=receipt.plan_id,
        plan_address=receipt.content_address,
        state=state,
        checks=checks,
        accepted=accepted,
        content_address=content_hash(body, prefix="mission-plan-public-conformance"),
    )


def _stage(
    ordinal: int,
    stage_id: str,
    state: MissionPlanPublicReplayStageState,
    input_address: str | None,
    output_address: str | None,
    detail: str,
) -> MissionPlanPublicReplayStage:
    body = {
        "ordinal": ordinal,
        "stage_id": stage_id,
        "state": state,
        "input_address": input_address,
        "output_address": output_address,
        "detail": detail,
    }
    return MissionPlanPublicReplayStage(
        **body,
        content_address=content_hash(body, prefix="mission-plan-public-replay-stage"),
    )


def replay_mission_plan_public(
    value: MissionPlanPublicReceipt | Mapping[str, Any],
    *,
    expected_plan_address: str | None = None,
) -> MissionPlanPublicReplay:
    """Replay public conformance stages without executing workflow handlers."""

    receipt = _receipt_from_value(value)
    report = conform_mission_plan_public(receipt, expected_plan_address=expected_plan_address)
    stages: list[MissionPlanPublicReplayStage] = []
    stages.append(
        _stage(
            1,
            "receipt-hydration",
            MissionPlanPublicReplayStageState.COMPLETED,
            None,
            receipt.content_address,
            "Public receipt fields were hydrated without planner access.",
        )
    )
    check_by_id = {item.check_id: item for item in report.checks}
    address_check = check_by_id["receipt.address"]
    stages.append(
        _stage(
            2,
            "address-reconstruction",
            MissionPlanPublicReplayStageState.COMPLETED
            if address_check.accepted
            else MissionPlanPublicReplayStageState.FAILED,
            receipt.content_address,
            address_check.content_address,
            "Published receipt address reconstruction completed.",
        )
    )
    dependency_check = check_by_id["workflow.dependency_order"]
    stages.append(
        _stage(
            3,
            "dependency-order",
            MissionPlanPublicReplayStageState.COMPLETED
            if dependency_check.accepted
            else MissionPlanPublicReplayStageState.FAILED,
            address_check.content_address,
            dependency_check.content_address,
            "Dependency ordering and duplicate identifiers were reconciled.",
        )
    )
    resource_ids = (
        "resources.total_cpu",
        "resources.peak_memory_gb",
        "resources.total_storage_gb",
        "resources.max_seconds",
    )
    resource_checks = tuple(check_by_id[item] for item in resource_ids)
    resource_accepted = all(item.accepted for item in resource_checks)
    stages.append(
        _stage(
            4,
            "resource-reconciliation",
            MissionPlanPublicReplayStageState.COMPLETED
            if resource_accepted
            else MissionPlanPublicReplayStageState.FAILED,
            dependency_check.content_address,
            content_hash(
                {"checks": [item.content_address for item in resource_checks]},
                prefix="mission-plan-public-replay-resource-stage",
            ),
            "Aggregate CPU, memory, storage, and runtime envelopes were reconciled.",
        )
    )
    boundary_ids = (
        "receipt.boundary",
        "steps.public_shape",
        "resources.public_shape",
        "receipt.public_shape",
    )
    boundary_checks = tuple(check_by_id[item] for item in boundary_ids)
    boundary_accepted = all(item.accepted for item in boundary_checks)
    stages.append(
        _stage(
            5,
            "public-boundary",
            MissionPlanPublicReplayStageState.COMPLETED
            if boundary_accepted
            else MissionPlanPublicReplayStageState.FAILED,
            resource_checks[-1].content_address,
            content_hash(
                {"checks": [item.content_address for item in boundary_checks]},
                prefix="mission-plan-public-replay-boundary-stage",
            ),
            "Public field, step, resource, and restricted-key boundaries were audited.",
        )
    )
    all_accepted = report.accepted and all(item.state is MissionPlanPublicReplayStageState.COMPLETED for item in stages)
    stages.append(
        _stage(
            6,
            "finalize",
            MissionPlanPublicReplayStageState.COMPLETED
            if all_accepted
            else MissionPlanPublicReplayStageState.FAILED,
            stages[-1].content_address,
            report.content_address,
            "Public conformance replay finalized without handler execution.",
        )
    )
    body = {
        "replay_version": MISSION_PLAN_PUBLIC_REPLAY_VERSION,
        "plan_id": receipt.plan_id,
        "plan_address": receipt.content_address,
        "conformance": report,
        "stages": stages,
        "accepted": all_accepted,
    }
    return MissionPlanPublicReplay(
        replay_version=MISSION_PLAN_PUBLIC_REPLAY_VERSION,
        plan_id=receipt.plan_id,
        plan_address=receipt.content_address,
        conformance=report,
        stages=tuple(stages),
        accepted=all_accepted,
        content_address=content_hash(body, prefix="mission-plan-public-replay"),
    )


def mission_plan_public_conformance_json(value: MissionPlanPublicConformance) -> str:
    """Render conformance as canonical JSON."""

    return canonical_json(value.to_dict()) + "\n"


def mission_plan_public_conformance_csv(value: MissionPlanPublicConformance) -> str:
    """Render one deterministic row per conformance check."""

    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("check_id", "category", "accepted", "observed", "expected", "message", "content_address"))
    for item in value.checks:
        writer.writerow(
            (
                item.check_id,
                item.category,
                item.accepted,
                canonical_json(item.observed),
                canonical_json(item.expected),
                item.message,
                item.content_address,
            )
        )
    return output.getvalue()


def mission_plan_public_conformance_markdown(value: MissionPlanPublicConformance) -> str:
    """Render conformance as a review table."""

    lines = [
        "# Mission plan public conformance",
        "",
        f"- Plan: `{value.plan_id}`",
        f"- Accepted: `{value.accepted}`",
        f"- Checks: `{value.passed_check_count}/{len(value.checks)}`",
        "",
        "| Check | Category | Result | Detail |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| `{item.check_id}` | `{item.category}` | `{'pass' if item.accepted else 'fail'}` | {item.message} |"
        for item in value.checks
    )
    return "\n".join(lines) + "\n"


def mission_plan_public_conformance_export_payloads(
    value: MissionPlanPublicConformance,
) -> dict[str, str]:
    """Return deterministic conformance projections."""

    return {
        "mission-plan-public-conformance.json": mission_plan_public_conformance_json(value),
        "mission-plan-public-conformance.csv": mission_plan_public_conformance_csv(value),
        "mission-plan-public-conformance.md": mission_plan_public_conformance_markdown(value),
    }


def mission_plan_public_replay_json(value: MissionPlanPublicReplay) -> str:
    """Render replay as canonical JSON."""

    return canonical_json(value.to_dict()) + "\n"


def mission_plan_public_replay_csv(value: MissionPlanPublicReplay) -> str:
    """Render one deterministic row per replay stage."""

    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("ordinal", "stage_id", "state", "input_address", "output_address", "detail", "content_address"))
    for item in value.stages:
        writer.writerow(
            (
                item.ordinal,
                item.stage_id,
                item.state,
                item.input_address,
                item.output_address,
                item.detail,
                item.content_address,
            )
        )
    return output.getvalue()


def mission_plan_public_replay_markdown(value: MissionPlanPublicReplay) -> str:
    """Render replay stages as a review timeline."""

    lines = [
        "# Mission plan public replay",
        "",
        f"- Plan: `{value.plan_id}`",
        f"- Accepted: `{value.accepted}`",
        f"- Stages: `{value.completed_stage_count}/{len(value.stages)}` completed",
        "",
        "| # | Stage | State | Detail |",
        "| ---: | --- | --- | --- |",
    ]
    lines.extend(
        f"| {item.ordinal} | `{item.stage_id}` | `{item.state.value}` | {item.detail} |"
        for item in value.stages
    )
    return "\n".join(lines) + "\n"


def mission_plan_public_replay_export_payloads(value: MissionPlanPublicReplay) -> dict[str, str]:
    """Return deterministic replay projections."""

    return {
        "mission-plan-public-replay.json": mission_plan_public_replay_json(value),
        "mission-plan-public-replay.csv": mission_plan_public_replay_csv(value),
        "mission-plan-public-replay.md": mission_plan_public_replay_markdown(value),
    }


def mission_plan_public_conformance_schema() -> dict[str, Any]:
    """Return the public conformance contract."""

    return {
        "version": MISSION_PLAN_PUBLIC_CONFORMANCE_SCHEMA_VERSION,
        "conformance_version": MISSION_PLAN_PUBLIC_CONFORMANCE_VERSION,
        "check_fields": ["check_id", "category", "accepted", "observed", "expected", "message", "content_address"],
        "categories": ["identity", "address", "boundary", "workflow", "resources", "decision"],
        "max_checks": MISSION_PLAN_PUBLIC_CONFORMANCE_MAX_CHECKS,
        "timestamp_free": True,
        "boundary": {
            "routing_metadata": False,
            "producer_metadata": False,
            "model_metadata": False,
            "programming_language_metadata": False,
            "raw_request_payload": False,
        },
    }


def mission_plan_public_conformance_capabilities() -> dict[str, Any]:
    """Return public conformance capabilities."""

    return {
        "version": MISSION_PLAN_PUBLIC_CONFORMANCE_CAPABILITIES_VERSION,
        "address_reconstruction": True,
        "dependency_order_reconciliation": True,
        "resource_reconciliation": True,
        "public_shape_audit": True,
        "restricted_key_audit": True,
        "addressed_checks": True,
        "timestamp_free": True,
        "json_export": True,
        "markdown_export": True,
        "csv_export": True,
        "read_only": True,
        "handler_execution": False,
        "clinical_authorization": False,
    }


def mission_plan_public_replay_schema() -> dict[str, Any]:
    """Return the public replay contract."""

    return {
        "version": MISSION_PLAN_PUBLIC_REPLAY_SCHEMA_VERSION,
        "replay_version": MISSION_PLAN_PUBLIC_REPLAY_VERSION,
        "stage_states": [item.value for item in MissionPlanPublicReplayStageState],
        "stages": [
            "receipt-hydration",
            "address-reconstruction",
            "dependency-order",
            "resource-reconciliation",
            "public-boundary",
            "finalize",
        ],
        "max_stages": MISSION_PLAN_PUBLIC_REPLAY_MAX_STAGES,
        "timestamp_free": True,
        "boundary": {
            "routing_metadata": False,
            "producer_metadata": False,
            "model_metadata": False,
            "programming_language_metadata": False,
            "raw_request_payload": False,
        },
    }


def mission_plan_public_replay_capabilities() -> dict[str, Any]:
    """Return public replay capabilities."""

    return {
        "version": MISSION_PLAN_PUBLIC_REPLAY_CAPABILITIES_VERSION,
        "timestamp_free_replay": True,
        "conformance_replay": True,
        "stage_addressing": True,
        "failure_visibility": True,
        "json_export": True,
        "markdown_export": True,
        "csv_export": True,
        "read_only": True,
        "handler_execution": False,
        "clinical_authorization": False,
    }


__all__ = [
    "MISSION_PLAN_PUBLIC_CONFORMANCE_CAPABILITIES_VERSION",
    "MISSION_PLAN_PUBLIC_CONFORMANCE_MAX_CHECKS",
    "MISSION_PLAN_PUBLIC_CONFORMANCE_SCHEMA_VERSION",
    "MISSION_PLAN_PUBLIC_CONFORMANCE_VERSION",
    "MISSION_PLAN_PUBLIC_REPLAY_CAPABILITIES_VERSION",
    "MISSION_PLAN_PUBLIC_REPLAY_MAX_STAGES",
    "MISSION_PLAN_PUBLIC_REPLAY_SCHEMA_VERSION",
    "MISSION_PLAN_PUBLIC_REPLAY_VERSION",
    "MissionPlanConformanceState",
    "MissionPlanPublicConformance",
    "MissionPlanPublicConformanceCheck",
    "MissionPlanPublicReplay",
    "MissionPlanPublicReplayStage",
    "MissionPlanPublicReplayStageState",
    "conform_mission_plan_public",
    "mission_plan_public_conformance_capabilities",
    "mission_plan_public_conformance_csv",
    "mission_plan_public_conformance_export_payloads",
    "mission_plan_public_conformance_json",
    "mission_plan_public_conformance_markdown",
    "mission_plan_public_conformance_schema",
    "mission_plan_public_replay_capabilities",
    "mission_plan_public_replay_csv",
    "mission_plan_public_replay_export_payloads",
    "mission_plan_public_replay_json",
    "mission_plan_public_replay_markdown",
    "mission_plan_public_replay_schema",
    "replay_mission_plan_public",
]
