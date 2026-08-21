"""Public aggregate boundary tests for Domain 03 C01-C04."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.specimen_frontier_public_data import (
    SPECIMEN_FRONTIER_CONTEXT_DIMENSION_FLOOR,
    SPECIMEN_FRONTIER_CONTROL_FLOOR,
    SPECIMEN_FRONTIER_OPERATION_FLOOR,
    SpecimenFrontierFixtureCatalog,
    SpecimenFrontierOperation,
    audit_specimen_frontier_fixture,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "specimen-frontier-public-aggregate.json"


class SpecimenFrontierPublicDataTests(unittest.TestCase):
    def test_canonical_catalog_meets_identity_scope_and_operation_floors(self) -> None:
        catalog = SpecimenFrontierFixtureCatalog.from_file(FIXTURE)
        report = audit_specimen_frontier_fixture(catalog)
        self.assertTrue(report.accepted)
        self.assertEqual(report.positive_count, SPECIMEN_FRONTIER_OPERATION_FLOOR)
        self.assertEqual(report.control_count, SPECIMEN_FRONTIER_CONTROL_FLOOR)
        self.assertEqual(
            set(report.operation_ids),
            {operation.value for operation in SpecimenFrontierOperation},
        )
        self.assertEqual(len(report.source_ids), 4)
        self.assertEqual(len(report.record_ids), 12)
        self.assertTrue(catalog.content_address.startswith("sha256:"))

    def test_context_is_exactly_six_ordered_dimensions(self) -> None:
        catalog = SpecimenFrontierFixtureCatalog.from_file(FIXTURE)
        self.assertEqual(
            len(catalog.context_key.split("|")),
            SPECIMEN_FRONTIER_CONTEXT_DIMENSION_FLOOR,
        )
        self.assertTrue(
            all(
                record.context_key == catalog.context_key
                for record in catalog.positives + catalog.controls
            )
        )

    def test_from_mapping_round_trips_without_embedded_raw_addresses(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        catalog = SpecimenFrontierFixtureCatalog.from_mapping(payload)
        self.assertEqual(catalog.fixture_id, "specimen-frontier-public-aggregate-2026-08-21")
        self.assertEqual(catalog.source_ids, tuple(sorted(catalog.source_ids)))
        self.assertEqual(catalog.record_ids, tuple(sorted(catalog.record_ids)))
        self.assertTrue(
            all(
                record.content_address.startswith("sha256:")
                for record in catalog.positives + catalog.controls
            )
        )

    def test_context_drift_is_rejected_by_audit(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["controls"][0]["context_key"] = (
            "GRCh38|diffuse_glioma|adult|other|tumor_core|pre_treatment"
        )
        catalog = SpecimenFrontierFixtureCatalog.from_mapping(payload)
        report = audit_specimen_frontier_fixture(catalog)
        self.assertFalse(report.accepted)
        self.assertIn("context_mismatch", report.issue_codes)

    def test_sensitive_aggregate_payload_is_rejected(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["positives"][0]["payload"]["records"][0]["medical_record_number"] = "x"
        catalog = SpecimenFrontierFixtureCatalog.from_mapping(payload)
        report = audit_specimen_frontier_fixture(catalog)
        self.assertIn("sensitive_record_payload", report.issue_codes)
        self.assertFalse(report.accepted)

    def test_duplicate_source_and_record_ids_are_visible(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["sources"].append(copy.deepcopy(payload["sources"][0]))
        payload["controls"][0]["record_id"] = payload["positives"][0]["record_id"]
        catalog = SpecimenFrontierFixtureCatalog.from_mapping(payload)
        report = audit_specimen_frontier_fixture(catalog)
        self.assertIn("duplicate_source_id", report.issue_codes)
        self.assertIn("duplicate_record_id", report.issue_codes)

    def test_undeclared_source_and_bad_record_address_are_rejected(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["positives"][0]["source_id"] = "not-declared"
        payload["positives"][0]["content_address"] = "sha256:bad"
        catalog = SpecimenFrontierFixtureCatalog.from_mapping(payload)
        report = audit_specimen_frontier_fixture(catalog)
        self.assertIn("undeclared_source", report.issue_codes)
        self.assertIn("record_address_mismatch", report.issue_codes)

    def test_non_aggregate_source_cannot_be_constructed(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["sources"][0]["patient_level"] = True
        with self.assertRaises(ValidationError):
            SpecimenFrontierFixtureCatalog.from_mapping(payload)

    def test_file_errors_are_reported_as_validation_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaises(ValidationError):
                SpecimenFrontierFixtureCatalog.from_file(path)


if __name__ == "__main__":
    unittest.main()
