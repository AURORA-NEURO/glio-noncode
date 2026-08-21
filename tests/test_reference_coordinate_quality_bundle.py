from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path

from glio_noncode.reference_coordinate_bundle import (
    ReferenceCoordinateBundleBuilder,
    ReferenceCoordinateBundleFormat,
)
from glio_noncode.reference_coordinate_public_data import ReferenceCoordinateFixtureCatalog
from glio_noncode.reference_coordinate_quality_gate import (
    evaluate_reference_coordinate_quality_gate,
)
from glio_noncode.reference_coordinate_reconciliation import reconcile_reference_coordinate_views

FIXTURE = Path(__file__).parents[1] / "examples" / "reference-coordinate-public-aggregate.json"


class ReferenceCoordinateQualityBundleTests(unittest.TestCase):
    def load(self) -> ReferenceCoordinateFixtureCatalog:
        return ReferenceCoordinateFixtureCatalog.from_file(FIXTURE)

    def test_quality_gate_passes_with_twenty_five_checks(self) -> None:
        report = evaluate_reference_coordinate_quality_gate(self.load())
        self.assertEqual(report.state, "accepted")
        self.assertTrue(report.passed)
        self.assertEqual(len(report.checks), 25)
        self.assertEqual(report.failed_check_ids, ())
        self.assertEqual(len(report.component_addresses), 10)

    def test_quality_gate_is_deterministic(self) -> None:
        catalog = self.load()
        first = evaluate_reference_coordinate_quality_gate(catalog)
        second = evaluate_reference_coordinate_quality_gate(catalog)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_verification_bundle_retains_positive_and_control_entries(self) -> None:
        catalog = self.load()
        builder = ReferenceCoordinateBundleBuilder()
        bundle = builder.build(catalog)
        verification = builder.verify(bundle, catalog)
        self.assertTrue(verification.passed)
        self.assertEqual(len(bundle.entries), 16)
        self.assertTrue(bundle.included_controls)
        self.assertFalse(bundle.published)
        self.assertEqual(bundle.state, "accepted")

    def test_accepted_only_bundle_publishes_four_positive_entries(self) -> None:
        catalog = self.load()
        builder = ReferenceCoordinateBundleBuilder()
        bundle = builder.build(catalog, accepted_only=True)
        self.assertTrue(bundle.published)
        self.assertFalse(bundle.included_controls)
        self.assertEqual(len(bundle.entries), 4)
        self.assertTrue(builder.verify(bundle, catalog).passed)

    def test_bundle_supports_json_csv_and_markdown(self) -> None:
        catalog = self.load()
        builder = ReferenceCoordinateBundleBuilder()
        for output_format, marker in (
            (ReferenceCoordinateBundleFormat.JSON, '"entries"'),
            (ReferenceCoordinateBundleFormat.CSV, "record_id,operation"),
            (ReferenceCoordinateBundleFormat.MARKDOWN, "| Record | Operation |"),
        ):
            bundle = builder.build(catalog, output_format=output_format)
            rendered = builder.render(bundle)
            self.assertIn(marker, rendered)
            self.assertNotIn("chain_text", rendered.lower())
            self.assertTrue(builder.verify(bundle, catalog).passed)

    def test_bundle_verification_detects_record_address_drift(self) -> None:
        catalog = self.load()
        builder = ReferenceCoordinateBundleBuilder()
        bundle = builder.build(catalog)
        entries = (replace(bundle.entries[0], record_address="sha256:drift"),) + bundle.entries[1:]
        mutated = replace(bundle, entries=entries)
        verification = builder.verify(mutated, catalog)
        self.assertFalse(verification.passed)
        self.assertEqual(verification.state, "review")
        self.assertTrue(
            any(
                check["check_id"] == "record-addresses" and not check["passed"]
                for check in verification.checks
            )
        )

    def test_reconciliation_passes_and_retains_graph_addresses(self) -> None:
        report = reconcile_reference_coordinate_views(self.load())
        self.assertTrue(report.passed)
        self.assertEqual(len(report.checks), 24)
        self.assertTrue(report.evaluation_address.startswith("sha256:"))
        self.assertTrue(report.bundle_address.startswith("sha256:"))
        self.assertTrue(report.lineage_address.startswith("sha256:"))

    def test_bundle_content_address_changes_with_format(self) -> None:
        catalog = self.load()
        builder = ReferenceCoordinateBundleBuilder()
        json_bundle = builder.build(catalog, output_format=ReferenceCoordinateBundleFormat.JSON)
        csv_bundle = builder.build(catalog, output_format=ReferenceCoordinateBundleFormat.CSV)
        self.assertNotEqual(json_bundle.content_address, csv_bundle.content_address)

    def test_review_controls_can_be_rendered_without_publication(self) -> None:
        catalog = self.load()
        builder = ReferenceCoordinateBundleBuilder()
        bundle = builder.build(catalog, allow_review=True)
        self.assertTrue(bundle.included_controls)
        self.assertFalse(bundle.published)
        self.assertIn("d04-c03-control-competing-segments", builder.render(bundle))


if __name__ == "__main__":
    unittest.main()
