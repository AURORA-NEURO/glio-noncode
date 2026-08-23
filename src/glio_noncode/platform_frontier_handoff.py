"""Reproducible handoff envelope for platform review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PlatformFrontierEvaluation, PlatformFrontierFixture
from .platform_frontier_metrics import PlatformFrontierMetrics
from .platform_frontier_review_queue import PlatformFrontierReviewQueue
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierHandoffItem:
    item_id: str
    label: str
    address: str
    required: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierHandoff:
    fixture_id: str
    context_key: str
    items: tuple[PlatformFrontierHandoffItem, ...]
    review_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_platform_frontier_handoff(fixture: PlatformFrontierFixture, evaluation: PlatformFrontierEvaluation, metrics: PlatformFrontierMetrics, queue: PlatformFrontierReviewQueue | None = None) -> PlatformFrontierHandoff:
    items_data = (("fixture", "fixture", fixture.content_address), ("evaluation", "evaluation", evaluation.content_address), ("metrics", "metrics", metrics.content_address))
    if queue is not None:
        items_data += (("review", "review queue", queue.content_address),)
    items = []
    for item_id, label, address in items_data:
        body = {"item_id": item_id, "label": label, "address": address, "required": True}
        items.append(PlatformFrontierHandoffItem(**body, content_address=content_hash(body)))
    return PlatformFrontierHandoff(fixture.fixture_id, fixture.context_key, tuple(items), len(queue.items) if queue else 0, all(item.address.startswith("sha256:") for item in items), content_hash(tuple(items)))


__all__ = ["PlatformFrontierHandoff", "PlatformFrontierHandoffItem", "build_platform_frontier_handoff"]
