"""Replay and drift tests for Domain 02 C09-C12."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.structural_haplotype_public_data import StructuralHaplotypeFixtureCatalog
from glio_noncode.structural_haplotype_replay import (
    StructuralHaplotypeReplayExpectation,
    replay_structural_haplotype_fixtures,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "structural-haplotype-public-aggregate.json"


class StructuralHaplotypeReplayTests(unittest.TestCase):
    def _expectation(self) -> StructuralHaplotypeReplayExpectation:
        catalog = StructuralHaplotypeFixtureCatalog.from_file(FIXTURE)
        return StructuralHaplotypeReplayExpectation(
            fixture_id=catalog.fixture_id,
            context_key=catalog.context_key,
            source_ids=catalog.source_ids,
            minimum_checks=40,
            minimum_positive_records=4,
            minimum_control_records=8,
        )

    def test_canonical_replay_passes(self) -> None:
        report = replay_structural_haplotype_fixtures([str(FIXTURE)], expectation=self._expectation(), required_context_key=self._expectation().context_key)
        self.assertTrue(report.passed)
        self.assertEqual(len(report.cases), 1)
        self.assertEqual(report.issue_codes, ())
        self.assertRegex(report.content_address, r"^sha256:[0-9a-f]{64}$")

    def test_empty_path_list_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValidationError, "at least one"):
            replay_structural_haplotype_fixtures([])

    def test_duplicate_identity_and_address_are_rejected(self) -> None:
        report = replay_structural_haplotype_fixtures([str(FIXTURE), str(FIXTURE)], expectation=self._expectation())
        self.assertFalse(report.passed)
        self.assertIn("duplicate_fixture_identity", report.issue_codes)
        self.assertIn("duplicate_fixture_address", report.issue_codes)

    def test_required_context_drift_is_rejected(self) -> None:
        wrong_context = "GRCh37|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"
        report = replay_structural_haplotype_fixtures([str(FIXTURE)], required_context_key=wrong_context)
        self.assertFalse(report.passed)
        self.assertIn("context_mismatch", report.cases[0].issue_codes)

    def test_expectation_source_drift_is_rejected(self) -> None:
        expectation = self._expectation()
        changed = StructuralHaplotypeReplayExpectation(
            fixture_id=expectation.fixture_id,
            context_key=expectation.context_key,
            source_ids=("different-source",),
        )
        report = replay_structural_haplotype_fixtures([str(FIXTURE)], expectation=changed)
        self.assertFalse(report.passed)
        self.assertIn("source_set_mismatch", report.cases[0].issue_codes)

    def test_expectation_check_floor_is_enforced(self) -> None:
        expectation = self._expectation()
        changed = StructuralHaplotypeReplayExpectation(
            fixture_id=expectation.fixture_id,
            context_key=expectation.context_key,
            source_ids=expectation.source_ids,
            minimum_checks=999,
        )
        report = replay_structural_haplotype_fixtures([str(FIXTURE)], expectation=changed)
        self.assertFalse(report.passed)
        self.assertIn("check_floor", report.cases[0].issue_codes)

    def test_fixture_identity_drift_is_rejected(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["fixture_id"] = "structural-haplotype-different-fixture"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "changed.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            report = replay_structural_haplotype_fixtures([str(path)], expectation=self._expectation())
        self.assertFalse(report.passed)
        self.assertIn("fixture_id_mismatch", report.cases[0].issue_codes)

    def test_cross_fixture_context_drift_is_rejected(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["fixture_id"] = "structural-haplotype-context-drift"
        raw["context_key"] = "GRCh37|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"
        for section in ("positives", "controls"):
            for record in raw[section]:
                record["context_key"] = raw["context_key"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "drift.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            report = replay_structural_haplotype_fixtures([str(FIXTURE), str(path)])
        self.assertFalse(report.passed)
        self.assertIn("cross_fixture_context_drift", report.issue_codes)


if __name__ == "__main__":
    unittest.main()
