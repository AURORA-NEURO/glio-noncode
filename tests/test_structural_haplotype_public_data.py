"""Public aggregate fixture tests for Domain 02 C09-C12."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.structural_haplotype_public_data import (
    STRUCTURAL_HAPLOTYPE_CONTROL_FLOOR,
    STRUCTURAL_HAPLOTYPE_OPERATION_FLOOR,
    StructuralHaplotypeFixtureCatalog,
    StructuralHaplotypeFixtureState,
    StructuralHaplotypeOperation,
    audit_structural_haplotype_fixture,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "structural-haplotype-public-aggregate.json"


class StructuralHaplotypePublicDataTests(unittest.TestCase):
    def test_canonical_fixture_has_exact_scope_and_operation_floors(self) -> None:
        catalog = StructuralHaplotypeFixtureCatalog.from_file(FIXTURE)
        audit = audit_structural_haplotype_fixture(catalog)
        self.assertTrue(audit.accepted)
        self.assertEqual(audit.state, StructuralHaplotypeFixtureState.ACCEPTED)
        self.assertEqual(len(catalog.positives), STRUCTURAL_HAPLOTYPE_OPERATION_FLOOR)
        self.assertEqual(len(catalog.controls), STRUCTURAL_HAPLOTYPE_CONTROL_FLOOR)
        self.assertEqual(set(catalog.operation_ids), {item.value for item in StructuralHaplotypeOperation})
        self.assertEqual(catalog.context_key.count("|"), 5)
        self.assertFalse(catalog.patient_level)
        self.assertEqual(len(catalog.sources), 4)

    def test_catalog_identity_is_deterministic(self) -> None:
        first = StructuralHaplotypeFixtureCatalog.from_file(FIXTURE)
        second = StructuralHaplotypeFixtureCatalog.from_file(FIXTURE)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertRegex(first.content_address, r"^sha256:[0-9a-f]{64}$")

    def test_source_ids_are_sorted_and_source_receipts_are_public(self) -> None:
        catalog = StructuralHaplotypeFixtureCatalog.from_file(FIXTURE)
        self.assertEqual(catalog.source_ids, tuple(sorted(catalog.source_ids)))
        self.assertTrue(all(source.url.startswith("https://") for source in catalog.sources))
        self.assertTrue(all("public" in source.data_scope or "aggregate" in source.data_scope for source in catalog.sources))
        self.assertTrue(all(source.patient_level is False for source in catalog.sources))

    def test_audit_rejects_sensitive_payload_keys(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["positives"][0]["payload"]["records"][0]["subject_id"] = "restricted"
        catalog = StructuralHaplotypeFixtureCatalog.from_mapping(raw)
        audit = audit_structural_haplotype_fixture(catalog)
        self.assertEqual(audit.state, StructuralHaplotypeFixtureState.REVIEW)
        self.assertIn("sensitive_payload_key", audit.issue_codes)

    def test_audit_rejects_duplicate_source_identity(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["sources"].append(copy.deepcopy(raw["sources"][0]))
        catalog = StructuralHaplotypeFixtureCatalog.from_mapping(raw)
        audit = audit_structural_haplotype_fixture(catalog)
        self.assertIn("duplicate_source_id", audit.issue_codes)

    def test_audit_rejects_duplicate_record_identity(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["controls"].append(copy.deepcopy(raw["controls"][0]))
        catalog = StructuralHaplotypeFixtureCatalog.from_mapping(raw)
        audit = audit_structural_haplotype_fixture(catalog)
        self.assertIn("duplicate_record_id", audit.issue_codes)

    def test_audit_rejects_record_context_drift(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["positives"][0]["context_key"] = "GRCh37|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"
        catalog = StructuralHaplotypeFixtureCatalog.from_mapping(raw)
        audit = audit_structural_haplotype_fixture(catalog)
        self.assertIn("record_context_mismatch", audit.issue_codes)

    def test_audit_rejects_record_without_source_receipt(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["controls"][0]["source_id"] = "missing-source"
        catalog = StructuralHaplotypeFixtureCatalog.from_mapping(raw)
        audit = audit_structural_haplotype_fixture(catalog)
        self.assertIn("record_source_missing", audit.issue_codes)

    def test_catalog_rejects_non_aggregate_flag(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["patient_level"] = True
        with self.assertRaisesRegex(ValidationError, "must be aggregate"):
            StructuralHaplotypeFixtureCatalog.from_mapping(raw)

    def test_catalog_rejects_wrong_schema_version(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["schema_version"] = "structural-haplotype-evidence-v0"
        with self.assertRaisesRegex(ValidationError, "unsupported"):
            StructuralHaplotypeFixtureCatalog.from_mapping(raw)

    def test_catalog_rejects_invalid_context_shape(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["context_key"] = "GRCh38|glioma"
        with self.assertRaisesRegex(ValidationError, "six fields"):
            StructuralHaplotypeFixtureCatalog.from_mapping(raw)

    def test_catalog_rejects_empty_record_payload(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["positives"][0]["payload"] = {}
        with self.assertRaisesRegex(ValidationError, "payload must not be empty"):
            StructuralHaplotypeFixtureCatalog.from_mapping(raw)

    def test_from_file_reports_missing_and_malformed_files(self) -> None:
        with self.assertRaisesRegex(ValidationError, "file not found"):
            StructuralHaplotypeFixtureCatalog.from_file(ROOT / "missing-structural-haplotype.json")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text("{not-json", encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "invalid"):
                StructuralHaplotypeFixtureCatalog.from_file(path)

    def test_source_receipt_rejects_non_web_url(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["sources"][0]["url"] = "ftp://example.org/source"
        with self.assertRaisesRegex(ValidationError, "web scheme"):
            StructuralHaplotypeFixtureCatalog.from_mapping(raw)


if __name__ == "__main__":
    unittest.main()
