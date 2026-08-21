from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.identity_public_data import (
    IDENTITY_FIXTURE_SCHEMA_VERSION,
    IdentityDataState,
    IdentityFixtureCatalog,
    IdentityRecordKind,
    IdentitySourceReceipt,
    audit_identity_fixture,
)

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "examples" / "identity-public-aggregate.json"
CONTEXT = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"
SOURCES = ("ncbi-clinvar-rs121913502", "ncbi-grch38-reference-assembly")


class IdentityPublicDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_checked_in_fixture_audits_as_public_aggregate_data(self) -> None:
        report = audit_identity_fixture(FIXTURE)
        self.assertTrue(report.accepted)
        self.assertEqual(report.state, IdentityDataState.ACCEPTED)
        self.assertEqual(report.fixture_version, IDENTITY_FIXTURE_SCHEMA_VERSION)
        self.assertEqual(report.context_key, CONTEXT)
        self.assertEqual(report.source_ids, SOURCES)
        self.assertEqual(report.positive_count, 4)
        self.assertEqual(report.negative_control_count, 8)
        self.assertEqual(report.issues, ())

    def test_audit_counts_positive_and_negative_kinds(self) -> None:
        report = audit_identity_fixture(FIXTURE)
        self.assertEqual(report.counts_by_kind["equivalence"], 1)
        self.assertEqual(report.counts_by_kind["reconciliation"], 1)
        self.assertEqual(report.counts_by_kind["sample"], 1)
        self.assertEqual(report.counts_by_kind["custody"], 1)
        self.assertEqual(report.counts_by_kind["negative:equivalence"], 2)
        self.assertEqual(report.counts_by_kind["negative:reconciliation"], 2)
        self.assertEqual(report.counts_by_kind["negative:sample"], 2)
        self.assertEqual(report.counts_by_kind["negative:custody"], 2)

    def test_catalog_indexes_records_and_controls(self) -> None:
        catalog = IdentityFixtureCatalog.from_file(FIXTURE)
        self.assertEqual(catalog.fixture_id, "identity-public-aggregate-001")
        self.assertEqual(catalog.context_key, CONTEXT)
        self.assertEqual(len(catalog.sources), 2)
        self.assertIsNotNone(catalog.record("equivalence:rs121913502"))
        self.assertIsNotNone(catalog.control("custody:invalid-timestamp"))
        self.assertIsNone(catalog.record("missing-record"))
        self.assertIsNone(catalog.control("missing-control"))
        self.assertEqual({record.kind for record in catalog.records}, set(IdentityRecordKind))

    def test_source_receipts_are_https_public_and_non_patient(self) -> None:
        catalog = IdentityFixtureCatalog.from_file(FIXTURE)
        for source in catalog.sources:
            self.assertTrue(source.source_url.startswith("https://"))
            self.assertTrue(source.public_aggregate)
            self.assertFalse(source.patient_level_data)
            self.assertEqual(source.context_key, CONTEXT)

    def test_audit_is_deterministic_and_addressed(self) -> None:
        first = audit_identity_fixture(FIXTURE).to_dict()
        second = audit_identity_fixture(FIXTURE).to_dict()
        self.assertEqual(first, second)
        self.assertRegex(first["content_address"], r"^sha256:[0-9a-f]{64}$")

    def test_duplicate_record_identity_is_reviewed(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["records"].append(copy.deepcopy(fixture["records"][0]))
        report = IdentityFixtureCatalog.from_fixture(fixture).audit()
        self.assertFalse(report.accepted)
        self.assertEqual(report.duplicate_record_ids, ("equivalence:rs121913502",))
        self.assertTrue(any(issue.code == "duplicate_record_id" for issue in report.issues))

    def test_duplicate_control_identity_is_reviewed(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["negative_controls"].append(copy.deepcopy(fixture["negative_controls"][0]))
        report = IdentityFixtureCatalog.from_fixture(fixture).audit()
        self.assertFalse(report.accepted)
        self.assertEqual(
            report.duplicate_control_ids,
            ("equivalence:out-of-domain-build",),
        )
        self.assertTrue(any(issue.code == "duplicate_control_id" for issue in report.issues))

    def test_record_control_collision_is_reviewed(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["negative_controls"][0]["control_id"] = fixture["records"][0]["record_id"]
        report = IdentityFixtureCatalog.from_fixture(fixture).audit()
        self.assertFalse(report.accepted)
        self.assertTrue(any(issue.code == "record_control_collision" for issue in report.issues))

    def test_context_mismatch_is_reviewed(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["records"][0]["context_key"] = CONTEXT.replace("tumor_core", "core_margin")
        report = IdentityFixtureCatalog.from_fixture(fixture).audit()
        self.assertFalse(report.accepted)
        self.assertEqual(report.context_mismatch_ids, ("equivalence:rs121913502",))

    def test_unknown_source_is_reviewed(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["records"][0]["source_id"] = "unknown-public-source"
        report = IdentityFixtureCatalog.from_fixture(fixture).audit()
        self.assertFalse(report.accepted)
        self.assertEqual(report.unknown_source_ids, ("unknown-public-source",))

    def test_sensitive_payload_key_is_reviewed_without_returning_value(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["records"][0]["payload"]["patient_id"] = "must-not-be-retained"
        report = IdentityFixtureCatalog.from_fixture(fixture).audit()
        self.assertFalse(report.accepted)
        self.assertIn("records[0].payload.patient_id", report.sensitive_paths)
        self.assertNotIn("must-not-be-retained", json.dumps(report.to_dict(), sort_keys=True))

    def test_patient_level_source_is_reviewed(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["source_receipts"][0]["patient_level_data"] = True
        report = IdentityFixtureCatalog.from_fixture(fixture).audit()
        self.assertFalse(report.accepted)
        self.assertTrue(any(issue.code == "source_patient_scope" for issue in report.issues))

    def test_non_public_source_is_reviewed(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["source_receipts"][0]["public_aggregate"] = False
        report = IdentityFixtureCatalog.from_fixture(fixture).audit()
        self.assertFalse(report.accepted)
        self.assertTrue(any(issue.code == "source_not_public_aggregate" for issue in report.issues))

    def test_scope_declaration_is_required(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["provenance"].pop("data_scope")
        report = IdentityFixtureCatalog.from_fixture(fixture).audit()
        self.assertFalse(report.accepted)
        self.assertTrue(any(issue.code == "fixture_scope_mismatch" for issue in report.issues))

    def test_evidence_boundary_is_required(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["provenance"].pop("evidence_boundary")
        report = IdentityFixtureCatalog.from_fixture(fixture).audit()
        self.assertFalse(report.accepted)
        self.assertTrue(any(issue.code == "missing_evidence_boundary" for issue in report.issues))

    def test_wrong_fixture_version_is_reviewed(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["fixture_version"] = "identity-evidence-old"
        report = IdentityFixtureCatalog.from_fixture(fixture).audit()
        self.assertFalse(report.accepted)
        self.assertTrue(any(issue.code == "fixture_version_mismatch" for issue in report.issues))

    def test_missing_source_receipts_is_reviewed(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["source_receipts"] = []
        report = IdentityFixtureCatalog.from_fixture(fixture).audit()
        self.assertFalse(report.accepted)
        self.assertTrue(any(issue.code == "missing_source_receipts" for issue in report.issues))

    def test_duplicate_source_identity_is_reviewed(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["source_receipts"][1]["source_id"] = fixture["source_receipts"][0]["source_id"]
        report = IdentityFixtureCatalog.from_fixture(fixture).audit()
        self.assertFalse(report.accepted)
        self.assertTrue(any(issue.code == "duplicate_source_id" for issue in report.issues))

    def test_mixed_source_context_is_reviewed(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["source_receipts"][1]["context_key"] = CONTEXT.replace(
            "pre_treatment", "post_treatment"
        )
        report = IdentityFixtureCatalog.from_fixture(fixture).audit()
        self.assertFalse(report.accepted)
        self.assertTrue(any(issue.code == "source_context_mismatch" for issue in report.issues))

    def test_source_receipt_requires_https(self) -> None:
        with self.assertRaises(ValidationError):
            IdentitySourceReceipt(
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
            IdentitySourceReceipt(
                "source",
                "https://example.test/source",
                "v1",
                CONTEXT,
                "yes",
                False,
                "public",
            )
        with self.assertRaises(ValidationError):
            IdentitySourceReceipt(
                "source",
                "https://example.test/source",
                "v1",
                CONTEXT,
                True,
                "no",
                "public",
            )

    def test_invalid_kind_is_a_validation_error(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["records"][0]["kind"] = "unsupported"
        with self.assertRaises(ValidationError):
            IdentityFixtureCatalog.from_fixture(fixture)

    def test_context_requires_all_qualifiers(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["context"].pop("territory")
        with self.assertRaises(ValidationError):
            IdentityFixtureCatalog.from_fixture(fixture)

    def test_payload_requires_an_object(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["records"][0]["payload"] = ["not", "an", "object"]
        with self.assertRaises(ValidationError):
            IdentityFixtureCatalog.from_fixture(fixture)

    def test_expected_signals_require_an_array(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["records"][0]["expected_signals"] = "not-an-array"
        with self.assertRaises(ValidationError):
            IdentityFixtureCatalog.from_fixture(fixture)

    def test_invalid_fixture_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaises(ValidationError):
                IdentityFixtureCatalog.from_file(path)

    def test_invalid_json_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text("{bad", encoding="utf-8")
            with self.assertRaises(ValidationError):
                IdentityFixtureCatalog.from_file(path)

    def test_report_serializes_counts_and_issue_paths(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["negative_controls"][0]["payload"]["mrn"] = "restricted"
        payload = IdentityFixtureCatalog.from_fixture(fixture).audit().to_dict()
        self.assertFalse(payload["accepted"])
        self.assertEqual(payload["positive_count"], 4)
        self.assertIn("negative_controls[0].payload.mrn", payload["sensitive_paths"])
        self.assertTrue(payload["issues"])


if __name__ == "__main__":
    unittest.main()
