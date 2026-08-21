"""Lineage graph and audit tests for Domain 02 C13-C16."""

from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.structural_frontier_lineage import (
    StructuralFrontierLineageNodeKind,
    StructuralFrontierLineageRelation,
    audit_structural_frontier_lineage,
    build_structural_frontier_lineage,
)
from glio_noncode.structural_frontier_public_data import StructuralFrontierFixtureState

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "structural-frontier-public-aggregate.json"
FIXTURE_NODE = "fixture:structural-frontier-public-aggregate-2026-08-21"


class StructuralFrontierLineageTests(unittest.TestCase):
    def test_canonical_graph_is_addressed_and_audited(self) -> None:
        graph = build_structural_frontier_lineage(FIXTURE.as_posix())
        audit = audit_structural_frontier_lineage(graph)
        self.assertEqual(graph.state, StructuralFrontierFixtureState.ACCEPTED)
        self.assertTrue(graph.accepted)
        self.assertTrue(graph.verify())
        self.assertTrue(audit.passed)
        self.assertEqual(audit.node_count, 29)
        self.assertEqual(audit.edge_count, 36)
        self.assertEqual(audit.issue_codes, ())

    def test_graph_has_four_sources_one_fixture_twelve_records_and_results(self) -> None:
        graph = build_structural_frontier_lineage(FIXTURE.as_posix())
        counts = {kind: sum(node.kind == kind for node in graph.nodes) for kind in StructuralFrontierLineageNodeKind}
        self.assertEqual(counts[StructuralFrontierLineageNodeKind.SOURCE], 4)
        self.assertEqual(counts[StructuralFrontierLineageNodeKind.FIXTURE], 1)
        self.assertEqual(counts[StructuralFrontierLineageNodeKind.RECORD], 12)
        self.assertEqual(counts[StructuralFrontierLineageNodeKind.RESULT], 12)
        self.assertEqual({edge.relation for edge in graph.edges}, set(StructuralFrontierLineageRelation))

    def test_roots_are_sources_and_fixture(self) -> None:
        graph = build_structural_frontier_lineage(FIXTURE.as_posix())
        self.assertEqual(len(graph.root_ids), 5)
        self.assertIn(FIXTURE_NODE, graph.root_ids)
        self.assertTrue(all(node_id.startswith("source:") for node_id in graph.root_ids if node_id != FIXTURE_NODE))

    def test_fixture_contains_every_record(self) -> None:
        graph = build_structural_frontier_lineage(FIXTURE.as_posix())
        children = graph.children(FIXTURE_NODE)
        self.assertEqual(len(children), 12)
        self.assertEqual(set(children), {node.node_id for node in graph.nodes if node.kind == StructuralFrontierLineageNodeKind.RECORD})

    def test_each_record_produces_one_result(self) -> None:
        graph = build_structural_frontier_lineage(FIXTURE.as_posix())
        for record in (node for node in graph.nodes if node.kind == StructuralFrontierLineageNodeKind.RECORD):
            children = graph.children(record.node_id)
            self.assertEqual(len(children), 1)
            self.assertTrue(children[0].startswith("result:"))
            self.assertEqual(graph.node(children[0]).record_id, record.record_id)

    def test_source_nodes_declare_records(self) -> None:
        graph = build_structural_frontier_lineage(FIXTURE.as_posix())
        for source_id in graph.source_ids:
            children = graph.children(f"source:{source_id}")
            self.assertGreaterEqual(len(children), 1)
            self.assertTrue(all(node_id.startswith("record:") for node_id in children))

    def test_graph_is_sanitized(self) -> None:
        graph = build_structural_frontier_lineage(FIXTURE.as_posix())
        serialized = json.dumps(graph.to_dict(), sort_keys=True)
        self.assertNotIn("raw_record", serialized)
        self.assertNotIn("patient_id", serialized)
        self.assertNotIn("subject_id", serialized)
        self.assertNotIn("CAX", serialized)

    def test_graph_is_deterministic(self) -> None:
        first = build_structural_frontier_lineage(FIXTURE.as_posix())
        second = build_structural_frontier_lineage(FIXTURE.as_posix())
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_custom_graph_id_changes_address(self) -> None:
        first = build_structural_frontier_lineage(FIXTURE.as_posix(), graph_id="frontier-lineage-a")
        second = build_structural_frontier_lineage(FIXTURE.as_posix(), graph_id="frontier-lineage-b")
        self.assertNotEqual(first.content_address, second.content_address)

    def test_unknown_node_lookup_is_rejected(self) -> None:
        graph = build_structural_frontier_lineage(FIXTURE.as_posix())
        with self.assertRaisesRegex(ValidationError, "unknown structural frontier lineage node"):
            graph.children("record:missing")

    def test_context_tampering_is_audited(self) -> None:
        graph = build_structural_frontier_lineage(FIXTURE.as_posix())
        changed = replace(graph.nodes[0], context_key="GRCh37|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment")
        tampered = replace(graph, nodes=(changed,) + graph.nodes[1:])
        audit = audit_structural_frontier_lineage(tampered)
        self.assertFalse(tampered.verify())
        self.assertIn("graph_address_or_endpoint_invalid", audit.issue_codes)
        self.assertIn("context_mismatch", audit.issue_codes)

    def test_result_removal_is_audited(self) -> None:
        graph = build_structural_frontier_lineage(FIXTURE.as_posix())
        removed = next(node for node in graph.nodes if node.kind == StructuralFrontierLineageNodeKind.RESULT)
        audit = audit_structural_frontier_lineage(replace(graph, nodes=tuple(node for node in graph.nodes if node != removed)))
        self.assertIn("record_result_mismatch", audit.issue_codes)

    def test_source_removal_is_audited(self) -> None:
        graph = build_structural_frontier_lineage(FIXTURE.as_posix())
        removed = next(node for node in graph.nodes if node.kind == StructuralFrontierLineageNodeKind.SOURCE)
        audit = audit_structural_frontier_lineage(replace(graph, nodes=tuple(node for node in graph.nodes if node != removed)))
        self.assertIn("source_coverage", audit.issue_codes)


if __name__ == "__main__":
    unittest.main()
