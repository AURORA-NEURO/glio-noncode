"""Replay identity tests for Domain 03 C01-C04."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.specimen_frontier_public_data import SpecimenFrontierFixtureCatalog
from glio_noncode.specimen_frontier_replay import (
    SpecimenFrontierReplayExpectation,
    replay_specimen_frontier_fixtures,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "specimen-frontier-public-aggregate.json"
CONTEXT = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"


class SpecimenFrontierReplayTests(unittest.TestCase):
    def _expectation(
        self, catalog: SpecimenFrontierFixtureCatalog
    ) -> SpecimenFrontierReplayExpectation:
        return SpecimenFrontierReplayExpectation(
            catalog.fixture_id,
            CONTEXT,
            catalog.source_ids,
            minimum_checks=40,
            minimum_positive_records=4,
            minimum_control_records=8,
        )

    def test_canonical_replay_passes_identity_and_floors(self) -> None:
        catalog = SpecimenFrontierFixtureCatalog.from_file(FIXTURE)
        report = replay_specimen_frontier_fixtures(
            [FIXTURE],
            expectation=self._expectation(catalog),
            required_context_key=CONTEXT,
        )
        self.assertTrue(report.passed)
        self.assertEqual(report.to_dict()["case_count"], 1)
        self.assertEqual(report.cases[0].issue_codes, ())

    def test_wrong_context_is_rejected(self) -> None:
        catalog = SpecimenFrontierFixtureCatalog.from_file(FIXTURE)
        report = replay_specimen_frontier_fixtures(
            [FIXTURE],
            expectation=self._expectation(catalog),
            required_context_key="GRCh38|diffuse_glioma|adult|other|tumor_core|pre_treatment",
        )
        self.assertFalse(report.passed)
        self.assertIn("context_mismatch", report.cases[0].issue_codes)

    def test_wrong_fixture_identity_is_rejected(self) -> None:
        catalog = SpecimenFrontierFixtureCatalog.from_file(FIXTURE)
        expectation = SpecimenFrontierReplayExpectation(
            "different-fixture",
            CONTEXT,
            catalog.source_ids,
        )
        report = replay_specimen_frontier_fixtures([FIXTURE], expectation=expectation)
        self.assertFalse(report.passed)
        self.assertIn("fixture_id_mismatch", report.cases[0].issue_codes)

    def test_wrong_source_set_is_rejected(self) -> None:
        catalog = SpecimenFrontierFixtureCatalog.from_file(FIXTURE)
        expectation = SpecimenFrontierReplayExpectation(
            catalog.fixture_id,
            CONTEXT,
            ("only-one-source",),
        )
        report = replay_specimen_frontier_fixtures([FIXTURE], expectation=expectation)
        self.assertFalse(report.passed)
        self.assertIn("source_set_mismatch", report.cases[0].issue_codes)

    def test_missing_input_paths_fail_fast(self) -> None:
        catalog = SpecimenFrontierFixtureCatalog.from_file(FIXTURE)
        with self.assertRaises(ValidationError):
            replay_specimen_frontier_fixtures([], expectation=self._expectation(catalog))

    def test_two_same_fixture_paths_are_allowed_without_address_collisions(self) -> None:
        catalog = SpecimenFrontierFixtureCatalog.from_file(FIXTURE)
        report = replay_specimen_frontier_fixtures(
            [FIXTURE, FIXTURE],
            expectation=self._expectation(catalog),
        )
        self.assertTrue(report.passed)
        self.assertEqual(len(report.cases), 2)
        self.assertEqual(report.cases[0].evaluation_address, report.cases[1].evaluation_address)

    def test_replay_report_address_is_deterministic(self) -> None:
        catalog = SpecimenFrontierFixtureCatalog.from_file(FIXTURE)
        first = replay_specimen_frontier_fixtures([FIXTURE], expectation=self._expectation(catalog))
        second = replay_specimen_frontier_fixtures(
            [FIXTURE], expectation=self._expectation(catalog)
        )
        self.assertEqual(first.content_address, second.content_address)

    def test_bad_json_path_is_validation_error(self) -> None:
        catalog = SpecimenFrontierFixtureCatalog.from_file(FIXTURE)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps({"not": "a fixture"}), encoding="utf-8")
            with self.assertRaises(ValidationError):
                replay_specimen_frontier_fixtures([path], expectation=self._expectation(catalog))


if __name__ == "__main__":
    unittest.main()
