from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.reference_coordinate_lineage import (
    ReferenceCoordinateEdgeKind,
    ReferenceCoordinateNodeKind,
    build_reference_coordinate_lineage,
)
from glio_noncode.reference_coordinate_public_data import ReferenceCoordinateFixtureCatalog

FIXTURE = Path(__file__).parents[1] / "examples" / "reference-coordinate-public-aggregate.json"


class ReferenceCoordinateLineageTests(unittest.TestCase):
    def load(self) -> ReferenceCoordinateFixtureCatalog:
        return ReferenceCoordinateFixtureCatalog.from_file(FIXTURE)

    def test_graph_has_expected_typed_shape(self) -> None:
        catalog = self.load()
        graph = build_reference_coordinate_lineage(catalog)
        self.assertEqual(len(graph.nodes), 39)
        self.assertEqual(len(graph.edges), 38)
        self.assertEqual(
            sum(node.kind == ReferenceCoordinateNodeKind.SOURCE for node in graph.nodes), 6
        )
        self.assertEqual(
            sum(node.kind == ReferenceCoordinateNodeKind.FIXTURE for node in graph.nodes), 1
        )
        self.assertEqual(
            sum(node.kind == ReferenceCoordinateNodeKind.RECORD for node in graph.nodes), 16
        )
        self.assertEqual(
            sum(node.kind == ReferenceCoordinateNodeKind.RESULT for node in graph.nodes), 16
        )
        self.assertEqual(
            sum(edge.kind == ReferenceCoordinateEdgeKind.DECLARES for edge in graph.edges), 6
        )
        self.assertEqual(
            sum(edge.kind == ReferenceCoordinateEdgeKind.CONTAINS for edge in graph.edges), 16
        )
        self.assertEqual(
            sum(edge.kind == ReferenceCoordinateEdgeKind.PRODUCES for edge in graph.edges), 16
        )

    def test_graph_audit_passes_and_is_addressed(self) -> None:
        catalog = self.load()
        graph = build_reference_coordinate_lineage(catalog)
        audit = graph.audit(catalog)
        self.assertTrue(audit.passed)
        self.assertEqual(audit.failed_check_ids, ())
        self.assertTrue(graph.content_address.startswith("sha256:"))
        self.assertTrue(audit.content_address.startswith("sha256:"))

    def test_graph_is_deterministic(self) -> None:
        catalog = self.load()
        first = build_reference_coordinate_lineage(catalog)
        second = build_reference_coordinate_lineage(catalog)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_graph_projection_has_no_raw_payload_or_chain_text(self) -> None:
        graph = build_reference_coordinate_lineage(self.load())
        serialized = json.dumps(graph.to_dict(), sort_keys=True)
        self.assertNotIn("chain_text", serialized)
        self.assertNotIn("subject_id", serialized)
        self.assertNotIn("payload", serialized)

    def test_graph_audit_detects_removed_edge(self) -> None:
        catalog = self.load()
        graph = build_reference_coordinate_lineage(catalog)
        mutated = replace(graph, edges=graph.edges[:-1])
        audit = mutated.audit(catalog)
        self.assertFalse(audit.passed)
        self.assertIn("result-edges", audit.failed_check_ids)
        self.assertIn("edge-count", audit.failed_check_ids)

    def test_unknown_node_lookup_is_rejected(self) -> None:
        graph = build_reference_coordinate_lineage(self.load())
        with self.assertRaises(ValidationError):
            graph.node("result:does-not-exist")

    def test_node_and_edge_addresses_are_complete(self) -> None:
        graph = build_reference_coordinate_lineage(self.load())
        self.assertTrue(all(node.content_address.startswith("sha256:") for node in graph.nodes))
        self.assertTrue(all(edge.content_address.startswith("sha256:") for edge in graph.edges))


if __name__ == "__main__":
    unittest.main()
