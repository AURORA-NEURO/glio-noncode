"""Focused regression coverage for the D208 diff runtime layer."""

from __future__ import annotations

import unittest

from glio_noncode import downloaded_data_quality_d207_history_diff as diff_model
from glio_noncode import downloaded_data_quality_d208_history_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_d208_history_diff_runtime_audit as audit_model
from glio_noncode import downloaded_data_quality_d208_history_diff_runtime_query as query_model
from glio_noncode import downloaded_data_quality_d208_history_diff_runtime_query_audit as query_audit_model


class D208DiffRuntimeTests(unittest.TestCase):
    def test_runtime_replays_strict_release_audit_and_query(self) -> None:
        history_model = diff_model.history_model
        source_runtime_model = history_model.registry_model.runtime_model
        source_history_model = source_runtime_model.diff_model.history_model
        source_registry_model = source_history_model.registry_model
        source_registry = source_registry_model.build_registry((), registry_id="d208-source-registry")
        source_left = source_history_model.build_history(source_registry, history_id="d208-source-history", snapshot_id="baseline")
        source_right = source_history_model.build_history(source_registry, history_id="d208-source-history", snapshot_id="candidate")
        source_diff = source_runtime_model.diff_model.build_diff(source_left, source_right, diff_id="d208-source-diff")
        ready_runtime = source_runtime_model.build_runtime(source_diff, runtime_id="d208-ready-source-runtime", policy=source_runtime_model.build_policy("d208-ready-source-policy", source_diff.diff_id, maximum_changed=1))
        blocked_runtime = source_runtime_model.build_runtime(source_diff, runtime_id="d208-blocked-source-runtime", policy=source_runtime_model.build_policy("d208-blocked-source-policy", source_diff.diff_id, maximum_changed=0))
        blocked_registry = history_model.registry_model.build_registry((blocked_runtime,), registry_id="d208-registry")
        ready_registry = history_model.registry_model.build_registry((ready_runtime,), registry_id="d208-registry")
        baseline = history_model.build_history(blocked_registry, history_id="d208-history", snapshot_id="blocked")
        candidate = history_model.append_history(baseline, ready_registry, snapshot_id="ready", expected_head=baseline.entries[-1].content_address)
        diff = diff_model.build_diff(baseline, candidate, diff_id="d208-diff")
        strict = runtime_model.run_runtime(diff, runtime_id="d208-strict-runtime", policy=runtime_model.build_policy("d208-strict-policy", diff.diff_id, maximum_added=0, maximum_removed=0, maximum_changed=0, allowed_directions=("improved", "changed", "unchanged"), require_accepted=True, require_state_change=False, allow_unchanged=True))
        release = runtime_model.run_runtime(diff, runtime_id="d208-release-runtime", policy=runtime_model.build_policy("d208-release-policy", diff.diff_id, maximum_added=1, maximum_removed=0, maximum_changed=0, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True))
        strict_audit = audit_model.audit_runtime(strict, diff)
        release_audit = audit_model.audit_runtime(release, diff)
        release_query = query_model.query_runtime(release, resources=query_model.RESOURCES, limit=query_model.MAX_LIMIT)
        release_query_audit = query_audit_model.audit_query(release_query, release)
        self.assertFalse(strict.release_ready)
        self.assertTrue(release.release_ready)
        self.assertEqual((strict_audit.check_count, strict_audit.passed_count, strict_audit.accepted), (15, 15, True))
        self.assertEqual((release_audit.check_count, release_audit.passed_count, release_audit.accepted), (15, 15, True))
        self.assertFalse(release_query.truncated)
        self.assertEqual((release_query_audit.check_count, release_query_audit.passed_count, release_query_audit.accepted), (12, 12, True))


if __name__ == "__main__":
    unittest.main()
