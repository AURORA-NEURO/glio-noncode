from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.frontier_public_data import (
    ContextFingerprint,
    PublicDataState,
    PublicFixtureCatalog,
    PublicRecordKind,
    PublicResearchRecord,
    SourceReceipt,
    audit_public_fixture,
)
from glio_noncode.serialization import canonical_json

ROOT = Path(__file__).parents[1]
FIXTURE_PATH = ROOT / "examples" / "frontier-glioma-case.json"
CONTEXT_KEY = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"


class FrontierPublicDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_context_fingerprint_round_trips_mapping_and_key(self) -> None:
        context = ContextFingerprint.from_value(self.fixture["context"])
        self.assertEqual(context.key, CONTEXT_KEY)
        self.assertEqual(ContextFingerprint.from_value(context.key), context)
        self.assertEqual(context.to_dict()["key"], CONTEXT_KEY)

    def test_context_fingerprint_reports_differing_fields(self) -> None:
        context = ContextFingerprint.from_value(self.fixture["context"])
        changed = ContextFingerprint(
            context.genome_build,
            context.disease_class,
            context.age_group,
            "different_cell_state",
            context.territory,
            context.treatment_phase,
        )
        self.assertEqual(context.differing_fields(changed), ("cell_state",))
        self.assertFalse(context.matches(changed))

    def test_context_rejects_wrong_component_count(self) -> None:
        with self.assertRaises(ValidationError):
            ContextFingerprint.from_value("GRCh38|diffuse_glioma")

    def test_context_rejects_empty_component(self) -> None:
        with self.assertRaises(ValidationError):
            ContextFingerprint.from_value("GRCh38|diffuse_glioma|adult|||pre_treatment")

    def test_context_rejects_non_text_mapping_value(self) -> None:
        broken = dict(self.fixture["context"])
        broken["cell_state"] = 4
        with self.assertRaises(ValidationError):
            ContextFingerprint.from_value(broken)

    def test_source_receipt_is_content_addressed(self) -> None:
        receipt = SourceReceipt.from_mapping(
            self.fixture["source_receipts"][0], default_patient_level=False
        )
        self.assertEqual(receipt.source_id, "glioma-regulatory-reference")
        self.assertFalse(receipt.patient_level_data)
        self.assertRegex(receipt.content_address, r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(receipt.to_dict()["accession"], receipt.accession)

    def test_source_receipt_defaults_coordinate_system(self) -> None:
        receipt = SourceReceipt.from_mapping(
            {
                "source_id": "source",
                "record_type": "aggregate",
                "accession": "ACC",
                "retrieval_mode": "local",
            },
            default_patient_level=False,
        )
        self.assertEqual(receipt.coordinate_system, "unspecified")

    def test_source_receipt_rejects_patient_level_default(self) -> None:
        receipt = SourceReceipt.from_mapping(
            {
                "source_id": "source",
                "record_type": "aggregate",
                "accession": "ACC",
                "retrieval_mode": "local",
            },
            default_patient_level=True,
        )
        self.assertTrue(receipt.patient_level_data)

    def test_source_receipt_rejects_non_boolean_patient_flag(self) -> None:
        with self.assertRaises(ValidationError):
            SourceReceipt.from_mapping(
                {
                    "source_id": "source",
                    "record_type": "aggregate",
                    "accession": "ACC",
                    "patient_level_data": "no",
                },
                default_patient_level=False,
            )

    def test_catalog_loads_all_public_record_families(self) -> None:
        catalog = PublicFixtureCatalog.from_fixture(self.fixture)
        report = catalog.audit()
        self.assertEqual(report.state, PublicDataState.ACCEPTED)
        self.assertEqual(report.record_count, 10)
        self.assertEqual(
            set(report.counts_by_kind),
            {"target", "experiment", "evidence", "claim", "workbench", "deployment"},
        )
        self.assertEqual(
            report.source_ids,
            ("glioma-regulatory-reference", "regulatory-assay-contract-reference"),
        )

    def test_catalog_file_entry_point_matches_mapping_entry_point(self) -> None:
        from_file = PublicFixtureCatalog.from_file(FIXTURE_PATH).audit().to_dict()
        from_mapping = PublicFixtureCatalog.from_fixture(self.fixture).audit().to_dict()
        self.assertEqual(from_file, from_mapping)
        self.assertEqual(audit_public_fixture(FIXTURE_PATH).to_dict(), from_file)

    def test_catalog_has_no_duplicate_ids_across_record_families(self) -> None:
        catalog = PublicFixtureCatalog.from_fixture(self.fixture)
        report = catalog.audit()
        self.assertEqual(report.duplicate_ids, ())
        self.assertIsNone(catalog.find("claim-egfr-regulatory-effect"))

    def test_catalog_find_returns_unique_record(self) -> None:
        catalog = PublicFixtureCatalog.from_fixture(self.fixture)
        record = catalog.find("EGFR-regulatory-guide-01")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.kind, PublicRecordKind.TARGET)
        self.assertEqual(record.context.key, CONTEXT_KEY)

    def test_catalog_records_by_kind_is_stable(self) -> None:
        catalog = PublicFixtureCatalog.from_fixture(self.fixture)
        targets = catalog.records_by_kind(PublicRecordKind.TARGET)
        experiments = catalog.records_by_kind(PublicRecordKind.EXPERIMENT)
        self.assertEqual(tuple(item.record_id for item in targets), ("EGFR-regulatory-guide-01",))
        self.assertEqual(
            tuple(item.record_id for item in experiments),
            ("orthogonal-open-chromatin-01", "allele-specific-contact-01"),
        )

    def test_catalog_label_search_finds_gene_identifier(self) -> None:
        catalog = PublicFixtureCatalog.from_fixture(self.fixture)
        results = catalog.search_label("EGFR")
        result_ids = {item.record_id for item in results}
        self.assertTrue(
            {
                "EGFR-regulatory-guide-01",
                "claim-egfr-regulatory-effect",
                "evidence-egfr-open-chromatin",
            }.issubset(result_ids)
        )
        self.assertGreaterEqual(len(result_ids), 3)

    def test_catalog_label_search_can_filter_record_kind(self) -> None:
        catalog = PublicFixtureCatalog.from_fixture(self.fixture)
        results = catalog.search_label("EGFR", kind=PublicRecordKind.CLAIM)
        self.assertEqual(
            tuple(item.record_id for item in results), ("claim-egfr-regulatory-effect",)
        )

    def test_catalog_label_search_rejects_empty_query(self) -> None:
        catalog = PublicFixtureCatalog.from_fixture(self.fixture)
        with self.assertRaises(ValidationError):
            catalog.search_label(" ")

    def test_source_manifest_contains_record_addresses(self) -> None:
        catalog = PublicFixtureCatalog.from_fixture(self.fixture)
        manifest = catalog.source_manifest()
        self.assertEqual(manifest["fixture_id"], self.fixture["fixture_id"])
        self.assertEqual(manifest["record_count"], 10)
        self.assertEqual(len(manifest["record_addresses"]), 10)
        self.assertRegex(manifest["manifest_address"], r"^sha256:[0-9a-f]{64}$")

    def test_catalog_report_is_deterministic(self) -> None:
        first = PublicFixtureCatalog.from_fixture(self.fixture).audit().to_dict()
        second = PublicFixtureCatalog.from_fixture(copy.deepcopy(self.fixture)).audit().to_dict()
        self.assertEqual(canonical_json(first), canonical_json(second))

    def test_same_family_duplicate_is_reviewed(self) -> None:
        mutated = copy.deepcopy(self.fixture)
        duplicate = copy.deepcopy(mutated["pipelines"]["validation"]["risk_records"][0])
        mutated["pipelines"]["validation"]["risk_records"].append(duplicate)
        report = PublicFixtureCatalog.from_fixture(mutated).audit()
        self.assertEqual(report.state, PublicDataState.REVIEW)
        self.assertEqual(report.duplicate_ids, ("target:EGFR-regulatory-guide-01",))
        self.assertTrue(any(item.code == "duplicate_record_id" for item in report.issues))

    def test_context_mismatch_is_reviewed(self) -> None:
        mutated = copy.deepcopy(self.fixture)
        mutated["pipelines"]["validation"]["risk_records"][0]["context_key"] = (
            "GRCh38|diffuse_glioma|adult|different_state|tumor_core|pre_treatment"
        )
        report = PublicFixtureCatalog.from_fixture(mutated).audit()
        self.assertEqual(report.state, PublicDataState.REVIEW)
        self.assertEqual(report.context_mismatch_ids, ("EGFR-regulatory-guide-01",))

    def test_sensitive_public_record_is_blocked(self) -> None:
        mutated = copy.deepcopy(self.fixture)
        mutated["pipelines"]["validation"]["risk_records"][0]["patient_id"] = "hidden"
        report = PublicFixtureCatalog.from_fixture(mutated).audit()
        self.assertEqual(report.state, PublicDataState.REVIEW)
        self.assertIn("records[EGFR-regulatory-guide-01].patient_id", report.sensitive_paths)

    def test_secret_like_public_record_is_blocked(self) -> None:
        mutated = copy.deepcopy(self.fixture)
        mutated["pipelines"]["workbench"]["records"][0]["api_key"] = "hidden"
        report = PublicFixtureCatalog.from_fixture(mutated).audit()
        self.assertEqual(report.state, PublicDataState.REVIEW)
        self.assertIn("records[claim-egfr-regulatory-effect].api_key", report.sensitive_paths)

    def test_patient_level_source_is_reviewed(self) -> None:
        mutated = copy.deepcopy(self.fixture)
        mutated["source_receipts"][0]["patient_level_data"] = True
        report = PublicFixtureCatalog.from_fixture(mutated).audit()
        self.assertEqual(report.state, PublicDataState.REVIEW)
        self.assertTrue(any(item.code == "patient_level_source" for item in report.issues))

    def test_duplicate_source_is_reviewed(self) -> None:
        mutated = copy.deepcopy(self.fixture)
        mutated["source_receipts"][1]["source_id"] = mutated["source_receipts"][0]["source_id"]
        report = PublicFixtureCatalog.from_fixture(mutated).audit()
        self.assertEqual(report.state, PublicDataState.REVIEW)
        self.assertTrue(any(item.code == "duplicate_source_id" for item in report.issues))

    def test_missing_source_receipt_is_reported_on_records(self) -> None:
        mutated = copy.deepcopy(self.fixture)
        mutated["source_receipts"] = []
        report = PublicFixtureCatalog.from_fixture(mutated).audit()
        self.assertEqual(report.state, PublicDataState.REVIEW)
        self.assertTrue(any(item.code == "unknown_source" for item in report.issues))

    def test_empty_pipelines_are_reviewed(self) -> None:
        mutated = copy.deepcopy(self.fixture)
        mutated["pipelines"] = {}
        report = PublicFixtureCatalog.from_fixture(mutated).audit()
        self.assertEqual(report.state, PublicDataState.REVIEW)
        self.assertTrue(any(item.code == "no_public_records" for item in report.issues))

    def test_record_normalization_uses_declared_fallback(self) -> None:
        context = ContextFingerprint.from_value(self.fixture["context"])
        record = PublicResearchRecord.from_mapping(
            {"title": "named aggregate observation", "score": 0.5},
            kind=PublicRecordKind.EVIDENCE,
            source_id="source",
            default_context=context,
            fallback_id="evidence:fallback",
        )
        self.assertEqual(record.record_id, "evidence:fallback")
        self.assertEqual(record.label, "named aggregate observation")
        self.assertEqual(record.context, context)

    def test_record_normalization_preserves_attributes_without_context(self) -> None:
        context = ContextFingerprint.from_value(self.fixture["context"])
        record = PublicResearchRecord.from_mapping(
            {"record_id": "record-1", "context": context.to_dict(), "gene": "EGFR", "score": 0.5},
            kind=PublicRecordKind.CLAIM,
            source_id="source",
            default_context=context,
            fallback_id="fallback",
        )
        self.assertEqual(record.context, context)
        self.assertNotIn("context", record.attributes)
        self.assertEqual(record.attributes["gene"], "EGFR")

    def test_record_rejects_out_of_range_bound_helper_values_in_fixture_layer(self) -> None:
        from glio_noncode.frontier_public_data import _bounded

        self.assertEqual(_bounded(0.5, field="score"), 0.5)
        with self.assertRaises(ValidationError):
            _bounded(1.1, field="score")
        with self.assertRaises(ValidationError):
            _bounded(-0.1, field="score")

    def test_file_loader_rejects_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text("{invalid", encoding="utf-8")
            with self.assertRaises(json.JSONDecodeError):
                PublicFixtureCatalog.from_file(path)

    def test_file_loader_rejects_non_object_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "array.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaises(ValidationError):
                PublicFixtureCatalog.from_file(path)


if __name__ == "__main__":
    unittest.main()
