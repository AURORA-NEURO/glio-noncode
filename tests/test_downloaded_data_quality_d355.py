"""Focused regression coverage for the D355 history diff layer."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import downloaded_data_quality_d354_runtime_registry_history as history_model
from glio_noncode import downloaded_data_quality_d355_history_diff as diff_model
from glio_noncode import downloaded_data_quality_d355_history_diff_audit as audit_model
from glio_noncode import downloaded_data_quality_d355_history_diff_query as query_model
from glio_noncode import downloaded_data_quality_d355_history_diff_query_audit as query_audit_model
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json


class D355HistoryDiffTests(unittest.TestCase):
    def test_diff_replays_delta_audit_query_and_identity_guard(self) -> None:
        registry_model = history_model.registry_model
        runtime_model = registry_model.runtime_model
        source_history_model = runtime_model.diff_model.history_model
        source_registry_model = source_history_model.registry_model
        source_registry = source_registry_model.build_registry((), registry_id="d355-source-registry")
        source_left = source_history_model.build_history(source_registry, history_id="d355-source-history", snapshot_id="baseline")
        source_right = source_history_model.build_history(source_registry, history_id="d355-source-history", snapshot_id="candidate")
        source_diff = runtime_model.diff_model.build_diff(source_left, source_right, diff_id="d355-source-diff")
        ready_runtime = runtime_model.build_runtime(source_diff, runtime_id="d355-ready-runtime", policy=runtime_model.build_policy("d355-ready-policy", source_diff.diff_id, maximum_changed=1))
        blocked_runtime = runtime_model.build_runtime(source_diff, runtime_id="d355-blocked-runtime", policy=runtime_model.build_policy("d355-blocked-policy", source_diff.diff_id, maximum_changed=0))
        blocked_registry = registry_model.build_registry((blocked_runtime,), registry_id="d355-registry")
        ready_registry = registry_model.build_registry((ready_runtime,), registry_id="d355-registry")
        baseline = history_model.build_history(blocked_registry, history_id="d355-history", snapshot_id="baseline")
        candidate = history_model.append_history(baseline, ready_registry, snapshot_id="ready", expected_head=baseline.entries[-1].content_address)
        value = diff_model.build_diff(baseline, candidate, diff_id="d355-diff")
        audit = audit_model.audit_diff(value)
        query = query_model.query_diff(value, resources=query_model.RESOURCES, change_filter="added", limit=query_model.MAX_LIMIT)
        query_audit = query_audit_model.audit_query(query, value)
        self.assertEqual((value.item_count, value.added_count, value.unchanged_count, value.direction, value.state_transition, value.accepted), (2, 1, 1, "improved", "blocked->ready", True))
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (16, 16, True))
        self.assertEqual((query.total_count, query.returned_count, query.truncated), (2, 2, False))
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (12, 12, True))
        foreign_registry = registry_model.build_registry((ready_runtime,), registry_id="d355-foreign-registry")
        with self.assertRaises(ValidationError):
            diff_model.build_diff(baseline, history_model.build_history(foreign_registry, history_id="d355-history", snapshot_id="foreign"), diff_id="d355-foreign")

        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "diff"
            diff_model.persist_diff(value, destination)
            reloaded = diff_model.load_diff(destination)
            self.assertEqual(reloaded.content_address, value.content_address)
            self.assertEqual(diff_model.diff_json(reloaded), diff_model.diff_json(value))

            diff_document = json.loads((destination / "diff.json").read_text(encoding="utf-8"))
            diff_document["accepted"] = False
            (destination / "diff.json").write_text(canonical_json(diff_document), encoding="utf-8")
            with self.assertRaises(ValidationError):
                diff_model.load_diff(destination)


if __name__ == "__main__":
    unittest.main()
