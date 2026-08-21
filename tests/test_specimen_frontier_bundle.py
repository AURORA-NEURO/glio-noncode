"""Release bundle tests for Domain 03 C01-C04."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.specimen_frontier_bundle import (
    SpecimenFrontierBundleFormat,
    SpecimenFrontierEvidenceBundleBuilder,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "specimen-frontier-public-aggregate.json"


class SpecimenFrontierBundleTests(unittest.TestCase):
    def test_json_bundle_is_quality_gated_and_verifiable(self) -> None:
        bundle = SpecimenFrontierEvidenceBundleBuilder().build(FIXTURE)
        payload = bundle.to_dict()
        self.assertTrue(bundle.accepted)
        self.assertEqual(payload["entry_count"], 12)
        self.assertEqual(payload["positive_entry_count"], 4)
        self.assertEqual(payload["review_entry_count"], 8)
        self.assertTrue(SpecimenFrontierEvidenceBundleBuilder.verify(payload))

    def test_json_render_is_parseable_and_stable(self) -> None:
        bundle = SpecimenFrontierEvidenceBundleBuilder().build(FIXTURE)
        first = bundle.render(SpecimenFrontierBundleFormat.JSON)
        second = bundle.render("json")
        self.assertEqual(first, second)
        self.assertEqual(json.loads(first)["content_address"], bundle.content_address)

    def test_csv_render_has_one_row_per_entry(self) -> None:
        bundle = SpecimenFrontierEvidenceBundleBuilder().build(FIXTURE)
        lines = bundle.render("csv").splitlines()
        self.assertEqual(len(lines), 13)
        self.assertIn("specimen_identifier", lines[0])
        self.assertIn("GNC-D03-C04", "\n".join(lines))

    def test_markdown_render_contains_boundary_and_operations(self) -> None:
        bundle = SpecimenFrontierEvidenceBundleBuilder().build(FIXTURE)
        markdown = bundle.render("markdown")
        self.assertTrue(markdown.startswith("# Specimen frontier evidence bundle"))
        self.assertIn("GNC-D03-C01", markdown)
        self.assertIn("GNC-D03-C04", markdown)
        self.assertIn("## Boundary", markdown)

    def test_write_selects_format_from_extension(self) -> None:
        builder = SpecimenFrontierEvidenceBundleBuilder()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            json_path = root / "bundle.json"
            csv_path = root / "bundle.csv"
            md_path = root / "bundle.md"
            builder.write(FIXTURE, json_path)
            builder.write(FIXTURE, csv_path)
            builder.write(FIXTURE, md_path)
            self.assertTrue(json.loads(json_path.read_text(encoding="utf-8"))["accepted"])
            self.assertTrue(csv_path.read_text(encoding="utf-8").startswith("entry_id,"))
            self.assertTrue(md_path.read_text(encoding="utf-8").startswith("# Specimen frontier"))

    def test_tampering_changes_verification_result(self) -> None:
        bundle = SpecimenFrontierEvidenceBundleBuilder().build(FIXTURE)
        payload = bundle.to_dict()
        payload["entries"][0]["summary"] = "tampered"
        self.assertFalse(SpecimenFrontierEvidenceBundleBuilder.verify(payload))

    def test_review_bundle_requires_explicit_opt_in(self) -> None:
        review_fixture = ROOT / "examples" / "specimen-frontier-pipeline-review.json"
        with self.assertRaises(ValidationError):
            SpecimenFrontierEvidenceBundleBuilder().build(review_fixture)

    def test_bundle_entry_order_is_deterministic(self) -> None:
        builder = SpecimenFrontierEvidenceBundleBuilder()
        first = builder.build(FIXTURE)
        second = builder.build(FIXTURE)
        self.assertEqual(
            [entry.entry_id for entry in first.entries],
            [entry.entry_id for entry in second.entries],
        )
        self.assertEqual(first.content_address, second.content_address)


if __name__ == "__main__":
    unittest.main()
