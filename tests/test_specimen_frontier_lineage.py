"""Lineage graph tests for Domain 03 C01-C04."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.specimen_frontier_lineage import (
    SpecimenFrontierLineageNodeKind,
    audit_specimen_frontier_lineage,
    build_specimen_frontier_lineage,
)
from glio_noncode.specimen_frontier_public_data import SpecimenFrontierFixtureCatalog

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "specimen-frontier-public-aggregate.json"


class SpecimenFrontierLineageTests(unittest.TestCase):
    def test_canonical_graph_has_four_layers_and_expected_shape(self) -> None:
        graph = build_specimen_frontier_lineage(str(FIXTURE))
        audit = audit_specimen_frontier_lineage(graph)
        self.assertTrue(graph.verify())
        self.assertTrue(audit.passed)
        self.assertEqual(len(graph.nodes), 29)
        self.assertEqual(len(graph.edges), 36)
        self.assertEqual(
            sum(node.kind == SpecimenFrontierLineageNodeKind.SOURCE for node in graph.nodes),
            4,
        )
        self.assertEqual(
            sum(node.kind == SpecimenFrontierLineageNodeKind.RECORD for node in graph.nodes),
            12,
        )
        self.assertEqual(
            sum(node.kind == SpecimenFrontierLineageNodeKind.RESULT for node in graph.nodes),
            12,
        )

    def test_graph_roots_are_source_nodes(self) -> None:
        graph = build_specimen_frontier_lineage(str(FIXTURE))
        self.assertEqual(
            set(graph.root_ids),
            {f"source:{source_id}" for source_id in graph.source_ids}
            | {f"fixture:{graph.fixture_id}"},
        )
        fixture_children = graph.children(f"fixture:{graph.fixture_id}")
        self.assertEqual(len(fixture_children), 12)

    def test_record_nodes_have_result_pairs_and_source_edges(self) -> None:
        graph = build_specimen_frontier_lineage(str(FIXTURE))
        for node in graph.nodes:
            if node.kind != SpecimenFrontierLineageNodeKind.RECORD:
                continue
            self.assertEqual(graph.children(node.node_id), (f"result:{node.record_id}",))
            self.assertTrue(node.source_id in graph.source_ids)

    def test_graph_content_address_is_stable(self) -> None:
        catalog = SpecimenFrontierFixtureCatalog.from_file(FIXTURE)
        first = build_specimen_frontier_lineage(catalog)
        second = build_specimen_frontier_lineage(catalog)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_context_drift_is_detected_by_lineage_audit(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["controls"][0]["context_key"] = (
            "GRCh38|diffuse_glioma|adult|other|tumor_core|pre_treatment"
        )
        graph = build_specimen_frontier_lineage(
            SpecimenFrontierFixtureCatalog.from_mapping(payload)
        )
        audit = audit_specimen_frontier_lineage(graph)
        self.assertIn("context_mismatch", audit.issue_codes)
        self.assertFalse(audit.passed)

    def test_unknown_node_lookup_fails(self) -> None:
        graph = build_specimen_frontier_lineage(str(FIXTURE))
        with self.assertRaises(ValidationError):
            graph.node("missing")


if __name__ == "__main__":
    unittest.main()
