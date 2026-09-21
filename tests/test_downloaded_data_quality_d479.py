"""Focused regression coverage for the D479 release-batch history diff layer."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import downloaded_data_quality_d475_history_diff as diff_source_model
from glio_noncode import downloaded_data_quality_d476_history_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_d477_release_batch as batch_model
from glio_noncode import downloaded_data_quality_d478_release_batch_history as history_model
from glio_noncode import downloaded_data_quality_d479_release_batch_history_diff as diff_model
from glio_noncode import downloaded_data_quality_d479_release_batch_history_diff_audit as audit_model
from glio_noncode import downloaded_data_quality_d479_release_batch_history_diff_query as query_model
from glio_noncode import downloaded_data_quality_d479_release_batch_history_diff_query_audit as query_audit_model
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json


def _histories() -> tuple[history_model.ReleaseBatchHistory, history_model.ReleaseBatchHistory]:
    source_history = diff_source_model.history_model

    def runtime(runtime_id: str, state: str, release_ready: bool, address: str) -> dict[str, object]:
        return {"runtime_id": runtime_id, "content_address": address, "diff_id": "d479-diff", "diff_address": "glio-noncode-d479-diff:fixture", "state": state, "release_ready": release_ready, "check_count": 15, "passed_count": 14 if state == "blocked" else 15, "item_count": 2}

    blocked_registry = source_history.build_registry_snapshot((runtime("d479-blocked-runtime", "blocked", False, "glio-noncode-d479-runtime:blocked"),), registry_id="d479-registry")
    ready_registry = source_history.build_registry_snapshot((runtime("d479-ready-runtime", "ready", True, "glio-noncode-d479-runtime:ready"),), registry_id="d479-registry")
    baseline = source_history.build_history(blocked_registry, history_id="d479-source-history", snapshot_id="blocked")
    candidate = source_history.append_history(baseline, ready_registry, snapshot_id="ready", expected_head=baseline.entries[-1].content_address)
    source_diff = diff_source_model.build_diff(baseline, candidate, diff_id="d479-diff")
    strict = runtime_model.run_runtime(source_diff, runtime_id="d479-strict-runtime", policy=runtime_model.build_policy("d479-strict-policy", source_diff.diff_id, maximum_added=0, maximum_removed=0, maximum_changed=0, allowed_directions=("improved", "changed", "unchanged"), require_accepted=True, require_state_change=False, allow_unchanged=True))
    release = runtime_model.run_runtime(source_diff, runtime_id="d479-release-runtime", policy=runtime_model.build_policy("d479-release-policy", source_diff.diff_id, maximum_added=1, maximum_removed=0, maximum_changed=1, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True))
    blocked_batch = batch_model.build_batch((strict, release), batch_id="d479-blocked-batch", policy=batch_model.build_policy("d479-all-ready-policy", minimum_runtimes=2, minimum_ready=2, maximum_blocked=0, require_same_diff=True, require_audited=False, require_release_ready=True))
    ready_batch = batch_model.build_batch((strict, release), batch_id="d479-ready-batch", policy=batch_model.build_policy("d479-controlled-policy", minimum_runtimes=2, minimum_ready=1, maximum_blocked=1, require_same_diff=True, require_audited=False, require_release_ready=False))
    left = history_model.build_history(blocked_batch, history_id="d479-release-history", snapshot_id="blocked")
    right = history_model.append_history(left, ready_batch, snapshot_id="ready", expected_head=left.entries[-1].content_address)
    return left, right


class D479ReleaseBatchHistoryDiffTests(unittest.TestCase):
    def test_diff_replays_direction_audit_query_and_persistence(self) -> None:
        left, right = _histories()
        value = diff_model.run_diff(left, right, diff_id="d479-release-diff")
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

    def test_same_history_identity_is_required(self) -> None:
        left, right = _histories()
        with self.assertRaises(ValidationError):
            diff_model.build_diff(left, history_model.build_history(batch_model.build_batch(()), history_id="other"))


if __name__ == "__main__":
    unittest.main()
