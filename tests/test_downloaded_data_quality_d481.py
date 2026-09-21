"""Focused regression coverage for the D481 history-diff runtime registry."""

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
from glio_noncode import downloaded_data_quality_d480_release_batch_history_diff_runtime_audit as runtime_audit_model
from glio_noncode import downloaded_data_quality_d481_history_diff_runtime_registry as registry_model
from glio_noncode import downloaded_data_quality_d481_history_diff_runtime_registry_audit as audit_model
from glio_noncode import downloaded_data_quality_d481_history_diff_runtime_registry_query as query_model
from glio_noncode import downloaded_data_quality_d481_history_diff_runtime_registry_query_audit as query_audit_model
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json


def _diff() -> diff_model.HistoryDiff:
    source_history = source_diff_model.history_model

    def fixture(runtime_id: str, state: str, release_ready: bool, address: str) -> dict[str, object]:
        return {"runtime_id": runtime_id, "content_address": address, "diff_id": "d481-source-diff", "diff_address": "glio-noncode-d481-source-diff:fixture", "state": state, "release_ready": release_ready, "check_count": 15, "passed_count": 14 if state == "blocked" else 15, "item_count": 2}

    blocked_registry = source_history.build_registry_snapshot((fixture("d481-blocked-runtime", "blocked", False, "glio-noncode-d481-runtime:blocked"),), registry_id="d481-registry")
    ready_registry = source_history.build_registry_snapshot((fixture("d481-ready-runtime", "ready", True, "glio-noncode-d481-runtime:ready"),), registry_id="d481-registry")
    baseline = source_history.build_history(blocked_registry, history_id="d481-source-history", snapshot_id="blocked")
    candidate = source_history.append_history(baseline, ready_registry, snapshot_id="ready", expected_head=baseline.entries[-1].content_address)
    source_diff = source_diff_model.build_diff(baseline, candidate, diff_id="d481-source-diff")
    old_strict = old_runtime_model.run_runtime(source_diff, runtime_id="d481-old-strict", policy=old_runtime_model.build_policy("d481-old-strict-policy", source_diff.diff_id, maximum_added=0, maximum_removed=0, maximum_changed=0, allowed_directions=("improved", "changed", "unchanged"), require_accepted=True, require_state_change=False, allow_unchanged=True))
    old_release = old_runtime_model.run_runtime(source_diff, runtime_id="d481-old-release", policy=old_runtime_model.build_policy("d481-old-release-policy", source_diff.diff_id, maximum_added=1, maximum_removed=0, maximum_changed=1, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True))
    blocked_batch = batch_model.build_batch((old_strict, old_release), batch_id="d481-blocked-batch", policy=batch_model.build_policy("d481-all-ready-policy", minimum_runtimes=2, minimum_ready=2, maximum_blocked=0, require_same_diff=True, require_audited=False, require_release_ready=True))
    ready_batch = batch_model.build_batch((old_strict, old_release), batch_id="d481-ready-batch", policy=batch_model.build_policy("d481-controlled-policy", minimum_runtimes=2, minimum_ready=1, maximum_blocked=1, require_same_diff=True, require_audited=False, require_release_ready=False))
    left = history_model.build_history(blocked_batch, history_id="d481-release-history", snapshot_id="blocked")
    right = history_model.append_history(left, ready_batch, snapshot_id="ready", expected_head=left.entries[-1].content_address)
    return diff_model.build_diff(left, right, diff_id="d481-release-diff")


class D481HistoryDiffRuntimeRegistryTests(unittest.TestCase):
    def test_registry_audit_query_and_persistence(self) -> None:
        diff = _diff()
        strict = runtime_model.run_runtime(diff, runtime_id="d481-strict-runtime", policy=runtime_model.build_policy("d481-strict-policy", diff.diff_id, maximum_added=0, maximum_removed=0, maximum_changed=0, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True))
        release = runtime_model.run_runtime(diff, runtime_id="d481-release-runtime", policy=runtime_model.build_policy("d481-release-policy", diff.diff_id, maximum_added=1, maximum_removed=0, maximum_changed=0, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True))
        strict_audit = runtime_audit_model.audit_runtime(strict, diff)
        release_audit = runtime_audit_model.audit_runtime(release, diff)
        policy = registry_model.build_policy("d481-controlled-policy", minimum_runtimes=2, minimum_ready=1, maximum_blocked=1, require_same_diff=True, require_same_direction=True, require_audited=True, require_release_ready=False)
        registry = registry_model.run_registry((strict, release), registry_id="d481-controlled-registry", policy=policy, audit_addresses={strict.runtime_id: strict_audit.content_address, release.runtime_id: release_audit.content_address})
        audit = audit_model.audit_registry(registry, (strict, release))
        query = query_model.query_registry(registry, resources=query_model.RESOURCES, limit=query_model.MAX_LIMIT)
        query_audit = query_audit_model.audit_query(query, registry)
        self.assertFalse(strict.release_ready)
        self.assertTrue(release.release_ready)
        self.assertTrue(registry.release_ready)
        self.assertEqual((registry.ready_count, registry.blocked_count, registry.audited_count), (1, 1, 2))
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (16, 16, True))
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (12, 12, True))
        self.assertFalse(query.truncated)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "registry"
            registry_model.persist_registry(registry, destination)
            loaded = registry_model.load_registry(destination)
            self.assertEqual(loaded.content_address, registry.content_address)
            document = json.loads((destination / "registry.json").read_text(encoding="utf-8"))
            document["release_ready"] = False
            (destination / "registry.json").write_text(canonical_json(document), encoding="utf-8")
            with self.assertRaises(ValidationError):
                registry_model.load_registry(destination)

    def test_all_ready_policy_reports_controlled_failures(self) -> None:
        diff = _diff()
        strict = runtime_model.run_runtime(diff, runtime_id="d481-strict-preview", policy=runtime_model.build_policy("d481-strict-preview-policy", diff.diff_id, maximum_added=0, maximum_removed=0, maximum_changed=0, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True))
        release = runtime_model.run_runtime(diff, runtime_id="d481-release-preview", policy=runtime_model.build_policy("d481-release-preview-policy", diff.diff_id, maximum_added=1, maximum_removed=0, maximum_changed=0, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True))
        policy = registry_model.build_policy("d481-all-ready-policy", minimum_runtimes=2, minimum_ready=2, maximum_blocked=0, require_same_diff=True, require_same_direction=True, require_audited=False, require_release_ready=True)
        registry = registry_model.build_registry((strict, release), registry_id="d481-all-ready-registry", policy=policy)
        self.assertFalse(registry.release_ready)
        self.assertEqual({item.check_id for item in registry.checks if not item.passed}, {"minimum_ready", "blocked_budget", "release_ready_policy"})


if __name__ == "__main__":
    unittest.main()
