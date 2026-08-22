"""Review packet assembled from beta workflow, projections, and audit chain."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_audit_trail import LinkGraphBetaFrontierAuditTrail, build_link_graph_beta_frontier_audit_trail
from .link_graph_beta_frontier_catalog import LinkGraphBetaFrontierModuleCatalog, build_link_graph_beta_frontier_module_catalog
from .link_graph_beta_frontier_field_projection import LinkGraphBetaFrontierProjectionReport, project_link_graph_beta_frontier_fixture
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, default_link_graph_beta_frontier_fixture
from .link_graph_beta_frontier_workflow import LinkGraphBetaFrontierWorkflowReport, run_link_graph_beta_frontier_workflow
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierReviewPacket:
    fixture_id: str
    workflow: LinkGraphBetaFrontierWorkflowReport
    projection: LinkGraphBetaFrontierProjectionReport
    audit_trail: LinkGraphBetaFrontierAuditTrail
    module_catalog: LinkGraphBetaFrontierModuleCatalog
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "workflow": self.workflow.to_dict(), "projection": self.projection.to_dict(), "audit_trail": self.audit_trail.to_dict(), "module_catalog": self.module_catalog.to_dict(), "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_review_packet(fixture: LinkGraphBetaFrontierFixture | None = None) -> LinkGraphBetaFrontierReviewPacket:
    value = fixture or default_link_graph_beta_frontier_fixture()
    workflow = run_link_graph_beta_frontier_workflow(value)
    projection = project_link_graph_beta_frontier_fixture(value)
    audit_trail = build_link_graph_beta_frontier_audit_trail(value, workflow.evaluation)
    catalog = build_link_graph_beta_frontier_module_catalog()
    return LinkGraphBetaFrontierReviewPacket(value.fixture_id, workflow, projection, audit_trail, catalog, workflow.accepted and projection.accepted and audit_trail.accepted and catalog.accepted)


def review_packet_summary(packet: LinkGraphBetaFrontierReviewPacket) -> dict[str, Any]:
    return {"fixture_id": packet.fixture_id, "workflow_stages": len(packet.workflow.stages), "projection_rows": len(packet.projection.rows), "audit_events": len(packet.audit_trail.events), "catalog_entries": len(packet.module_catalog.entries), "accepted": packet.accepted}


__all__ = ["LinkGraphBetaFrontierReviewPacket", "build_link_graph_beta_frontier_review_packet", "review_packet_summary"]
