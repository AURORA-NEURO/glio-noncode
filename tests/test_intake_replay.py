"""Replay integrity tests for Domain 01 intake fixtures."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.intake_public_data import IntakeFixtureCatalog
from glio_noncode.intake_replay import (
    IntakeReplayExpectation,
    IntakeReplayRunner,
    replay_intake_fixtures,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "examples" / "intake-public-aggregate.json"
FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
CONTEXT = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"


def expectation() -> IntakeReplayExpectation:
    catalog = IntakeFixtureCatalog.from_file(FIXTURE_PATH)
    return IntakeReplayExpectation(
        catalog.fixture_id,
        CONTEXT,
        tuple(sorted(source.source_id for source in catalog.sources)),
        minimum_checks=33,
        minimum_positive_records=4,
        minimum_negative_controls=8,
    )


class IntakeReplayTests(unittest.TestCase):
    def test_single_fixture_replays_cleanly(self) -> None:
        report = replay_intake_fixtures([FIXTURE_PATH], expectation=expectation())
        self.assertTrue(report.passed)
        self.assertEqual(report.state.value, "accepted")
        self.assertEqual(len(report.cases), 1)
        self.assertEqual(report.integrity_issues, ())
        self.assertTrue(report.cases[0].passed)

    def test_replay_enforces_minimum_check_floor(self) -> None:
        expected = IntakeReplayExpectation(
            expectation().fixture_id,
            CONTEXT,
            expectation().source_ids,
            minimum_checks=99,
            minimum_positive_records=4,
            minimum_negative_controls=8,
        )
        report = IntakeReplayRunner().replay([FIXTURE_PATH], expectation=expected)
        self.assertFalse(report.passed)
        self.assertTrue(any(issue.endswith("check_floor_not_met") for issue in report.integrity_issues))

    def test_replay_rejects_context_drift(self) -> None:
        expected = expectation()
        report = IntakeReplayRunner().replay(
            [FIXTURE_PATH],
            expectation=expected,
            required_context_key="GRCh37|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment",
        )
        self.assertFalse(report.passed)
        self.assertTrue(any("context_mismatch" in issue for issue in report.integrity_issues))

    def test_replay_rejects_source_set_drift(self) -> None:
        expected = IntakeReplayExpectation(
            expectation().fixture_id,
            CONTEXT,
            ("only-one-source",),
            minimum_checks=33,
            minimum_positive_records=4,
            minimum_negative_controls=8,
        )
        report = IntakeReplayRunner().replay([FIXTURE_PATH], expectation=expected)
        self.assertFalse(report.passed)
        self.assertIn("source_set_mismatch", report.cases[0].integrity_issues)

    def test_duplicate_fixture_ids_and_case_addresses_are_detected(self) -> None:
        report = IntakeReplayRunner().replay(
            [FIXTURE_PATH, FIXTURE_PATH],
            expectation=expectation(),
        )
        self.assertFalse(report.passed)
        self.assertIn("duplicate_fixture_ids", report.integrity_issues)
        self.assertIn("duplicate_case_addresses", report.integrity_issues)

    def test_mutated_fixture_is_reported_as_not_accepted(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw["provenance"]["patient_level_data"] = True
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mutated.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            report = IntakeReplayRunner().replay([path], expectation=expectation())
        self.assertFalse(report.passed)
        self.assertIn("fixture_not_accepted", report.cases[0].integrity_issues)

    def test_empty_replay_is_invalid(self) -> None:
        with self.assertRaises(ValidationError):
            IntakeReplayRunner().replay([], expectation=expectation())

    def test_expectation_rejects_zero_floor_and_duplicate_sources(self) -> None:
        with self.assertRaises(ValidationError):
            IntakeReplayExpectation("fixture", CONTEXT, (), minimum_checks=0)
        with self.assertRaises(ValidationError):
            IntakeReplayExpectation("fixture", CONTEXT, ("source", "source"), minimum_checks=1)


if __name__ == "__main__":
    unittest.main()
