"""Data-boundary tests for the Domain 02 public aggregate fixture."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.structural_public_data import (
    STRUCTURAL_FIXTURE_SCHEMA_VERSION,
    StructuralFixtureCatalog,
    StructuralFixtureState,
    audit_structural_fixture,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "examples" / "structural-public-aggregate.json"
FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
CONTEXT = FIXTURE["context_key"]


class StructuralPublicDataTests(unittest.TestCase):
    def test_fixture_has_expected_schema_scope_and_floors(self) -> None:
        catalog = StructuralFixtureCatalog.from_mapping(FIXTURE)
        report = audit_structural_fixture(catalog)
        self.assertEqual(catalog.schema_version, STRUCTURAL_FIXTURE_SCHEMA_VERSION)
        self.assertEqual(report.state, StructuralFixtureState.ACCEPTED)
        self.assertTrue(report.accepted)
        self.assertEqual(report.positive_count, 4)
        self.assertEqual(report.control_count, 8)
        self.assertEqual(
            set(report.operation_ids),
            {"reconstruction", "consensus", "complex_resolution", "copy_number"},
        )
        self.assertEqual(len(report.source_ids), 4)
        self.assertRegex(report.content_address, r"^sha256:[0-9a-f]{64}$")

    def test_source_receipts_are_public_and_non_patient(self) -> None:
        catalog = StructuralFixtureCatalog.from_file(FIXTURE_PATH)
        self.assertTrue(all(source.url.startswith("https://") for source in catalog.sources))
        self.assertTrue(all(not source.patient_level for source in catalog.sources))
        self.assertTrue(all("public" in source.data_scope for source in catalog.sources))
        self.assertTrue(all("aggregate" in source.data_scope for source in catalog.sources))

    def test_record_context_and_sources_match_catalog(self) -> None:
        catalog = StructuralFixtureCatalog.from_mapping(FIXTURE)
        source_ids = set(catalog.source_ids)
        for record in catalog.positives + catalog.controls:
            self.assertEqual(record.context_key, CONTEXT)
            self.assertIn(record.source_id, source_ids)
            self.assertTrue(record.payload)

    def test_duplicate_record_identity_is_rejected_by_audit(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw["controls"][0]["record_id"] = raw["positives"][0]["record_id"]
        catalog = StructuralFixtureCatalog.from_mapping(raw)
        report = audit_structural_fixture(catalog)
        self.assertEqual(report.state, StructuralFixtureState.REVIEW)
        self.assertIn("duplicate_record_id", report.issue_codes)

    def test_duplicate_source_identity_is_rejected_by_audit(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw["sources"][1]["source_id"] = raw["sources"][0]["source_id"]
        catalog = StructuralFixtureCatalog.from_mapping(raw)
        report = audit_structural_fixture(catalog)
        self.assertIn("duplicate_source_id", report.issue_codes)

    def test_context_drift_is_rejected_by_audit(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw["positives"][0]["context_key"] = CONTEXT.replace("GRCh38", "GRCh37")
        catalog = StructuralFixtureCatalog.from_mapping(raw)
        report = audit_structural_fixture(catalog)
        self.assertIn("record_context_mismatch", report.issue_codes)

    def test_missing_source_receipt_is_rejected_by_audit(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw["controls"][0]["source_id"] = "missing-source"
        catalog = StructuralFixtureCatalog.from_mapping(raw)
        report = audit_structural_fixture(catalog)
        self.assertIn("record_source_missing", report.issue_codes)

    def test_sensitive_payload_path_is_rejected_without_returning_value(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw["positives"][0]["payload"]["subject_id"] = "private-marker"
        catalog = StructuralFixtureCatalog.from_mapping(raw)
        report = audit_structural_fixture(catalog)
        self.assertIn("sensitive_payload_path", report.issue_codes)
        self.assertNotIn("private-marker", str(report.to_dict()))

    def test_patient_level_source_cannot_be_constructed(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw["sources"][0]["patient_level"] = True
        with self.assertRaises(ValidationError):
            StructuralFixtureCatalog.from_mapping(raw)

    def test_schema_version_and_url_are_explicit_contracts(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw["schema_version"] = "structural-evidence-old"
        with self.assertRaises(ValidationError):
            StructuralFixtureCatalog.from_mapping(raw)
        raw = copy.deepcopy(FIXTURE)
        raw["sources"][0]["url"] = "dbvar://private"
        with self.assertRaises(ValidationError):
            StructuralFixtureCatalog.from_mapping(raw)

    def test_record_arrays_require_objects(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw["positives"] = ["not-an-object"]
        with self.assertRaises(ValidationError):
            StructuralFixtureCatalog.from_mapping(raw)

    def test_catalog_content_address_changes_when_scope_changes(self) -> None:
        first = StructuralFixtureCatalog.from_mapping(FIXTURE)
        raw = copy.deepcopy(FIXTURE)
        raw["notes"].append("new scope note")
        second = StructuralFixtureCatalog.from_mapping(raw)
        self.assertNotEqual(first.content_address, second.content_address)

    def test_records_preserve_expected_issue_codes_and_counts(self) -> None:
        catalog = StructuralFixtureCatalog.from_file(FIXTURE_PATH)
        missing_mate = next(
            record for record in catalog.controls if record.record_id == "control-reconstruction-missing-mate"
        )
        self.assertEqual(missing_mate.required_issue_codes, ("missing_mate_id",))
        self.assertEqual(missing_mate.expected_counts["errors"], 1)


if __name__ == "__main__":
    unittest.main()
