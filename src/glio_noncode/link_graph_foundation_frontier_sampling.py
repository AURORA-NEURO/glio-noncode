"""Deterministic sample windows for review without changing fixture semantics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture, default_link_graph_foundation_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierSampleWindow:
    window_id: str
    offset: int
    limit: int
    record_ids: tuple[str, ...]
    operation_counts: dict[str, int]

    @property
    def complete(self) -> bool:
        return len(self.record_ids) <= self.limit and self.offset >= 0

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierSamplingReport:
    fixture_id: str
    windows: tuple[LinkGraphFoundationFrontierSampleWindow, ...]
    covered_record_ids: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def coverage_count(self) -> int:
        return len(self.covered_record_ids)

    def window(self, window_id: str) -> LinkGraphFoundationFrontierSampleWindow:
        return next(item for item in self.windows if item.window_id == window_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "windows": [item.to_dict() for item in self.windows], "covered_record_ids": self.covered_record_ids, "coverage_count": self.coverage_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _window(window_id: str, records: tuple[Any, ...], offset: int, limit: int) -> LinkGraphFoundationFrontierSampleWindow:
    selected = records[offset:offset + limit]
    return LinkGraphFoundationFrontierSampleWindow(window_id, offset, limit, tuple(item.record_id for item in selected), {operation: sum(item.operation.value == operation for item in selected) for operation in sorted({item.operation.value for item in records})})


def build_link_graph_foundation_frontier_sampling(fixture: LinkGraphFoundationFrontierFixture | None = None, *, window_size: int = 4) -> LinkGraphFoundationFrontierSamplingReport:
    value = fixture or default_link_graph_foundation_frontier_fixture()
    if window_size <= 0:
        raise ValueError("window_size must be positive")
    windows = tuple(_window(f"window-{index // window_size + 1}", value.records, index, window_size) for index in range(0, len(value.records), window_size))
    covered = tuple(record_id for window in windows for record_id in window.record_ids)
    return LinkGraphFoundationFrontierSamplingReport(value.fixture_id, windows, covered, len(covered) == len(value.records) and len(set(covered)) == len(covered) and all(window.complete for window in windows))


def sample_link_graph_foundation_frontier_evaluation(evaluation: LinkGraphFoundationFrontierEvaluation, *, offset: int = 0, limit: int = 4) -> tuple[dict[str, Any], ...]:
    if offset < 0 or limit <= 0:
        raise ValueError("offset must be non-negative and limit must be positive")
    return tuple({"record_id": row.record_id, "operation": row.operation, "observed_state": row.observed_state, "accepted": row.state_match and row.issue_match} for row in evaluation.rows[offset:offset + limit])


__all__ = ["LinkGraphFoundationFrontierSampleWindow", "LinkGraphFoundationFrontierSamplingReport", "build_link_graph_foundation_frontier_sampling", "sample_link_graph_foundation_frontier_evaluation"]
