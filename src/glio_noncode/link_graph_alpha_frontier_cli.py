"""CLI operations for inspecting the D10 C09-C12 link plane."""

from __future__ import annotations

from typing import Any

from .link_graph_alpha_frontier_catalog import build_link_graph_alpha_frontier_catalog
from .link_graph_alpha_frontier_contracts import build_link_graph_alpha_frontier_contracts
from .link_graph_alpha_frontier_exports import export_link_graph_alpha_frontier_manifest
from .link_graph_alpha_frontier_fixture_eval import evaluate_link_graph_alpha_frontier_fixture
from .link_graph_alpha_frontier_metrics import build_link_graph_alpha_frontier_metrics
from .link_graph_alpha_frontier_pipeline import run_link_graph_alpha_frontier_pipeline
from .link_graph_alpha_frontier_public_data import audit_link_graph_alpha_frontier_data, default_link_graph_alpha_frontier_fixture
from .link_graph_alpha_frontier_reports import link_graph_alpha_frontier_summary_payload
from .link_graph_alpha_frontier_runbook import build_link_graph_alpha_frontier_runbook
from .link_graph_alpha_frontier_schema import validate_link_graph_alpha_frontier_schema
from .link_graph_alpha_frontier_support import result_state_counts


LINK_GRAPH_ALPHA_FRONTIER_COMMANDS = (
    "link-graph-alpha-frontier-fixture",
    "link-graph-alpha-frontier-evaluate",
    "link-graph-alpha-frontier-contracts",
    "link-graph-alpha-frontier-schema",
    "link-graph-alpha-frontier-metrics",
    "link-graph-alpha-frontier-catalog",
    "link-graph-alpha-frontier-accessibility",
    "link-graph-alpha-frontier-runbook",
    "link-graph-alpha-frontier-review",
    "link-graph-alpha-frontier-release",
    "link-graph-alpha-frontier-manifest",
    "link-graph-alpha-frontier-summary",
)


def run_link_graph_alpha_frontier_operation(command: str) -> dict[str, Any]:
    fixture = default_link_graph_alpha_frontier_fixture()
    evaluation = evaluate_link_graph_alpha_frontier_fixture(fixture)
    if command == "link-graph-alpha-frontier-fixture":
        return {"fixture": fixture.to_dict(), "audit": audit_link_graph_alpha_frontier_data(fixture).to_dict()}
    if command == "link-graph-alpha-frontier-evaluate":
        return evaluation.to_dict()
    if command == "link-graph-alpha-frontier-contracts":
        return build_link_graph_alpha_frontier_contracts().to_dict()
    if command == "link-graph-alpha-frontier-schema":
        return validate_link_graph_alpha_frontier_schema(fixture, evaluation).to_dict()
    if command == "link-graph-alpha-frontier-metrics":
        return build_link_graph_alpha_frontier_metrics(evaluation, fixture).to_dict()
    if command == "link-graph-alpha-frontier-catalog":
        return build_link_graph_alpha_frontier_catalog().to_dict()
    if command == "link-graph-alpha-frontier-accessibility":
        pipeline = run_link_graph_alpha_frontier_pipeline()
        return pipeline.accessibility.to_dict()
    if command == "link-graph-alpha-frontier-runbook":
        return build_link_graph_alpha_frontier_runbook().to_dict()
    if command == "link-graph-alpha-frontier-review":
        return run_link_graph_alpha_frontier_pipeline().review_queue.to_dict()
    if command == "link-graph-alpha-frontier-release":
        return run_link_graph_alpha_frontier_pipeline().release.to_dict()
    if command == "link-graph-alpha-frontier-manifest":
        return {"manifest": export_link_graph_alpha_frontier_manifest(fixture, evaluation)}
    if command == "link-graph-alpha-frontier-summary":
        return link_graph_alpha_frontier_summary_payload(fixture, evaluation, build_link_graph_alpha_frontier_metrics(evaluation, fixture))
    raise KeyError(command)


__all__ = ["LINK_GRAPH_ALPHA_FRONTIER_COMMANDS", "run_link_graph_alpha_frontier_operation"]
