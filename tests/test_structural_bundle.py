"""Bundle rendering and verification tests for Domain 02."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.structural_bundle import (
    StructuralBundleFormat,
    StructuralEvidenceBundleBuilder,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "structural-public-aggregate.json"


class StructuralBundleTests(unittest.TestCase):
    def test_json_bundle_is_accepted_and_address_verifies(self) -> None:
        bundle = StructuralEvidenceBundleBuilder().build(FIXTURE)
        self.assertTrue(bundle.accepted)
        self.assertEqual(len(bundle.entries), 12)
        self.assertEqual(sum(entry.entry_class == "positive" for entry in bundle.entries), 4)
        self.assertEqual(sum(entry.entry_class == "review" for entry in bundle.entries), 8)
        self.assertTrue(StructuralEvidenceBundleBuilder.verify(bundle.to_dict()))
        self.assertRegex(bundle.content_address, r"^sha256:[0-9a-f]{64}$")

    def test_entry_order_is_deterministic_and_capability_bound(self) -> None:
        bundle = StructuralEvidenceBundleBuilder().build(FIXTURE)
        ordered = [(entry.entry_class, entry.capability_id, entry.entry_id) for entry in bundle.entries]
        self.assertEqual(ordered, sorted(ordered))
        self.assertEqual(
            {entry.capability_id for entry in bundle.entries},
            {"GNC-D02-C01", "GNC-D02-C02", "GNC-D02-C03", "GNC-D02-C04"},
        )

    def test_bundle_does_not_copy_raw_operation_payloads(self) -> None:
        bundle = StructuralEvidenceBundleBuilder().build(FIXTURE)
        serialized = json.dumps(bundle.to_dict())
        self.assertNotIn("N]8:100000]", serialized)
        self.assertNotIn("caller_id\\tcaller_version", serialized)
        self.assertNotIn("sha256:recon-del-public-summary", serialized)
        self.assertIn("positive-reconstruction", serialized)

    def test_json_csv_and_markdown_renderings_have_expected_boundaries(self) -> None:
        bundle = StructuralEvidenceBundleBuilder().build(FIXTURE)
        json_text = bundle.render(StructuralBundleFormat.JSON)
        csv_text = bundle.render(StructuralBundleFormat.CSV)
        markdown_text = bundle.render(StructuralBundleFormat.MARKDOWN)
        self.assertTrue(json_text.startswith("{\n"))
        self.assertEqual(len(csv_text.splitlines()), 13)
        self.assertTrue(markdown_text.startswith("# Structural evidence bundle"))
        self.assertIn("GNC-D02-C01", markdown_text)
        self.assertIn("public aggregate structural observations", markdown_text)

    def test_write_infers_formats_from_output_suffix(self) -> None:
        builder = StructuralEvidenceBundleBuilder()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            json_path = root / "bundle.json"
            csv_path = root / "bundle.csv"
            markdown_path = root / "bundle.md"
            builder.write(FIXTURE, json_path)
            builder.write(FIXTURE, csv_path)
            builder.write(FIXTURE, markdown_path)
            self.assertTrue(json_path.read_text(encoding="utf-8").startswith("{\n"))
            self.assertTrue(csv_path.read_text(encoding="utf-8").startswith("entry_id,"))
            self.assertTrue(markdown_path.read_text(encoding="utf-8").startswith("# Structural"))

    def test_review_bundle_requires_explicit_override(self) -> None:
        review_fixture = ROOT / "examples" / "structural-pipeline-batch.json"
        with self.assertRaises(ValidationError):
            StructuralEvidenceBundleBuilder().build(review_fixture)

    def test_tampering_with_entry_state_invalidates_address(self) -> None:
        bundle = StructuralEvidenceBundleBuilder().build(FIXTURE)
        payload = bundle.to_dict()
        payload["entries"][0]["state"] = "tampered"
        self.assertFalse(StructuralEvidenceBundleBuilder.verify(payload))

    def test_tampering_with_convenience_count_does_not_change_address_check(self) -> None:
        bundle = StructuralEvidenceBundleBuilder().build(FIXTURE)
        payload = bundle.to_dict()
        payload["entry_count"] = 999
        self.assertTrue(StructuralEvidenceBundleBuilder.verify(payload))

    def test_bundle_id_changes_content_address(self) -> None:
        first = StructuralEvidenceBundleBuilder().build(FIXTURE, bundle_id="bundle-a")
        second = StructuralEvidenceBundleBuilder().build(FIXTURE, bundle_id="bundle-b")
        self.assertNotEqual(first.content_address, second.content_address)

    def test_quality_summary_retains_failed_ids_as_empty_on_acceptance(self) -> None:
        bundle = StructuralEvidenceBundleBuilder().build(FIXTURE)
        self.assertEqual(bundle.quality_summary["state"], "accepted")
        self.assertEqual(bundle.quality_summary["failed_check_ids"], ())
        self.assertEqual(bundle.component_summaries["quality"]["check_count"], 17)

    def test_bundle_carries_sanitized_lineage_receipt(self) -> None:
        bundle = StructuralEvidenceBundleBuilder().build(FIXTURE)
        lineage = bundle.component_summaries["lineage"]
        self.assertEqual(lineage["node_count"], 29)
        self.assertEqual(lineage["edge_count"], 36)
        self.assertEqual(lineage["state"], "accepted")
        self.assertEqual(bundle.quality_summary["lineage_address"], lineage["content_address"])
        self.assertEqual(bundle.to_dict()["lineage_address"], lineage["content_address"])


if __name__ == "__main__":
    unittest.main()
