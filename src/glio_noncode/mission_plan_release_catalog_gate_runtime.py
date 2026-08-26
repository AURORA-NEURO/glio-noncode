"""Timestamp-free runtime rehearsal for public mission-plan catalog gates.

The catalog gate is a pure decision function.  This companion runtime records
the ordered proof path that produces that decision: catalog hydration, semantic
audit, aggregate reporting, policy evaluation, deterministic replay, and final
state.  Stages are addressed and retain failed states instead of hiding them.
No stage executes a workflow handler or consults private planner state.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from io import StringIO
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .mission_plan_release_catalog import (
    MissionPlanReleaseCatalog,
    MissionPlanReleaseCatalogBundle,
    MissionPlanReleaseCatalogOffline,
    load_mission_plan_release_catalog,
)
from .mission_plan_release_catalog_audit import build_mission_plan_release_catalog_audit
from .mission_plan_release_catalog_gate import (
    MissionPlanReleaseCatalogGatePolicy,
    build_mission_plan_release_catalog_gate,
)
from .mission_plan_release_catalog_report import build_mission_plan_release_catalog_report
from .serialization import canonical_json, content_hash, jsonable


MISSION_PLAN_RELEASE_CATALOG_GATE_RUNTIME_VERSION = "mission-plan-release-catalog-gate-runtime-v1"
MISSION_PLAN_RELEASE_CATALOG_GATE_RUNTIME_SCHEMA_VERSION = "mission-plan-release-catalog-gate-runtime-schema-v1"
MISSION_PLAN_RELEASE_CATALOG_GATE_RUNTIME_CAPABILITIES_VERSION = "mission-plan-release-catalog-gate-runtime-capabilities-v1"
MISSION_PLAN_RELEASE_CATALOG_GATE_RUNTIME_MAX_STAGES = 8


def _text(value: Any, field: str, *, maximum: int = 180) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f"{field} must not be empty")
    if len(normalized) > maximum:
        raise ValidationError(f"{field} exceeds the maximum length")
    return normalized


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return {str(key): child for key, child in value.items()}


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


class MissionPlanReleaseCatalogGateRuntimeStageState(StrEnum):
    """Stable state for one gate-runtime stage."""

    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseCatalogGateRuntimeStage:
    """One addressed, ordered gate-runtime stage."""

    ordinal: int
    stage_id: str
    state: MissionPlanReleaseCatalogGateRuntimeStageState
    input_address: str | None
    output_address: str | None
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        if isinstance(self.ordinal, bool) or not isinstance(self.ordinal, int) or self.ordinal <= 0:
            raise ValidationError("catalog gate runtime stage ordinal must be positive")
        _text(self.stage_id, "catalog_gate_runtime_stage.stage_id", maximum=96)
        _text(self.detail, "catalog_gate_runtime_stage.detail", maximum=400)
        if self.input_address is not None:
            _text(self.input_address, "catalog_gate_runtime_stage.input_address")
        if self.output_address is not None:
            _text(self.output_address, "catalog_gate_runtime_stage.output_address")
        _text(self.content_address, "catalog_gate_runtime_stage.content_address")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MissionPlanReleaseCatalogGateRuntimeStage":
        body = _mapping(value, "catalog gate runtime stage")
        allowed = {"ordinal", "stage_id", "state", "input_address", "output_address", "detail", "content_address"}
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"catalog gate runtime stage contains unsupported fields: {sorted(unknown)}")
        if isinstance(body.get("ordinal"), bool):
            raise ValidationError("catalog gate runtime stage ordinal is invalid")
        try:
            ordinal = int(body.get("ordinal"))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValidationError("catalog gate runtime stage ordinal is invalid") from exc
        try:
            state = MissionPlanReleaseCatalogGateRuntimeStageState(str(body.get("state")))
        except ValueError as exc:
            raise ValidationError("catalog gate runtime stage state is invalid") from exc
        stage = cls(
            ordinal=ordinal,
            stage_id=_text(body.get("stage_id"), "catalog_gate_runtime_stage.stage_id", maximum=96),
            state=state,
            input_address=None if body.get("input_address") is None else _text(body.get("input_address"), "catalog_gate_runtime_stage.input_address"),
            output_address=None if body.get("output_address") is None else _text(body.get("output_address"), "catalog_gate_runtime_stage.output_address"),
            detail=_text(body.get("detail"), "catalog_gate_runtime_stage.detail", maximum=400),
            content_address=_text(body.get("content_address"), "catalog_gate_runtime_stage.content_address"),
        )
        expected = {
            "ordinal": stage.ordinal,
            "stage_id": stage.stage_id,
            "state": stage.state,
            "input_address": stage.input_address,
            "output_address": stage.output_address,
            "detail": stage.detail,
        }
        if stage.content_address != content_hash(expected, prefix="mission-plan-release-catalog-gate-runtime-stage"):
            raise ValidationError("catalog gate runtime stage content address does not reconcile")
        return stage

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseCatalogGateRuntime:
    """Addressed runtime rehearsal for one catalog-gate decision."""

    runtime_version: str
    catalog_id: str
    catalog_address: str
    gate_address: str
    stages: tuple[MissionPlanReleaseCatalogGateRuntimeStage, ...]
    replay_first_address: str
    replay_second_address: str
    replay_deterministic: bool
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if self.runtime_version != MISSION_PLAN_RELEASE_CATALOG_GATE_RUNTIME_VERSION:
            raise ValidationError("catalog gate runtime version is invalid")
        _text(self.catalog_id, "catalog_gate_runtime.catalog_id", maximum=96)
        for field in ("catalog_address", "gate_address", "replay_first_address", "replay_second_address", "content_address"):
            _text(getattr(self, field), f"catalog_gate_runtime.{field}")
        if not isinstance(self.replay_deterministic, bool) or not isinstance(self.accepted, bool):
            raise ValidationError("catalog gate runtime booleans are invalid")
        if len(self.stages) > MISSION_PLAN_RELEASE_CATALOG_GATE_RUNTIME_MAX_STAGES:
            raise ValidationError("catalog gate runtime stage count exceeds the bound")
        if tuple(item.ordinal for item in self.stages) != tuple(range(1, len(self.stages) + 1)):
            raise ValidationError("catalog gate runtime stages must have contiguous ordinals")

    @property
    def completed_stage_count(self) -> int:
        return sum(item.state is MissionPlanReleaseCatalogGateRuntimeStageState.COMPLETED for item in self.stages)

    @property
    def failed_stage_count(self) -> int:
        return sum(item.state is MissionPlanReleaseCatalogGateRuntimeStageState.FAILED for item in self.stages)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MissionPlanReleaseCatalogGateRuntime":
        body = _mapping(value, "mission plan release catalog gate runtime")
        allowed = {
            "runtime_version",
            "catalog_id",
            "catalog_address",
            "gate_address",
            "stage_count",
            "completed_stage_count",
            "failed_stage_count",
            "stages",
            "replay_first_address",
            "replay_second_address",
            "replay_deterministic",
            "accepted",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"catalog gate runtime contains unsupported fields: {sorted(unknown)}")
        raw_stages = body.get("stages", ())
        if not isinstance(raw_stages, (list, tuple)):
            raise ValidationError("catalog gate runtime stages must be an array")
        runtime = cls(
            runtime_version=_text(body.get("runtime_version"), "catalog_gate_runtime.runtime_version"),
            catalog_id=_text(body.get("catalog_id"), "catalog_gate_runtime.catalog_id", maximum=96),
            catalog_address=_text(body.get("catalog_address"), "catalog_gate_runtime.catalog_address"),
            gate_address=_text(body.get("gate_address"), "catalog_gate_runtime.gate_address"),
            stages=tuple(MissionPlanReleaseCatalogGateRuntimeStage.from_mapping(item) for item in raw_stages),
            replay_first_address=_text(body.get("replay_first_address"), "catalog_gate_runtime.replay_first_address"),
            replay_second_address=_text(body.get("replay_second_address"), "catalog_gate_runtime.replay_second_address"),
            replay_deterministic=_bool(body.get("replay_deterministic"), "catalog_gate_runtime.replay_deterministic"),
            accepted=_bool(body.get("accepted"), "catalog_gate_runtime.accepted"),
            content_address=_text(body.get("content_address"), "catalog_gate_runtime.content_address"),
        )
        if body.get("stage_count") != len(runtime.stages):
            raise ValidationError("catalog gate runtime stage count does not reconcile")
        if body.get("completed_stage_count") != runtime.completed_stage_count:
            raise ValidationError("catalog gate runtime completed stage count does not reconcile")
        if body.get("failed_stage_count") != runtime.failed_stage_count:
            raise ValidationError("catalog gate runtime failed stage count does not reconcile")
        expected = _runtime_address_body(runtime)
        if runtime.content_address != content_hash(expected, prefix="mission-plan-release-catalog-gate-runtime"):
            raise ValidationError("catalog gate runtime content address does not reconcile")
        return runtime

    def to_dict(self) -> dict[str, Any]:
        body = {
            "runtime_version": self.runtime_version,
            "catalog_id": self.catalog_id,
            "catalog_address": self.catalog_address,
            "gate_address": self.gate_address,
            "stage_count": len(self.stages),
            "completed_stage_count": self.completed_stage_count,
            "failed_stage_count": self.failed_stage_count,
            "stages": self.stages,
            "replay_first_address": self.replay_first_address,
            "replay_second_address": self.replay_second_address,
            "replay_deterministic": self.replay_deterministic,
            "accepted": self.accepted,
        }
        return jsonable(body | {"content_address": self.content_address})


def _runtime_address_body(runtime: MissionPlanReleaseCatalogGateRuntime) -> dict[str, Any]:
    return {
        "runtime_version": runtime.runtime_version,
        "catalog_id": runtime.catalog_id,
        "catalog_address": runtime.catalog_address,
        "gate_address": runtime.gate_address,
        "stages": runtime.stages,
        "replay_first_address": runtime.replay_first_address,
        "replay_second_address": runtime.replay_second_address,
        "replay_deterministic": runtime.replay_deterministic,
        "accepted": runtime.accepted,
    }


def _stage(
    ordinal: int,
    stage_id: str,
    state: MissionPlanReleaseCatalogGateRuntimeStageState,
    input_address: str | None,
    output_address: str | None,
    detail: str,
) -> MissionPlanReleaseCatalogGateRuntimeStage:
    body = {
        "ordinal": ordinal,
        "stage_id": stage_id,
        "state": state,
        "input_address": input_address,
        "output_address": output_address,
        "detail": detail,
    }
    return MissionPlanReleaseCatalogGateRuntimeStage(
        **body,
        content_address=content_hash(body, prefix="mission-plan-release-catalog-gate-runtime-stage"),
    )


def _catalog_address(value: MissionPlanReleaseCatalog | MissionPlanReleaseCatalogBundle | MissionPlanReleaseCatalogOffline | Mapping[str, Any] | str | Path) -> tuple[str, str]:
    if isinstance(value, MissionPlanReleaseCatalog):
        return value.catalog_id, value.content_address
    if isinstance(value, MissionPlanReleaseCatalogBundle):
        return value.catalog.catalog_id, value.catalog.content_address
    if isinstance(value, MissionPlanReleaseCatalogOffline):
        return value.catalog.catalog_id, value.catalog.content_address
    if isinstance(value, (str, Path)):
        catalog = load_mission_plan_release_catalog(value).catalog
        return catalog.catalog_id, catalog.content_address
    body = _mapping(value, "catalog gate runtime source")
    if isinstance(body.get("catalog"), Mapping):
        body = _mapping(body["catalog"], "catalog gate runtime catalog")
    catalog = MissionPlanReleaseCatalog.from_mapping(body)
    return catalog.catalog_id, catalog.content_address


def run_mission_plan_release_catalog_gate_runtime(
    value: MissionPlanReleaseCatalog | MissionPlanReleaseCatalogBundle | MissionPlanReleaseCatalogOffline | Mapping[str, Any] | str | Path,
    policy: MissionPlanReleaseCatalogGatePolicy | Mapping[str, Any] | None = None,
) -> MissionPlanReleaseCatalogGateRuntime:
    """Run the deterministic, side-effect-free catalog-gate proof path."""

    catalog_id, catalog_address = _catalog_address(value)
    selected_policy = policy if isinstance(policy, MissionPlanReleaseCatalogGatePolicy) else MissionPlanReleaseCatalogGatePolicy.from_mapping(policy or {})
    stages: list[MissionPlanReleaseCatalogGateRuntimeStage] = []
    stages.append(_stage(1, "catalog-hydration", MissionPlanReleaseCatalogGateRuntimeStageState.COMPLETED, catalog_address, catalog_address, "Public catalog hydrated and address checked."))
    audit = build_mission_plan_release_catalog_audit(value)
    stages.append(_stage(2, "semantic-audit", MissionPlanReleaseCatalogGateRuntimeStageState.COMPLETED if audit.accepted else MissionPlanReleaseCatalogGateRuntimeStageState.FAILED, catalog_address, audit.content_address, "Independent catalog semantic audit completed."))
    report = build_mission_plan_release_catalog_report(value)
    stages.append(_stage(3, "aggregate-report", MissionPlanReleaseCatalogGateRuntimeStageState.COMPLETED, audit.content_address, report.content_address, "Catalog distributions and conserved totals computed."))
    gate = build_mission_plan_release_catalog_gate(value, selected_policy)
    stages.append(_stage(4, "policy-gate", MissionPlanReleaseCatalogGateRuntimeStageState.COMPLETED if gate.accepted else MissionPlanReleaseCatalogGateRuntimeStageState.FAILED, report.content_address, gate.content_address, "Explicit catalog handoff thresholds evaluated."))
    first = build_mission_plan_release_catalog_gate(value, selected_policy)
    second = build_mission_plan_release_catalog_gate(value, selected_policy)
    deterministic = first.content_address == second.content_address == gate.content_address
    replay_address = content_hash({"first": first.content_address, "second": second.content_address, "expected": gate.content_address, "deterministic": deterministic}, prefix="mission-plan-release-catalog-gate-replay")
    stages.append(_stage(5, "deterministic-replay", MissionPlanReleaseCatalogGateRuntimeStageState.COMPLETED if deterministic else MissionPlanReleaseCatalogGateRuntimeStageState.FAILED, gate.content_address, replay_address, "Policy gate rebuilt twice with stable content addressing."))
    accepted = gate.accepted and audit.accepted and report.accepted and deterministic
    final_address = content_hash({"catalog_address": catalog_address, "gate_address": gate.content_address, "replay_address": replay_address, "accepted": accepted}, prefix="mission-plan-release-catalog-gate-finalize")
    stages.append(_stage(6, "public-state", MissionPlanReleaseCatalogGateRuntimeStageState.COMPLETED if accepted else MissionPlanReleaseCatalogGateRuntimeStageState.FAILED, replay_address, final_address, "Final public catalog-gate state published."))
    body = {
        "runtime_version": MISSION_PLAN_RELEASE_CATALOG_GATE_RUNTIME_VERSION,
        "catalog_id": catalog_id,
        "catalog_address": catalog_address,
        "gate_address": gate.content_address,
        "stages": tuple(stages),
        "replay_first_address": first.content_address,
        "replay_second_address": second.content_address,
        "replay_deterministic": deterministic,
        "accepted": accepted,
    }
    return MissionPlanReleaseCatalogGateRuntime(
        **body,
        content_address=content_hash(body, prefix="mission-plan-release-catalog-gate-runtime"),
    )


def mission_plan_release_catalog_gate_runtime_json(runtime: MissionPlanReleaseCatalogGateRuntime | Mapping[str, Any]) -> str:
    value = runtime if isinstance(runtime, MissionPlanReleaseCatalogGateRuntime) else MissionPlanReleaseCatalogGateRuntime.from_mapping(runtime)
    return canonical_json(value.to_dict())


def mission_plan_release_catalog_gate_runtime_csv(runtime: MissionPlanReleaseCatalogGateRuntime | Mapping[str, Any]) -> str:
    value = runtime if isinstance(runtime, MissionPlanReleaseCatalogGateRuntime) else MissionPlanReleaseCatalogGateRuntime.from_mapping(runtime)
    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("ordinal", "stage_id", "state", "input_address", "output_address", "detail", "content_address"))
    for item in value.stages:
        writer.writerow((item.ordinal, item.stage_id, item.state.value, item.input_address or "", item.output_address or "", item.detail, item.content_address))
    return output.getvalue()


def mission_plan_release_catalog_gate_runtime_markdown(runtime: MissionPlanReleaseCatalogGateRuntime | Mapping[str, Any]) -> str:
    value = runtime if isinstance(runtime, MissionPlanReleaseCatalogGateRuntime) else MissionPlanReleaseCatalogGateRuntime.from_mapping(runtime)
    lines = [
        "# Mission plan release catalog gate runtime",
        "",
        f"- Catalog: `{value.catalog_id}`",
        f"- Catalog address: `{value.catalog_address}`",
        f"- Gate address: `{value.gate_address}`",
        f"- Stages: {len(value.stages)}",
        f"- Completed: {value.completed_stage_count}",
        f"- Failed: {value.failed_stage_count}",
        f"- Replay deterministic: {str(value.replay_deterministic).lower()}",
        f"- Accepted: {str(value.accepted).lower()}",
        "",
        "## Stages",
        "",
        "| Ordinal | Stage | State | Input | Output | Detail |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    lines.extend(f"| {item.ordinal} | {item.stage_id} | {item.state.value} | `{item.input_address or ''}` | `{item.output_address or ''}` | {item.detail} |" for item in value.stages)
    return "\n".join(lines) + "\n"


def mission_plan_release_catalog_gate_runtime_export_payloads(runtime: MissionPlanReleaseCatalogGateRuntime | Mapping[str, Any]) -> dict[str, str]:
    value = runtime if isinstance(runtime, MissionPlanReleaseCatalogGateRuntime) else MissionPlanReleaseCatalogGateRuntime.from_mapping(runtime)
    return {
        "mission-plan-release-catalog-gate-runtime.json": mission_plan_release_catalog_gate_runtime_json(value),
        "mission-plan-release-catalog-gate-runtime.csv": mission_plan_release_catalog_gate_runtime_csv(value),
        "mission-plan-release-catalog-gate-runtime.md": mission_plan_release_catalog_gate_runtime_markdown(value),
    }


def mission_plan_release_catalog_gate_runtime_schema() -> dict[str, Any]:
    return {
        "version": MISSION_PLAN_RELEASE_CATALOG_GATE_RUNTIME_SCHEMA_VERSION,
        "runtime_version": MISSION_PLAN_RELEASE_CATALOG_GATE_RUNTIME_VERSION,
        "max_stages": MISSION_PLAN_RELEASE_CATALOG_GATE_RUNTIME_MAX_STAGES,
        "stage_states": [item.value for item in MissionPlanReleaseCatalogGateRuntimeStageState],
        "stages": ["catalog-hydration", "semantic-audit", "aggregate-report", "policy-gate", "deterministic-replay", "public-state"],
        "timestamp_free": True,
        "handler_execution": False,
        "clinical_authorization": False,
    }


def mission_plan_release_catalog_gate_runtime_capabilities() -> dict[str, Any]:
    return {
        "version": MISSION_PLAN_RELEASE_CATALOG_GATE_RUNTIME_CAPABILITIES_VERSION,
        "timestamp_free_replay": True,
        "stage_addressing": True,
        "failure_visibility": True,
        "audit_stage": True,
        "report_stage": True,
        "policy_stage": True,
        "read_only": True,
        "verified_offline_input": True,
        "json_export": True,
        "csv_export": True,
        "markdown_export": True,
        "handler_execution": False,
        "clinical_authorization": False,
        "boundary": {
            "raw_request_payload": False,
            "routing_metadata": False,
            "attribution": False,
            "language_metadata": False,
            "model_metadata": False,
            "producer_metadata": False,
            "identity_metadata": False,
        },
    }


__all__ = [
    "MISSION_PLAN_RELEASE_CATALOG_GATE_RUNTIME_CAPABILITIES_VERSION",
    "MISSION_PLAN_RELEASE_CATALOG_GATE_RUNTIME_MAX_STAGES",
    "MISSION_PLAN_RELEASE_CATALOG_GATE_RUNTIME_SCHEMA_VERSION",
    "MISSION_PLAN_RELEASE_CATALOG_GATE_RUNTIME_VERSION",
    "MissionPlanReleaseCatalogGateRuntime",
    "MissionPlanReleaseCatalogGateRuntimeStage",
    "MissionPlanReleaseCatalogGateRuntimeStageState",
    "mission_plan_release_catalog_gate_runtime_capabilities",
    "mission_plan_release_catalog_gate_runtime_csv",
    "mission_plan_release_catalog_gate_runtime_export_payloads",
    "mission_plan_release_catalog_gate_runtime_json",
    "mission_plan_release_catalog_gate_runtime_markdown",
    "mission_plan_release_catalog_gate_runtime_schema",
    "run_mission_plan_release_catalog_gate_runtime",
]
