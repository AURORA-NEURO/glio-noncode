from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.specimen_lineage_bundle import (
    SpecimenLineageBundleFormat,
    SpecimenLineageEvidenceBundleBuilder,
)
from glio_noncode.specimen_lineage_lineage import (
    audit_specimen_lineage_lineage,
    build_specimen_lineage_lineage,
)
from glio_noncode.specimen_lineage_public_data import SpecimenLineageFixtureCatalog
from glio_noncode.specimen_lineage_quality_gate import evaluate_specimen_lineage_quality_gate

FIXTURE = Path("examples/specimen-lineage-public-aggregate.json")


class SpecimenLineageQualityBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = SpecimenLineageFixtureCatalog.from_file(FIXTURE)

    def test_quality_gate_passes_and_reconciles_all_surfaces(self) -> None:
        report = evaluate_specimen_lineage_quality_gate(self.catalog)
        self.assertTrue(report.passed)
        self.assertEqual(report.positive_count, 4)
        self.assertEqual(report.control_count, 8)
        self.assertEqual(report.operation_count, 4)
        self.assertEqual(report.failed_check_ids, ())
        self.assertTrue(report.lineage_address.startswith("sha256:"))

    def test_quality_gate_is_deterministic(self) -> None:
        first = evaluate_specimen_lineage_quality_gate(self.catalog)
        second = evaluate_specimen_lineage_quality_gate(self.catalog)
        self.assertEqual(first.content_address, second.content_address)

    def test_lineage_graph_has_sanitized_release_shape(self) -> None:
        graph = build_specimen_lineage_lineage(self.catalog)
        audit = audit_specimen_lineage_lineage(graph)
        self.assertTrue(audit.passed)
        self.assertEqual(audit.node_count, 29)
        self.assertEqual(audit.edge_count, 28)
        self.assertEqual(len(graph.root_ids), 4)

    def test_lineage_graph_has_source_fixture_record_result_layers(self) -> None:
        graph = build_specimen_lineage_lineage(self.catalog)
        kinds = {node.kind.value for node in graph.nodes}
        self.assertEqual(kinds, {"source", "fixture", "record", "result"})
        self.assertEqual(sum(node.kind.value == "source" for node in graph.nodes), 4)
        self.assertEqual(sum(node.kind.value == "record" for node in graph.nodes), 12)
        self.assertEqual(sum(node.kind.value == "result" for node in graph.nodes), 12)

    def test_bundle_builds_and_verifies(self) -> None:
        builder = SpecimenLineageEvidenceBundleBuilder()
        bundle = builder.build(self.catalog)
        self.assertEqual(bundle.state, "accepted")
        self.assertEqual(bundle.entry_count, 12)
        self.assertTrue(builder.verify(bundle))
        self.assertTrue(bundle.content_address.startswith("sha256:"))

    def test_bundle_writes_all_supported_formats(self) -> None:
        builder = SpecimenLineageEvidenceBundleBuilder()
        bundle = builder.build(self.catalog)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outputs = {
                SpecimenLineageBundleFormat.JSON: root / "bundle.json",
                SpecimenLineageBundleFormat.CSV: root / "bundle.csv",
                SpecimenLineageBundleFormat.MARKDOWN: root / "bundle.md",
            }
            for format_value, path in outputs.items():
                builder.write(bundle, path, format=format_value)
                self.assertTrue(path.is_file())
                self.assertTrue(path.read_text(encoding="utf-8"))
            self.assertEqual(
                json.loads(outputs[SpecimenLineageBundleFormat.JSON].read_text(encoding="utf-8"))[
                    "entry_count"
                ],
                12,
            )
            self.assertIn(
                "entry_id,record_id",
                outputs[SpecimenLineageBundleFormat.CSV].read_text(encoding="utf-8"),
            )
            self.assertIn(
                "# specimen-lineage-c09-c12",
                outputs[SpecimenLineageBundleFormat.MARKDOWN].read_text(encoding="utf-8"),
            )

    def test_bundle_verify_detects_address_drift(self) -> None:
        builder = SpecimenLineageEvidenceBundleBuilder()
        bundle = builder.build(self.catalog)
        object.__setattr__(bundle, "content_address", "sha256:incorrect")
        self.assertFalse(builder.verify(bundle))

    def test_bundle_refuses_review_without_opt_in(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["positives"][0]["expected_counts"]["edges"] = 99
        catalog = SpecimenLineageFixtureCatalog.from_mapping(payload)
        with self.assertRaises(ValidationError):
            SpecimenLineageEvidenceBundleBuilder().build(catalog)

    def test_bundle_review_opt_in_retains_review_state(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["positives"][0]["expected_counts"]["edges"] = 99
        catalog = SpecimenLineageFixtureCatalog.from_mapping(payload)
        bundle = SpecimenLineageEvidenceBundleBuilder().build(catalog, allow_review=True)
        self.assertEqual(bundle.state, "review")
        self.assertEqual(bundle.entry_count, 12)


if __name__ == "__main__":
    unittest.main()
