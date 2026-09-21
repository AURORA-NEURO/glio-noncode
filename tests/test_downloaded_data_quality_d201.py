"""Focused regression coverage for the D201 runtime registry layer."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry as registry_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_audit as audit_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_query as query_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_query_audit as query_audit_model
from glio_noncode.errors import ValidationError


class D201RuntimeRegistryTests(unittest.TestCase):
    def test_registry_replays_admission_audit_query_persistence_and_duplicate_guard(self) -> None:
        source_history_model = runtime_model.diff_model.history_model
        source_registry_model = source_history_model.registry_model
        source_registry = source_registry_model.build_registry((), registry_id="d201-source-registry")
        left = source_history_model.build_history(source_registry, history_id="d201-history", snapshot_id="baseline")
        right = source_history_model.build_history(source_registry, history_id="d201-history", snapshot_id="candidate")
        diff = runtime_model.diff_model.build_diff(left, right, diff_id="d201-diff")
        ready = runtime_model.build_runtime(
            diff,
            runtime_id="d201-ready-runtime",
            policy=runtime_model.build_policy("d201-ready-policy", diff.diff_id, minimum_items=1, maximum_changed=1),
        )
        blocked = runtime_model.build_runtime(
            diff,
            runtime_id="d201-blocked-runtime",
            policy=runtime_model.build_policy("d201-blocked-policy", diff.diff_id, minimum_items=2),
        )
        registry = registry_model.build_registry((blocked, ready), registry_id="d201-registry")
        audit = audit_model.audit_registry(registry)
        query = query_model.query_registry(
            registry,
            resources=query_model.RESOURCES,
            state_filter="blocked",
            limit=query_model.MAX_LIMIT,
        )
        query_audit = query_audit_model.audit_query(query, registry)
        self.assertEqual((registry.state, registry.entry_count, registry.ready_count, registry.blocked_count, registry.release_ready), ("blocked", 2, 1, 1, False))
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (16, 16, True))
        self.assertGreater(query.returned_count, 0)
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (12, 12, True))
        with self.assertRaises(ValidationError):
            registry_model.build_registry((ready, ready), registry_id="d201-duplicate")
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "registry"
            registry_model.persist_registry(registry, destination)
            self.assertEqual(tuple(sorted(path.name for path in destination.iterdir())), tuple(sorted(registry_model.FILES)))
            self.assertEqual(registry_model.load_registry(destination).content_address, registry.content_address)
            summary = destination / "summary.json"
            summary.write_text(summary.read_text(encoding="utf-8").replace('"state":"blocked"', '"state":"ready"', 1), encoding="utf-8")
            with self.assertRaises(ValidationError):
                registry_model.load_registry(destination)


if __name__ == "__main__":
    unittest.main()
