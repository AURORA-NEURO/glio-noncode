"""CLI operations for the Domain 10 C01-C04 link baseline plane."""

from __future__ import annotations

from typing import Any

from .link_graph_foundation_frontier_contracts import build_link_graph_foundation_frontier_contracts
from .link_graph_foundation_frontier_fixture_eval import evaluate_link_graph_foundation_frontier_fixture
from .link_graph_foundation_frontier_metrics import build_link_graph_foundation_frontier_metrics
from .link_graph_foundation_frontier_pipeline import run_link_graph_foundation_frontier_pipeline
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierOperation, audit_link_graph_foundation_frontier_data, default_link_graph_foundation_frontier_fixture
from .link_graph_foundation_frontier_schema import validate_link_graph_foundation_frontier_schema


LINK_GRAPH_FOUNDATION_FRONTIER_COMMANDS = ("link-graph-foundation-frontier-fixture", "link-graph-foundation-frontier-evaluate", "link-graph-foundation-frontier-contracts", "link-graph-foundation-frontier-schema", "link-graph-foundation-frontier-metrics", "link-graph-foundation-frontier-review", "link-graph-foundation-frontier-release", "link-graph-foundation-frontier-summary")


def run_link_graph_foundation_frontier_operation(command: str) -> dict[str, Any]:
    fixture = default_link_graph_foundation_frontier_fixture()
    evaluation = evaluate_link_graph_foundation_frontier_fixture(fixture)
    if command == LINK_GRAPH_FOUNDATION_FRONTIER_COMMANDS[0]:
        return {"fixture": fixture.to_dict(), "audit": audit_link_graph_foundation_frontier_data(fixture).to_dict(), "boundary": fixture.boundary, "record_count": len(fixture.records), "source_count": len(fixture.sources), "accepted": audit_link_graph_foundation_frontier_data(fixture).accepted}
    if command == LINK_GRAPH_FOUNDATION_FRONTIER_COMMANDS[1]:
        return evaluation.to_dict()
    if command == LINK_GRAPH_FOUNDATION_FRONTIER_COMMANDS[2]:
        return build_link_graph_foundation_frontier_contracts().to_dict()
    if command == LINK_GRAPH_FOUNDATION_FRONTIER_COMMANDS[3]:
        return validate_link_graph_foundation_frontier_schema(fixture, evaluation).to_dict()
    if command == LINK_GRAPH_FOUNDATION_FRONTIER_COMMANDS[4]:
        return build_link_graph_foundation_frontier_metrics(evaluation, fixture).to_dict()
    pipeline = run_link_graph_foundation_frontier_pipeline()
    if command == LINK_GRAPH_FOUNDATION_FRONTIER_COMMANDS[5]:
        return pipeline.review_queue.to_dict()
    if command == LINK_GRAPH_FOUNDATION_FRONTIER_COMMANDS[6]:
        return pipeline.release.to_dict()
    if command == LINK_GRAPH_FOUNDATION_FRONTIER_COMMANDS[7]:
        return {"fixture_id": fixture.fixture_id, "boundary": fixture.boundary, "record_count": len(fixture.records), "source_count": len(fixture.sources), "positive_count": len(fixture.positive_records), "control_count": len(fixture.control_records), "operations": [item.value for item in LinkGraphFoundationFrontierOperation], "operation_counts": {item.value: len(fixture.operation_records(item)) for item in LinkGraphFoundationFrontierOperation}, "accepted": pipeline.accepted, "state_accuracy": pipeline.metrics.state_accuracy, "state_counts": pipeline.metrics.state_counts, "content_address": pipeline.content_address}
    raise KeyError(command)


__all__ = ["LINK_GRAPH_FOUNDATION_FRONTIER_COMMANDS", "run_link_graph_foundation_frontier_operation"]
