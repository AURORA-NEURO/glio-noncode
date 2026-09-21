"""Focused regression coverage for D492 runtime registry history comparisons."""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from glio_noncode import downloaded_data_quality_d491_ledger_diff_runtime_registry_history as history_model
from glio_noncode import downloaded_data_quality_d492_ledger_diff_runtime_registry_history_diff as diff_model
from glio_noncode import downloaded_data_quality_d492_ledger_diff_runtime_registry_history_diff_audit as audit_model
from glio_noncode import downloaded_data_quality_d492_ledger_diff_runtime_registry_history_diff_query as query_model
from glio_noncode import downloaded_data_quality_d492_ledger_diff_runtime_registry_history_diff_query_audit as query_audit_model
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json
from tests.test_downloaded_data_quality_d491 import _registries

class D492RuntimeRegistryHistoryDiffTests(unittest.TestCase):
    def test_added_promotion_diff_audits_queries_and_persistence(self) -> None:
        blocked, ready, _ = _registries()
        baseline = history_model.build_history(blocked, history_id="d492-history", snapshot_id="blocked")
        candidate = history_model.append_history(baseline, ready, snapshot_id="ready", expected_head=baseline.entries[-1].content_address)
        diff = diff_model.build_diff(baseline, candidate, diff_id="d492-promotion-diff")
        audit = audit_model.audit_diff(diff, baseline, candidate)
        query = query_model.query_diff(diff, resources=("items", "changes"), change_filter="added", limit=query_model.MAX_LIMIT)
        query_audit = query_audit_model.audit_query(query, diff)
        direction_query = query_model.query_diff(diff, resources=("direction",), direction_filter="improved", limit=query_model.MAX_LIMIT)
        self.assertEqual((diff.added_count, diff.removed_count, diff.changed_count, diff.unchanged_count), (1, 0, 0, 1))
        self.assertEqual((diff.direction, diff.state_transition), ("improved", "blocked->ready"))
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (16, 16, True))
        self.assertEqual((query.returned_count, query.total_count, query.truncated), (1, 1, False))
        self.assertEqual((direction_query.returned_count, direction_query.rows[0].value), (2, '"improved"'))
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (12, 12, True))
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "diff"
            diff_model.persist_diff(diff, destination)
            self.assertEqual(tuple(sorted(x.name for x in destination.iterdir())), tuple(sorted(diff_model.FILES)))
            self.assertEqual(diff_model.load_diff(destination).content_address, diff.content_address)
            document = json.loads((destination / "diff.json").read_text(encoding="utf-8")); document["direction"] = "regressed"
            (destination / "diff.json").write_text(canonical_json(document), encoding="utf-8")
            with self.assertRaises(ValidationError): diff_model.load_diff(destination)

    def test_changed_fields_and_history_identity_guard(self) -> None:
        blocked, ready, _ = _registries()
        left = history_model.build_history(blocked, history_id="d492-changed-history", snapshot_id="same")
        right = history_model.build_history(ready, history_id="d492-changed-history", snapshot_id="same")
        diff = diff_model.build_diff(left, right, diff_id="d492-changed-diff")
        self.assertEqual((diff.changed_count, diff.direction), (1, "improved"))
        self.assertIn("registry_id", diff.items[0].changed_fields)
        self.assertIn("release_ready", diff.items[0].changed_fields)
        with self.assertRaises(ValidationError):
            diff_model.build_diff(left, history_model.build_history(ready, history_id="other-history", snapshot_id="same"))

    def test_removed_snapshot_reports_regression_and_detached_audit(self) -> None:
        blocked, ready, _ = _registries()
        ready_history = history_model.build_history(blocked, history_id="d492-regression", snapshot_id="blocked")
        ready_history = history_model.append_history(ready_history, ready, snapshot_id="ready")
        blocked_history = history_model.build_history(blocked, history_id="d492-regression", snapshot_id="blocked")
        diff = diff_model.build_diff(ready_history, blocked_history, diff_id="d492-regression-diff")
        audit = audit_model.audit_diff(diff)
        self.assertEqual((diff.removed_count, diff.direction, diff.state_transition), (1, "regressed", "ready->blocked"))
        self.assertTrue(audit.accepted)

if __name__ == "__main__":
    unittest.main()
