"""Focused regression coverage for the D480 history-diff runtime layer."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import downloaded_data_quality_d475_history_diff as source_diff_model
from glio_noncode import downloaded_data_quality_d476_history_diff_runtime as old_runtime_model
from glio_noncode import downloaded_data_quality_d477_release_batch as batch_model
from glio_noncode import downloaded_data_quality_d478_release_batch_history as history_model
from glio_noncode import downloaded_data_quality_d479_release_batch_history_diff as diff_model
from glio_noncode import downloaded_data_quality_d480_release_batch_history_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_d480_release_batch_history_diff_runtime_audit as audit_model
from glio_noncode import downloaded_data_quality_d480_release_batch_history_diff_runtime_query as query_model
from glio_noncode import downloaded_data_quality_d480_release_batch_history_diff_runtime_query_audit as query_audit_model
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json


def _diff() -> diff_model.HistoryDiff:
    source_history = source_diff_model.history_model

    def fixture(runtime_id: str, state: str, release_ready: bool, address: str) -> dict[str, object]:
        return {"runtime_id": runtime_id, "content_address": address, "diff_id": "d480-source-diff", "diff_address": "glio-noncode-d480-source-diff:fixture", "state": state, "release_ready": release_ready, "check_count": 15, "passed_count": 14 if state == "blocked" else 15, "item_count": 2}

    blocked_registry = source_history.build_registry_snapshot((fixture("d480-blocked-runtime", "blocked", False, "glio-noncode-d480-runtime:blocked"),), registry_id="d480-registry")
    ready_registry = source_history.build_registry_snapshot((fixture("d480-ready-runtime", "ready", True, "glio-noncode-d480-runtime:ready"),), registry_id="d480-registry")
    baseline = source_history.build_history(blocked_registry, history_id="d480-source-history", snapshot_id="blocked")
    candidate = source_history.append_history(baseline, ready_registry, snapshot_id="ready", expected_head=baseline.entries[-1].content_address)
    source_diff = source_diff_model.build_diff(baseline, candidate, diff_id="d480-source-diff")
    old_strict = old_runtime_model.run_runtime(source_diff, runtime_id="d480-old-strict", policy=old_runtime_model.build_policy("d480-old-strict-policy", source_diff.diff_id, maximum_added=0, maximum_removed=0, maximum_changed=0, allowed_directions=("improved", "changed", "unchanged"), require_accepted=True, require_state_change=False, allow_unchanged=True))
    old_release = old_runtime_model.run_runtime(source_diff, runtime_id="d480-old-release", policy=old_runtime_model.build_policy("d480-old-release-policy", source_diff.diff_id, maximum_added=1, maximum_removed=0, maximum_changed=1, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True))
    blocked_batch = batch_model.build_batch((old_strict, old_release), batch_id="d480-blocked-batch", policy=batch_model.build_policy("d480-all-ready-policy", minimum_runtimes=2, minimum_ready=2, maximum_blocked=0, require_same_diff=True, require_audited=False, require_release_ready=True))
    ready_batch = batch_model.build_batch((old_strict, old_release), batch_id="d480-ready-batch", policy=batch_model.build_policy("d480-controlled-policy", minimum_runtimes=2, minimum_ready=1, maximum_blocked=1, require_same_diff=True, require_audited=False, require_release_ready=False))
    left = history_model.build_history(blocked_batch, history_id="d480-release-history", snapshot_id="blocked")
    right = history_model.append_history(left, ready_batch, snapshot_id="ready", expected_head=left.entries[-1].content_address)
    return diff_model.build_diff(left, right, diff_id="d480-release-diff")


class D480HistoryDiffRuntimeTests(unittest.TestCase):
    def test_strict_release_audit_query_and_persistence(self) -> None:
        diff = _diff()
        strict = runtime_model.run_runtime(diff, runtime_id="d480-strict-runtime", policy=runtime_model.build_policy("d480-strict-policy", diff.diff_id, maximum_added=0, maximum_removed=0, maximum_changed=0, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True))
        release = runtime_model.run_runtime(diff, runtime_id="d480-release-runtime", policy=runtime_model.build_policy("d480-release-policy", diff.diff_id, maximum_added=1, maximum_removed=0, maximum_changed=0, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True))
        release_audit = audit_model.audit_runtime(release, diff)
        release_query = query_model.query_runtime(release, resources=query_model.RESOURCES, limit=query_model.MAX_LIMIT)
        query_audit = query_audit_model.audit_query(release_query, release)
        self.assertFalse(strict.release_ready)
        self.assertTrue(release.release_ready)
        self.assertIn("added_budget", [item.check_id for item in strict.checks if not item.passed])
        self.assertEqual((release_audit.check_count, release_audit.passed_count, release_audit.accepted), (15, 15, True))
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (12, 12, True))
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "release"
            runtime_model.persist_runtime(release, destination)
            loaded = runtime_model.load_runtime(destination, diff)
            self.assertEqual(loaded.content_address, release.content_address)
            document = json.loads((destination / "runtime.json").read_text(encoding="utf-8"))
            document["release_ready"] = False
            (destination / "runtime.json").write_text(canonical_json(document), encoding="utf-8")
            with self.assertRaises(ValidationError):
                runtime_model.load_runtime(destination, diff)


if __name__ == "__main__":
    unittest.main()
