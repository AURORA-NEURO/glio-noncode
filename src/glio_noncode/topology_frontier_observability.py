"""Stage trace and run comparison for Domain 09."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable
from .topology_frontier_runtime import TopologyFrontierRuntimeResult


class TopologyFrontierStage(StrEnum):
    DATA_AUDIT = "data_audit"
    EVALUATION = "evaluation"
    REPLAY = "replay"
    SCENARIOS = "scenarios"
    POLICY = "policy"
    SCHEMA = "schema"
    LINEAGE = "lineage"
    RECONCILIATION = "reconciliation"
    BUNDLE = "bundle"


@dataclass(frozen=True, slots=True)
class TopologyFrontierStageReceipt:
    stage: TopologyFrontierStage
    passed: bool
    artifact_address: str
    record_count: int
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyFrontierEvent:
    sequence: int
    stage: TopologyFrontierStage
    event_kind: str
    record_ids: tuple[str, ...]
    artifact_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyFrontierTrace:
    run_id: str
    stage_receipts: tuple[TopologyFrontierStageReceipt, ...]
    events: tuple[TopologyFrontierEvent, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.stage_receipts) and all(item.passed for item in self.stage_receipts)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


@dataclass(frozen=True, slots=True)
class TopologyFrontierRunComparison:
    left_run_id: str
    right_run_id: str
    status_changed: bool
    quality_changed: bool
    review_count_delta: int
    state_changes: tuple[tuple[str, str, str], ...]
    address_changed: bool
    content_address: str

    @property
    def equivalent(self) -> bool:
        return not self.status_changed and not self.quality_changed and not self.state_changes

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"equivalent": self.equivalent}


def _stage_rows(runtime: TopologyFrontierRuntimeResult) -> tuple[tuple[TopologyFrontierStage, bool, str, int, str], ...]:
    bundle = runtime.quality.bundle
    schema_check = next(check for check in runtime.quality.checks if check.check_id == "schema")
    return (
        (TopologyFrontierStage.DATA_AUDIT, bundle.data_audit.accepted, bundle.data_audit.content_address, 16, "source and payload boundary"),
        (TopologyFrontierStage.EVALUATION, bundle.evaluation.accepted, bundle.evaluation.content_address, len(bundle.evaluation.receipts), "adapter receipts and checks"),
        (TopologyFrontierStage.REPLAY, bundle.replay.accepted, bundle.replay.content_address, len(bundle.evaluation.receipts), "deterministic replay"),
        (TopologyFrontierStage.SCENARIOS, bundle.scenarios.accepted, bundle.scenarios.content_address, len(bundle.scenarios.scenarios), "positive and control scenarios"),
        (TopologyFrontierStage.POLICY, bundle.policy.accepted, bundle.policy.content_address, len(bundle.policy.checks), "scope and interpretation policy"),
        (TopologyFrontierStage.SCHEMA, schema_check.passed, schema_check.content_address, 20, "operation schema validation"),
        (TopologyFrontierStage.LINEAGE, bundle.lineage.accepted, bundle.lineage.content_address, len(bundle.lineage.edges), "source-to-receipt lineage"),
        (TopologyFrontierStage.RECONCILIATION, bundle.reconciliation.accepted, bundle.reconciliation.content_address, len(bundle.reconciliation.items), "expected and observed states"),
        (TopologyFrontierStage.BUNDLE, bundle.accepted, bundle.bundle_address, len(bundle.record_ids), "content-addressed release input"),
    )


def build_topology_frontier_trace(runtime: TopologyFrontierRuntimeResult) -> TopologyFrontierTrace:
    stages: list[TopologyFrontierStageReceipt] = []
    events: list[TopologyFrontierEvent] = []
    record_ids = runtime.quality.bundle.record_ids
    for index, (stage, passed, artifact_address, record_count, detail) in enumerate(_stage_rows(runtime), start=1):
        body = {"stage": stage, "passed": passed, "artifact_address": artifact_address, "record_count": record_count, "detail": detail}
        stages.append(TopologyFrontierStageReceipt(**body, content_address=content_hash(body)))
        event_body = {"sequence": index, "stage": stage, "event_kind": "stage_completed" if passed else "stage_failed", "record_ids": record_ids if stage in {TopologyFrontierStage.EVALUATION, TopologyFrontierStage.BUNDLE} else (), "artifact_address": artifact_address, "detail": detail}
        events.append(TopologyFrontierEvent(**event_body, content_address=content_hash(event_body)))
    body = {"run_id": runtime.run_id, "stage_receipts": stages, "events": events}
    return TopologyFrontierTrace(runtime.run_id, tuple(stages), tuple(events), content_hash(body))


def compare_topology_frontier_runs(left: TopologyFrontierRuntimeResult, right: TopologyFrontierRuntimeResult) -> TopologyFrontierRunComparison:
    left_map = {item.record_id: item.adapter_state for item in left.quality.bundle.evaluation.receipts}
    right_map = {item.record_id: item.adapter_state for item in right.quality.bundle.evaluation.receipts}
    changes = tuple((record_id, left_map.get(record_id, "missing"), right_map.get(record_id, "missing")) for record_id in sorted(set(left_map) | set(right_map)) if left_map.get(record_id) != right_map.get(record_id))
    body = {"left_run_id": left.run_id, "right_run_id": right.run_id, "status_changed": left.status != right.status, "quality_changed": left.quality.accepted != right.quality.accepted, "review_count_delta": right.quality.bundle.metrics.total_review - left.quality.bundle.metrics.total_review, "state_changes": changes, "address_changed": left.quality.bundle.bundle_address != right.quality.bundle.bundle_address}
    return TopologyFrontierRunComparison(**body, content_address=content_hash(body))


__all__ = [
    "TopologyFrontierEvent",
    "TopologyFrontierRunComparison",
    "TopologyFrontierStage",
    "TopologyFrontierStageReceipt",
    "TopologyFrontierTrace",
    "build_topology_frontier_trace",
    "compare_topology_frontier_runs",
]
