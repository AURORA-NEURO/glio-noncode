from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.specimen_beta_frontier_bundle import (
    SpecimenBetaFrontierBundleFormat,
    SpecimenBetaFrontierEvidenceBundleBuilder,
)
from glio_noncode.specimen_beta_frontier_public_data import SpecimenBetaFrontierFixtureCatalog

FIXTURE = Path("examples/specimen-beta-frontier-public-aggregate.json")


class SpecimenBetaFrontierBundleTests(unittest.TestCase):
    def test_accepted_bundle_has_twelve_sanitized_entries(self) -> None:
        catalog = SpecimenBetaFrontierFixtureCatalog.from_file(FIXTURE)
        builder = SpecimenBetaFrontierEvidenceBundleBuilder()
        bundle = builder.build(catalog)
        self.assertEqual(bundle.state, "accepted")
        self.assertEqual(bundle.entry_count, 12)
        self.assertTrue(builder.verify(bundle))

    def test_bundle_has_quality_and_lineage_addresses(self) -> None:
        catalog = SpecimenBetaFrontierFixtureCatalog.from_file(FIXTURE)
        bundle = SpecimenBetaFrontierEvidenceBundleBuilder().build(catalog)
        self.assertTrue(bundle.quality_address.startswith("sha256:"))
        self.assertTrue(bundle.lineage_address.startswith("sha256:"))
        self.assertTrue(bundle.content_address.startswith("sha256:"))

    def test_bundle_entry_order_and_identity_are_deterministic(self) -> None:
        catalog = SpecimenBetaFrontierFixtureCatalog.from_file(FIXTURE)
        builder = SpecimenBetaFrontierEvidenceBundleBuilder()
        first = builder.build(catalog)
        second = builder.build(catalog)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(
            [entry.record_id for entry in first.entries],
            [record.record_id for record in catalog.records],
        )

    def test_json_csv_and_markdown_projections_write(self) -> None:
        catalog = SpecimenBetaFrontierFixtureCatalog.from_file(FIXTURE)
        builder = SpecimenBetaFrontierEvidenceBundleBuilder()
        bundle = builder.build(catalog)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outputs = {
                SpecimenBetaFrontierBundleFormat.JSON: root / "bundle.json",
                SpecimenBetaFrontierBundleFormat.CSV: root / "bundle.csv",
                SpecimenBetaFrontierBundleFormat.MARKDOWN: root / "bundle.md",
            }
            for format_value, path in outputs.items():
                builder.write(bundle, path, format=format_value)
                self.assertTrue(path.is_file())
                self.assertTrue(path.read_text(encoding="utf-8"))
            self.assertEqual(
                json.loads(
                    outputs[SpecimenBetaFrontierBundleFormat.JSON].read_text(encoding="utf-8")
                )["entry_count"],
                12,
            )
            self.assertIn(
                "entry_id,record_id",
                outputs[SpecimenBetaFrontierBundleFormat.CSV].read_text(encoding="utf-8"),
            )
            self.assertIn(
                "Specimen beta frontier evidence bundle",
                outputs[SpecimenBetaFrontierBundleFormat.MARKDOWN].read_text(encoding="utf-8"),
            )

    def test_bundle_verify_detects_address_drift(self) -> None:
        catalog = SpecimenBetaFrontierFixtureCatalog.from_file(FIXTURE)
        builder = SpecimenBetaFrontierEvidenceBundleBuilder()
        bundle = builder.build(catalog)
        object.__setattr__(bundle, "content_address", "sha256:incorrect")
        self.assertFalse(builder.verify(bundle))

    def test_bundle_refuses_review_when_not_opted_in(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["positives"][0]["expected_counts"]["somatic"] = 0
        catalog = SpecimenBetaFrontierFixtureCatalog.from_mapping(payload)
        with self.assertRaises(ValidationError):
            SpecimenBetaFrontierEvidenceBundleBuilder().build(catalog)

    def test_bundle_review_opt_in_preserves_review_state(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["positives"][0]["expected_counts"]["somatic"] = 0
        catalog = SpecimenBetaFrontierFixtureCatalog.from_mapping(payload)
        bundle = SpecimenBetaFrontierEvidenceBundleBuilder().build(catalog, allow_review=True)
        self.assertEqual(bundle.state, "review")
        self.assertEqual(bundle.entry_count, 12)


if __name__ == "__main__":
    unittest.main()
