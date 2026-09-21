"""Focused regression coverage for the D442 registry history layer."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import downloaded_data_quality_d442_runtime_registry_history as history_model
from glio_noncode import downloaded_data_quality_d442_runtime_registry_history_audit as audit_model
from glio_noncode import downloaded_data_quality_d442_runtime_registry_history_query as query_model
from glio_noncode import downloaded_data_quality_d442_runtime_registry_history_query_audit as query_audit_model
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json


class D442RegistryHistoryTests(unittest.TestCase):
    def test_history_replays_append_query_and_head_guards(self) -> None:
        registry_model = history_model.registry_model
        runtime_model = registry_model.runtime_model
        source_history_model = runtime_model.diff_model.history_model
        source_registry_model = source_history_model.registry_model
        source_registry = source_registry_model.build_registry((), registry_id="d442-source-registry")
        left = source_history_model.build_history(source_registry, history_id="d442-source-history", snapshot_id="baseline")
        right = source_history_model.build_history(source_registry, history_id="d442-source-history", snapshot_id="candidate")
        diff = runtime_model.diff_model.build_diff(left, right, diff_id="d442-diff")
        ready_runtime = runtime_model.build_runtime(diff, runtime_id="d442-ready-runtime", policy=runtime_model.build_policy("d442-ready-policy", diff.diff_id, maximum_changed=1))
        blocked_runtime = runtime_model.build_runtime(diff, runtime_id="d442-blocked-runtime", policy=runtime_model.build_policy("d442-blocked-policy", diff.diff_id, maximum_changed=0))
        blocked_registry = registry_model.build_registry((blocked_runtime,), registry_id="d442-registry")
        ready_registry = registry_model.build_registry((ready_runtime,), registry_id="d442-registry")
        history = history_model.build_history(blocked_registry, history_id="d442-history", snapshot_id="blocked")
        history = history_model.append_history(history, ready_registry, snapshot_id="ready", expected_head=history.entries[-1].content_address)
        audit = audit_model.audit_history(history)
        query = query_model.query_history(history, resources=query_model.RESOURCES, readiness_filter=True, limit=query_model.MAX_LIMIT)
        query_audit = query_audit_model.audit_query(query, history)
        self.assertEqual((history.entry_count, history.latest_state, history.latest_release_ready, tuple(item.transition for item in history.entries)), (2, "ready", True, ("initial", "improved")))
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (16, 16, True))
        self.assertFalse(query.truncated)
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (12, 12, True))
        with self.assertRaises(ValidationError):
            history_model.append_history(history, ready_registry, snapshot_id="duplicate", expected_head=history.entries[-1].content_address)
        with self.assertRaises(ValidationError):
            history_model.append_history(history, blocked_registry, snapshot_id="stale", expected_head=history.entries[0].content_address)

        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "history"
            history_model.persist_history(history, destination)
            reloaded = history_model.load_history(destination)
            self.assertEqual(reloaded.content_address, history.content_address)
            self.assertEqual(history_model.history_json(reloaded), history_model.history_json(history))

            history_document = json.loads((destination / "history.json").read_text(encoding="utf-8"))
            history_document["latest_release_ready"] = False
            (destination / "history.json").write_text(canonical_json(history_document), encoding="utf-8")
            with self.assertRaises(ValidationError):
                history_model.load_history(destination)


if __name__ == "__main__":
    unittest.main()
