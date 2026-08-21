"""Public-data boundary tests for Domain 02 C05-C08."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.structural_beta_public_data import (
    STRUCTURAL_BETA_CONTROL_FLOOR,
    STRUCTURAL_BETA_FIXTURE_SCHEMA_VERSION,
    STRUCTURAL_BETA_OPERATION_FLOOR,
    StructuralBetaFixtureCatalog,
    StructuralBetaFixtureState,
    StructuralBetaOperation,
    StructuralBetaSourceReceipt,
    audit_structural_beta_fixture,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "structural-beta-public-aggregate.json"
RAW_FIXTURE = json.loads(FIXTURE.read_text(encoding="utf-8"))


class StructuralBetaPublicDataTests(unittest.TestCase):
    def test_fixture_parses_with_operation_and_evidence_floors(self) -> None:
        catalog = StructuralBetaFixtureCatalog.from_file(FIXTURE)
        audit = audit_structural_beta_fixture(catalog)
        self.assertEqual(catalog.schema_version, STRUCTURAL_BETA_FIXTURE_SCHEMA_VERSION)
        self.assertEqual(len(catalog.positives), STRUCTURAL_BETA_OPERATION_FLOOR)
        self.assertEqual(len(catalog.controls), STRUCTURAL_BETA_CONTROL_FLOOR)
        self.assertEqual(set(catalog.operation_ids), {item.value for item in StructuralBetaOperation})
        self.assertEqual(audit.state, StructuralBetaFixtureState.ACCEPTED)
        self.assertTrue(audit.accepted)
        self.assertEqual(audit.issue_codes, ())

    def test_source_ids_and_record_ids_are_deterministic(self) -> None:
        catalog = StructuralBetaFixtureCatalog.from_file(FIXTURE)
        self.assertEqual(catalog.source_ids, tuple(sorted(catalog.source_ids)))
        self.assertEqual(len(catalog.record_ids), len(set(catalog.record_ids)))
        self.assertRegex(catalog.content_address, r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(catalog.content_address, StructuralBetaFixtureCatalog.from_mapping(catalog.to_dict()).content_address)

    def test_patient_level_source_is_rejected_at_construction(self) -> None:
        with self.assertRaises(ValidationError):
            StructuralBetaSourceReceipt(
                source_id="restricted",
                title="Restricted source",
                url="https://example.org/source",
                version="1",
                license="restricted",
                data_scope="patient-level",
                patient_level=True,
            )

    def test_audit_detects_sensitive_payload_path(self) -> None:
        raw = copy.deepcopy(RAW_FIXTURE)
        raw["positives"][0]["payload"]["subject_id"] = "restricted"
        catalog = StructuralBetaFixtureCatalog.from_mapping(raw)
        report = audit_structural_beta_fixture(catalog)
        self.assertEqual(report.state, StructuralBetaFixtureState.REVIEW)
        self.assertIn("sensitive_payload_path", report.issue_codes)

    def test_audit_detects_duplicate_source_and_record_identity(self) -> None:
        raw = copy.deepcopy(RAW_FIXTURE)
        raw["sources"][1]["source_id"] = raw["sources"][0]["source_id"]
        raw["controls"][0]["record_id"] = raw["positives"][0]["record_id"]
        report = audit_structural_beta_fixture(StructuralBetaFixtureCatalog.from_mapping(raw))
        self.assertIn("duplicate_source_id", report.issue_codes)
        self.assertIn("duplicate_record_id", report.issue_codes)

    def test_audit_detects_record_context_and_source_drift(self) -> None:
        raw = copy.deepcopy(RAW_FIXTURE)
        raw["positives"][0]["context_key"] = "GRCh38|diffuse_glioma|adult|other|tumor_core|pre_treatment"
        raw["positives"][1]["source_id"] = "missing-source"
        report = audit_structural_beta_fixture(StructuralBetaFixtureCatalog.from_mapping(raw))
        self.assertIn("record_context_mismatch", report.issue_codes)
        self.assertIn("record_source_missing", report.issue_codes)

    def test_audit_detects_missing_operation_and_floor(self) -> None:
        raw = copy.deepcopy(RAW_FIXTURE)
        raw["positives"] = raw["positives"][:2]
        raw["controls"] = raw["controls"][:1]
        raw["positives"][0]["operation"] = "focal_amplification"
        raw["positives"][1]["operation"] = "focal_amplification"
        report = audit_structural_beta_fixture(StructuralBetaFixtureCatalog.from_mapping(raw))
        self.assertIn("positive_floor", report.issue_codes)
        self.assertIn("control_floor", report.issue_codes)
        self.assertIn("operation_floor", report.issue_codes)

    def test_loader_rejects_invalid_json_and_missing_file(self) -> None:
        with self.assertRaises(ValidationError):
            StructuralBetaFixtureCatalog.from_file(ROOT / "examples" / "missing-beta-fixture.json")
        with self.assertRaises(ValidationError):
            StructuralBetaFixtureCatalog.from_mapping({"schema_version": "wrong"})

    def test_source_receipt_requires_explicit_web_url(self) -> None:
        with self.assertRaises(ValidationError):
            StructuralBetaSourceReceipt(
                source_id="source",
                title="Source",
                url="local/path",
                version="1",
                license="public",
                data_scope="public aggregate",
            )

    def test_all_fixture_payloads_are_mapping_objects(self) -> None:
        catalog = StructuralBetaFixtureCatalog.from_file(FIXTURE)
        self.assertTrue(all(isinstance(record.payload, dict) for record in catalog.positives + catalog.controls))
        self.assertTrue(all(record.context_key == catalog.context_key for record in catalog.positives + catalog.controls))

    def test_notes_are_preserved_without_affecting_operation_identity(self) -> None:
        catalog = StructuralBetaFixtureCatalog.from_file(FIXTURE)
        self.assertGreaterEqual(len(catalog.notes), 3)
        self.assertIn("C05-C08", " ".join(catalog.notes))


if __name__ == "__main__":
    unittest.main()
