"""Focused regression coverage for the D454 registry history layer."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json


class D454RegistryHistoryTests(unittest.TestCase):
    def test_history_replays_append_query_and_head_guards(self) -> None:
        # The historical compatibility chain is intentionally deep. Running
        # the same unittest entry point in a plain interpreter keeps pytest's
        # assertion-rewriting frames from turning that valid chain into a
        # recursion-limit failure.
        if __name__ != "__main__":
            completed = subprocess.run(
                [sys.executable, str(Path(__file__).resolve())],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            return

        from glio_noncode import downloaded_data_quality_d454_runtime_registry_history as history_model
        from glio_noncode import downloaded_data_quality_d454_runtime_registry_history_audit as audit_model
        from glio_noncode import downloaded_data_quality_d454_runtime_registry_history_query as query_model
        from glio_noncode import downloaded_data_quality_d454_runtime_registry_history_query_audit as query_audit_model

        def runtime(runtime_id: str, state: str, release_ready: bool, address: str) -> dict[str, object]:
            return {
                "runtime_id": runtime_id,
                "content_address": address,
                "diff_id": "d454-diff",
                "diff_address": "glio-noncode-d454-diff:fixture",
                "state": state,
                "release_ready": release_ready,
                "check_count": 15,
                "passed_count": 14 if state == "blocked" else 15,
                "item_count": 2,
            }

        blocked_registry = history_model.build_registry_snapshot(
            (runtime("d454-blocked-runtime", "blocked", False, "glio-noncode-d454-runtime:blocked"),),
            registry_id="d454-registry",
        )
        ready_registry = history_model.build_registry_snapshot(
            (runtime("d454-ready-runtime", "ready", True, "glio-noncode-d454-runtime:ready"),),
            registry_id="d454-registry",
        )
        history = history_model.build_history(blocked_registry, history_id="d454-history", snapshot_id="blocked")
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
