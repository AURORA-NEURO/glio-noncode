"""Lineage graph tests for the Domain 02 structural evidence stack."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.structural_lineage import (
    StructuralLineageBuilder,
    StructuralLineageNodeKind,
    StructuralLineageRelation,
    audit_structural_lineage,
    build_structural_lineage,
)
from glio_noncode.structural_public_data import StructuralFixtureCatalog, StructuralFixtureState

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "structural-public-aggregate.json"


class StructuralLineageTests(unittest.TestCase):
    def test_graph_is_accepted_and_content_addressed(self) -> None:
        graph = build_structural_lineage(str(FIXTURE))
        self.assertEqual(graph.state, StructuralFixtureState.ACCEPTED)
        self.assertTrue(graph.accepted)
        self.assertTrue(graph.verify())
        self.assertRegex(graph.content_address, r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(len(graph.nodes), 29)
        self.assertEqual(len(graph.edges), 36)

    def test_graph_contains_public_sources_fixture_records_and_results(self) -> None:
        graph = build_structural_lineage(str(FIXTURE))
        kinds = {kind: sum(node.kind == kind for node in graph.nodes) for kind in StructuralLineageNodeKind}
        self.assertEqual(kinds[StructuralLineageNodeKind.SOURCE], 4)
        self.assertEqual(kinds[StructuralLineageNodeKind.FIXTURE], 1)
        self.assertEqual(kinds[StructuralLineageNodeKind.RECORD], 12)
        self.assertEqual(kinds[StructuralLineageNodeKind.RESULT], 12)
        self.assertEqual(len(graph.root_ids), 5)
        self.assertIn("fixture:structural-public-aggregate-2026-08-21", graph.root_ids)

    def test_graph_edges_have_explicit_relationships_and_valid_endpoints(self) -> None:
        graph = build_structural_lineage(str(FIXTURE))
        relations = {edge.relation for edge in graph.edges}
        self.assertEqual(
            relations,
            {
                StructuralLineageRelation.DECLARES,
                StructuralLineageRelation.CONTAINS,
                StructuralLineageRelation.PRODUCES,
            },
        )
        self.assertTrue(all(edge.from_node in graph.node_ids for edge in graph.edges))
        self.assertTrue(all(edge.to_node in graph.node_ids for edge in graph.edges))
        self.assertTrue(all(edge.content_address.startswith("sha256:") for edge in graph.edges))

    def test_children_exposes_source_and_result_paths(self) -> None:
        graph = build_structural_lineage(str(FIXTURE))
        source_children = graph.children("source:ncbi-dbvar-nstd75")
        self.assertEqual(len(source_children), 3)
        self.assertTrue(all(item.startswith("record:") for item in source_children))
        record_children = graph.children("record:positive-reconstruction")
        self.assertEqual(record_children, ("result:positive-reconstruction",))
        self.assertEqual(graph.node("result:positive-reconstruction").kind, StructuralLineageNodeKind.RESULT)

    def test_graph_does_not_copy_raw_payload_values(self) -> None:
        graph = build_structural_lineage(str(FIXTURE))
        serialized = json.dumps(graph.to_dict(), sort_keys=True)
        self.assertNotIn("N]8:100000]", serialized)
        self.assertNotIn("caller_id\\tcaller_version", serialized)
        self.assertNotIn("raw_private_payload_marker", serialized)
        self.assertIn("positive-reconstruction", serialized)

    def test_graph_audit_passes(self) -> None:
        graph = build_structural_lineage(str(FIXTURE))
        audit = audit_structural_lineage(graph)
        self.assertTrue(audit.passed)
        self.assertEqual(audit.state, StructuralFixtureState.ACCEPTED)
        self.assertEqual(audit.issue_codes, ())
        self.assertEqual(audit.node_count, 29)
        self.assertEqual(audit.edge_count, 36)

    def test_graph_audit_rejects_tampered_address(self) -> None:
        graph = build_structural_lineage(str(FIXTURE))
        tampered = copy.copy(graph)
        object.__setattr__(tampered, "content_address", "sha256:" + "0" * 64)
        audit = audit_structural_lineage(tampered)
        self.assertFalse(audit.passed)
        self.assertIn("graph_address_or_endpoint_invalid", audit.issue_codes)

    def test_graph_audit_rejects_context_drift(self) -> None:
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        raw["positives"][0]["context_key"] = "GRCh38|diffuse_glioma|adult|other|tumor_core|pre_treatment"
        catalog = StructuralFixtureCatalog.from_mapping(raw)
        graph = StructuralLineageBuilder().build(catalog)
        audit = audit_structural_lineage(graph)
        self.assertFalse(audit.passed)
        self.assertIn("context_mismatch", audit.issue_codes)

    def test_graph_state_follows_evaluation_state(self) -> None:
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        raw["positives"][0]["expected_counts"]["events"] = 99
        catalog = StructuralFixtureCatalog.from_mapping(raw)
        graph = StructuralLineageBuilder().build(catalog)
        self.assertEqual(graph.state, StructuralFixtureState.REVIEW)
        self.assertFalse(graph.accepted)

    def test_graph_id_changes_address_without_changing_lineage_shape(self) -> None:
        first = build_structural_lineage(str(FIXTURE), graph_id="lineage-a")
        second = build_structural_lineage(str(FIXTURE), graph_id="lineage-b")
        self.assertNotEqual(first.content_address, second.content_address)
        self.assertEqual(first.node_ids, second.node_ids)
        self.assertEqual(first.edge_ids, second.edge_ids)

    def test_unknown_node_lookup_is_rejected(self) -> None:
        graph = build_structural_lineage(str(FIXTURE))
        with self.assertRaises(ValidationError):
            graph.children("unknown")
        with self.assertRaises(ValidationError):
            graph.node("unknown")

    def test_graph_rendering_is_deterministic(self) -> None:
        first = build_structural_lineage(str(FIXTURE))
        second = build_structural_lineage(str(FIXTURE))
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.content_address, second.content_address)


if __name__ == "__main__":
    unittest.main()
