from __future__ import annotations

import json
import unittest
from pathlib import Path

from glio_noncode.specimen_beta_frontier_lineage import (
    audit_specimen_beta_frontier_lineage,
    build_specimen_beta_frontier_lineage,
)
from glio_noncode.specimen_beta_frontier_public_data import SpecimenBetaFrontierFixtureCatalog

FIXTURE = Path("examples/specimen-beta-frontier-public-aggregate.json")


class SpecimenBetaFrontierLineageTests(unittest.TestCase):
    def test_lineage_has_expected_shape_and_passes(self) -> None:
        catalog = SpecimenBetaFrontierFixtureCatalog.from_file(FIXTURE)
        graph = build_specimen_beta_frontier_lineage(catalog)
        audit = audit_specimen_beta_frontier_lineage(graph)
        self.assertTrue(audit.passed)
        self.assertEqual(len(graph.nodes), 29)
        self.assertEqual(len(graph.edges), 36)

    def test_lineage_has_source_fixture_record_and_result_nodes(self) -> None:
        catalog = SpecimenBetaFrontierFixtureCatalog.from_file(FIXTURE)
        graph = build_specimen_beta_frontier_lineage(catalog)
        kinds = {node.kind.value for node in graph.nodes}
        self.assertEqual(kinds, {"source", "fixture", "record", "result"})
        self.assertEqual(len(graph.root_ids), 5)

    def test_lineage_relations_are_typed(self) -> None:
        catalog = SpecimenBetaFrontierFixtureCatalog.from_file(FIXTURE)
        graph = build_specimen_beta_frontier_lineage(catalog)
        self.assertEqual(
            {edge.relation.value for edge in graph.edges},
            {"declares", "contains", "produces"},
        )

    def test_context_drift_is_detected_by_lineage_audit(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["controls"][0]["context_key"] = (
            "GRCh38|diffuse_glioma|adult|other|tumor_core|pre_treatment"
        )
        catalog = SpecimenBetaFrontierFixtureCatalog.from_mapping(payload)
        graph = build_specimen_beta_frontier_lineage(catalog)
        audit = audit_specimen_beta_frontier_lineage(graph)
        self.assertIn("context_mismatch", audit.issue_codes)

    def test_graph_address_is_deterministic(self) -> None:
        catalog = SpecimenBetaFrontierFixtureCatalog.from_file(FIXTURE)
        first = build_specimen_beta_frontier_lineage(catalog)
        second = build_specimen_beta_frontier_lineage(catalog)
        self.assertEqual(first.content_address, second.content_address)

    def test_missing_endpoint_is_detected(self) -> None:
        catalog = SpecimenBetaFrontierFixtureCatalog.from_file(FIXTURE)
        graph = build_specimen_beta_frontier_lineage(catalog)
        object.__setattr__(graph.edges[0], "to_node", "record:missing")
        audit = audit_specimen_beta_frontier_lineage(graph)
        self.assertIn("missing_endpoint", audit.issue_codes)


if __name__ == "__main__":
    unittest.main()
