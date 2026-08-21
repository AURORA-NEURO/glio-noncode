"""Replay identity tests for Domain 02 C13-C16."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.structural_frontier_public_data import StructuralFrontierFixtureCatalog
from glio_noncode.structural_frontier_replay import (
    StructuralFrontierReplayExpectation,
    replay_structural_frontier_fixtures,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "structural-frontier-public-aggregate.json"
CONTEXT = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"


def _expectation() -> StructuralFrontierReplayExpectation:
    catalog = StructuralFrontierFixtureCatalog.from_file(FIXTURE)
    return StructuralFrontierReplayExpectation(
        fixture_id=catalog.fixture_id,
        context_key=CONTEXT,
        source_ids=catalog.source_ids,
    )


class StructuralFrontierReplayTests(unittest.TestCase):
    def test_canonical_replay_passes_identity_and_floors(self) -> None:
        report = replay_structural_frontier_fixtures((FIXTURE,), expectation=_expectation(), required_context_key=CONTEXT)
        self.assertTrue(report.passed)
        self.assertEqual(len(report.cases), 1)
        self.assertEqual(report.cases[0].check_count, 72)
        self.assertEqual(report.cases[0].positive_count, 4)
        self.assertEqual(report.cases[0].control_count, 8)
        self.assertEqual(report.cases[0].issue_codes, ())

    def test_replay_is_deterministic(self) -> None:
        first = replay_structural_frontier_fixtures((FIXTURE,), expectation=_expectation())
        second = replay_structural_frontier_fixtures((FIXTURE,), expectation=_expectation())
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_fixture_id_mismatch_is_visible(self) -> None:
        expectation = _expectation()
        wrong = StructuralFrontierReplayExpectation("different-fixture", CONTEXT, expectation.source_ids)
        report = replay_structural_frontier_fixtures((FIXTURE,), expectation=wrong)
        self.assertFalse(report.passed)
        self.assertIn("fixture_id_mismatch", report.cases[0].issue_codes)

    def test_context_mismatch_is_visible(self) -> None:
        report = replay_structural_frontier_fixtures(
            (FIXTURE,),
            expectation=_expectation(),
            required_context_key="GRCh37|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment",
        )
        self.assertFalse(report.passed)
        self.assertIn("context_mismatch", report.cases[0].issue_codes)

    def test_source_set_mismatch_is_visible(self) -> None:
        expectation = StructuralFrontierReplayExpectation(
            StructuralFrontierFixtureCatalog.from_file(FIXTURE).fixture_id,
            CONTEXT,
            ("one-source",),
        )
        report = replay_structural_frontier_fixtures((FIXTURE,), expectation=expectation)
        self.assertFalse(report.passed)
        self.assertIn("source_set_mismatch", report.cases[0].issue_codes)

    def test_check_and_record_floors_are_enforced(self) -> None:
        catalog = StructuralFrontierFixtureCatalog.from_file(FIXTURE)
        expectation = StructuralFrontierReplayExpectation(
            catalog.fixture_id,
            CONTEXT,
            catalog.source_ids,
            minimum_checks=73,
            minimum_positive_records=5,
            minimum_control_records=9,
        )
        report = replay_structural_frontier_fixtures((FIXTURE,), expectation=expectation)
        self.assertFalse(report.passed)
        self.assertIn("check_floor", report.cases[0].issue_codes)
        self.assertIn("positive_floor", report.cases[0].issue_codes)
        self.assertIn("control_floor", report.cases[0].issue_codes)

    def test_failed_evaluation_is_replayed_as_failure(self) -> None:
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        raw["positives"][0]["expected_counts"]["expanded"] = 0
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tampered.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            report = replay_structural_frontier_fixtures((path,), expectation=_expectation())
        self.assertFalse(report.passed)
        self.assertIn("evaluation_failed", report.cases[0].issue_codes)

    def test_empty_path_list_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValidationError, "at least one path"):
            replay_structural_frontier_fixtures((), expectation=_expectation())

    def test_invalid_expectation_floor_is_rejected(self) -> None:
        catalog = StructuralFrontierFixtureCatalog.from_file(FIXTURE)
        with self.assertRaisesRegex(ValidationError, "floors must be positive"):
            StructuralFrontierReplayExpectation(catalog.fixture_id, CONTEXT, catalog.source_ids, minimum_checks=0)

    def test_replay_case_has_addressed_evaluation(self) -> None:
        report = replay_structural_frontier_fixtures((FIXTURE,), expectation=_expectation())
        self.assertRegex(report.cases[0].evaluation_address, r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(report.content_address, r"^sha256:[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
