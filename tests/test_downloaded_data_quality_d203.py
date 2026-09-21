"""Focused regression coverage for the D203 history diff layer."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from glio_noncode import downloaded_data_quality_d203_history_diff as diff_model
from glio_noncode import downloaded_data_quality_d203_history_diff_audit as audit_model
from glio_noncode import downloaded_data_quality_d203_history_diff_query as query_model
from glio_noncode import downloaded_data_quality_d203_history_diff_query_audit as query_audit_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history as history_model
from glio_noncode.errors import ValidationError


class D203HistoryDiffTests(unittest.TestCase):
    def test_diff_replays_delta_audit_query_persistence_and_identity_guard(self) -> None:
        registry_model = history_model.registry_model
        runtime_model = registry_model.runtime_model
        source_history_model = runtime_model.diff_model.history_model
        source_registry_model = source_history_model.registry_model
        source_registry = source_registry_model.build_registry((), registry_id="d203-source-registry")
        source_left = source_history_model.build_history(source_registry, history_id="d203-source-history", snapshot_id="baseline")
        source_right = source_history_model.build_history(source_registry, history_id="d203-source-history", snapshot_id="candidate")
        source_diff = runtime_model.diff_model.build_diff(source_left, source_right, diff_id="d203-source-diff")
        ready_runtime = runtime_model.build_runtime(source_diff, runtime_id="d203-ready-runtime", policy=runtime_model.build_policy("d203-ready-policy", source_diff.diff_id, maximum_changed=1))
        blocked_runtime = runtime_model.build_runtime(source_diff, runtime_id="d203-blocked-runtime", policy=runtime_model.build_policy("d203-blocked-policy", source_diff.diff_id, maximum_changed=0))
        registry = registry_model.build_registry((blocked_runtime,), registry_id="d203-registry")
        candidate_registry = registry_model.build_registry((ready_runtime,), registry_id="d203-registry")
        baseline = history_model.build_history(registry, history_id="d203-history", snapshot_id="baseline")
        candidate = history_model.append_history(baseline, candidate_registry, snapshot_id="candidate", expected_head=baseline.entries[-1].content_address)
        value = diff_model.build_diff(baseline, candidate, diff_id="d203-diff")
        audit = audit_model.audit_diff(value)
        query = query_model.query_diff(value, resources=query_model.RESOURCES, change_filter="added", limit=query_model.MAX_LIMIT)
        query_audit = query_audit_model.audit_query(query, value)
        self.assertEqual((value.item_count, value.added_count, value.unchanged_count, value.direction, value.state_transition, value.accepted), (2, 1, 1, "improved", "blocked->ready", True))
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (16, 16, True))
        self.assertEqual((query.total_count, query.returned_count, query.truncated), (2, 2, False))
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (12, 12, True))
        foreign_registry = registry_model.build_registry((ready_runtime,), registry_id="d203-foreign-registry")
        with self.assertRaises(ValidationError):
            diff_model.build_diff(baseline, history_model.build_history(foreign_registry, history_id="d203-history", snapshot_id="foreign"), diff_id="d203-foreign")
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "diff"
            diff_model.persist_diff(value, destination)
            self.assertEqual(tuple(sorted(path.name for path in destination.iterdir())), tuple(sorted(diff_model.FILES)))
            self.assertEqual(diff_model.load_diff(destination).content_address, value.content_address)
            summary = destination / "summary.json"
            summary.write_text(summary.read_text(encoding="utf-8").replace('"direction":"improved"', '"direction":"regressed"', 1), encoding="utf-8")
            with self.assertRaises(ValidationError):
                diff_model.load_diff(destination)


if __name__ == "__main__":
    unittest.main()
