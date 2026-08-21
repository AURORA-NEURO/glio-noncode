from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path

from glio_noncode.specimen_preanalytic_lineage import (
    audit_specimen_preanalytic_lineage,
    build_specimen_preanalytic_lineage,
)
from glio_noncode.specimen_preanalytic_public_data import SpecimenPreanalyticFixtureCatalog

FIXTURE = Path("examples/specimen-preanalytic-public-aggregate.json")


class SpecimenPreanalyticLineageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = SpecimenPreanalyticFixtureCatalog.from_file(FIXTURE)

    def test_graph_has_expected_typed_shape(self) -> None:
        graph = build_specimen_preanalytic_lineage(self.catalog)
        self.assertEqual(len(graph.nodes), 29)
        self.assertEqual(len(graph.edges), 28)
        self.assertEqual(
            {edge.relation for edge in graph.edges}, {"declares", "contains", "produces"}
        )

    def test_graph_audit_passes_and_is_addressed(self) -> None:
        graph = build_specimen_preanalytic_lineage(self.catalog)
        audit = audit_specimen_preanalytic_lineage(graph)
        self.assertTrue(audit.passed)
        self.assertTrue(graph.content_address.startswith("sha256:"))
        self.assertEqual(audit.failed_check_ids, ())

    def test_graph_audit_detects_dangling_edge(self) -> None:
        graph = build_specimen_preanalytic_lineage(self.catalog)
        edge = replace(graph.edges[0], target_node_id="missing-node")
        mutated = replace(graph, edges=(edge,) + graph.edges[1:])
        audit = audit_specimen_preanalytic_lineage(mutated)
        self.assertFalse(audit.passed)
        self.assertIn("edge-endpoints", audit.failed_check_ids)

    def test_graph_projection_is_public_and_context_consistent(self) -> None:
        graph = build_specimen_preanalytic_lineage(self.catalog)
        self.assertTrue(all(node.public for node in graph.nodes))
        self.assertTrue(all(node.context_key == self.catalog.context_key for node in graph.nodes))
        self.assertTrue(all(node.address.startswith("sha256:") for node in graph.nodes))


if __name__ == "__main__":
    unittest.main()
