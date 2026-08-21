from __future__ import annotations

import json
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.specimen_lineage_public_data import (
    SPECIMEN_LINEAGE_CONTEXT_DIMENSION_FLOOR,
    SPECIMEN_LINEAGE_FIXTURE_SCHEMA_VERSION,
    SpecimenLineageFixtureCatalog,
    SpecimenLineageFixtureState,
    SpecimenLineageOperation,
    audit_specimen_lineage_fixture,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "specimen-lineage-public-aggregate.json"
CONTEXT = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"


class SpecimenLineagePublicDataTests(unittest.TestCase):
    def test_fixture_has_expected_release_shape(self) -> None:
        catalog = SpecimenLineageFixtureCatalog.from_file(FIXTURE)
        self.assertEqual(catalog.schema_version, SPECIMEN_LINEAGE_FIXTURE_SCHEMA_VERSION)
        self.assertEqual(catalog.context_key, CONTEXT)
        self.assertEqual(
            len(catalog.context_key.split("|")), SPECIMEN_LINEAGE_CONTEXT_DIMENSION_FLOOR
        )
        self.assertEqual(len(catalog.positives), 4)
        self.assertEqual(len(catalog.controls), 8)
        self.assertEqual(
            set(catalog.operation_ids), {operation.value for operation in SpecimenLineageOperation}
        )

    def test_audit_accepts_aggregate_fixture(self) -> None:
        catalog = SpecimenLineageFixtureCatalog.from_file(FIXTURE)
        report = audit_specimen_lineage_fixture(catalog)
        self.assertTrue(report.accepted)
        self.assertEqual(report.issue_codes, ())
        self.assertTrue(report.content_address.startswith("sha256:"))

    def test_record_addresses_are_stable(self) -> None:
        first = SpecimenLineageFixtureCatalog.from_file(FIXTURE)
        second = SpecimenLineageFixtureCatalog.from_file(FIXTURE)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(
            [record.content_address for record in first.records],
            [record.content_address for record in second.records],
        )

    def test_positive_and_control_roles_are_explicit(self) -> None:
        catalog = SpecimenLineageFixtureCatalog.from_file(FIXTURE)
        self.assertTrue(
            all(
                record.expected_fixture_state == SpecimenLineageFixtureState.ACCEPTED
                for record in catalog.positives
            )
        )
        self.assertTrue(
            all(
                record.expected_fixture_state == SpecimenLineageFixtureState.REVIEW
                for record in catalog.controls
            )
        )

    def test_audit_rejects_context_drift(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["controls"][0]["context_key"] = "GRCh38|other|adult|other|other|other"
        catalog = SpecimenLineageFixtureCatalog.from_mapping(payload)
        report = audit_specimen_lineage_fixture(catalog)
        self.assertFalse(report.accepted)
        self.assertIn("context_mismatch", report.issue_codes)

    def test_audit_rejects_undeclared_sources(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["positives"][0]["source_ids"] = ["source-not-declared"]
        catalog = SpecimenLineageFixtureCatalog.from_mapping(payload)
        report = audit_specimen_lineage_fixture(catalog)
        self.assertIn("undeclared_source", report.issue_codes)

    def test_audit_rejects_direct_identifier_field(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["positives"][0]["payload"]["records"][0]["patient_id"] = "not-in-fixture"
        catalog = SpecimenLineageFixtureCatalog.from_mapping(payload)
        report = audit_specimen_lineage_fixture(catalog)
        self.assertIn("sensitive_record_payload", report.issue_codes)

    def test_audit_rejects_non_aggregate_source(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["sources"][0]["patient_level"] = True
        with self.assertRaises(ValidationError):
            SpecimenLineageFixtureCatalog.from_mapping(payload)

    def test_catalog_exposes_sorted_identity_views(self) -> None:
        catalog = SpecimenLineageFixtureCatalog.from_file(FIXTURE)
        self.assertEqual(tuple(sorted(catalog.source_ids)), catalog.source_ids)
        self.assertEqual(tuple(sorted(catalog.record_ids)), catalog.record_ids)
        self.assertEqual(len(set(catalog.record_ids)), 12)


if __name__ == "__main__":
    unittest.main()
