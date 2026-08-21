from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.reference_coordinate_public_data import (
    REFERENCE_COORDINATE_CONTEXT_KEY,
    REFERENCE_COORDINATE_CONTROL_COUNT,
    REFERENCE_COORDINATE_FIXTURE_VERSION,
    REFERENCE_COORDINATE_POSITIVE_COUNT,
    ReferenceCoordinateFixtureCatalog,
    ReferenceCoordinateOperation,
    ReferenceCoordinateRole,
    audit_reference_coordinate_data,
)

FIXTURE = Path(__file__).parents[1] / "examples" / "reference-coordinate-public-aggregate.json"


class ReferenceCoordinatePublicDataTests(unittest.TestCase):
    def load(self) -> ReferenceCoordinateFixtureCatalog:
        return ReferenceCoordinateFixtureCatalog.from_file(FIXTURE)

    def test_checked_in_fixture_passes_deep_data_audit(self) -> None:
        catalog = self.load()
        report = audit_reference_coordinate_data(catalog)
        self.assertEqual(report.state, "accepted")
        self.assertTrue(report.passed)
        self.assertEqual(len(report.checks), 26)
        self.assertEqual(report.failed_check_ids, ())

    def test_fixture_identity_counts_and_operations_are_locked(self) -> None:
        catalog = self.load()
        self.assertEqual(catalog.fixture_version, REFERENCE_COORDINATE_FIXTURE_VERSION)
        self.assertEqual(catalog.context_key, REFERENCE_COORDINATE_CONTEXT_KEY)
        self.assertEqual(len(catalog.positives), REFERENCE_COORDINATE_POSITIVE_COUNT)
        self.assertEqual(len(catalog.controls), REFERENCE_COORDINATE_CONTROL_COUNT)
        self.assertEqual(
            set(catalog.operation_ids),
            {operation.value for operation in ReferenceCoordinateOperation},
        )
        self.assertEqual(
            sum(record.role == ReferenceCoordinateRole.POSITIVE for record in catalog.records),
            4,
        )

    def test_public_sources_are_https_aggregate_and_addressed(self) -> None:
        catalog = self.load()
        self.assertEqual(len(catalog.source_receipts), 6)
        self.assertTrue(
            all(source.uri.startswith("https://") for source in catalog.source_receipts)
        )
        self.assertTrue(all(not source.patient_level for source in catalog.source_receipts))
        self.assertTrue(
            all(source.content_address.startswith("sha256:") for source in catalog.source_receipts)
        )
        self.assertEqual(len(catalog.source_ids), len(set(catalog.source_ids)))

    def test_record_addresses_are_deterministic_and_source_closed(self) -> None:
        catalog = self.load()
        replayed = ReferenceCoordinateFixtureCatalog.from_mapping(catalog.to_dict())
        self.assertEqual(catalog.content_address, replayed.content_address)
        self.assertEqual(
            tuple(record.content_address for record in catalog.records),
            tuple(record.content_address for record in replayed.records),
        )
        self.assertTrue(
            all(
                set(record.source_ids).issubset(set(catalog.source_ids))
                for record in catalog.records
            )
        )

    def test_direct_identifier_payload_is_rejected_before_execution(self) -> None:
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        raw["records"][0]["payload"]["subject_id"] = "not-allowed"
        with self.assertRaises(ValidationError):
            ReferenceCoordinateFixtureCatalog.from_mapping(raw)

    def test_patient_level_source_is_rejected(self) -> None:
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        raw["source_receipts"][0]["patient_level"] = True
        with self.assertRaises(ValidationError):
            ReferenceCoordinateFixtureCatalog.from_mapping(raw)

    def test_context_drift_is_reported_without_silent_transport(self) -> None:
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        raw["context_key"] = "GRCh37|diffuse_glioma|adult|bulk_tumor|reference_plane|baseline"
        catalog = ReferenceCoordinateFixtureCatalog.from_mapping(raw)
        report = audit_reference_coordinate_data(catalog)
        self.assertEqual(report.state, "review")
        self.assertIn("context-exact", report.failed_check_ids)
        self.assertIn("record-context", report.failed_check_ids)

    def test_unknown_operation_is_rejected(self) -> None:
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        raw["records"][0]["operation"] = "coordinate_guess"
        with self.assertRaises(ValueError):
            ReferenceCoordinateFixtureCatalog.from_mapping(raw)

    def test_payload_shape_controls_are_explicit(self) -> None:
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        raw["records"][0]["payload"] = {"query": ""}
        catalog = ReferenceCoordinateFixtureCatalog.from_mapping(raw)
        report = audit_reference_coordinate_data(catalog)
        self.assertEqual(report.state, "review")
        self.assertIn("payload-shapes", report.failed_check_ids)

    def test_fixture_serialization_does_not_add_raw_addresses_to_input(self) -> None:
        catalog = self.load()
        serialized = catalog.to_dict()
        self.assertEqual(serialized["fixture_id"], catalog.fixture_id)
        self.assertNotIn("subject_id", str(serialized).lower())
        self.assertNotIn("patient_id", str(serialized).lower())

    def test_mutating_one_record_changes_fixture_address(self) -> None:
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        original = self.load()
        mutated = copy.deepcopy(raw)
        mutated["records"][0]["payload"]["query"] = "hg19"
        changed = ReferenceCoordinateFixtureCatalog.from_mapping(mutated)
        self.assertNotEqual(original.content_address, changed.content_address)


if __name__ == "__main__":
    unittest.main()
