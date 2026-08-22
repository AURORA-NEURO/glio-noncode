"""Named result projections for dashboards and tabular exports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_pipeline import LinkGraphAlphaFrontierPipelineReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierProjection:
    projection_id: str
    fields: tuple[str, ...]
    purpose: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"projection_id": self.projection_id, "fields": self.fields, "purpose": self.purpose}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_link_graph_alpha_frontier_projections() -> tuple[LinkGraphAlphaFrontierProjection, ...]:
    return (
        LinkGraphAlphaFrontierProjection("review-row", ("record_id", "operation", "role", "observed_state", "observed_issue_codes"), "ordered review table"),
        LinkGraphAlphaFrontierProjection("summary", ("run_id", "accepted", "record_count", "source_count", "state_counts", "issue_counts"), "bounded run summary"),
        LinkGraphAlphaFrontierProjection("evidence", ("record_id", "evidence_ids", "source_ids", "content_address"), "source trace table"),
    )


def project_link_graph_alpha_frontier_pipeline(pipeline: LinkGraphAlphaFrontierPipelineReport, projection: LinkGraphAlphaFrontierProjection) -> dict[str, Any]:
    summary = {"run_id": pipeline.run_id, "accepted": pipeline.accepted, "record_count": len(pipeline.evaluation.rows), "source_count": len(pipeline.fixture.sources), "state_counts": pipeline.metrics.state_counts, "issue_counts": pipeline.metrics.issue_counts}
    if projection.projection_id == "summary":
        return {field: summary.get(field) for field in projection.fields}
    if projection.projection_id == "evidence":
        return {"rows": [{"record_id": row.record_id, "evidence_ids": row.adapter.evidence_ids, "source_ids": row.adapter.source_ids, "content_address": row.adapter.content_address} for row in pipeline.evaluation.rows]}
    return {"rows": [{"record_id": row.record_id, "operation": row.operation, "role": row.role, "observed_state": row.observed_state, "observed_issue_codes": row.observed_issue_codes} for row in pipeline.evaluation.rows]}


__all__ = ["LinkGraphAlphaFrontierProjection", "default_link_graph_alpha_frontier_projections", "project_link_graph_alpha_frontier_pipeline"]
