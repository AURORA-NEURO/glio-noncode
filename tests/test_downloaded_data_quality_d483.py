"""Focused regression coverage for D483 runtime registry history diffs."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import downloaded_data_quality_d482_history_diff_runtime_registry_history as history_model
from glio_noncode import downloaded_data_quality_d483_history_diff_runtime_registry_history_diff as diff_model
from glio_noncode import downloaded_data_quality_d483_history_diff_runtime_registry_history_diff_audit as audit_model
from glio_noncode import downloaded_data_quality_d483_history_diff_runtime_registry_history_diff_query as query_model
from glio_noncode import downloaded_data_quality_d483_history_diff_runtime_registry_history_diff_query_audit as query_audit_model
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json
from tests.test_downloaded_data_quality_d482 import _registries


class D483RuntimeRegistryHistoryDiffTests(unittest.TestCase):
    def test_diff_replays_direction_audit_query_and_persistence(self) -> None:
        blocked, ready, _ = _registries()
        left = history_model.build_history(blocked, history_id="d483-history", snapshot_id="blocked")
        right = history_model.append_history(left, ready, snapshot_id="ready", expected_head=left.entries[-1].content_address)
        value = diff_model.run_diff(left, right, diff_id="d483-history-diff")
        audit = audit_model.audit_diff(value, left, right)
        query = query_model.query_diff(value, resources=("items", "changes", "direction"), change_filter="added", limit=query_model.MAX_LIMIT)
        query_audit = query_audit_model.audit_query(query, value)
        self.assertEqual((value.added_count, value.removed_count, value.changed_count, value.unchanged_count), (1, 0, 0, 1))
        self.assertEqual((value.direction, value.state_transition), ("improved", "blocked->ready"))
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (16, 16, True))
        self.assertEqual((query.total_count, query.returned_count, query.truncated), (2, 2, False))
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (12, 12, True))
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "diff"
            diff_model.persist_diff(value, destination)
            loaded = diff_model.load_diff(destination)
            self.assertEqual(loaded.content_address, value.content_address)
            document = json.loads((destination / "diff.json").read_text(encoding="utf-8"))
            document["direction"] = "regressed"
            (destination / "diff.json").write_text(canonical_json(document), encoding="utf-8")
            with self.assertRaises(ValidationError):
                diff_model.load_diff(destination)

    def test_changed_fields_and_history_identity_guard(self) -> None:
        blocked, ready, _ = _registries()
        left = history_model.build_history(blocked, history_id="d483-changed-history", snapshot_id="same")
        right = history_model.build_history(ready, history_id="d483-changed-history", snapshot_id="same")
        value = diff_model.build_diff(left, right, diff_id="d483-changed-diff")
        self.assertEqual((value.changed_count, value.added_count, value.unchanged_count, value.direction), (1, 0, 0, "improved"))
        self.assertIn("registry_id", value.items[0].changed_fields)
        self.assertIn("release_ready", value.items[0].changed_fields)
        with self.assertRaises(ValidationError):
            diff_model.build_diff(left, history_model.build_history(ready, history_id="other-history", snapshot_id="same"))


if __name__ == "__main__":
    unittest.main()
