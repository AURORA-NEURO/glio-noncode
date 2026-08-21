"""Bundle rendering and verification tests for Domain 02 C09-C12."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.structural_haplotype_bundle import (
    StructuralHaplotypeBundleFormat,
    StructuralHaplotypeEvidenceBundleBuilder,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "structural-haplotype-public-aggregate.json"


class StructuralHaplotypeBundleTests(unittest.TestCase):
    def test_bundle_is_accepted_and_address_verifies(self) -> None:
        bundle = StructuralHaplotypeEvidenceBundleBuilder().build(FIXTURE)
        self.assertTrue(bundle.accepted)
        self.assertEqual(len(bundle.entries), 12)
        self.assertEqual(sum(entry.entry_class == "positive" for entry in bundle.entries), 4)
        self.assertEqual(sum(entry.entry_class == "review" for entry in bundle.entries), 8)
        self.assertTrue(StructuralHaplotypeEvidenceBundleBuilder.verify(bundle.to_dict()))
        self.assertRegex(bundle.content_address, r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(bundle.quality_summary["lineage_address"], bundle.lineage_address)

    def test_entries_are_sorted_and_capability_bound(self) -> None:
        bundle = StructuralHaplotypeEvidenceBundleBuilder().build(FIXTURE)
        ordered = [(entry.entry_class, entry.capability_id, entry.entry_id) for entry in bundle.entries]
        self.assertEqual(ordered, sorted(ordered))
        self.assertEqual({entry.capability_id for entry in bundle.entries}, {"GNC-D02-C09", "GNC-D02-C10", "GNC-D02-C11", "GNC-D02-C12"})

    def test_bundle_has_lineage_component_shape(self) -> None:
        bundle = StructuralHaplotypeEvidenceBundleBuilder().build(FIXTURE)
        lineage = bundle.component_summaries["lineage"]
        self.assertEqual(lineage["node_count"], 29)
        self.assertEqual(lineage["edge_count"], 36)
        self.assertEqual(lineage["content_address"], bundle.lineage_address)

    def test_bundle_does_not_copy_raw_operation_payloads(self) -> None:
        bundle = StructuralHaplotypeEvidenceBundleBuilder().build(FIXTURE)
        serialized = json.dumps(bundle.to_dict(), sort_keys=True)
        self.assertNotIn("raw_record", serialized)
        self.assertNotIn("subject_id", serialized)
        self.assertNotIn("aggregate-phase-1", serialized)
        self.assertNotIn("AGCT", serialized)
        self.assertIn("positive-phased-haplotype", serialized)

    def test_json_csv_and_markdown_renderings(self) -> None:
        bundle = StructuralHaplotypeEvidenceBundleBuilder().build(FIXTURE)
        self.assertTrue(bundle.render(StructuralHaplotypeBundleFormat.JSON).startswith("{\n"))
        self.assertEqual(len(bundle.render(StructuralHaplotypeBundleFormat.CSV).splitlines()), 13)
        markdown = bundle.render(StructuralHaplotypeBundleFormat.MARKDOWN)
        self.assertTrue(markdown.startswith("# Structural haplotype evidence bundle"))
        self.assertIn("GNC-D02-C12", markdown)

    def test_write_infers_formats_from_suffix(self) -> None:
        builder = StructuralHaplotypeEvidenceBundleBuilder()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            json_path, csv_path, markdown_path = root / "bundle.json", root / "bundle.csv", root / "bundle.md"
            builder.write(FIXTURE, json_path)
            builder.write(FIXTURE, csv_path)
            builder.write(FIXTURE, markdown_path)
            self.assertTrue(json_path.read_text(encoding="utf-8").startswith("{\n"))
            self.assertTrue(csv_path.read_text(encoding="utf-8").startswith("entry_id,"))
            self.assertTrue(markdown_path.read_text(encoding="utf-8").startswith("# Structural haplotype"))

    def test_review_bundle_requires_explicit_override(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["positives"][0]["expected_counts"]["haplotypes"] = 99
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValidationError):
                StructuralHaplotypeEvidenceBundleBuilder().build(path)
            bundle = StructuralHaplotypeEvidenceBundleBuilder().build(path, allow_review=True)
            self.assertFalse(bundle.accepted)
            self.assertEqual(bundle.state.value, "review")

    def test_tampering_with_entry_state_invalidates_address(self) -> None:
        bundle = StructuralHaplotypeEvidenceBundleBuilder().build(FIXTURE)
        payload = bundle.to_dict()
        payload["entries"][0]["state"] = "tampered"
        self.assertFalse(StructuralHaplotypeEvidenceBundleBuilder.verify(payload))

    def test_tampering_with_convenience_count_does_not_change_address(self) -> None:
        bundle = StructuralHaplotypeEvidenceBundleBuilder().build(FIXTURE)
        payload = bundle.to_dict()
        payload["entry_count"] = 999
        self.assertTrue(StructuralHaplotypeEvidenceBundleBuilder.verify(payload))

    def test_bundle_id_changes_content_address(self) -> None:
        first = StructuralHaplotypeEvidenceBundleBuilder().build(FIXTURE, bundle_id="haplotype-a")
        second = StructuralHaplotypeEvidenceBundleBuilder().build(FIXTURE, bundle_id="haplotype-b")
        self.assertNotEqual(first.content_address, second.content_address)


if __name__ == "__main__":
    unittest.main()
