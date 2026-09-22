"""Focused tests for D493 policy-driven history-diff release evaluation."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import downloaded_data_quality_d491_ledger_diff_runtime_registry_history as history_model
from glio_noncode import downloaded_data_quality_d492_ledger_diff_runtime_registry_history_diff as diff_model
from glio_noncode import downloaded_data_quality_d493_ledger_diff_runtime_registry_history_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_d493_ledger_diff_runtime_registry_history_diff_runtime_audit as audit_model
from glio_noncode import downloaded_data_quality_d493_ledger_diff_runtime_registry_history_diff_runtime_query as query_model
from glio_noncode import downloaded_data_quality_d493_ledger_diff_runtime_registry_history_diff_runtime_query_audit as query_audit_model
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json
from tests.test_downloaded_data_quality_d491 import _registries


def _diff() -> diff_model.HistoryDiff:
    blocked, ready, _ = _registries()
    baseline = history_model.build_history(blocked, history_id="d493-history", snapshot_id="blocked")
    candidate = history_model.append_history(
        baseline,
        ready,
        snapshot_id="ready",
        expected_head=baseline.entries[-1].content_address,
    )
    return diff_model.build_diff(baseline, candidate, diff_id="d493-promotion-diff")


def _policy(diff: diff_model.HistoryDiff, *, maximum_added: int = 1, **changes: object) -> runtime_model.RuntimePolicy:
    values: dict[str, object] = {
        "minimum_items": 2,
        "maximum_added": maximum_added,
        "maximum_removed": 0,
        "maximum_changed": 0,
        "allowed_directions": ("improved",),
        "require_accepted": True,
        "require_state_change": True,
        "allow_unchanged": True,
    }
    values.update(changes)
    return runtime_model.build_policy("d493-test-policy", diff.diff_id, **values)  # type: ignore[arg-type]


class D493LedgerDiffRuntimeTests(unittest.TestCase):
    def test_strict_and_release_runtime_audits_queries_and_persistence(self) -> None:
        source = _diff()
        strict = runtime_model.run_runtime(source, runtime_id="d493-strict", policy=_policy(source, maximum_added=0))
        release = runtime_model.run_runtime(source, runtime_id="d493-release", policy=_policy(source))
        strict_audit = audit_model.audit_runtime(strict, source)
        release_audit = audit_model.audit_runtime(release, source)
        query = query_model.query_runtime(release, resources=query_model.RESOURCES, limit=query_model.MAX_LIMIT)
        query_audit = query_audit_model.audit_query(query, release)

        self.assertFalse(strict.release_ready)
        self.assertEqual([item.check_id for item in strict.checks if not item.passed], ["added_budget", "release_disposition"])
        self.assertTrue(strict_audit.accepted)
        self.assertEqual((release.state, release.passed_count, release.check_count), ("ready", 15, 15))
        self.assertEqual((release_audit.accepted, release_audit.passed_count, release_audit.check_count), (True, 15, 15))
        self.assertEqual((query_audit.accepted, query_audit.passed_count, query_audit.check_count), (True, 12, 12))
        self.assertEqual((query.returned_count, query.total_count, query.truncated), (query.total_count, query.total_count, False))

        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "release-runtime"
            runtime_model.persist_runtime(release, target)
            self.assertEqual(tuple(sorted(path.name for path in target.iterdir())), tuple(sorted(runtime_model.FILES)))
            self.assertEqual(runtime_model.load_runtime(target, source).content_address, release.content_address)
            document = json.loads((target / "runtime.json").read_text(encoding="utf-8"))
            document["release_ready"] = False
            (target / "runtime.json").write_text(canonical_json(document), encoding="utf-8")
            with self.assertRaises(ValidationError):
                runtime_model.load_runtime(target, source)

    def test_direction_and_unchanged_policies_block_release(self) -> None:
        source = _diff()
        runtime = runtime_model.run_runtime(
            source,
            runtime_id="d493-policy-blocked",
            policy=_policy(source, allowed_directions=("regressed",), allow_unchanged=False),
        )
        failed = {item.check_id for item in runtime.checks if not item.passed}
        self.assertEqual(runtime.state, "blocked")
        self.assertEqual(failed, {"direction_policy", "unchanged_policy", "release_disposition"})
        self.assertTrue(audit_model.audit_runtime(runtime, source).accepted)

    def test_query_filters_blocked_policy_findings(self) -> None:
        source = _diff()
        runtime = runtime_model.run_runtime(source, runtime_id="d493-filtered", policy=_policy(source, maximum_added=0))
        query = query_model.query_runtime(
            runtime,
            resources=("checks",),
            state_filter="blocked",
            passed_filter=False,
            severity_filter="error",
            limit=query_model.MAX_LIMIT,
        )
        audit = query_audit_model.audit_query(query, runtime)
        self.assertEqual({row.key for row in query.rows}, {"added_budget", "release_disposition"})
        self.assertEqual((query.returned_count, query.total_count, query.truncated), (2, 2, False))
        self.assertTrue(audit.accepted)


if __name__ == "__main__":
    unittest.main()
