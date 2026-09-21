"""Focused regression coverage for the D478 release-batch history layer."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import downloaded_data_quality_d475_history_diff as diff_model
from glio_noncode import downloaded_data_quality_d476_history_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_d477_release_batch as batch_model
from glio_noncode import downloaded_data_quality_d478_release_batch_history as history_model
from glio_noncode import downloaded_data_quality_d478_release_batch_history_audit as audit_model
from glio_noncode import downloaded_data_quality_d478_release_batch_history_query as query_model
from glio_noncode import downloaded_data_quality_d478_release_batch_history_query_audit as query_audit_model
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json


def _batches() -> tuple[batch_model.ReleaseBatch, batch_model.ReleaseBatch]:
    source_history = diff_model.history_model

    def runtime(runtime_id: str, state: str, release_ready: bool, address: str) -> dict[str, object]:
        return {"runtime_id": runtime_id, "content_address": address, "diff_id": "d478-diff", "diff_address": "glio-noncode-d478-diff:fixture", "state": state, "release_ready": release_ready, "check_count": 15, "passed_count": 14 if state == "blocked" else 15, "item_count": 2}

    blocked_registry = source_history.build_registry_snapshot((runtime("d478-blocked-runtime", "blocked", False, "glio-noncode-d478-runtime:blocked"),), registry_id="d478-registry")
    ready_registry = source_history.build_registry_snapshot((runtime("d478-ready-runtime", "ready", True, "glio-noncode-d478-runtime:ready"),), registry_id="d478-registry")
    baseline = source_history.build_history(blocked_registry, history_id="d478-source-history", snapshot_id="blocked")
    candidate = source_history.append_history(baseline, ready_registry, snapshot_id="ready", expected_head=baseline.entries[-1].content_address)
    diff = diff_model.build_diff(baseline, candidate, diff_id="d478-diff")
    strict = runtime_model.run_runtime(diff, runtime_id="d478-strict-runtime", policy=runtime_model.build_policy("d478-strict-policy", diff.diff_id, maximum_added=0, maximum_removed=0, maximum_changed=0, allowed_directions=("improved", "changed", "unchanged"), require_accepted=True, require_state_change=False, allow_unchanged=True))
    release = runtime_model.run_runtime(diff, runtime_id="d478-release-runtime", policy=runtime_model.build_policy("d478-release-policy", diff.diff_id, maximum_added=1, maximum_removed=0, maximum_changed=1, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True))
    blocked = batch_model.build_batch((strict, release), batch_id="d478-blocked-batch", policy=batch_model.build_policy("d478-all-ready-policy", minimum_runtimes=2, minimum_ready=2, maximum_blocked=0, require_same_diff=True, require_audited=False, require_release_ready=True))
    ready = batch_model.build_batch((strict, release), batch_id="d478-ready-batch", policy=batch_model.build_policy("d478-controlled-policy", minimum_runtimes=2, minimum_ready=1, maximum_blocked=1, require_same_diff=True, require_audited=False, require_release_ready=False))
    return blocked, ready


class D478ReleaseBatchHistoryTests(unittest.TestCase):
    def test_history_promotes_and_replays_audit_query_and_persistence(self) -> None:
        blocked, ready = _batches()
        initial = history_model.build_history(blocked, history_id="d478-release-history", snapshot_id="blocked")
        history = history_model.append_history(initial, ready, snapshot_id="ready", expected_head=initial.entries[-1].content_address)
        audit = audit_model.audit_history(history, (blocked, ready))
        query = query_model.query_history(history, resources=("entries", "transitions"), transition_filter="promoted", limit=query_model.MAX_LIMIT)
        query_audit = query_audit_model.audit_query(query, history)
        self.assertEqual(history.latest_state, "ready")
        self.assertTrue(history.latest_release_ready)
        self.assertEqual((history.initial_count, history.promoted_count, history.regressed_count), (1, 1, 0))
        self.assertEqual(history.entries[-1].transition, "promoted")
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (16, 16, True))
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (12, 12, True))
        self.assertGreater(query.total_count, 0)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "history"
            history_model.persist_history(history, destination)
            loaded = history_model.load_history(destination)
            self.assertEqual(loaded.content_address, history.content_address)
            document = json.loads((destination / "history.json").read_text(encoding="utf-8"))
            document["latest_state"] = "blocked"
            (destination / "history.json").write_text(canonical_json(document), encoding="utf-8")
            with self.assertRaises(ValidationError):
                history_model.load_history(destination)

    def test_head_and_duplicate_guards_are_enforced(self) -> None:
        blocked, ready = _batches()
        history = history_model.build_history(blocked, history_id="d478-guard-history", snapshot_id="blocked")
        with self.assertRaises(ValidationError):
            history_model.append_history(history, ready, snapshot_id="ready", expected_head="wrong-head")
        history = history_model.append_history(history, ready, snapshot_id="ready", expected_head=history.entries[-1].content_address)
        with self.assertRaises(ValidationError):
            history_model.append_history(history, ready, snapshot_id="duplicate", expected_head=history.entries[-1].content_address)


if __name__ == "__main__":
    unittest.main()
