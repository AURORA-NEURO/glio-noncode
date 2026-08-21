"""Public aggregate catalog tests for Domain 02 C13-C16."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.structural_frontier_public_data import (
    STRUCTURAL_FRONTIER_CONTROL_FLOOR,
    STRUCTURAL_FRONTIER_FIXTURE_SCHEMA_VERSION,
    STRUCTURAL_FRONTIER_OPERATION_FLOOR,
    StructuralFrontierFixtureCatalog,
    StructuralFrontierFixtureState,
    StructuralFrontierOperation,
    audit_structural_frontier_fixture,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "structural-frontier-public-aggregate.json"
CONTEXT = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"


def _raw() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class StructuralFrontierPublicDataTests(unittest.TestCase):
    def test_canonical_catalog_has_exact_scope_and_floors(self) -> None:
        catalog = StructuralFrontierFixtureCatalog.from_file(FIXTURE)
        self.assertEqual(catalog.schema_version, STRUCTURAL_FRONTIER_FIXTURE_SCHEMA_VERSION)
        self.assertEqual(catalog.context_key, CONTEXT)
        self.assertFalse(catalog.patient_level)
        self.assertEqual(len(catalog.sources), 4)
        self.assertEqual(len(catalog.positives), STRUCTURAL_FRONTIER_OPERATION_FLOOR)
        self.assertEqual(len(catalog.controls), STRUCTURAL_FRONTIER_CONTROL_FLOOR)
        self.assertEqual(set(catalog.operation_ids), {item.value for item in StructuralFrontierOperation})

    def test_catalog_record_identity_and_sources_are_deterministic(self) -> None:
        first = StructuralFrontierFixtureCatalog.from_file(FIXTURE)
        second = StructuralFrontierFixtureCatalog.from_file(FIXTURE)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.record_ids, second.record_ids)
        self.assertEqual(first.source_ids, tuple(sorted(first.source_ids)))
        self.assertEqual(len(first.record_ids), len(set(first.record_ids)))
        self.assertEqual(len(first.source_ids), len(set(first.source_ids)))

    def test_source_receipts_are_public_aggregate_and_addressed_catalog_is_stable(self) -> None:
        catalog = StructuralFrontierFixtureCatalog.from_file(FIXTURE)
        for source in catalog.sources:
            self.assertTrue(source.url.startswith("https://"))
            self.assertTrue(source.license)
            self.assertTrue(source.data_scope)
            self.assertFalse(source.patient_level)
        self.assertRegex(catalog.content_address, r"^sha256:[0-9a-f]{64}$")

    def test_audit_accepts_canonical_catalog(self) -> None:
        report = audit_structural_frontier_fixture(StructuralFrontierFixtureCatalog.from_file(FIXTURE))
        self.assertEqual(report.state, StructuralFrontierFixtureState.ACCEPTED)
        self.assertTrue(report.accepted)
        self.assertEqual(report.issue_codes, ())
        self.assertEqual(report.positive_count, 4)
        self.assertEqual(report.control_count, 8)
        self.assertEqual(report.operation_ids, tuple(sorted(item.value for item in StructuralFrontierOperation)))

    def test_duplicate_source_id_is_audited(self) -> None:
        raw = _raw()
        raw["sources"][1]["source_id"] = raw["sources"][0]["source_id"]
        catalog = StructuralFrontierFixtureCatalog.from_mapping(raw)
        report = audit_structural_frontier_fixture(catalog)
        self.assertFalse(report.accepted)
        self.assertIn("duplicate_source_id", report.issue_codes)

    def test_duplicate_record_id_is_audited(self) -> None:
        raw = _raw()
        raw["controls"][0]["record_id"] = raw["positives"][0]["record_id"]
        catalog = StructuralFrontierFixtureCatalog.from_mapping(raw)
        report = audit_structural_frontier_fixture(catalog)
        self.assertIn("duplicate_record_id", report.issue_codes)

    def test_context_drift_is_audited_without_normalization(self) -> None:
        raw = _raw()
        raw["controls"][0]["context_key"] = "GRCh37|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"
        catalog = StructuralFrontierFixtureCatalog.from_mapping(raw)
        report = audit_structural_frontier_fixture(catalog)
        self.assertIn("record_context_mismatch", report.issue_codes)
        self.assertEqual(catalog.controls[0].context_key.split("|", 1)[0], "GRCh37")

    def test_sensitive_payload_key_is_rejected_at_audit(self) -> None:
        raw = _raw()
        raw["positives"][0]["payload"]["records"][0]["subject_id"] = "restricted"
        catalog = StructuralFrontierFixtureCatalog.from_mapping(raw)
        report = audit_structural_frontier_fixture(catalog)
        self.assertIn("sensitive_payload_key", report.issue_codes)

    def test_missing_source_reference_is_audited(self) -> None:
        raw = _raw()
        raw["positives"][0]["source_id"] = "unknown-public-source"
        catalog = StructuralFrontierFixtureCatalog.from_mapping(raw)
        report = audit_structural_frontier_fixture(catalog)
        self.assertIn("record_source_missing", report.issue_codes)

    def test_invalid_schema_is_rejected(self) -> None:
        raw = _raw()
        raw["schema_version"] = "old-schema"
        with self.assertRaisesRegex(ValidationError, "unsupported"):
            StructuralFrontierFixtureCatalog.from_mapping(raw)

    def test_missing_sources_are_rejected(self) -> None:
        raw = _raw()
        raw["sources"] = []
        with self.assertRaisesRegex(ValidationError, "requires source receipts"):
            StructuralFrontierFixtureCatalog.from_mapping(raw)

    def test_invalid_source_url_is_rejected(self) -> None:
        raw = _raw()
        raw["sources"][0]["url"] = "ftp://example.test/source"
        with self.assertRaisesRegex(ValidationError, "web scheme"):
            StructuralFrontierFixtureCatalog.from_mapping(raw)

    def test_patient_level_source_is_rejected(self) -> None:
        raw = _raw()
        raw["sources"][0]["patient_level"] = True
        with self.assertRaisesRegex(ValidationError, "must be aggregate"):
            StructuralFrontierFixtureCatalog.from_mapping(raw)

    def test_invalid_record_payload_and_context_are_rejected(self) -> None:
        raw = _raw()
        raw["positives"][0]["payload"] = {}
        with self.assertRaisesRegex(ValidationError, "payload must not be empty"):
            StructuralFrontierFixtureCatalog.from_mapping(raw)
        raw = _raw()
        raw["positives"][0]["context_key"] = "GRCh38|too|short"
        with self.assertRaisesRegex(ValidationError, "requires six fields"):
            StructuralFrontierFixtureCatalog.from_mapping(raw)

    def test_required_issue_codes_and_counts_are_typed(self) -> None:
        catalog = StructuralFrontierFixtureCatalog.from_file(FIXTURE)
        control = next(item for item in catalog.controls if item.record_id == "control-tandem-invalid-motif")
        self.assertEqual(control.required_issue_codes, ("invalid_motif",))
        self.assertEqual(control.expected_counts["observations"], 1)
        self.assertEqual(control.expected_state, StructuralFrontierFixtureState.REVIEW)

    def test_negative_expected_count_is_rejected(self) -> None:
        raw = _raw()
        raw["positives"][0]["expected_counts"]["observations"] = -1
        with self.assertRaisesRegex(ValidationError, "expected counts"):
            StructuralFrontierFixtureCatalog.from_mapping(raw)

    def test_duplicate_required_issue_code_is_rejected(self) -> None:
        raw = _raw()
        raw["controls"][0]["required_issue_codes"] = ["invalid_motif", "invalid_motif"]
        with self.assertRaisesRegex(ValidationError, "issue codes must be unique"):
            StructuralFrontierFixtureCatalog.from_mapping(raw)

    def test_mapping_round_trip_preserves_catalog_address(self) -> None:
        catalog = StructuralFrontierFixtureCatalog.from_file(FIXTURE)
        round_trip = StructuralFrontierFixtureCatalog.from_mapping(copy.deepcopy(catalog.to_dict()))
        self.assertEqual(catalog.content_address, round_trip.content_address)
        self.assertEqual(catalog.source_ids, round_trip.source_ids)
        self.assertEqual(catalog.record_ids, round_trip.record_ids)


if __name__ == "__main__":
    unittest.main()
