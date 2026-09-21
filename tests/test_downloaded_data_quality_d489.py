"""Focused regression coverage for D489 ledger-diff runtimes."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import downloaded_data_quality_d488_gate_decision_ledger_diff as diff_model
from glio_noncode import downloaded_data_quality_d489_gate_decision_ledger_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_d489_gate_decision_ledger_diff_runtime_audit as audit_model
from glio_noncode import downloaded_data_quality_d489_gate_decision_ledger_diff_runtime_query as query_model
from glio_noncode import downloaded_data_quality_d489_gate_decision_ledger_diff_runtime_query_audit as query_audit_model
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json
from tests.test_downloaded_data_quality_d488 import _ledgers


def _diff() -> diff_model.LedgerDiff:
    baseline, candidate = _ledgers()
    policy = diff_model.build_policy(
        "d489-diff-policy",
        baseline.ledger_id,
        candidate.ledger_id,
        minimum_items=2,
        maximum_added=1,
        maximum_removed=0,
        maximum_changed=0,
        allowed_directions=("improved",),
        require_same_scenario=True,
        require_append_only=True,
        require_head_change=True,
        require_accepted=True,
    )
    return diff_model.build_diff(baseline, candidate, diff_id="d489-ledger-diff", policy=policy)


class D489LedgerDiffRuntimeTests(unittest.TestCase):
    def test_strict_release_audit_query_and_persistence(self) -> None:
        diff = _diff()
        strict = runtime_model.run_runtime(
            diff,
            runtime_id="d489-strict-runtime",
            policy=runtime_model.build_policy("d489-strict-policy", diff.diff_id, maximum_added=0, maximum_removed=0, maximum_changed=0, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True),
        )
        release = runtime_model.run_runtime(
            diff,
            runtime_id="d489-release-runtime",
            policy=runtime_model.build_policy("d489-release-policy", diff.diff_id, maximum_added=1, maximum_removed=0, maximum_changed=0, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True),
        )
        release_audit = audit_model.audit_runtime(release, diff)
        release_query = query_model.query_runtime(release, resources=query_model.RESOURCES, limit=query_model.MAX_LIMIT)
        query_audit = query_audit_model.audit_query(release_query, release)
        self.assertFalse(strict.release_ready)
        self.assertTrue(release.release_ready)
        self.assertIn("added_budget", [item.check_id for item in strict.checks if not item.passed])
        self.assertEqual((release_audit.check_count, release_audit.passed_count, release_audit.accepted), (15, 15, True))
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (12, 12, True))
        self.assertFalse(release_query.truncated)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "release"
            runtime_model.persist_runtime(release, destination)
            self.assertEqual(tuple(sorted(path.name for path in destination.iterdir())), tuple(sorted(runtime_model.FILES)))
            loaded = runtime_model.load_runtime(destination, diff)
            self.assertEqual(loaded.content_address, release.content_address)
            document = json.loads((destination / "runtime.json").read_text(encoding="utf-8"))
            document["release_ready"] = False
            (destination / "runtime.json").write_text(canonical_json(document), encoding="utf-8")
            with self.assertRaises(ValidationError):
                runtime_model.load_runtime(destination, diff)

    def test_direction_and_unchanged_controls_block(self) -> None:
        diff = _diff()
        policy = runtime_model.build_policy("d489-direction-policy", diff.diff_id, maximum_added=1, maximum_removed=0, maximum_changed=0, allowed_directions=("regressed",), require_accepted=True, require_state_change=True, allow_unchanged=False)
        value = runtime_model.build_runtime(diff, runtime_id="d489-direction-runtime", policy=policy)
        self.assertFalse(value.release_ready)
        self.assertEqual({item.check_id for item in value.checks if not item.passed}, {"direction_policy", "unchanged_policy", "release_disposition"})


if __name__ == "__main__":
    unittest.main()
