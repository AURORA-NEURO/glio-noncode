"""Sanitized field projections for reviewers and downstream summaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluationRow


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierProjection:
    projection_id: str
    fields: tuple[str, ...]
    public_only: bool
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"projection_id": self.projection_id, "fields": self.fields, "public_only": self.public_only, "detail": self.detail}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierProjectionResult:
    projection_id: str
    rows: tuple[dict[str, Any], ...]
    omitted_fields: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"projection_id": self.projection_id, "rows": self.rows, "omitted_fields": self.omitted_fields, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_topology_alpha_frontier_projections() -> tuple[TopologyAlphaFrontierProjection, ...]:
    return (TopologyAlphaFrontierProjection("review", ("record_id", "operation", "role", "state", "issues", "evidence_count", "result_address"), True, "review-safe row projection"), TopologyAlphaFrontierProjection("metrics", ("record_id", "operation", "state", "result_address"), True, "compact metric projection"), TopologyAlphaFrontierProjection("source-lineage", ("record_id", "operation", "source_ids", "result_address"), True, "source closure projection"))


def project_topology_alpha_frontier_rows(rows: Iterable[TopologyAlphaFrontierEvaluationRow], projection: TopologyAlphaFrontierProjection) -> TopologyAlphaFrontierProjectionResult:
    values = []
    allowed = {"record_id", "operation", "role", "state", "issues", "evidence_count", "result_address", "source_ids"}
    for row in rows:
        source = {"record_id": row.record_id, "operation": row.operation, "role": row.role, "state": row.observed_state, "issues": row.observed_issue_codes, "evidence_count": len(row.adapter.evidence_ids), "result_address": row.adapter.content_address, "source_ids": row.adapter.source_ids}
        values.append({field: source[field] for field in projection.fields if field in allowed})
    omitted = tuple(sorted(allowed - set(projection.fields)))
    return TopologyAlphaFrontierProjectionResult(projection.projection_id, tuple(values), omitted, projection.public_only and all("subject_id" not in row and "patient_id" not in row for row in values))


__all__ = ["TopologyAlphaFrontierProjection", "TopologyAlphaFrontierProjectionResult", "default_topology_alpha_frontier_projections", "project_topology_alpha_frontier_rows"]
