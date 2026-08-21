"""Stage traces and comparison helpers for Domain 06 C13-C16."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .sequence_frontier_runtime import SequenceFrontierRuntimeResult
from .sequence_frontier_views import SequenceFrontierView, sequence_frontier_review_summary
from .serialization import content_hash, jsonable, require_non_empty


class SequenceFrontierStage(StrEnum):
    DATA_AUDIT = "data_audit"
    ADAPTER_EVALUATION = "adapter_evaluation"
    REPLAY = "replay"
    SCENARIOS = "scenarios"
    POLICY = "policy"
    LINEAGE = "lineage"
    RECONCILIATION = "reconciliation"
    METRICS = "metrics"
    BUNDLE = "bundle"


@dataclass(frozen=True, slots=True)
class SequenceFrontierStageReceipt:
    stage: SequenceFrontierStage
    status: str
    check_count: int
    passed_check_count: int
    review_count: int
    artifact_address: str
    duration_ms: int
    content_address: str

    def __post_init__(self) -> None:
        if (
            min(self.check_count, self.passed_check_count, self.review_count, self.duration_ms) < 0
            or self.passed_check_count > self.check_count
        ):
            raise ValueError("sequence frontier stage counts are invalid")
        require_non_empty(self.status, "stage status")
        require_non_empty(self.artifact_address, "stage artifact address")

    @property
    def accepted(self) -> bool:
        return self.status == "accepted"

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


@dataclass(frozen=True, slots=True)
class SequenceFrontierEvent:
    event_id: str
    run_id: str
    stage: SequenceFrontierStage
    event_type: str
    state: str
    detail: str
    artifact_address: str
    sequence: int
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "event_id",
            "run_id",
            "event_type",
            "state",
            "detail",
            "artifact_address",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.sequence < 1:
            raise ValueError("event sequence must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceFrontierTrace:
    run_id: str
    stage_receipts: tuple[SequenceFrontierStageReceipt, ...]
    events: tuple[SequenceFrontierEvent, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.stage_receipts) and all(item.accepted for item in self.stage_receipts)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "stage_names": [item.stage.value for item in self.stage_receipts],
        }


@dataclass(frozen=True, slots=True)
class SequenceFrontierRunComparison:
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
        return (
            not self.status_changed
            and not self.quality_changed
            and self.review_count_delta == 0
            and not self.state_changes
            and not self.address_changed
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"equivalent": self.equivalent}


def _stage(
    stage: SequenceFrontierStage, status: str, checks: int, passed: int, review: int, address: str
) -> SequenceFrontierStageReceipt:
    body = {
        "stage": stage,
        "status": status,
        "check_count": checks,
        "passed_check_count": passed,
        "review_count": review,
        "artifact_address": address,
        "duration_ms": 0,
    }
    return SequenceFrontierStageReceipt(**body, content_address=content_hash(body))


def build_sequence_frontier_trace(
    runtime: SequenceFrontierRuntimeResult, view: SequenceFrontierView | None = None
) -> SequenceFrontierTrace:
    bundle = runtime.quality.bundle
    review_count = view.review_count if view else bundle.metrics.review_records
    stages = (
        _stage(
            SequenceFrontierStage.DATA_AUDIT,
            "accepted" if bundle.data_audit.accepted else "rejected",
            len(bundle.data_audit.checks),
            sum(item.passed for item in bundle.data_audit.checks),
            review_count,
            bundle.data_audit.content_address,
        ),
        _stage(
            SequenceFrontierStage.ADAPTER_EVALUATION,
            "accepted" if bundle.evaluation.accepted else "rejected",
            len(bundle.evaluation.checks),
            sum(item.passed for item in bundle.evaluation.checks),
            review_count,
            bundle.evaluation.content_address,
        ),
        _stage(
            SequenceFrontierStage.REPLAY,
            "accepted" if bundle.replay.accepted else "rejected",
            len(bundle.replay.checks),
            sum(item.passed for item in bundle.replay.checks),
            review_count,
            bundle.replay.content_address,
        ),
        _stage(
            SequenceFrontierStage.SCENARIOS,
            "accepted" if bundle.scenarios.accepted else "rejected",
            len(bundle.scenarios.checks),
            sum(item.passed for item in bundle.scenarios.checks),
            review_count,
            bundle.scenarios.content_address,
        ),
        _stage(
            SequenceFrontierStage.POLICY,
            "accepted" if bundle.policy.accepted else "rejected",
            len(bundle.policy.checks),
            sum(item.passed for item in bundle.policy.checks),
            review_count,
            bundle.policy.content_address,
        ),
        _stage(
            SequenceFrontierStage.LINEAGE,
            "accepted" if bundle.lineage.accepted else "rejected",
            len(bundle.lineage.edges),
            len(bundle.lineage.edges),
            review_count,
            bundle.lineage.content_address,
        ),
        _stage(
            SequenceFrontierStage.RECONCILIATION,
            "accepted" if bundle.reconciliation.accepted else "rejected",
            len(bundle.reconciliation.items) + len(bundle.reconciliation.checks),
            sum(item.passed for item in bundle.reconciliation.items)
            + sum(passed for _, passed in bundle.reconciliation.checks),
            review_count,
            bundle.reconciliation.content_address,
        ),
        _stage(
            SequenceFrontierStage.METRICS,
            "accepted",
            1,
            1,
            review_count,
            bundle.metrics.content_address,
        ),
        _stage(
            SequenceFrontierStage.BUNDLE,
            "accepted" if bundle.accepted else "rejected",
            1,
            int(bundle.accepted),
            review_count,
            bundle.content_address,
        ),
    )
    events: list[SequenceFrontierEvent] = []
    for sequence, receipt in enumerate(stages, start=1):
        body = {
            "event_id": f"{runtime.run_id}:{sequence}",
            "run_id": runtime.run_id,
            "stage": receipt.stage,
            "event_type": "stage_completed",
            "state": receipt.status,
            "detail": f"{receipt.stage.value} completed",
            "artifact_address": receipt.artifact_address,
            "sequence": sequence,
        }
        events.append(SequenceFrontierEvent(**body, content_address=content_hash(body)))
    body = {"run_id": runtime.run_id, "stage_receipts": stages, "events": events}
    return SequenceFrontierTrace(runtime.run_id, stages, tuple(events), content_hash(body))


def compare_sequence_frontier_runs(
    left: SequenceFrontierRuntimeResult, right: SequenceFrontierRuntimeResult
) -> SequenceFrontierRunComparison:
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
        "address_changed": left.quality.bundle.content_address
        != right.quality.bundle.content_address,
    }
    return SequenceFrontierRunComparison(**body, content_address=content_hash(body))


def sequence_frontier_review_budget(
    view: SequenceFrontierView, *, maximum_priority: int | None = None
) -> dict[str, Any]:
    entries = (
        view.review_queue
        if maximum_priority is None
        else tuple(item for item in view.review_queue if item.priority <= maximum_priority)
    )
    summary = sequence_frontier_review_summary(view)
    body = {
        "fixture_id": view.fixture_id,
        "eligible_review_count": len(entries),
        "maximum_priority": maximum_priority,
        "eligible_record_ids": tuple(item.record_id for item in entries),
        "summary_address": summary["content_address"],
    }
    return body | {"content_address": content_hash(body)}


__all__ = [
    "SequenceFrontierEvent",
    "SequenceFrontierRunComparison",
    "SequenceFrontierStage",
    "SequenceFrontierStageReceipt",
    "SequenceFrontierTrace",
    "build_sequence_frontier_trace",
    "compare_sequence_frontier_runs",
    "sequence_frontier_review_budget",
]
