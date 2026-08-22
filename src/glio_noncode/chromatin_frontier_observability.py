"""Stage and event trace objects for Domain 07 runtime inspection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .chromatin_frontier_runtime import ChromatinFrontierRuntimeResult
from .serialization import content_hash, jsonable


class ChromatinFrontierStage(StrEnum):
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
class ChromatinFrontierStageReceipt:
    stage: ChromatinFrontierStage
    passed: bool
    artifact_address: str
    record_count: int
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinFrontierEvent:
    sequence: int
    stage: ChromatinFrontierStage
    event_kind: str
    record_ids: tuple[str, ...]
    artifact_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinFrontierTrace:
    run_id: str
    stage_receipts: tuple[ChromatinFrontierStageReceipt, ...]
    events: tuple[ChromatinFrontierEvent, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.stage_receipts) and all(item.passed for item in self.stage_receipts)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


@dataclass(frozen=True, slots=True)
class ChromatinFrontierRunComparison:
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


def _stage_rows(
    runtime: ChromatinFrontierRuntimeResult,
) -> tuple[tuple[ChromatinFrontierStage, bool, str, int, str], ...]:
    bundle = runtime.quality.bundle
    schema_check = next(
        check for check in runtime.quality.checks if check.check_id == "schema"
    )
    return (
        (
            ChromatinFrontierStage.DATA_AUDIT,
            bundle.data_audit.accepted,
            bundle.data_audit.content_address,
            16,
            "source and payload boundary",
        ),
        (
            ChromatinFrontierStage.EVALUATION,
            bundle.evaluation.accepted,
            bundle.evaluation.content_address,
            len(bundle.evaluation.receipts),
            "adapter receipts and checks",
        ),
        (
            ChromatinFrontierStage.REPLAY,
            bundle.replay.accepted,
            bundle.replay.content_address,
            len(bundle.evaluation.receipts),
            "deterministic replay",
        ),
        (
            ChromatinFrontierStage.SCENARIOS,
            bundle.scenarios.accepted,
            bundle.scenarios.content_address,
            len(bundle.scenarios.scenarios),
            "positive and control scenarios",
        ),
        (
            ChromatinFrontierStage.POLICY,
            bundle.policy.accepted,
            bundle.policy.content_address,
            len(bundle.policy.checks),
            "scope and interpretation policy",
        ),
        (
            ChromatinFrontierStage.SCHEMA,
            schema_check.passed,
            schema_check.content_address,
            4,
            "operation schema validation",
        ),
        (
            ChromatinFrontierStage.LINEAGE,
            bool(bundle.lineage.accepted),
            bundle.lineage.content_address,
            len(bundle.lineage.edges),
            "source-to-receipt lineage",
        ),
        (
            ChromatinFrontierStage.RECONCILIATION,
            bundle.reconciliation.accepted,
            bundle.reconciliation.content_address,
            len(bundle.reconciliation.items),
            "expected and observed states",
        ),
        (
            ChromatinFrontierStage.BUNDLE,
            bundle.accepted,
            bundle.bundle_address,
            len(bundle.record_ids),
            "content-addressed release input",
        ),
    )


def build_chromatin_frontier_trace(
    runtime: ChromatinFrontierRuntimeResult,
) -> ChromatinFrontierTrace:
    stages: list[ChromatinFrontierStageReceipt] = []
    events: list[ChromatinFrontierEvent] = []
    record_ids = runtime.quality.bundle.record_ids
    for index, (stage, passed, artifact_address, record_count, detail) in enumerate(
        _stage_rows(runtime), start=1
    ):
        body = {
            "stage": stage,
            "passed": passed,
            "artifact_address": artifact_address,
            "record_count": record_count,
            "detail": detail,
        }
        stage_receipt = ChromatinFrontierStageReceipt(
            **body,
            content_address=content_hash(body),
        )
        stages.append(stage_receipt)
        event_body = {
            "sequence": index,
            "stage": stage,
            "event_kind": "stage_completed" if passed else "stage_failed",
            "record_ids": record_ids
            if stage in {ChromatinFrontierStage.EVALUATION, ChromatinFrontierStage.BUNDLE}
            else (),
            "artifact_address": artifact_address,
            "detail": detail,
        }
        events.append(
            ChromatinFrontierEvent(**event_body, content_address=content_hash(event_body))
        )
    body = {"run_id": runtime.run_id, "stage_receipts": stages, "events": events}
    return ChromatinFrontierTrace(runtime.run_id, tuple(stages), tuple(events), content_hash(body))


def compare_chromatin_frontier_runs(
    left: ChromatinFrontierRuntimeResult,
    right: ChromatinFrontierRuntimeResult,
) -> ChromatinFrontierRunComparison:
    left_map = {
        item.record_id: item.adapter_state for item in left.quality.bundle.evaluation.receipts
    }
    right_map = {
        item.record_id: item.adapter_state for item in right.quality.bundle.evaluation.receipts
    }
    changes = tuple(
        (record_id, left_map.get(record_id, "missing"), right_map.get(record_id, "missing"))
        for record_id in sorted(set(left_map) | set(right_map))
        if left_map.get(record_id) != right_map.get(record_id)
    )
    body = {
        "left_run_id": left.run_id,
        "right_run_id": right.run_id,
        "status_changed": left.status != right.status,
        "quality_changed": left.quality.accepted != right.quality.accepted,
        "review_count_delta": right.quality.bundle.metrics.review_records
        - left.quality.bundle.metrics.review_records,
        "state_changes": changes,
        "address_changed": left.quality.bundle.bundle_address
        != right.quality.bundle.bundle_address,
    }
    return ChromatinFrontierRunComparison(**body, content_address=content_hash(body))


def chromatin_frontier_review_budget(
    view: Any,
    *,
    maximum_priority: int | None = None,
) -> dict[str, Any]:
    entries = (
        view.review_queue
        if maximum_priority is None
        else tuple(item for item in view.review_queue if item.priority <= maximum_priority)
    )
    body = {
        "fixture_id": view.fixture_id,
        "eligible_review_count": len(entries),
        "maximum_priority": maximum_priority,
        "eligible_record_ids": tuple(item.record_id for item in entries),
        "summary_address": view.content_address,
    }
    return body | {"content_address": content_hash(body)}


__all__ = [
    "ChromatinFrontierEvent",
    "ChromatinFrontierRunComparison",
    "ChromatinFrontierStage",
    "ChromatinFrontierStageReceipt",
    "ChromatinFrontierTrace",
    "build_chromatin_frontier_trace",
    "chromatin_frontier_review_budget",
    "compare_chromatin_frontier_runs",
]
