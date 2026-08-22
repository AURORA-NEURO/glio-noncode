"""CLI operations for the Domain 10 C05-C08 beta link plane."""

from __future__ import annotations

from typing import Any

from .link_graph_beta_frontier_contracts import build_link_graph_beta_frontier_contracts
from .link_graph_beta_frontier_fixture_eval import evaluate_link_graph_beta_frontier_fixture
from .link_graph_beta_frontier_metrics import build_link_graph_beta_frontier_metrics
from .link_graph_beta_frontier_pipeline import run_link_graph_beta_frontier_pipeline
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierOperation, audit_link_graph_beta_frontier_data, default_link_graph_beta_frontier_fixture
from .link_graph_beta_frontier_schema import validate_link_graph_beta_frontier_schema


LINK_GRAPH_BETA_FRONTIER_COMMANDS = ("link-graph-beta-frontier-fixture", "link-graph-beta-frontier-evaluate", "link-graph-beta-frontier-contracts", "link-graph-beta-frontier-schema", "link-graph-beta-frontier-metrics", "link-graph-beta-frontier-review", "link-graph-beta-frontier-release", "link-graph-beta-frontier-summary")


def run_link_graph_beta_frontier_operation(command: str) -> dict[str, Any]:
    fixture = default_link_graph_beta_frontier_fixture()
    evaluation = evaluate_link_graph_beta_frontier_fixture(fixture)
    if command == LINK_GRAPH_BETA_FRONTIER_COMMANDS[0]:
        audit = audit_link_graph_beta_frontier_data(fixture)
        return {"fixture": fixture.to_dict(), "audit": audit.to_dict(), "boundary": fixture.boundary, "record_count": len(fixture.records), "source_count": len(fixture.sources), "accepted": audit.accepted}
    if command == LINK_GRAPH_BETA_FRONTIER_COMMANDS[1]:
        return evaluation.to_dict()
    if command == LINK_GRAPH_BETA_FRONTIER_COMMANDS[2]:
        return build_link_graph_beta_frontier_contracts().to_dict()
    if command == LINK_GRAPH_BETA_FRONTIER_COMMANDS[3]:
        return validate_link_graph_beta_frontier_schema(fixture, evaluation).to_dict()
    if command == LINK_GRAPH_BETA_FRONTIER_COMMANDS[4]:
        return build_link_graph_beta_frontier_metrics(evaluation, fixture).to_dict()
    pipeline = run_link_graph_beta_frontier_pipeline()
    if command == LINK_GRAPH_BETA_FRONTIER_COMMANDS[5]:
        return pipeline.review_queue.to_dict()
    if command == LINK_GRAPH_BETA_FRONTIER_COMMANDS[6]:
        return pipeline.release.to_dict()
    if command == LINK_GRAPH_BETA_FRONTIER_COMMANDS[7]:
        return {"fixture_id": fixture.fixture_id, "boundary": fixture.boundary, "record_count": len(fixture.records), "source_count": len(fixture.sources), "positive_count": len(fixture.positive_records), "control_count": len(fixture.control_records), "operations": [item.value for item in LinkGraphBetaFrontierOperation], "operation_counts": {item.value: len(fixture.operation_records(item)) for item in LinkGraphBetaFrontierOperation}, "accepted": pipeline.accepted, "state_accuracy": pipeline.metrics.state_accuracy, "state_counts": pipeline.metrics.state_counts, "content_address": pipeline.content_address}
    raise KeyError(command)


__all__ = ["LINK_GRAPH_BETA_FRONTIER_COMMANDS", "run_link_graph_beta_frontier_operation"]
