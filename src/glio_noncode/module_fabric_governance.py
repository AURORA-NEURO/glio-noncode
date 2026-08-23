"""Governance projections for module-fabric release and review decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .module_fabric_contracts import FabricEvaluation, FabricFixture, FabricState, MODULE_FABRIC_BOUNDARY
from .module_fabric_public_data import default_module_fabric_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class FabricClaimBoundary:
    allowed_uses: tuple[str, ...]
    excluded_uses: tuple[str, ...]
    boundary: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricReviewItem:
    record_id: str
    domain_id: str
    capability_id: str
    priority: int
    reasons: tuple[str, ...]
    next_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricReviewQueue:
    queue_id: str
    items: tuple[FabricReviewItem, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_module_fabric_claim_boundary() -> FabricClaimBoundary:
    body = {
        "allowed_uses": ("audit declared module references", "replay public aggregate integration receipts", "route unresolved references for repair"),
        "excluded_uses": ("infer biological truth", "validate clinical utility", "authorize deployment", "copy private subject data"),
        "boundary": MODULE_FABRIC_BOUNDARY,
    }
    return FabricClaimBoundary(**body, content_address=content_hash(body, prefix="module-fabric-claim"))


def build_module_fabric_review_queue(
    fixture: FabricFixture | None = None,
    evaluation: FabricEvaluation | None = None,
    *,
    queue_id: str = "module-fabric-review",
) -> FabricReviewQueue:
    value = fixture or default_module_fabric_fixture()
    report = evaluation
    if report is None:
        from .module_fabric_fixture_eval import evaluate_module_fabric_fixture

        report = evaluate_module_fabric_fixture(value)
    items = []
    for index, (record, execution) in enumerate(zip(value.records, report.executions, strict=True), start=1):
        if execution.observed_state is FabricState.ACCEPTED:
            continue
        reasons = tuple(execution.issue_codes) or ("held_control",)
        body = {
            "record_id": record.record_id,
            "domain_id": record.domain_id,
            "capability_id": record.capability_id,
            "priority": index,
            "reasons": reasons,
            "next_action": "review context and declared ownership before repair",
        }
        items.append(FabricReviewItem(**body, content_address=content_hash(body, prefix="module-fabric-review-item")))
    items.sort(key=lambda item: (item.priority, item.record_id))
    body = {"queue_id": queue_id, "items": items}
    return FabricReviewQueue(queue_id, tuple(items), content_hash(body, prefix="module-fabric-review-queue"))


__all__ = [
    "FabricClaimBoundary",
    "FabricReviewItem",
    "FabricReviewQueue",
    "build_module_fabric_review_queue",
    "default_module_fabric_claim_boundary",
]
