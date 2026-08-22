"""Review packet assembled from the foundation workflow and projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_audit_trail import LinkGraphFoundationFrontierAuditTrail, build_link_graph_foundation_frontier_audit_trail
from .link_graph_foundation_frontier_catalog import LinkGraphFoundationFrontierModuleCatalog, build_link_graph_foundation_frontier_module_catalog
from .link_graph_foundation_frontier_field_projection import LinkGraphFoundationFrontierProjectionReport, project_link_graph_foundation_frontier_fixture
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture, default_link_graph_foundation_frontier_fixture
from .link_graph_foundation_frontier_workflow import LinkGraphFoundationFrontierWorkflowReport, run_link_graph_foundation_frontier_workflow
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierReviewPacket:
    fixture_id: str
    workflow: LinkGraphFoundationFrontierWorkflowReport
    projection: LinkGraphFoundationFrontierProjectionReport
    audit_trail: LinkGraphFoundationFrontierAuditTrail
    module_catalog: LinkGraphFoundationFrontierModuleCatalog
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


def build_link_graph_foundation_frontier_review_packet(fixture: LinkGraphFoundationFrontierFixture | None = None) -> LinkGraphFoundationFrontierReviewPacket:
    value = fixture or default_link_graph_foundation_frontier_fixture()
    workflow = run_link_graph_foundation_frontier_workflow(value)
    projection = project_link_graph_foundation_frontier_fixture(value)
    audit_trail = build_link_graph_foundation_frontier_audit_trail(value, workflow.evaluation)
    catalog = build_link_graph_foundation_frontier_module_catalog()
    return LinkGraphFoundationFrontierReviewPacket(value.fixture_id, workflow, projection, audit_trail, catalog, workflow.accepted and projection.accepted and audit_trail.accepted and catalog.accepted)


def review_packet_summary(packet: LinkGraphFoundationFrontierReviewPacket) -> dict[str, Any]:
    return {"fixture_id": packet.fixture_id, "workflow_stages": len(packet.workflow.stages), "projection_rows": len(packet.projection.rows), "audit_events": len(packet.audit_trail.events), "catalog_entries": len(packet.module_catalog.entries), "accepted": packet.accepted}


__all__ = ["LinkGraphFoundationFrontierReviewPacket", "build_link_graph_foundation_frontier_review_packet", "review_packet_summary"]
