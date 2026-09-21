"""Focused regression coverage for the D229 runtime registry layer."""

from __future__ import annotations

import unittest

from glio_noncode import downloaded_data_quality_d229_runtime_registry as registry_model
from glio_noncode import downloaded_data_quality_d229_runtime_registry_audit as audit_model
from glio_noncode import downloaded_data_quality_d229_runtime_registry_query as query_model
from glio_noncode import downloaded_data_quality_d229_runtime_registry_query_audit as query_audit_model
from glio_noncode.errors import ValidationError


class D229RuntimeRegistryTests(unittest.TestCase):
    def test_registry_replays_aggregate_audit_query_and_duplicate_guard(self) -> None:
        runtime_model = registry_model.runtime_model
        source_history_model = runtime_model.diff_model.history_model
        source_registry_model = source_history_model.registry_model
        source_registry = source_registry_model.build_registry((), registry_id="d229-source-registry")
        left = source_history_model.build_history(source_registry, history_id="d229-source-history", snapshot_id="baseline")
        right = source_history_model.build_history(source_registry, history_id="d229-source-history", snapshot_id="candidate")
        diff = runtime_model.diff_model.build_diff(left, right, diff_id="d229-diff")
        ready = runtime_model.build_runtime(diff, runtime_id="d229-ready-runtime", policy=runtime_model.build_policy("d229-ready-policy", diff.diff_id, maximum_changed=1))
        blocked = runtime_model.build_runtime(diff, runtime_id="d229-blocked-runtime", policy=runtime_model.build_policy("d229-blocked-policy", diff.diff_id, maximum_changed=0))
        registry = registry_model.build_registry((blocked, ready), registry_id="d229-registry")
        audit = audit_model.audit_registry(registry)
        query = query_model.query_registry(registry, resources=query_model.RESOURCES, state_filter="blocked", limit=query_model.MAX_LIMIT)
        query_audit = query_audit_model.audit_query(query, registry)
        self.assertEqual((registry.state, registry.entry_count, registry.ready_count, registry.blocked_count, registry.release_ready), ("blocked", 2, 1, 1, False))
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (16, 16, True))
        self.assertFalse(query.truncated)
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (12, 12, True))
        with self.assertRaises(ValidationError):
            registry_model.build_registry((ready, ready), registry_id="d229-duplicate")


if __name__ == "__main__":
    unittest.main()
