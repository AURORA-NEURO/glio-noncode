"""Focused regression coverage for D485 policy scenarios."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import downloaded_data_quality_d482_history_diff_runtime_registry_history as history_model
from glio_noncode import downloaded_data_quality_d483_history_diff_runtime_registry_history_diff as diff_model
from glio_noncode import downloaded_data_quality_d484_history_diff_runtime_registry_history_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_d485_history_diff_runtime_policy_scenario as scenario_model
from glio_noncode import downloaded_data_quality_d485_history_diff_runtime_policy_scenario_audit as audit_model
from glio_noncode import downloaded_data_quality_d485_history_diff_runtime_policy_scenario_query as query_model
from glio_noncode import downloaded_data_quality_d485_history_diff_runtime_policy_scenario_query_audit as query_audit_model
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json
from tests.test_downloaded_data_quality_d482 import _registries


def _runtimes() -> tuple[runtime_model.HistoryDiffRuntime, runtime_model.HistoryDiffRuntime]:
    blocked, ready, _ = _registries()
    left = history_model.build_history(blocked, history_id="d485-history", snapshot_id="blocked")
    right = history_model.append_history(left, ready, snapshot_id="ready", expected_head=left.entries[-1].content_address)
    diff = diff_model.build_diff(left, right, diff_id="d485-history-diff")
    strict = runtime_model.run_runtime(diff, runtime_id="d485-strict-runtime", policy=runtime_model.build_policy("d485-strict-policy", diff.diff_id, maximum_added=0, maximum_removed=0, maximum_changed=0, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True))
    release = runtime_model.run_runtime(diff, runtime_id="d485-release-runtime", policy=runtime_model.build_policy("d485-release-policy", diff.diff_id, maximum_added=1, maximum_removed=0, maximum_changed=0, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True))
    return strict, release


class D485PolicyScenarioTests(unittest.TestCase):
    def test_mixed_scenario_audit_query_and_persistence(self) -> None:
        strict, release = _runtimes()
        policy = scenario_model.build_policy("d485-controlled-policy", minimum_runtimes=2, minimum_ready=1, maximum_blocked=1, require_at_least_one_blocked=True, allow_mixed=True)
        value = scenario_model.build_scenario((strict, release), scenario_id="d485-controlled-scenario", policy=policy)
        audit = audit_model.audit_scenario(value, (strict, release))
        query = query_model.query_scenario(value, resources=query_model.RESOURCES, limit=query_model.MAX_LIMIT)
        query_audit = query_audit_model.audit_query(query, value)
        self.assertEqual((value.state, value.ready_count, value.blocked_count), ("mixed", 1, 1))
        self.assertTrue(value.release_ready)
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (18, 18, True))
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (12, 12, True))
        self.assertFalse(query.truncated)
        self.assertIn("mixed_outcome", value.risk_flags)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "scenario"
            scenario_model.persist_scenario(value, destination)
            loaded = scenario_model.load_scenario(destination)
            self.assertEqual(loaded.content_address, value.content_address)
            document = json.loads((destination / "policy.json").read_text(encoding="utf-8"))
            document["maximum_blocked"] = 0
            (destination / "policy.json").write_text(canonical_json(document), encoding="utf-8")
            with self.assertRaises(ValidationError):
                scenario_model.load_scenario(destination)

    def test_policy_controls_and_duplicate_identity_are_visible(self) -> None:
        strict, release = _runtimes()
        policy = scenario_model.build_policy("d485-strict-scenario-policy", minimum_runtimes=2, minimum_ready=2, maximum_blocked=0, require_at_least_one_ready=True, allow_mixed=False)
        value = scenario_model.build_scenario((strict, release), scenario_id="d485-strict-scenario", policy=policy)
        failed = {item.check_id for item in value.checks if not item.passed}
        self.assertFalse(value.release_ready)
        self.assertIn("minimum_ready", failed)
        self.assertIn("blocked_budget", failed)
        duplicate = scenario_model.build_scenario((release, release), scenario_id="d485-duplicate-scenario", policy=scenario_model.build_policy("d485-duplicate-policy", minimum_runtimes=2, minimum_ready=1, maximum_blocked=0))
        self.assertIn("unique_runtime_ids", {item.check_id for item in duplicate.checks if not item.passed})
        self.assertFalse(duplicate.release_ready)


if __name__ == "__main__":
    unittest.main()
