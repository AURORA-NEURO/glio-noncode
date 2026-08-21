"""Replay integrity tests for the Domain 02 structural evidence fixture."""

from __future__ import annotations

import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.structural_public_data import StructuralFixtureCatalog
from glio_noncode.structural_replay import (
    StructuralReplayExpectation,
    replay_structural_fixtures,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "structural-public-aggregate.json"
CONTEXT = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"


class StructuralReplayTests(unittest.TestCase):
    def _expectation(self) -> StructuralReplayExpectation:
        catalog = StructuralFixtureCatalog.from_file(FIXTURE)
        return StructuralReplayExpectation(
            fixture_id=catalog.fixture_id,
            context_key=CONTEXT,
            source_ids=catalog.source_ids,
            minimum_checks=30,
            minimum_positive_records=4,
            minimum_control_records=8,
        )

    def test_single_fixture_replay_passes(self) -> None:
        report = replay_structural_fixtures(
            (str(FIXTURE),),
            expectation=self._expectation(),
            required_context_key=CONTEXT,
        )
        self.assertTrue(report.passed)
        self.assertEqual(report.issue_codes, ())
        self.assertEqual(len(report.cases), 1)
        self.assertTrue(report.cases[0].passed)
        self.assertRegex(report.content_address, r"^sha256:[0-9a-f]{64}$")

    def test_duplicate_fixture_identity_is_rejected(self) -> None:
        report = replay_structural_fixtures(
            (str(FIXTURE), str(FIXTURE)),
            expectation=self._expectation(),
            required_context_key=CONTEXT,
        )
        self.assertFalse(report.passed)
        self.assertIn("duplicate_fixture_identity", report.issue_codes)
        self.assertIn("duplicate_fixture_address", report.issue_codes)

    def test_wrong_context_is_rejected(self) -> None:
        expectation = self._expectation()
        report = replay_structural_fixtures(
            (str(FIXTURE),),
            expectation=StructuralReplayExpectation(
                expectation.fixture_id,
                CONTEXT.replace("GRCh38", "GRCh37"),
                expectation.source_ids,
            ),
            required_context_key=CONTEXT.replace("GRCh38", "GRCh37"),
        )
        self.assertFalse(report.passed)
        self.assertIn("expected_context_mismatch", report.cases[0].issue_codes)
        self.assertIn("context_mismatch", report.cases[0].issue_codes)

    def test_wrong_source_set_is_rejected(self) -> None:
        expectation = self._expectation()
        report = replay_structural_fixtures(
            (str(FIXTURE),),
            expectation=StructuralReplayExpectation(
                expectation.fixture_id,
                expectation.context_key,
                ("only-one-source",),
            ),
        )
        self.assertFalse(report.passed)
        self.assertIn("source_set_mismatch", report.cases[0].issue_codes)

    def test_check_floor_is_enforced(self) -> None:
        expectation = self._expectation()
        report = replay_structural_fixtures(
            (str(FIXTURE),),
            expectation=StructuralReplayExpectation(
                expectation.fixture_id,
                expectation.context_key,
                expectation.source_ids,
                minimum_checks=1000,
            ),
        )
        self.assertFalse(report.passed)
        self.assertIn("check_floor", report.cases[0].issue_codes)

    def test_replay_case_addresses_are_distinct_from_report_address(self) -> None:
        report = replay_structural_fixtures((str(FIXTURE),), expectation=self._expectation())
        self.assertNotEqual(report.content_address, report.cases[0].content_address)
        self.assertTrue(report.cases[0].content_address.startswith("sha256:"))
        self.assertTrue(report.cases[0].evaluation_address.startswith("sha256:"))

    def test_empty_path_list_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            replay_structural_fixtures(())


if __name__ == "__main__":
    unittest.main()
