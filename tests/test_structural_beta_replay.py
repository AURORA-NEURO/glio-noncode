"""Replay-integrity tests for Domain 02 C05-C08."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.structural_beta_public_data import StructuralBetaFixtureCatalog
from glio_noncode.structural_beta_replay import (
    StructuralBetaReplayExpectation,
    replay_structural_beta_fixtures,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "structural-beta-public-aggregate.json"
CONTEXT = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"


class StructuralBetaReplayTests(unittest.TestCase):
    def _expectation(self) -> StructuralBetaReplayExpectation:
        catalog = StructuralBetaFixtureCatalog.from_file(FIXTURE)
        return StructuralBetaReplayExpectation(
            fixture_id=catalog.fixture_id,
            context_key=CONTEXT,
            source_ids=catalog.source_ids,
        )

    def test_replay_passes_with_identity_context_source_and_floor(self) -> None:
        report = replay_structural_beta_fixtures(
            [str(FIXTURE)], expectation=self._expectation(), required_context_key=CONTEXT
        )
        self.assertTrue(report.passed)
        self.assertEqual(report.cases[0].issue_codes, ())
        self.assertRegex(report.content_address, r"^sha256:[0-9a-f]{64}$")

    def test_replay_rejects_duplicate_fixture_identity_and_address(self) -> None:
        report = replay_structural_beta_fixtures(
            [str(FIXTURE), str(FIXTURE)], expectation=self._expectation()
        )
        self.assertFalse(report.passed)
        self.assertIn("duplicate_fixture_identity", report.issue_codes)
        self.assertIn("duplicate_fixture_address", report.issue_codes)

    def test_replay_rejects_wrong_expected_context(self) -> None:
        expectation = self._expectation()
        wrong = copy.copy(expectation)
        object.__setattr__(wrong, "context_key", "GRCh38|diffuse_glioma|adult|other|tumor_core|pre_treatment")
        report = replay_structural_beta_fixtures([str(FIXTURE)], expectation=wrong)
        self.assertFalse(report.passed)
        self.assertIn("expected_context_mismatch", report.cases[0].issue_codes)

    def test_replay_rejects_wrong_source_set(self) -> None:
        expectation = copy.copy(self._expectation())
        object.__setattr__(expectation, "source_ids", ("only-one-source",))
        report = replay_structural_beta_fixtures([str(FIXTURE)], expectation=expectation)
        self.assertFalse(report.passed)
        self.assertIn("source_set_mismatch", report.cases[0].issue_codes)

    def test_replay_rejects_context_drift_across_fixture_paths(self) -> None:
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        raw["fixture_id"] = "structural-beta-context-drift"
        raw["context_key"] = "GRCh38|diffuse_glioma|adult|other|tumor_core|pre_treatment"
        raw["positives"] = [dict(item, context_key=raw["context_key"]) for item in raw["positives"]]
        raw["controls"] = [dict(item, context_key=raw["context_key"]) for item in raw["controls"]]
        with tempfile.TemporaryDirectory() as directory:
            alternate = Path(directory) / "drift.json"
            alternate.write_text(json.dumps(raw), encoding="utf-8")
            report = replay_structural_beta_fixtures([str(FIXTURE), str(alternate)])
        self.assertFalse(report.passed)
        self.assertIn("cross_fixture_context_drift", report.issue_codes)

    def test_replay_requires_at_least_one_path(self) -> None:
        with self.assertRaises(ValidationError):
            replay_structural_beta_fixtures([])


if __name__ == "__main__":
    unittest.main()
