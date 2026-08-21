"""Data-boundary tests for the Domain 01 intake fixture."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.intake_public_data import (
    INTAKE_FIXTURE_SCHEMA_VERSION,
    IntakeDataState,
    IntakeFixtureCatalog,
    IntakeFixtureControl,
    IntakeFixtureRecord,
    IntakeRecordKind,
    IntakeSourceReceipt,
    audit_intake_fixture,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "examples" / "intake-public-aggregate.json"
FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
CONTEXT = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"


class IntakePublicDataTests(unittest.TestCase):
    def test_checked_in_fixture_is_accepted(self) -> None:
        report = audit_intake_fixture(FIXTURE_PATH)
        self.assertEqual(report.state, IntakeDataState.ACCEPTED)
        self.assertTrue(report.accepted)
        self.assertEqual(report.record_count, 4)
        self.assertEqual(report.control_count, 8)
        self.assertEqual(report.context_key, CONTEXT)
        self.assertEqual(report.issues, ())
        self.assertRegex(report.content_address, r"^sha256:[0-9a-f]{64}$")

    def test_catalog_indexes_records_controls_and_sources(self) -> None:
        catalog = IntakeFixtureCatalog.from_file(FIXTURE_PATH)
        self.assertEqual(catalog.fixture_id, "intake-public-aggregate-001")
        self.assertEqual(catalog.fixture_version, INTAKE_FIXTURE_SCHEMA_VERSION)
        self.assertEqual(catalog.context_key, CONTEXT)
        self.assertEqual(len(catalog.sources), 4)
        self.assertEqual(len(catalog.records), 4)
        self.assertEqual(len(catalog.controls), 8)
        self.assertIsNotNone(catalog.record("consent-clinvar-public-use"))
        self.assertIsNotNone(catalog.control("consent-withdrawn"))
        self.assertIsNone(catalog.record("unknown"))
        self.assertIsNone(catalog.control("unknown"))

    def test_context_has_exact_six_fields_in_declared_order(self) -> None:
        catalog = IntakeFixtureCatalog.from_fixture(FIXTURE)
        self.assertEqual(
            catalog.context_key.split("|"),
            [
                "GRCh38",
                "diffuse_glioma",
                "adult",
                "malignant_oligodendrocyte_like",
                "tumor_core",
                "pre_treatment",
            ],
        )
        for source in catalog.sources:
            self.assertEqual(source.context_key, CONTEXT)
        for record in catalog.records:
            self.assertEqual(record.context_key, CONTEXT)
        for control in catalog.controls:
            self.assertEqual(control.context_key, CONTEXT)

    def test_source_receipts_are_public_and_not_patient_level(self) -> None:
        catalog = IntakeFixtureCatalog.from_file(FIXTURE_PATH)
        self.assertEqual(
            {source.source_kind for source in catalog.sources},
            {"public_policy", "public_aggregate", "validation_control"},
        )
        for source in catalog.sources:
            self.assertTrue(source.source_url.startswith("https://"))
            self.assertTrue(source.public_aggregate)
            self.assertFalse(source.patient_level_data)

    def test_positive_kinds_cover_all_four_capabilities(self) -> None:
        catalog = IntakeFixtureCatalog.from_file(FIXTURE_PATH)
        self.assertEqual({record.kind for record in catalog.records}, set(IntakeRecordKind))
        self.assertEqual(
            {record.operation for record in catalog.records},
            {
                "attach-consent-policy",
                "quarantine-input-anomalies",
                "score-data-completeness",
                "export-intake-bundle",
            },
        )

    def test_control_as_record_preserves_negative_identity(self) -> None:
        control = IntakeFixtureCatalog.from_file(FIXTURE_PATH).control("consent-withdrawn")
        assert control is not None
        record = control.as_record()
        self.assertEqual(record.record_id, "negative:consent-withdrawn")
        self.assertEqual(record.kind, IntakeRecordKind.CONSENT)
        self.assertEqual(record.expected_state, "blocked")
        self.assertEqual(record.public_identifier, "control:withdrawn-policy")

    def test_duplicate_source_id_is_reported(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw["source_receipts"].append(copy.deepcopy(raw["source_receipts"][0]))
        report = IntakeFixtureCatalog.from_fixture(raw).audit()
        self.assertEqual(report.state, IntakeDataState.REVIEW)
        self.assertIn("nih-gds-policy", report.duplicate_source_ids)
        self.assertIn("duplicate_source_id", {issue.code for issue in report.issues})

    def test_duplicate_record_and_control_ids_are_reported(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw["records"].append(copy.deepcopy(raw["records"][0]))
        raw["negative_controls"].append(copy.deepcopy(raw["negative_controls"][0]))
        report = IntakeFixtureCatalog.from_fixture(raw).audit()
        self.assertIn("consent-clinvar-public-use", report.duplicate_record_ids)
        self.assertIn("consent-withdrawn", report.duplicate_control_ids)
        codes = {issue.code for issue in report.issues}
        self.assertIn("duplicate_record_id", codes)
        self.assertIn("duplicate_control_id", codes)

    def test_record_control_collision_is_reported(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw["negative_controls"][0]["control_id"] = raw["records"][0]["record_id"]
        report = IntakeFixtureCatalog.from_fixture(raw).audit()
        self.assertIn("record_control_id_collision", {issue.code for issue in report.issues})

    def test_context_and_unknown_source_are_reported_for_both_envelopes(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw["records"][0]["context_key"] = "GRCh37|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"
        raw["negative_controls"][0]["source_id"] = "unknown-public-source"
        report = IntakeFixtureCatalog.from_fixture(raw).audit()
        self.assertIn("consent-clinvar-public-use", report.context_mismatch_ids)
        self.assertIn("unknown-public-source", report.unknown_source_ids)
        codes = {issue.code for issue in report.issues}
        self.assertIn("record_context_mismatch", codes)
        self.assertIn("unknown_record_source", codes)

    def test_sensitive_payload_path_is_rejected_without_reading_value(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw["records"][0]["payload"]["private_note"] = "not-retained"
        report = IntakeFixtureCatalog.from_fixture(raw).audit()
        self.assertEqual(report.state, IntakeDataState.REVIEW)
        self.assertTrue(any(path.endswith("private_note") for path in report.sensitive_paths))
        self.assertIn("sensitive_record_path", {issue.code for issue in report.issues})

    def test_patient_scope_and_missing_boundary_are_rejected(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw["provenance"]["patient_level_data"] = True
        raw["provenance"].pop("evidence_boundary")
        report = IntakeFixtureCatalog.from_fixture(raw).audit()
        codes = {issue.code for issue in report.issues}
        self.assertIn("fixture_patient_scope", codes)
        self.assertIn("missing_evidence_boundary", codes)

    def test_declared_counts_and_scope_are_checked(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw["provenance"]["data_scope"] = "private"
        raw["provenance"]["expected_record_count"] = 99
        raw["provenance"]["expected_control_count"] = 99
        report = IntakeFixtureCatalog.from_fixture(raw).audit()
        codes = {issue.code for issue in report.issues}
        self.assertIn("invalid_data_scope", codes)
        self.assertIn("record_count_mismatch", codes)
        self.assertIn("control_count_mismatch", codes)

    def test_control_expected_acceptance_is_invalid(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw["negative_controls"][0]["expected_state"] = "accepted"
        report = IntakeFixtureCatalog.from_fixture(raw).audit()
        self.assertIn("control_expected_acceptance", {issue.code for issue in report.issues})

    def test_invalid_source_receipt_contracts_raise(self) -> None:
        with self.assertRaises(ValidationError):
            IntakeSourceReceipt(
                "source",
                "http://not-secure.example",
                "v1",
                CONTEXT,
                True,
                False,
                "public",
                "public_aggregate",
            )
        with self.assertRaises(ValidationError):
            IntakeSourceReceipt(
                "source",
                "https://example.org/source",
                "v1",
                CONTEXT,
                True,
                False,
                "public",
                "unknown",
            )

    def test_invalid_record_and_control_contracts_raise(self) -> None:
        with self.assertRaises(ValidationError):
            IntakeFixtureRecord(
                "record",
                IntakeRecordKind.CONSENT,
                "operation",
                "source",
                CONTEXT,
                [],
                "public-id",
            )
        with self.assertRaises(ValidationError):
            IntakeFixtureControl(
                "control",
                IntakeRecordKind.CONSENT,
                "operation",
                "source",
                CONTEXT,
                {},
                "public-id",
                "review",
                ("duplicate", "duplicate"),
            )

    def test_missing_fixture_version_becomes_review_issue(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw.pop("fixture_version")
        catalog = IntakeFixtureCatalog.from_fixture(raw)
        report = catalog.audit()
        self.assertEqual(catalog.fixture_version, "missing")
        self.assertIn("missing_fixture_version", {issue.code for issue in report.issues})

    def test_file_parser_rejects_non_json_and_non_object_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "invalid.json"
            invalid.write_text("not-json", encoding="utf-8")
            with self.assertRaises(ValidationError):
                IntakeFixtureCatalog.from_file(invalid)
            array = Path(directory) / "array.json"
            array.write_text("[]", encoding="utf-8")
            with self.assertRaises(ValidationError):
                IntakeFixtureCatalog.from_file(array)


if __name__ == "__main__":
    unittest.main()
