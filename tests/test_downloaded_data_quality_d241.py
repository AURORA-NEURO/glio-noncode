"""Focused regression coverage for the D241 runtime registry layer."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import downloaded_data_quality_d241_runtime_registry as registry_model
from glio_noncode import downloaded_data_quality_d241_runtime_registry_audit as audit_model
from glio_noncode import downloaded_data_quality_d241_runtime_registry_query as query_model
from glio_noncode import downloaded_data_quality_d241_runtime_registry_query_audit as query_audit_model
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json


class D241RuntimeRegistryTests(unittest.TestCase):
    def test_registry_replays_aggregate_audit_query_and_duplicate_guard(self) -> None:
        runtime_model = registry_model.runtime_model
        source_history_model = runtime_model.diff_model.history_model
        source_registry_model = source_history_model.registry_model
        source_registry = source_registry_model.build_registry((), registry_id="d241-source-registry")
        left = source_history_model.build_history(source_registry, history_id="d241-source-history", snapshot_id="baseline")
        right = source_history_model.build_history(source_registry, history_id="d241-source-history", snapshot_id="candidate")
        diff = runtime_model.diff_model.build_diff(left, right, diff_id="d241-diff")
        ready = runtime_model.build_runtime(diff, runtime_id="d241-ready-runtime", policy=runtime_model.build_policy("d241-ready-policy", diff.diff_id, maximum_changed=1))
        blocked = runtime_model.build_runtime(diff, runtime_id="d241-blocked-runtime", policy=runtime_model.build_policy("d241-blocked-policy", diff.diff_id, maximum_changed=0))
        registry = registry_model.build_registry((blocked, ready), registry_id="d241-registry")
        audit = audit_model.audit_registry(registry)
        query = query_model.query_registry(registry, resources=query_model.RESOURCES, state_filter="blocked", limit=query_model.MAX_LIMIT)
        query_audit = query_audit_model.audit_query(query, registry)
        self.assertEqual((registry.state, registry.entry_count, registry.ready_count, registry.blocked_count, registry.release_ready), ("blocked", 2, 1, 1, False))
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (16, 16, True))
        self.assertFalse(query.truncated)
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (12, 12, True))
        with self.assertRaises(ValidationError):
            registry_model.build_registry((ready, ready), registry_id="d241-duplicate")

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

