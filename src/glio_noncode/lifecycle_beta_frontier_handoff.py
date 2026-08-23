"""Reproducible handoff manifest for Domain 14 C05-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierEvaluation, LifecycleBetaFrontierFixture, LifecycleBetaFrontierOperation
from .lifecycle_beta_frontier_metrics import LifecycleBetaFrontierMetrics
from .serialization import content_hash, jsonable


LIFECYCLE_BETA_FRONTIER_ALLOWED_USES = ("aggregate review", "software validation", "provenance inspection", "reproducible replay")
LIFECYCLE_BETA_FRONTIER_EXCLUDED_USES = ("patient-level inference", "clinical use", "treatment selection", "causal authorization", "automatic publication")


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierHandoffItem:
    operation: LifecycleBetaFrontierOperation
    record_count: int
    positive_count: int
    control_count: int
    accepted_count: int
    source_ids: tuple[str, ...]
    required_checks: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierHandoff:
    fixture_id: str
    version: str
    allowed_uses: tuple[str, ...]
    excluded_uses: tuple[str, ...]
    operation_items: tuple[LifecycleBetaFrontierHandoffItem, ...]
    source_ids: tuple[str, ...]
    record_count: int
    operation_count: int
    accepted: bool
    content_address: str

    def item(self, operation: LifecycleBetaFrontierOperation | str) -> LifecycleBetaFrontierHandoffItem:
        selected = operation.value if isinstance(operation, LifecycleBetaFrontierOperation) else str(operation)
        return next(item for item in self.operation_items if item.operation.value == selected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"record_count": self.record_count, "operation_count": self.operation_count}


def build_lifecycle_beta_frontier_handoff(fixture: LifecycleBetaFrontierFixture | None = None, evaluation: LifecycleBetaFrontierEvaluation | None = None, metrics: LifecycleBetaFrontierMetrics | None = None) -> LifecycleBetaFrontierHandoff:
    fixture = fixture or __import__("glio_noncode.lifecycle_beta_frontier_public_data", fromlist=["default_lifecycle_beta_frontier_fixture"]).default_lifecycle_beta_frontier_fixture()
    evaluation = evaluation or __import__("glio_noncode.lifecycle_beta_frontier_fixture_eval", fromlist=["evaluate_lifecycle_beta_frontier_fixture"]).evaluate_lifecycle_beta_frontier_fixture(fixture)
    metrics = metrics or __import__("glio_noncode.lifecycle_beta_frontier_metrics", fromlist=["measure_lifecycle_beta_frontier"]).measure_lifecycle_beta_frontier(evaluation)
    items = []
    for metric in metrics.operation_metrics:
        body = {"operation": metric.operation, "record_count": metric.record_count, "positive_count": metric.positive_count, "control_count": metric.control_count, "accepted_count": metric.accepted_count, "source_ids": tuple(sorted({source for record in fixture.by_operation(metric.operation) for source in record.source_ids})), "required_checks": ("state", "issue_codes", "content_address")}
        items.append(LifecycleBetaFrontierHandoffItem(**body, content_address=content_hash(body)))
    body = {"fixture_id": fixture.fixture_id, "version": fixture.fixture_version, "allowed_uses": LIFECYCLE_BETA_FRONTIER_ALLOWED_USES, "excluded_uses": LIFECYCLE_BETA_FRONTIER_EXCLUDED_USES, "operation_items": tuple(items), "source_ids": tuple(item.source_id for item in fixture.sources), "record_count": len(fixture.records), "operation_count": len(items), "accepted": len(items) == 8 and len(fixture.records) == 32}
    return LifecycleBetaFrontierHandoff(**body, content_address=content_hash(body))


def validate_lifecycle_beta_frontier_handoff(handoff: LifecycleBetaFrontierHandoff) -> bool:
    return handoff.accepted and handoff.record_count == 32 and handoff.operation_count == 8 and set(handoff.allowed_uses).isdisjoint(handoff.excluded_uses) and all(item.record_count == 4 and item.positive_count == 1 and item.control_count == 3 and item.accepted_count == 1 for item in handoff.operation_items)


def render_lifecycle_beta_frontier_handoff_markdown(handoff: LifecycleBetaFrontierHandoff) -> str:
    lines = ["# Lifecycle-beta frontier research handoff", "", "Public aggregate only; unresolved controls remain review-visible.", "", "| Operation | Records | Positive | Controls | Accepted | Sources |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for item in handoff.operation_items:
        lines.append(f"| {item.operation.value} | {item.record_count} | {item.positive_count} | {item.control_count} | {item.accepted_count} | {len(item.source_ids)} |")
    lines.extend(("", "## Allowed uses", "", *[f"- {item}" for item in handoff.allowed_uses], "", "## Excluded uses", "", *[f"- {item}" for item in handoff.excluded_uses], "", "## Reproducibility", "", "Fixture, execution, and source addresses are retained in the JSON and CSV exports.", f"Content address: {handoff.content_address}"))
    return "\n".join(lines) + "\n"


def lifecycle_beta_frontier_handoff_summary(handoff: LifecycleBetaFrontierHandoff | None = None) -> dict[str, Any]:
    handoff = handoff or build_lifecycle_beta_frontier_handoff()
    return {"accepted": validate_lifecycle_beta_frontier_handoff(handoff), "record_count": handoff.record_count, "operation_count": handoff.operation_count, "publication_surface_count": 6, "content_address": handoff.content_address}


__all__ = ["LIFECYCLE_BETA_FRONTIER_ALLOWED_USES", "LIFECYCLE_BETA_FRONTIER_EXCLUDED_USES", "LifecycleBetaFrontierHandoff", "LifecycleBetaFrontierHandoffItem", "build_lifecycle_beta_frontier_handoff", "lifecycle_beta_frontier_handoff_summary", "render_lifecycle_beta_frontier_handoff_markdown", "validate_lifecycle_beta_frontier_handoff"]
