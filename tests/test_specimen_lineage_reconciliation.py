from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from glio_noncode.specimen_lineage_public_data import SpecimenLineageFixtureCatalog
from glio_noncode.specimen_lineage_reconciliation import (
    audit_specimen_lineage_receipt_index,
    build_specimen_lineage_receipt_index,
)

FIXTURE = Path("examples/specimen-lineage-public-aggregate.json")


class SpecimenLineageReconciliationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = SpecimenLineageFixtureCatalog.from_file(FIXTURE)

    def test_index_contains_one_entry_per_fixture_record(self) -> None:
        index = build_specimen_lineage_receipt_index(self.catalog)
        self.assertEqual(len(index.entries), len(self.catalog.records))
        self.assertEqual(set(index.record_ids), set(self.catalog.record_ids))
        self.assertEqual(
            set(index.operation_ids),
            {"region_lineage", "longitudinal_linking", "phase_mapping", "treatment_context"},
        )

    def test_index_addresses_records_and_results(self) -> None:
        index = build_specimen_lineage_receipt_index(self.catalog)
        self.assertTrue(index.content_address.startswith("sha256:"))
        self.assertTrue(all(entry.record_address.startswith("sha256:") for entry in index.entries))
        self.assertTrue(all(entry.result_address.startswith("sha256:") for entry in index.entries))
        self.assertTrue(all(entry.content_address.startswith("sha256:") for entry in index.entries))

    def test_reconciliation_passes_with_sixteen_checks(self) -> None:
        index = build_specimen_lineage_receipt_index(self.catalog)
        report = audit_specimen_lineage_receipt_index(self.catalog, index)
        self.assertTrue(report.passed)
        self.assertEqual(len(report.checks), 16)
        self.assertEqual(report.failed_check_ids, ())
        self.assertTrue(report.content_address.startswith("sha256:"))

    def test_reconciliation_is_deterministic(self) -> None:
        first = build_specimen_lineage_receipt_index(self.catalog)
        second = build_specimen_lineage_receipt_index(self.catalog)
        self.assertEqual(first.content_address, second.content_address)
        first_report = audit_specimen_lineage_receipt_index(self.catalog, first)
        second_report = audit_specimen_lineage_receipt_index(self.catalog, second)
        self.assertEqual(first_report.content_address, second_report.content_address)

    def test_index_projection_is_sanitized(self) -> None:
        index = build_specimen_lineage_receipt_index(self.catalog)
        serialized = json.dumps(index.to_dict(), sort_keys=True)
        self.assertNotIn('"payload"', serialized)
        self.assertNotIn('"records"', serialized)
        self.assertNotIn('"subject_id"', serialized)
        self.assertNotIn('"patient_id"', serialized)

    def test_reconciliation_detects_result_address_drift(self) -> None:
        index = build_specimen_lineage_receipt_index(self.catalog)
        entry = replace(index.entries[0], result_address="sha256:drifted")
        mutated = replace(index, entries=(entry,) + index.entries[1:])
        report = audit_specimen_lineage_receipt_index(self.catalog, mutated)
        self.assertFalse(report.passed)
        self.assertIn("result-addresses", report.failed_check_ids)

    def test_reconciliation_detects_context_drift(self) -> None:
        index = build_specimen_lineage_receipt_index(self.catalog)
        entry = replace(index.entries[0], context_key="GRCh38|drift|adult|drift|drift|drift")
        mutated = replace(index, entries=(entry,) + index.entries[1:])
        report = audit_specimen_lineage_receipt_index(self.catalog, mutated)
        self.assertFalse(report.passed)
        self.assertIn("context-consistency", report.failed_check_ids)

    def test_reconciliation_detects_duplicate_record_identity(self) -> None:
        index = build_specimen_lineage_receipt_index(self.catalog)
        entry = replace(index.entries[1], record_id=index.entries[0].record_id)
        mutated = replace(index, entries=(index.entries[0], entry) + index.entries[2:])
        report = audit_specimen_lineage_receipt_index(self.catalog, mutated)
        self.assertFalse(report.passed)
        self.assertIn("record-uniqueness", report.failed_check_ids)

    def test_reconciliation_detects_missing_record(self) -> None:
        index = build_specimen_lineage_receipt_index(self.catalog)
        mutated = replace(index, entries=index.entries[:-1])
        report = audit_specimen_lineage_receipt_index(self.catalog, mutated)
        self.assertFalse(report.passed)
        self.assertIn("entry-floor", report.failed_check_ids)

    def test_reconciliation_detects_entry_address_drift(self) -> None:
        index = build_specimen_lineage_receipt_index(self.catalog)
        entry = replace(index.entries[0], content_address="sha256:drifted")
        mutated = replace(index, entries=(entry,) + index.entries[1:])
        report = audit_specimen_lineage_receipt_index(self.catalog, mutated)
        self.assertFalse(report.passed)
        self.assertIn("entry-addresses", report.failed_check_ids)


if __name__ == "__main__":
    unittest.main()
