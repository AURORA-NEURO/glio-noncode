"""Deterministic stage traces and run-comparison helpers for C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .atlas_alpha_evidence_runtime import AtlasAlphaEvidenceRuntimeResult
from .atlas_alpha_evidence_views import AtlasAlphaEvidenceView, review_queue_summary
from .serialization import content_hash, jsonable, require_non_empty


class AtlasAlphaEvidenceStage(StrEnum):
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
class AtlasAlphaEvidenceStageReceipt:
    """One stage's bounded result and timing metadata."""

    stage: AtlasAlphaEvidenceStage
    status: str
    check_count: int
    passed_check_count: int
    review_count: int
    artifact_address: str
    duration_ms: int
    content_address: str

    def __post_init__(self) -> None:
        if (
            self.check_count < 0
            or self.passed_check_count < 0
            or self.review_count < 0
            or self.duration_ms < 0
        ):
            raise ValueError("stage receipt counts and duration cannot be negative")
        if self.passed_check_count > self.check_count:
            raise ValueError("passed stage checks cannot exceed check count")
        require_non_empty(self.status, "stage status")
        require_non_empty(self.artifact_address, "stage artifact address")

    @property
    def accepted(self) -> bool:
        return self.status == "accepted"

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceEvent:
    """Sanitized event emitted at a stage boundary."""

    event_id: str
    run_id: str
    stage: AtlasAlphaEvidenceStage
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
class AtlasAlphaEvidenceTrace:
    """Ordered, sanitized execution trace."""

    run_id: str
    stage_receipts: tuple[AtlasAlphaEvidenceStageReceipt, ...]
    events: tuple[AtlasAlphaEvidenceEvent, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.stage_receipts) and all(
            receipt.accepted for receipt in self.stage_receipts
        )

    @property
    def stage_names(self) -> tuple[str, ...]:
        return tuple(receipt.stage.value for receipt in self.stage_receipts)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted, "stage_names": list(self.stage_names)}


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceRunComparison:
    """Difference summary between two sanitized runs."""

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
    stage: AtlasAlphaEvidenceStage,
    status: str,
    check_count: int,
    passed: int,
    review_count: int,
    address: str,
    duration_ms: int = 0,
) -> AtlasAlphaEvidenceStageReceipt:
    body = {
        "stage": stage,
        "status": status,
        "check_count": check_count,
        "passed_check_count": passed,
        "review_count": review_count,
        "artifact_address": address,
        "duration_ms": duration_ms,
    }
    return AtlasAlphaEvidenceStageReceipt(**body, content_address=content_hash(body))


def build_atlas_alpha_evidence_trace(
    runtime: AtlasAlphaEvidenceRuntimeResult, view: AtlasAlphaEvidenceView | None = None
) -> AtlasAlphaEvidenceTrace:
    """Build a nine-stage trace from one runtime quality result."""

    quality = runtime.quality
    bundle = quality.bundle
    review_count = view.review_count if view else bundle.metrics.review_records
    stages = (
        _stage(
            AtlasAlphaEvidenceStage.DATA_AUDIT,
            "accepted" if bundle.data_audit.accepted else "rejected",
            len(bundle.data_audit.checks),
            sum(item.passed for item in bundle.data_audit.checks),
            review_count,
            bundle.data_audit.content_address,
        ),
        _stage(
            AtlasAlphaEvidenceStage.ADAPTER_EVALUATION,
            "accepted" if bundle.evaluation.accepted else "rejected",
            len(bundle.evaluation.checks),
            sum(item.passed for item in bundle.evaluation.checks),
            review_count,
            bundle.evaluation.content_address,
        ),
        _stage(
            AtlasAlphaEvidenceStage.REPLAY,
            "accepted" if bundle.replay.accepted else "rejected",
            len(bundle.replay.checks),
            sum(item.passed for item in bundle.replay.checks),
            review_count,
            bundle.replay.content_address,
        ),
        _stage(
            AtlasAlphaEvidenceStage.SCENARIOS,
            "accepted" if bundle.scenarios.accepted else "rejected",
            len(bundle.scenarios.checks),
            sum(item.passed for item in bundle.scenarios.checks),
            review_count,
            bundle.scenarios.content_address,
        ),
        _stage(
            AtlasAlphaEvidenceStage.POLICY,
            "accepted" if bundle.policy.accepted else "rejected",
            len(bundle.policy.checks),
            sum(item.passed for item in bundle.policy.checks),
            review_count,
            bundle.policy.content_address,
        ),
        _stage(
            AtlasAlphaEvidenceStage.LINEAGE,
            "accepted" if bundle.lineage.accepted else "rejected",
            len(bundle.lineage.edges),
            len(bundle.lineage.edges),
            review_count,
            bundle.lineage.content_address,
        ),
        _stage(
            AtlasAlphaEvidenceStage.RECONCILIATION,
            "accepted" if bundle.reconciliation.accepted else "rejected",
            len(bundle.reconciliation.items) + len(bundle.reconciliation.checks),
            sum(item.passed for item in bundle.reconciliation.items)
            + sum(passed for _, passed in bundle.reconciliation.checks),
            review_count,
            bundle.reconciliation.content_address,
        ),
        _stage(
            AtlasAlphaEvidenceStage.METRICS,
            "accepted",
            1,
            1,
            review_count,
            bundle.metrics.content_address,
        ),
        _stage(
            AtlasAlphaEvidenceStage.BUNDLE,
            "accepted" if bundle.accepted else "rejected",
            1,
            int(bundle.accepted),
            review_count,
            bundle.content_address,
        ),
    )
    events: list[AtlasAlphaEvidenceEvent] = []
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
        events.append(AtlasAlphaEvidenceEvent(**body, content_address=content_hash(body)))
    body = {"run_id": runtime.run_id, "stage_receipts": stages, "events": events}
    return AtlasAlphaEvidenceTrace(runtime.run_id, stages, tuple(events), content_hash(body))


def compare_atlas_alpha_evidence_runs(
    left: AtlasAlphaEvidenceRuntimeResult, right: AtlasAlphaEvidenceRuntimeResult
) -> AtlasAlphaEvidenceRunComparison:
    """Compare states, quality, review volume, and addresses without payloads."""

    left_map = {
        item.record_id: item.adapter_state for item in left.quality.bundle.evaluation.receipts
    }
    right_map = {
        item.record_id: item.adapter_state for item in right.quality.bundle.evaluation.receipts
    }
    state_changes = tuple(
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
        "state_changes": state_changes,
        "address_changed": left.quality.bundle.content_address
        != right.quality.bundle.content_address,
    }
    return AtlasAlphaEvidenceRunComparison(**body, content_address=content_hash(body))


def atlas_alpha_evidence_review_budget(
    view: AtlasAlphaEvidenceView, *, maximum_priority: int | None = None
) -> dict[str, Any]:
    """Return a bounded review budget summary for workflow surfaces."""

    entries = (
        view.review_queue
        if maximum_priority is None
        else tuple(item for item in view.review_queue if item.priority <= maximum_priority)
    )
    summary = review_queue_summary(view)
    return {
        "fixture_id": view.fixture_id,
        "eligible_review_count": len(entries),
        "maximum_priority": maximum_priority,
        "eligible_record_ids": tuple(item.record_id for item in entries),
        "summary_address": summary["content_address"],
        "content_address": content_hash(
            {
                "fixture_id": view.fixture_id,
                "eligible_review_count": len(entries),
                "maximum_priority": maximum_priority,
                "eligible_record_ids": tuple(item.record_id for item in entries),
                "summary_address": summary["content_address"],
            }
        ),
    }


__all__ = [
    "AtlasAlphaEvidenceEvent",
    "AtlasAlphaEvidenceRunComparison",
    "AtlasAlphaEvidenceStage",
    "AtlasAlphaEvidenceStageReceipt",
    "AtlasAlphaEvidenceTrace",
    "atlas_alpha_evidence_review_budget",
    "build_atlas_alpha_evidence_trace",
    "compare_atlas_alpha_evidence_runs",
]
