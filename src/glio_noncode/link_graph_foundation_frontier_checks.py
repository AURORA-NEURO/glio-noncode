"""Fixture cardinality and context invariants."""

from __future__ import annotations

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture, LinkGraphFoundationFrontierOperation
from .link_graph_foundation_frontier_support import LinkGraphFoundationFrontierReport, check, report


def run_link_graph_foundation_frontier_invariants(fixture: LinkGraphFoundationFrontierFixture, evaluation: LinkGraphFoundationFrontierEvaluation) -> LinkGraphFoundationFrontierReport:
    checks = (check("records", len(fixture.records) == 16, "fixture has 16 records"), check("sources", len(fixture.sources) == 5, "fixture has 5 sources"), check("operations", all(len(fixture.operation_records(item)) == 4 for item in LinkGraphFoundationFrontierOperation), "operations are balanced"), check("roles", len(fixture.positive_records) == 4 and len(fixture.control_records) == 12, "roles are balanced"), check("rows", len(evaluation.rows) == len(fixture.records) and evaluation.accepted, "replay covers fixture"), check("foreign", all(record.context_key == fixture.foreign_context_key for record in fixture.records if record.record_id.endswith("C3")), "C3 rows use foreign context"))
    return report("link-graph-foundation-frontier-invariants", checks)


__all__ = ["run_link_graph_foundation_frontier_invariants"]
