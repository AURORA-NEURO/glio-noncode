from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from glio_noncode.specimen_preanalytic_bundle import (
    SpecimenPreanalyticBundleFormat,
    SpecimenPreanalyticEvidenceBundleBuilder,
)
from glio_noncode.specimen_preanalytic_lineage import build_specimen_preanalytic_lineage
from glio_noncode.specimen_preanalytic_public_data import SpecimenPreanalyticFixtureCatalog
from glio_noncode.specimen_preanalytic_quality_gate import (
    evaluate_specimen_preanalytic_quality_gate,
)
from glio_noncode.specimen_preanalytic_reconciliation import (
    audit_specimen_preanalytic_receipt_index,
    build_specimen_preanalytic_receipt_index,
)

FIXTURE = Path("examples/specimen-preanalytic-public-aggregate.json")


class SpecimenPreanalyticQualityBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = SpecimenPreanalyticFixtureCatalog.from_file(FIXTURE)
        self.builder = SpecimenPreanalyticEvidenceBundleBuilder()

    def test_quality_gate_passes_with_twenty_five_checks(self) -> None:
        report = evaluate_specimen_preanalytic_quality_gate(self.catalog)
        self.assertTrue(report.passed)
        self.assertEqual(len(report.checks), 25)
        self.assertEqual(report.failed_check_ids, ())

    def test_quality_gate_is_deterministic(self) -> None:
        first = evaluate_specimen_preanalytic_quality_gate(self.catalog)
        second = evaluate_specimen_preanalytic_quality_gate(self.catalog)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.bundle_address, second.bundle_address)

    def test_bundle_builds_and_verifies(self) -> None:
        bundle = self.builder.build(self.catalog)
        self.assertEqual(bundle.state, "accepted")
        self.assertEqual(len(bundle.entries), 12)
        self.assertTrue(self.builder.verify(bundle))
        self.assertTrue(bundle.content_address.startswith("sha256:"))

    def test_bundle_supports_json_csv_and_markdown(self) -> None:
        bundle = self.builder.build(self.catalog)
        json_text = self.builder.render(bundle, SpecimenPreanalyticBundleFormat.JSON)
        csv_text = self.builder.render(bundle, SpecimenPreanalyticBundleFormat.CSV)
        markdown = self.builder.render(bundle, SpecimenPreanalyticBundleFormat.MARKDOWN)
        self.assertEqual(len(json.loads(json_text)["entries"]), 12)
        self.assertEqual(len(csv_text.splitlines()), 13)
        self.assertIn("# specimen-preanalytic-c13-c16", markdown)
        self.assertIn("positive-preanalytic-quality", markdown)

    def test_bundle_verification_detects_entry_address_drift(self) -> None:
        bundle = self.builder.build(self.catalog)
        entry = replace(bundle.entries[0], entry_address="sha256:drift")
        mutated = replace(bundle, entries=(entry,) + bundle.entries[1:])
        self.assertFalse(self.builder.verify(mutated))

    def test_reconciliation_passes_and_detects_result_drift(self) -> None:
        index = build_specimen_preanalytic_receipt_index(self.catalog)
        report = audit_specimen_preanalytic_receipt_index(self.catalog, index)
        self.assertTrue(report.passed)
        self.assertEqual(len(report.checks), 16)
        entry = replace(index.entries[0], result_address="sha256:drift")
        mutated = replace(index, entries=(entry,) + index.entries[1:])
        drift = audit_specimen_preanalytic_receipt_index(self.catalog, mutated)
        self.assertFalse(drift.passed)
        self.assertIn("result-addresses", drift.failed_check_ids)

    def test_lineage_address_is_retained_by_quality_components(self) -> None:
        graph = build_specimen_preanalytic_lineage(self.catalog)
        report = evaluate_specimen_preanalytic_quality_gate(self.catalog)
        self.assertEqual(report.lineage_address, graph.content_address)


if __name__ == "__main__":
    unittest.main()
