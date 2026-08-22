"""Sanitized review view for board, launch, snapshot, and access receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_gamma_frontier_fixture_eval import GammaFrontierEvaluation
from .workspace_gamma_frontier_policy import GammaFrontierPolicyDecision
from .workspace_gamma_frontier_public_data import GammaFrontierFixture
from .workspace_gamma_frontier_release import GammaFrontierReleaseManifest


@dataclass(frozen=True, slots=True)
class GammaFrontierReviewRow:
    """One review-safe row without secrets or raw launch inputs."""

    row_id: str
    record_id: str
    operation: str
    role: str
    state: str
    decision: str
    issue_codes: tuple[str, ...]
    source_ids: tuple[str, ...]
    notes: str
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "row_id",
            "record_id",
            "operation",
            "role",
            "state",
            "decision",
            "notes",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierReviewView:
    """Stable table plus summary fields for UI and CSV consumers."""

    fixture_id: str
    rows: tuple[GammaFrontierReviewRow, ...]
    source_matrix: tuple[dict[str, Any], ...]
    summary: dict[str, Any]
    release_state: str
    content_address: str

    def by_operation(self, operation: str) -> tuple[GammaFrontierReviewRow, ...]:
        return tuple(item for item in self.rows if item.operation == operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_gamma_frontier_review_view(
    fixture: GammaFrontierFixture,
    evaluation: GammaFrontierEvaluation,
    decisions: tuple[GammaFrontierPolicyDecision, ...],
    release: GammaFrontierReleaseManifest,
) -> GammaFrontierReviewView:
    """Build a deterministic, sanitized review table."""

    decision_map = {item.record_id: item for item in decisions}
    rows = tuple(
        GammaFrontierReviewRow(
            row_id=f"review-row-{index:03d}",
            record_id=record.record_id,
            operation=record.operation.value,
            role=record.role.value,
            state=execution.state,
            decision=decision_map[record.record_id].decision.value,
            issue_codes=execution.issue_codes,
            source_ids=record.source_ids,
            notes=record.notes,
            content_address=content_hash(
                {"record": record.record_id, "execution": execution.content_address},
                prefix="review-row",
            ),
        )
        for index, (record, execution) in enumerate(
            zip(fixture.records, evaluation.executions, strict=True), start=1
        )
    )
    source_matrix = tuple(
        {
            "source_id": source.source_id,
            "title": source.title,
            "uri": source.uri,
            "access_note": source.access_note,
            "content_address": source.content_address,
        }
        for source in fixture.sources
    )
    summary = {
        "row_count": len(rows),
        "positive_count": len(fixture.positive_records),
        "control_count": len(fixture.control_records),
        "issue_row_count": sum(bool(row.issue_codes) for row in rows),
        "operation_counts": {
            operation: sum(row.operation == operation for row in rows)
            for operation in sorted({row.operation for row in rows})
        },
    }
    body = {
        "fixture_id": fixture.fixture_id,
        "rows": rows,
        "source_matrix": source_matrix,
        "summary": summary,
        "release_state": release.state.value,
    }
    return GammaFrontierReviewView(**body, content_address=content_hash(body, prefix="review-view"))


__all__ = ["GammaFrontierReviewRow", "GammaFrontierReviewView", "build_gamma_frontier_review_view"]
