from __future__ import annotations

import json
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.specimen_beta_frontier_public_data import (
    SPECIMEN_BETA_FRONTIER_CONTEXT_DIMENSION_FLOOR,
    SpecimenBetaFrontierFixtureCatalog,
    audit_specimen_beta_frontier_fixture,
)

FIXTURE = Path("examples/specimen-beta-frontier-public-aggregate.json")


class SpecimenBetaFrontierPublicDataTests(unittest.TestCase):
    def test_catalog_has_four_positives_eight_controls_and_four_operations(self) -> None:
        catalog = SpecimenBetaFrontierFixtureCatalog.from_file(FIXTURE)
        self.assertEqual(len(catalog.positives), 4)
        self.assertEqual(len(catalog.controls), 8)
        self.assertEqual(len(catalog.operation_ids), 4)
        self.assertEqual(
            len(catalog.context_key.split("|")),
            SPECIMEN_BETA_FRONTIER_CONTEXT_DIMENSION_FLOOR,
        )

    def test_public_aggregate_audit_passes(self) -> None:
        catalog = SpecimenBetaFrontierFixtureCatalog.from_file(FIXTURE)
        report = audit_specimen_beta_frontier_fixture(catalog)
        self.assertTrue(report.accepted)
        self.assertEqual(report.issue_codes, ())
        self.assertTrue(report.content_address.startswith("sha256:"))

    def test_records_are_exactly_context_bound_and_addressed(self) -> None:
        catalog = SpecimenBetaFrontierFixtureCatalog.from_file(FIXTURE)
        self.assertTrue(
            all(record.context_key == catalog.context_key for record in catalog.records)
        )
        self.assertTrue(
            all(record.content_address.startswith("sha256:") for record in catalog.records)
        )
        self.assertEqual(len(catalog.record_ids), len(set(catalog.record_ids)))

    def test_sensitive_nested_key_is_rejected(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["controls"][0]["payload"]["records"][0]["nested"] = {"patient_id": "not-in-fixture"}
        catalog = SpecimenBetaFrontierFixtureCatalog.from_mapping(payload)
        report = audit_specimen_beta_frontier_fixture(catalog)
        self.assertIn("sensitive_record_payload", report.issue_codes)
        self.assertFalse(report.accepted)

    def test_context_drift_is_rejected(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["controls"][0]["context_key"] = (
            "GRCh38|diffuse_glioma|adult|other|tumor_core|pre_treatment"
        )
        catalog = SpecimenBetaFrontierFixtureCatalog.from_mapping(payload)
        report = audit_specimen_beta_frontier_fixture(catalog)
        self.assertIn("context_mismatch", report.issue_codes)

    def test_record_address_drift_is_rejected(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["positives"][0]["content_address"] = "sha256:incorrect"
        catalog = SpecimenBetaFrontierFixtureCatalog.from_mapping(payload)
        report = audit_specimen_beta_frontier_fixture(catalog)
        self.assertIn("record_address_mismatch", report.issue_codes)

    def test_patient_level_source_is_rejected_at_construction(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["sources"][0]["patient_level"] = True
        with self.assertRaises(ValidationError):
            SpecimenBetaFrontierFixtureCatalog.from_mapping(payload)

    def test_aggregate_scope_is_not_inferred_from_missing_field(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["aggregate_only"] = False
        with self.assertRaises(ValidationError):
            SpecimenBetaFrontierFixtureCatalog.from_mapping(payload)


if __name__ == "__main__":
    unittest.main()
