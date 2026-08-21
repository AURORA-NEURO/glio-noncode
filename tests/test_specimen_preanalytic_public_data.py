from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.specimen_preanalytic_public_data import (
    EXPECTED_CONTEXT_KEY,
    SpecimenPreanalyticFixtureCatalog,
    audit_specimen_preanalytic_data,
)

FIXTURE = Path("examples/specimen-preanalytic-public-aggregate.json")


class SpecimenPreanalyticPublicDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = SpecimenPreanalyticFixtureCatalog.from_file(FIXTURE)

    def test_fixture_has_locked_release_shape(self) -> None:
        self.assertEqual(self.catalog.context_key, EXPECTED_CONTEXT_KEY)
        self.assertEqual(len(self.catalog.records), 12)
        self.assertEqual(len(self.catalog.positives), 4)
        self.assertEqual(len(self.catalog.controls), 8)
        self.assertEqual(
            set(self.catalog.operation_ids),
            {"preanalytic_quality", "assay_lineage", "identity_adjudication", "context_envelope"},
        )

    def test_data_audit_accepts_public_aggregate_fixture(self) -> None:
        report = audit_specimen_preanalytic_data(self.catalog)
        self.assertTrue(report.passed)
        self.assertEqual(len(report.checks), 23)
        self.assertEqual(report.failed_check_ids, ())

    def test_sources_are_public_and_addressed(self) -> None:
        self.assertEqual(len(self.catalog.source_receipts), 4)
        self.assertTrue(all(not source.patient_level for source in self.catalog.source_receipts))
        self.assertTrue(
            all(source.uri.startswith("https://") for source in self.catalog.source_receipts)
        )
        self.assertTrue(
            all(
                source.content_address.startswith("sha256:")
                for source in self.catalog.source_receipts
            )
        )

    def test_record_addresses_are_deterministic(self) -> None:
        first = SpecimenPreanalyticFixtureCatalog.from_file(FIXTURE)
        second = SpecimenPreanalyticFixtureCatalog.from_file(FIXTURE)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(
            tuple(record.content_address for record in first.records),
            tuple(record.content_address for record in second.records),
        )

    def test_context_drift_is_reviewed(self) -> None:
        mutated = replace(self.catalog, context_key="GRCh38|drift|adult|stem_like|core|untreated")
        report = audit_specimen_preanalytic_data(mutated)
        self.assertFalse(report.passed)
        self.assertIn("context-exact", report.failed_check_ids)

    def test_direct_identifier_payload_is_rejected(self) -> None:
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        raw["records"][0]["payload"]["patient_id"] = "forbidden"
        with self.assertRaises(ValidationError):
            SpecimenPreanalyticFixtureCatalog.from_mapping(raw)

    def test_patient_level_source_is_rejected(self) -> None:
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        raw["source_receipts"][0]["patient_level"] = True
        with self.assertRaises(ValidationError):
            SpecimenPreanalyticFixtureCatalog.from_mapping(raw)


if __name__ == "__main__":
    unittest.main()
