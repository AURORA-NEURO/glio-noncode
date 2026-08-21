from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.variation_public_data import (
    VARIATION_FIXTURE_SCHEMA_VERSION,
    VariationDataState,
    VariationFixtureCatalog,
    VariationRecordKind,
    VariationSourceReceipt,
    audit_variation_fixture,
)

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "examples" / "variation-public-aggregate.json"
CONTEXT = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"
SOURCES = ("ncbi-clinvar-rs121913502", "ncbi-grch38-reference-assembly")


class VariationPublicDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_checked_in_fixture_audits_as_public_aggregate_data(self) -> None:
        report = audit_variation_fixture(FIXTURE)
        self.assertTrue(report.accepted)
        self.assertEqual(report.state, VariationDataState.ACCEPTED)
        self.assertEqual(report.fixture_version, VARIATION_FIXTURE_SCHEMA_VERSION)
        self.assertEqual(report.context_key, CONTEXT)
        self.assertEqual(report.source_ids, SOURCES)
        self.assertEqual(report.record_count, 5)
        self.assertEqual(report.issues, ())

    def test_audit_counts_all_five_variation_record_kinds(self) -> None:
        report = audit_variation_fixture(FIXTURE)
        self.assertEqual(
            report.counts_by_kind,
            {kind.value: 1 for kind in VariationRecordKind},
        )

    def test_catalog_indexes_public_records_by_identity(self) -> None:
        catalog = VariationFixtureCatalog.from_file(FIXTURE)
        self.assertEqual(catalog.fixture_id, "variation-public-aggregate-001")
        self.assertEqual(catalog.context_key, CONTEXT)
        self.assertEqual(len(catalog.sources), 2)
        self.assertIsNotNone(catalog.record("dbsnp:rs121913502:vrs"))
        self.assertIsNone(catalog.record("missing-record"))
        self.assertEqual(
            {record.kind for record in catalog.records},
            set(VariationRecordKind),
        )

    def test_source_receipts_are_https_public_and_non_patient(self) -> None:
        catalog = VariationFixtureCatalog.from_file(FIXTURE)
        for source in catalog.sources:
            self.assertTrue(source.source_url.startswith("https://"))
            self.assertTrue(source.public_aggregate)
            self.assertFalse(source.patient_level_data)
            self.assertEqual(source.context_key, CONTEXT)

    def test_audit_is_deterministic(self) -> None:
        first = audit_variation_fixture(FIXTURE).to_dict()
        second = audit_variation_fixture(FIXTURE).to_dict()
        self.assertEqual(first, second)
        self.assertRegex(first["content_address"], r"^sha256:[0-9a-f]{64}$")

    def test_duplicate_record_identity_is_reviewed(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["records"].append(copy.deepcopy(fixture["records"][0]))
        report = VariationFixtureCatalog.from_fixture(fixture).audit()
        self.assertFalse(report.accepted)
        self.assertEqual(report.state, VariationDataState.REVIEW)
        self.assertEqual(report.duplicate_record_ids, ("dbsnp:rs121913502:vrs",))
        self.assertTrue(any(issue.code == "duplicate_record_id" for issue in report.issues))

    def test_record_context_mismatch_is_reviewed(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["records"][0]["context_key"] = CONTEXT.replace(
            "tumor_core", "core_margin"
        )
        report = VariationFixtureCatalog.from_fixture(fixture).audit()
        self.assertFalse(report.accepted)
        self.assertEqual(report.context_mismatch_ids, ("dbsnp:rs121913502:vrs",))

    def test_unknown_record_source_is_reviewed(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["records"][0]["source_id"] = "unknown-public-source"
        report = VariationFixtureCatalog.from_fixture(fixture).audit()
        self.assertFalse(report.accepted)
        self.assertEqual(report.unknown_source_ids, ("unknown-public-source",))

    def test_sensitive_payload_key_is_reviewed_without_returning_value(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["records"][0]["payload"]["patient_id"] = "must-not-be-retained"
        report = VariationFixtureCatalog.from_fixture(fixture).audit()
        self.assertFalse(report.accepted)
        self.assertIn("records[0].payload.patient_id", report.sensitive_paths)
        serialized = json.dumps(report.to_dict(), sort_keys=True)
        self.assertNotIn("must-not-be-retained", serialized)

    def test_operational_subject_id_is_allowed_for_public_allele_subjects(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["records"][2]["payload"]["subject"]["subject_id"] = "dbsnp:rs121913502"
        report = VariationFixtureCatalog.from_fixture(fixture).audit()
        self.assertTrue(report.accepted)
        self.assertEqual(report.sensitive_paths, ())

    def test_patient_level_source_declaration_is_reviewed(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["source_receipts"][0]["patient_level_data"] = True
        report = VariationFixtureCatalog.from_fixture(fixture).audit()
        self.assertFalse(report.accepted)
        self.assertTrue(any(issue.code == "source_patient_scope" for issue in report.issues))

    def test_non_public_source_declaration_is_reviewed(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["source_receipts"][0]["public_aggregate"] = False
        report = VariationFixtureCatalog.from_fixture(fixture).audit()
        self.assertFalse(report.accepted)
        self.assertTrue(any(issue.code == "source_not_public_aggregate" for issue in report.issues))

    def test_missing_evidence_boundary_is_reviewed(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["provenance"].pop("evidence_boundary")
        report = VariationFixtureCatalog.from_fixture(fixture).audit()
        self.assertFalse(report.accepted)
        self.assertTrue(any(issue.code == "missing_evidence_boundary" for issue in report.issues))

    def test_wrong_fixture_version_is_reviewed(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["fixture_version"] = "variation-evidence-old"
        report = VariationFixtureCatalog.from_fixture(fixture).audit()
        self.assertFalse(report.accepted)
        self.assertTrue(any(issue.code == "fixture_version_mismatch" for issue in report.issues))

    def test_missing_source_receipts_is_reviewed(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["source_receipts"] = []
        report = VariationFixtureCatalog.from_fixture(fixture).audit()
        self.assertFalse(report.accepted)
        self.assertTrue(any(issue.code == "missing_source_receipts" for issue in report.issues))

    def test_mixed_source_context_is_reviewed(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["source_receipts"][1]["context_key"] = CONTEXT.replace(
            "pre_treatment", "post_treatment"
        )
        report = VariationFixtureCatalog.from_fixture(fixture).audit()
        self.assertFalse(report.accepted)
        self.assertTrue(any(issue.code == "source_context_mismatch" for issue in report.issues))

    def test_duplicate_source_identity_is_reviewed(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["source_receipts"][1]["source_id"] = fixture["source_receipts"][0]["source_id"]
        report = VariationFixtureCatalog.from_fixture(fixture).audit()
        self.assertFalse(report.accepted)
        self.assertTrue(any(issue.code == "duplicate_source_id" for issue in report.issues))

    def test_source_receipt_requires_https(self) -> None:
        with self.assertRaises(ValidationError):
            VariationSourceReceipt(
                "source",
                "http://example.test/source",
                "v1",
                CONTEXT,
                True,
                False,
                "public",
            )

    def test_source_receipt_requires_boolean_scope_flags(self) -> None:
        with self.assertRaises(ValidationError):
            VariationSourceReceipt(
                "source",
                "https://example.test/source",
                "v1",
                CONTEXT,
                "yes",
                False,
                "public",
            )
        with self.assertRaises(ValidationError):
            VariationSourceReceipt(
                "source",
                "https://example.test/source",
                "v1",
                CONTEXT,
                True,
                "no",
                "public",
            )

    def test_context_requires_all_six_qualifiers(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["context"].pop("territory")
        with self.assertRaises(ValidationError):
            VariationFixtureCatalog.from_fixture(fixture)

    def test_record_payload_requires_an_object(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["records"][0]["payload"] = ["not", "an", "object"]
        with self.assertRaises(ValidationError):
            VariationFixtureCatalog.from_fixture(fixture)

    def test_invalid_fixture_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaises(ValidationError):
                VariationFixtureCatalog.from_file(path)

    def test_invalid_json_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text("{bad", encoding="utf-8")
            with self.assertRaises(ValidationError):
                VariationFixtureCatalog.from_file(path)

    def test_record_kind_is_enum_backed(self) -> None:
        catalog = VariationFixtureCatalog.from_file(FIXTURE)
        for record in catalog.records:
            self.assertIsInstance(record.kind, VariationRecordKind)
            self.assertIn(record.kind.value, {kind.value for kind in VariationRecordKind})

    def test_report_serializes_issue_paths_and_counts(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["records"][0]["payload"]["mrn"] = "restricted"
        payload = VariationFixtureCatalog.from_fixture(fixture).audit().to_dict()
        self.assertFalse(payload["accepted"])
        self.assertEqual(payload["record_count"], 5)
        self.assertIn("records[0].payload.mrn", payload["sensitive_paths"])
        self.assertTrue(payload["issues"])


if __name__ == "__main__":
    unittest.main()
