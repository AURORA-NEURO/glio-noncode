"""Content-address integrity checks for baseline rows and results."""

from __future__ import annotations

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture
from .link_graph_foundation_frontier_support import LinkGraphFoundationFrontierReport, check, report
from .serialization import content_hash


def evaluate_link_graph_foundation_frontier_integrity(fixture: LinkGraphFoundationFrontierFixture, evaluation: LinkGraphFoundationFrontierEvaluation) -> LinkGraphFoundationFrontierReport:
    expected_fixture_address = content_hash({"fixture_id": fixture.fixture_id, "version": fixture.version, "sources": fixture.sources, "records": fixture.records})
    checks = (check("fixture_address", fixture.content_address == expected_fixture_address, "fixture address is reproducible"), check("record_addresses", all(record.content_address.startswith("sha256:") for record in fixture.records), "record addresses are present"), check("result_addresses", all(row.adapter.content_address.startswith("sha256:") for row in evaluation.rows), "result addresses are present"), check("unique_records", len({record.content_address for record in fixture.records}) == len(fixture.records), "record addresses are unique"))
    return report("link-graph-foundation-frontier-integrity", checks)


__all__ = ["evaluate_link_graph_foundation_frontier_integrity"]
