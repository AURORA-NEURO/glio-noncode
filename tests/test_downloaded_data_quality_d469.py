"""Focused regression coverage for the D469 runtime registry layer."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json


class D469RuntimeRegistryTests(unittest.TestCase):
    def test_registry_replays_aggregate_audit_query_and_duplicate_guard(self) -> None:
        # Keep pytest assertion-rewriting frames out of the deep historical
        # compatibility import. The plain unittest process exercises the same
        # production path without changing its behavior.
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

        from glio_noncode import downloaded_data_quality_d469_runtime_registry as registry_model
        from glio_noncode import downloaded_data_quality_d469_runtime_registry_audit as audit_model
        from glio_noncode import downloaded_data_quality_d469_runtime_registry_query as query_model
        from glio_noncode import downloaded_data_quality_d469_runtime_registry_query_audit as query_audit_model

        from glio_noncode import downloaded_data_quality_d467_history_diff as diff_model
        from glio_noncode import downloaded_data_quality_d468_history_diff_runtime as runtime_model

        history_model = diff_model.history_model
        def runtime(runtime_id: str, state: str, release_ready: bool, address: str) -> dict[str, object]:
            return {
                "runtime_id": runtime_id,
                "content_address": address,
                "diff_id": "d469-diff",
                "diff_address": "glio-noncode-d469-diff:fixture",
                "state": state,
                "release_ready": release_ready,
                "check_count": 15,
                "passed_count": 14 if state == "blocked" else 15,
                "item_count": 2,
            }

        blocked_source = history_model.build_registry_snapshot(
            (runtime("d469-source-blocked", "blocked", False, "glio-noncode-d469-source-runtime:blocked"),),
            registry_id="d469-registry",
        )
        ready_source = history_model.build_registry_snapshot(
            (runtime("d469-source-ready", "ready", True, "glio-noncode-d469-source-runtime:ready"),),
            registry_id="d469-registry",
        )
        left = history_model.build_history(blocked_source, history_id="d469-source-history", snapshot_id="baseline")
        right = history_model.append_history(left, ready_source, snapshot_id="ready", expected_head=left.entries[-1].content_address)
        diff = diff_model.build_diff(left, right, diff_id="d469-diff")
        ready = runtime_model.run_runtime(diff, runtime_id="d469-ready-runtime", policy=runtime_model.build_policy("d469-ready-policy", diff.diff_id, maximum_added=1, maximum_removed=0, maximum_changed=0, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True))
        blocked = runtime_model.run_runtime(diff, runtime_id="d469-blocked-runtime", policy=runtime_model.build_policy("d469-blocked-policy", diff.diff_id, maximum_added=0, maximum_removed=0, maximum_changed=0, allowed_directions=("improved", "changed", "unchanged"), require_accepted=True, require_state_change=False, allow_unchanged=True))
        registry = registry_model.build_registry((blocked, ready), registry_id="d469-registry")
        audit = audit_model.audit_registry(registry)
        query = query_model.query_registry(registry, resources=query_model.RESOURCES, state_filter="blocked", limit=query_model.MAX_LIMIT)
        query_audit = query_audit_model.audit_query(query, registry)
        self.assertEqual((registry.state, registry.entry_count, registry.ready_count, registry.blocked_count, registry.release_ready), ("blocked", 2, 1, 1, False))
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (16, 16, True))
        self.assertFalse(query.truncated)
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (12, 12, True))
        with self.assertRaises(ValidationError):
            registry_model.build_registry((ready, ready), registry_id="d469-duplicate")

        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "registry"
            registry_model.persist_registry(registry, destination)
            reloaded = registry_model.load_registry(destination)
            self.assertEqual(reloaded.content_address, registry.content_address)
            self.assertEqual(registry_model.registry_json(reloaded), registry_model.registry_json(registry))

            registry_document = json.loads((destination / "registry.json").read_text(encoding="utf-8"))
            registry_document["release_ready"] = True
            (destination / "registry.json").write_text(canonical_json(registry_document), encoding="utf-8")
            with self.assertRaises(ValidationError):
                registry_model.load_registry(destination)


if __name__ == "__main__":
    unittest.main()
