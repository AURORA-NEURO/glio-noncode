"""Focused regression coverage for the D477 release-batch layer."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import downloaded_data_quality_d475_history_diff as diff_model
from glio_noncode import downloaded_data_quality_d476_history_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_d476_history_diff_runtime_audit as runtime_audit_model
from glio_noncode import downloaded_data_quality_d477_release_batch as batch_model
from glio_noncode import downloaded_data_quality_d477_release_batch_audit as audit_model
from glio_noncode import downloaded_data_quality_d477_release_batch_query as query_model
from glio_noncode import downloaded_data_quality_d477_release_batch_query_audit as query_audit_model
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json


def _runtimes() -> tuple[runtime_model.DiffRuntime, runtime_model.DiffRuntime]:
    history_model = diff_model.history_model

    def runtime(runtime_id: str, state: str, release_ready: bool, address: str) -> dict[str, object]:
        return {"runtime_id": runtime_id, "content_address": address, "diff_id": "d477-diff", "diff_address": "glio-noncode-d477-diff:fixture", "state": state, "release_ready": release_ready, "check_count": 15, "passed_count": 14 if state == "blocked" else 15, "item_count": 2}

    blocked_registry = history_model.build_registry_snapshot((runtime("d477-blocked-runtime", "blocked", False, "glio-noncode-d477-runtime:blocked"),), registry_id="d477-registry")
    ready_registry = history_model.build_registry_snapshot((runtime("d477-ready-runtime", "ready", True, "glio-noncode-d477-runtime:ready"),), registry_id="d477-registry")
    baseline = history_model.build_history(blocked_registry, history_id="d477-history", snapshot_id="blocked")
    candidate = history_model.append_history(baseline, ready_registry, snapshot_id="ready", expected_head=baseline.entries[-1].content_address)
    diff = diff_model.build_diff(baseline, candidate, diff_id="d477-diff")
    strict = runtime_model.run_runtime(diff, runtime_id="d477-strict-runtime", policy=runtime_model.build_policy("d477-strict-policy", diff.diff_id, maximum_added=0, maximum_removed=0, maximum_changed=0, allowed_directions=("improved", "changed", "unchanged"), require_accepted=True, require_state_change=False, allow_unchanged=True))
    release = runtime_model.run_runtime(diff, runtime_id="d477-release-runtime", policy=runtime_model.build_policy("d477-release-policy", diff.diff_id, maximum_added=1, maximum_removed=0, maximum_changed=1, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True))
    return strict, release


class D477ReleaseBatchTests(unittest.TestCase):
    def test_policy_batch_replays_audits_query_and_persistence(self) -> None:
        strict, release = _runtimes()
        strict_audit = runtime_audit_model.audit_runtime(strict)
        release_audit = runtime_audit_model.audit_runtime(release)
        policy = batch_model.build_policy("d477-controlled-policy", minimum_runtimes=2, minimum_ready=1, maximum_blocked=1, require_same_diff=True, require_audited=True, require_release_ready=False)
        batch = batch_model.run_batch((strict, release), batch_id="d477-controlled-batch", policy=policy, audit_addresses={strict.runtime_id: strict_audit.content_address, release.runtime_id: release_audit.content_address})
        audit = audit_model.audit_batch(batch, (strict, release))
        query = query_model.query_batch(batch, resources=query_model.RESOURCES, limit=query_model.MAX_LIMIT)
        query_audit = query_audit_model.audit_query(query, batch)
        self.assertTrue(batch.release_ready)
        self.assertEqual((batch.item_count, batch.ready_count, batch.blocked_count, batch.audited_count), (2, 1, 1, 2))
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (16, 16, True))
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (12, 12, True))
        self.assertFalse(query.truncated)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "batch"
            batch_model.persist_batch(batch, destination)
            loaded = batch_model.load_batch(destination)
            self.assertEqual(loaded.content_address, batch.content_address)
            self.assertEqual(batch_model.summary_json(loaded), batch_model.summary_json(batch))
            document = json.loads((destination / "batch.json").read_text(encoding="utf-8"))
            document["accepted"] = False
            (destination / "batch.json").write_text(canonical_json(document), encoding="utf-8")
            with self.assertRaises(ValidationError):
                batch_model.load_batch(destination)

    def test_release_all_policy_blocks_mixed_batch(self) -> None:
        strict, release = _runtimes()
        policy = batch_model.build_policy("d477-all-ready-policy", minimum_runtimes=2, minimum_ready=2, maximum_blocked=0, require_same_diff=True, require_audited=False, require_release_ready=True)
        batch = batch_model.build_batch((strict, release), batch_id="d477-all-ready-batch", policy=policy)
        self.assertFalse(batch.release_ready)
        self.assertEqual(batch.state, "blocked")
        self.assertIn("minimum_ready", [item.check_id for item in batch.checks if not item.passed])
        self.assertIn("blocked_budget", [item.check_id for item in batch.checks if not item.passed])


if __name__ == "__main__":
    unittest.main()
