"""Bundle rendering and verification tests for Domain 02 C05-C08."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.structural_beta_bundle import (
    StructuralBetaBundleFormat,
    StructuralBetaEvidenceBundleBuilder,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "structural-beta-public-aggregate.json"


class StructuralBetaBundleTests(unittest.TestCase):
    def test_bundle_is_accepted_and_address_verifies(self) -> None:
        bundle = StructuralBetaEvidenceBundleBuilder().build(FIXTURE)
        self.assertTrue(bundle.accepted)
        self.assertEqual(len(bundle.entries), 12)
        self.assertEqual(sum(entry.entry_class == "positive" for entry in bundle.entries), 4)
        self.assertEqual(sum(entry.entry_class == "review" for entry in bundle.entries), 8)
        self.assertTrue(StructuralBetaEvidenceBundleBuilder.verify(bundle.to_dict()))
        self.assertRegex(bundle.content_address, r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(bundle.quality_summary["lineage_address"], bundle.lineage_address)

    def test_entries_are_sorted_and_capability_bound(self) -> None:
        bundle = StructuralBetaEvidenceBundleBuilder().build(FIXTURE)
        ordered = [(entry.entry_class, entry.capability_id, entry.entry_id) for entry in bundle.entries]
        self.assertEqual(ordered, sorted(ordered))
        self.assertEqual(
            {entry.capability_id for entry in bundle.entries},
            {"GNC-D02-C05", "GNC-D02-C06", "GNC-D02-C07", "GNC-D02-C08"},
        )

    def test_bundle_has_lineage_component_shape(self) -> None:
        bundle = StructuralBetaEvidenceBundleBuilder().build(FIXTURE)
        lineage = bundle.component_summaries["lineage"]
        self.assertEqual(lineage["node_count"], 29)
        self.assertEqual(lineage["edge_count"], 36)
        self.assertEqual(lineage["content_address"], bundle.lineage_address)

    def test_bundle_does_not_copy_raw_operation_payloads(self) -> None:
        bundle = StructuralBetaEvidenceBundleBuilder().build(FIXTURE)
        serialized = json.dumps(bundle.to_dict(), sort_keys=True)
        self.assertNotIn("subject_id", serialized)
        self.assertNotIn("raw_record", serialized)
        self.assertNotIn('"copy_number": -1', serialized)
        self.assertIn("positive-focal-amplification", serialized)

    def test_json_csv_and_markdown_renderings(self) -> None:
        bundle = StructuralBetaEvidenceBundleBuilder().build(FIXTURE)
        self.assertTrue(bundle.render(StructuralBetaBundleFormat.JSON).startswith("{\n"))
        self.assertEqual(len(bundle.render(StructuralBetaBundleFormat.CSV).splitlines()), 13)
        markdown = bundle.render(StructuralBetaBundleFormat.MARKDOWN)
        self.assertTrue(markdown.startswith("# Structural beta evidence bundle"))
        self.assertIn("GNC-D02-C08", markdown)

    def test_write_infers_formats_from_suffix(self) -> None:
        builder = StructuralBetaEvidenceBundleBuilder()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            json_path = root / "beta.json"
            csv_path = root / "beta.csv"
            markdown_path = root / "beta.md"
            builder.write(FIXTURE, json_path)
            builder.write(FIXTURE, csv_path)
            builder.write(FIXTURE, markdown_path)
            self.assertTrue(json_path.read_text(encoding="utf-8").startswith("{\n"))
            self.assertTrue(csv_path.read_text(encoding="utf-8").startswith("entry_id,"))
            self.assertTrue(markdown_path.read_text(encoding="utf-8").startswith("# Structural beta"))

    def test_review_bundle_requires_explicit_override(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["positives"][0]["expected_counts"]["candidates"] = 99
        with tempfile.TemporaryDirectory() as directory:
            review_fixture = Path(directory) / "review.json"
            review_fixture.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValidationError):
                StructuralBetaEvidenceBundleBuilder().build(review_fixture)
            bundle = StructuralBetaEvidenceBundleBuilder().build(
                review_fixture,
                allow_review=True,
            )
            self.assertFalse(bundle.accepted)
            self.assertIn("review", bundle.state)

    def test_tampering_with_entry_state_invalidates_address(self) -> None:
        bundle = StructuralBetaEvidenceBundleBuilder().build(FIXTURE)
        payload = bundle.to_dict()
        payload["entries"][0]["state"] = "tampered"
        self.assertFalse(StructuralBetaEvidenceBundleBuilder.verify(payload))

    def test_tampering_with_convenience_count_does_not_change_address_check(self) -> None:
        bundle = StructuralBetaEvidenceBundleBuilder().build(FIXTURE)
        payload = bundle.to_dict()
        payload["entry_count"] = 999
        self.assertTrue(StructuralBetaEvidenceBundleBuilder.verify(payload))

    def test_bundle_id_changes_content_address(self) -> None:
        first = StructuralBetaEvidenceBundleBuilder().build(FIXTURE, bundle_id="beta-a")
        second = StructuralBetaEvidenceBundleBuilder().build(FIXTURE, bundle_id="beta-b")
        self.assertNotEqual(first.content_address, second.content_address)


if __name__ == "__main__":
    unittest.main()
