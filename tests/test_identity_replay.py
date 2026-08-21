from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.identity_public_data import IdentityDataState
from glio_noncode.identity_replay import (
    IdentityReplayExpectation,
    IdentityReplayRunner,
    replay_identity_fixtures,
)

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "examples" / "identity-public-aggregate.json"
CONTEXT = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"
SOURCES = ("ncbi-clinvar-rs121913502", "ncbi-grch38-reference-assembly")


class IdentityReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.expectation = IdentityReplayExpectation(
            "identity-public-aggregate-001",
            CONTEXT,
            SOURCES,
        )

    def test_checked_in_fixture_replays(self) -> None:
        report = replay_identity_fixtures((FIXTURE,), expectation=self.expectation)
        self.assertTrue(report.passed)
        self.assertEqual(report.state, IdentityDataState.ACCEPTED)
        self.assertEqual(len(report.cases), 1)
        self.assertEqual(report.failed_reasons, ())

    def test_case_receipt_retains_count_floors_and_address(self) -> None:
        report = replay_identity_fixtures((FIXTURE,), expectation=self.expectation)
        case = report.cases[0]
        self.assertTrue(case.passed)
        self.assertEqual(case.check_count, 37)
        self.assertEqual(case.positive_count, 4)
        self.assertEqual(case.negative_control_count, 8)
        self.assertRegex(case.content_address, r"^sha256:[0-9a-f]{64}$")

    def test_replay_is_deterministic(self) -> None:
        first = replay_identity_fixtures((FIXTURE,), expectation=self.expectation)
        second = replay_identity_fixtures((FIXTURE,), expectation=self.expectation)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_wrong_context_is_reviewed(self) -> None:
        wrong = IdentityReplayExpectation(
            self.expectation.fixture_id,
            CONTEXT.replace("tumor_core", "core_margin"),
            SOURCES,
        )
        report = replay_identity_fixtures((FIXTURE,), expectation=wrong)
        self.assertFalse(report.passed)
        self.assertIn("context differs from replay expectation", " ".join(report.failed_reasons))
        self.assertEqual(report.context_mismatch_paths, (str(FIXTURE),))

    def test_wrong_source_set_is_reviewed(self) -> None:
        wrong = IdentityReplayExpectation(
            self.expectation.fixture_id,
            CONTEXT,
            ("only-one-public-source",),
        )
        report = replay_identity_fixtures((FIXTURE,), expectation=wrong)
        self.assertFalse(report.passed)
        self.assertEqual(report.source_mismatch_paths, (str(FIXTURE),))

    def test_duplicate_fixture_paths_are_reviewed(self) -> None:
        report = replay_identity_fixtures((FIXTURE, FIXTURE), expectation=self.expectation)
        self.assertFalse(report.passed)
        self.assertEqual(report.duplicate_fixture_ids, ("identity-public-aggregate-001",))
        self.assertTrue(report.duplicate_public_identities)

    def test_mutated_fixture_fails_operation_replay(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["records"][2]["payload"]["observations"][1]["subject_id"] = (
            "public-aggregate-subject-other"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mutated.json"
            path.write_text(json.dumps(fixture), encoding="utf-8")
            report = replay_identity_fixtures((path,), expectation=self.expectation)
        self.assertFalse(report.passed)
        self.assertEqual(report.state, IdentityDataState.REVIEW)

    def test_empty_paths_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            IdentityReplayRunner().replay((), expectation=self.expectation)

    def test_expectation_requires_positive_floors(self) -> None:
        with self.assertRaises(ValidationError):
            IdentityReplayExpectation("fixture", CONTEXT, SOURCES, min_check_count=0)
        with self.assertRaises(ValidationError):
            IdentityReplayExpectation("fixture", CONTEXT, SOURCES, min_positive_count=0)
        with self.assertRaises(ValidationError):
            IdentityReplayExpectation("fixture", CONTEXT, SOURCES, min_negative_control_count=0)

    def test_report_serializes_case_count_and_passed(self) -> None:
        payload = replay_identity_fixtures((FIXTURE,), expectation=self.expectation).to_dict()
        self.assertEqual(payload["case_count"], 1)
        self.assertTrue(payload["passed"])
        self.assertEqual(payload["failed_reasons"], [])


if __name__ == "__main__":
    unittest.main()
