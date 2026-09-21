"""Focused regression coverage for D482 runtime registry histories."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import downloaded_data_quality_d480_release_batch_history_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_d481_history_diff_runtime_registry as registry_model
from glio_noncode import downloaded_data_quality_d482_history_diff_runtime_registry_history as history_model
from glio_noncode import downloaded_data_quality_d482_history_diff_runtime_registry_history_audit as audit_model
from glio_noncode import downloaded_data_quality_d482_history_diff_runtime_registry_history_query as query_model
from glio_noncode import downloaded_data_quality_d482_history_diff_runtime_registry_history_query_audit as query_audit_model
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json
from tests.test_downloaded_data_quality_d481 import _diff


def _registries() -> tuple[registry_model.RuntimeRegistry, registry_model.RuntimeRegistry, registry_model.RuntimeRegistry]:
    diff = _diff()
    strict = runtime_model.run_runtime(diff, runtime_id="d482-strict-runtime", policy=runtime_model.build_policy("d482-strict-policy", diff.diff_id, maximum_added=0, maximum_removed=0, maximum_changed=0, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True))
    release = runtime_model.run_runtime(diff, runtime_id="d482-release-runtime", policy=runtime_model.build_policy("d482-release-policy", diff.diff_id, maximum_added=1, maximum_removed=0, maximum_changed=0, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True))
    all_ready = registry_model.build_registry((strict, release), registry_id="d482-all-ready-registry", policy=registry_model.build_policy("d482-all-ready-policy", minimum_runtimes=2, minimum_ready=2, maximum_blocked=0, require_same_diff=True, require_same_direction=True, require_audited=False, require_release_ready=True))
    controlled = registry_model.build_registry((strict, release), registry_id="d482-controlled-registry", policy=registry_model.build_policy("d482-controlled-policy", minimum_runtimes=2, minimum_ready=1, maximum_blocked=1, require_same_diff=True, require_same_direction=True, require_audited=False, require_release_ready=False))
    regressed = registry_model.build_registry((strict, release), registry_id="d482-regressed-registry", policy=registry_model.build_policy("d482-regressed-policy", minimum_runtimes=2, minimum_ready=2, maximum_blocked=0, require_same_diff=True, require_same_direction=True, require_audited=False, require_release_ready=True))
    return all_ready, controlled, regressed


class D482RuntimeRegistryHistoryTests(unittest.TestCase):
    def test_history_promotes_replays_audit_query_and_persistence(self) -> None:
        blocked, ready, _ = _registries()
        history = history_model.build_history(blocked, history_id="d482-history", snapshot_id="blocked")
        history = history_model.append_history(history, ready, snapshot_id="ready", expected_head=history.entries[-1].content_address)
        history_audit = audit_model.audit_history(history, (blocked, ready))
        query = query_model.query_history(history, resources=query_model.RESOURCES, limit=query_model.MAX_LIMIT)
        query_audit = query_audit_model.audit_query(query, history)
        promoted = query_model.query_history(history, resources=("transitions",), transition_filter="promoted", limit=query_model.MAX_LIMIT)
        self.assertEqual((history.entry_count, history.initial_count, history.promoted_count, history.latest_state, history.latest_release_ready), (2, 1, 1, "ready", True))
        self.assertEqual((history_audit.check_count, history_audit.passed_count, history_audit.accepted), (16, 16, True))
        self.assertEqual((query.total_count, query.returned_count, query.truncated), (29, 29, False))
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (12, 12, True))
        self.assertEqual((promoted.total_count, promoted.returned_count, promoted.rows[0].transition), (1, 1, "promoted"))
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

    def test_head_duplicate_and_regression_guards(self) -> None:
        blocked, ready, regressed = _registries()
        history = history_model.build_history(blocked, history_id="d482-guards", snapshot_id="blocked")
        with self.assertRaises(ValidationError):
            history_model.append_history(history, ready, expected_head="wrong-head")
        history = history_model.append_history(history, ready, snapshot_id="ready", expected_head=history.entries[-1].content_address)
        with self.assertRaises(ValidationError):
            history_model.append_history(history, ready, snapshot_id="duplicate-registry")
        with self.assertRaises(ValidationError):
            history_model.append_history(history, regressed, snapshot_id="ready")
        history = history_model.append_history(history, regressed, snapshot_id="regressed", expected_head=history.entries[-1].content_address)
        self.assertEqual((history.regressed_count, history.latest_state, history.latest_release_ready), (1, "blocked", False))
        history_model.verify_history(history)


if __name__ == "__main__":
    unittest.main()
