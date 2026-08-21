"""Lineage graph and audit tests for Domain 02 C05-C08."""

from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.structural_beta_lineage import (
    StructuralBetaLineageNodeKind,
    StructuralBetaLineageRelation,
    audit_structural_beta_lineage,
    build_structural_beta_lineage,
)
from glio_noncode.structural_beta_public_data import StructuralBetaFixtureState

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "structural-beta-public-aggregate.json"


class StructuralBetaLineageTests(unittest.TestCase):
    def test_canonical_graph_is_addressed_and_audited(self) -> None:
        graph = build_structural_beta_lineage(str(FIXTURE))
        audit = audit_structural_beta_lineage(graph)
        self.assertEqual(graph.state, StructuralBetaFixtureState.ACCEPTED)
        self.assertTrue(graph.accepted)
        self.assertTrue(graph.verify())
        self.assertTrue(audit.passed)
        self.assertEqual(audit.node_count, 29)
        self.assertEqual(audit.edge_count, 36)
        self.assertEqual(audit.issue_codes, ())
        self.assertRegex(graph.content_address, r"^sha256:[0-9a-f]{64}$")

    def test_graph_has_expected_typed_shape(self) -> None:
        graph = build_structural_beta_lineage(str(FIXTURE))
        counts = {
            kind: sum(node.kind == kind for node in graph.nodes)
            for kind in StructuralBetaLineageNodeKind
        }
        self.assertEqual(counts[StructuralBetaLineageNodeKind.SOURCE], 4)
        self.assertEqual(counts[StructuralBetaLineageNodeKind.FIXTURE], 1)
        self.assertEqual(counts[StructuralBetaLineageNodeKind.RECORD], 12)
        self.assertEqual(counts[StructuralBetaLineageNodeKind.RESULT], 12)
        relations = {edge.relation for edge in graph.edges}
        self.assertEqual(
            relations,
            {
                StructuralBetaLineageRelation.DECLARES,
                StructuralBetaLineageRelation.CONTAINS,
                StructuralBetaLineageRelation.PRODUCES,
            },
        )

    def test_graph_roots_are_public_sources_and_fixture(self) -> None:
        graph = build_structural_beta_lineage(str(FIXTURE))
        self.assertEqual(len(graph.root_ids), 5)
        self.assertIn("fixture:structural-beta-public-aggregate-2026-08-21", graph.root_ids)
        self.assertTrue(all(node_id.startswith("source:") for node_id in graph.root_ids if node_id != "fixture:structural-beta-public-aggregate-2026-08-21"))

    def test_source_children_declare_records(self) -> None:
        graph = build_structural_beta_lineage(str(FIXTURE))
        for source_id in graph.source_ids:
            children = graph.children(f"source:{source_id}")
            self.assertGreaterEqual(len(children), 1)
            self.assertTrue(all(child.startswith("record:") for child in children))

    def test_fixture_contains_every_record(self) -> None:
        graph = build_structural_beta_lineage(str(FIXTURE))
        fixture_children = graph.children("fixture:structural-beta-public-aggregate-2026-08-21")
        self.assertEqual(len(fixture_children), 12)
        self.assertEqual(set(fixture_children), {node.node_id for node in graph.nodes if node.kind == StructuralBetaLineageNodeKind.RECORD})

    def test_each_record_produces_one_result(self) -> None:
        graph = build_structural_beta_lineage(str(FIXTURE))
        record_nodes = [node for node in graph.nodes if node.kind == StructuralBetaLineageNodeKind.RECORD]
        for record in record_nodes:
            children = graph.children(record.node_id)
            self.assertEqual(len(children), 1)
            self.assertTrue(children[0].startswith("result:"))
            self.assertEqual(graph.node(children[0]).record_id, record.record_id)

    def test_lineage_nodes_are_sanitized(self) -> None:
        graph = build_structural_beta_lineage(str(FIXTURE))
        serialized = json.dumps(graph.to_dict(), sort_keys=True)
        self.assertNotIn("raw_record", serialized)
        self.assertNotIn("subject_id", serialized)
        self.assertNotIn("patient_id", serialized)
        self.assertNotIn('"copy_number": -1', serialized)
        self.assertIn("ncbi-dbvar-nstd102", serialized)

    def test_graph_id_is_deterministic(self) -> None:
        first = build_structural_beta_lineage(str(FIXTURE))
        second = build_structural_beta_lineage(str(FIXTURE))
        self.assertEqual(first.graph_id, second.graph_id)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_custom_graph_id_changes_graph_address(self) -> None:
        first = build_structural_beta_lineage(str(FIXTURE), graph_id="beta-lineage-a")
        second = build_structural_beta_lineage(str(FIXTURE), graph_id="beta-lineage-b")
        self.assertNotEqual(first.graph_id, second.graph_id)
        self.assertNotEqual(first.content_address, second.content_address)

    def test_unknown_node_lookup_is_rejected(self) -> None:
        graph = build_structural_beta_lineage(str(FIXTURE))
        with self.assertRaisesRegex(ValidationError, "unknown beta lineage node"):
            graph.children("record:missing")

    def test_context_tampering_is_audited(self) -> None:
        graph = build_structural_beta_lineage(str(FIXTURE))
        changed = replace(graph.nodes[0], context_key="GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_margin|pre_treatment")
        tampered = replace(graph, nodes=(changed,) + graph.nodes[1:])
        audit = audit_structural_beta_lineage(tampered)
        self.assertFalse(tampered.verify())
        self.assertFalse(audit.passed)
        self.assertIn("graph_address_or_endpoint_invalid", audit.issue_codes)
        self.assertIn("context_mismatch", audit.issue_codes)

    def test_record_result_removal_is_audited(self) -> None:
        graph = build_structural_beta_lineage(str(FIXTURE))
        removed = next(node for node in graph.nodes if node.kind == StructuralBetaLineageNodeKind.RESULT)
        tampered = replace(graph, nodes=tuple(node for node in graph.nodes if node != removed))
        audit = audit_structural_beta_lineage(tampered)
        self.assertFalse(audit.passed)
        self.assertIn("record_result_mismatch", audit.issue_codes)

    def test_source_removal_is_audited(self) -> None:
        graph = build_structural_beta_lineage(str(FIXTURE))
        removed = next(node for node in graph.nodes if node.kind == StructuralBetaLineageNodeKind.SOURCE)
        tampered = replace(graph, nodes=tuple(node for node in graph.nodes if node != removed))
        audit = audit_structural_beta_lineage(tampered)
        self.assertFalse(audit.passed)
        self.assertIn("source_coverage", audit.issue_codes)

    def test_result_state_is_preserved_without_payload(self) -> None:
        graph = build_structural_beta_lineage(str(FIXTURE))
        result_nodes = [node for node in graph.nodes if node.kind == StructuralBetaLineageNodeKind.RESULT]
        self.assertTrue(any(node.state == StructuralBetaFixtureState.ACCEPTED.value for node in result_nodes))
        self.assertTrue(any(node.state == StructuralBetaFixtureState.REVIEW.value for node in result_nodes))
        self.assertTrue(all(node.content_address.startswith("sha256:") for node in result_nodes))
        self.assertTrue(all(node.context_key == graph.context_key for node in result_nodes))


if __name__ == "__main__":
    unittest.main()
