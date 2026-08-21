from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.specimen_beta_frontier_public_data import SpecimenBetaFrontierFixtureCatalog
from glio_noncode.specimen_beta_frontier_replay import (
    SpecimenBetaFrontierReplayExpectation,
    replay_specimen_beta_frontier_fixtures,
)

FIXTURE = Path("examples/specimen-beta-frontier-public-aggregate.json")


class SpecimenBetaFrontierReplayTests(unittest.TestCase):
    def _expectation(self) -> SpecimenBetaFrontierReplayExpectation:
        catalog = SpecimenBetaFrontierFixtureCatalog.from_file(FIXTURE)
        return SpecimenBetaFrontierReplayExpectation(
            catalog.fixture_id,
            catalog.context_key,
            catalog.source_ids,
        )

    def test_canonical_fixture_replays(self) -> None:
        report = replay_specimen_beta_frontier_fixtures([FIXTURE], expectation=self._expectation())
        self.assertTrue(report.passed)
        self.assertEqual(report.issue_codes, ())

    def test_context_drift_fails_replay(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["context_key"] = "GRCh38|diffuse_glioma|adult|other|tumor_core|pre_treatment"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mutated.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            report = replay_specimen_beta_frontier_fixtures([path], expectation=self._expectation())
        self.assertFalse(report.passed)
        self.assertIn("context_mismatch", report.issue_codes)

    def test_source_drift_fails_replay(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["sources"][0]["source_id"] = "different-source"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mutated.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            report = replay_specimen_beta_frontier_fixtures([path], expectation=self._expectation())
        self.assertIn("source_set_mismatch", report.issue_codes)

    def test_duplicate_record_ids_fail_replay(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["controls"][0]["record_id"] = payload["positives"][0]["record_id"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mutated.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            report = replay_specimen_beta_frontier_fixtures([path], expectation=self._expectation())
        self.assertIn("duplicate_record_id", report.issue_codes)

    def test_changed_check_floor_fails_replay(self) -> None:
        expectation = self._expectation()
        changed = SpecimenBetaFrontierReplayExpectation(
            expectation.fixture_id,
            expectation.context_key,
            expectation.source_ids,
            minimum_checks=73,
        )
        report = replay_specimen_beta_frontier_fixtures([FIXTURE], expectation=changed)
        self.assertIn("check_floor", report.issue_codes)

    def test_replay_address_is_deterministic(self) -> None:
        first = replay_specimen_beta_frontier_fixtures([FIXTURE], expectation=self._expectation())
        second = replay_specimen_beta_frontier_fixtures([FIXTURE], expectation=self._expectation())
        self.assertEqual(first.content_address, second.content_address)


if __name__ == "__main__":
    unittest.main()
