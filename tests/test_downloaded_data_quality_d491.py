"""Focused regression coverage for D491 registry history lineage."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import downloaded_data_quality_d490_ledger_diff_runtime_registry as registry_model
from glio_noncode import downloaded_data_quality_d491_ledger_diff_runtime_registry_history as history_model
from glio_noncode import downloaded_data_quality_d491_ledger_diff_runtime_registry_history_audit as audit_model
from glio_noncode import downloaded_data_quality_d491_ledger_diff_runtime_registry_history_query as query_model
from glio_noncode import downloaded_data_quality_d491_ledger_diff_runtime_registry_history_query_audit as query_audit_model
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json
from tests.test_downloaded_data_quality_d490 import _runtimes


def _registries() -> tuple[registry_model.RuntimeRegistry, registry_model.RuntimeRegistry, registry_model.RuntimeRegistry]:
    runtimes = _runtimes()
    blocked = registry_model.build_registry(runtimes, registry_id="d491-blocked-registry", policy=registry_model.build_policy("d491-blocked-policy", minimum_runtimes=2, minimum_ready=2, maximum_blocked=0, require_same_diff=True, require_same_direction=True, require_audited=False, require_release_ready=True))
    ready = registry_model.build_registry(runtimes, registry_id="d491-ready-registry", policy=registry_model.build_policy("d491-ready-policy", minimum_runtimes=2, minimum_ready=1, maximum_blocked=1, require_same_diff=True, require_same_direction=True, require_audited=False, require_release_ready=False))
    regressed = registry_model.build_registry(runtimes, registry_id="d491-regressed-registry", policy=registry_model.build_policy("d491-regressed-policy", minimum_runtimes=2, minimum_ready=2, maximum_blocked=0, require_same_diff=True, require_same_direction=True, require_audited=False, require_release_ready=True))
    return blocked, ready, regressed


class D491LedgerDiffRuntimeRegistryHistoryTests(unittest.TestCase):
    def test_lineage_promotes_regresses_and_replays_audits_and_queries(self) -> None:
        blocked, ready, regressed = _registries()
        history = history_model.build_history(blocked, history_id="d491-history", snapshot_id="blocked")
        history = history_model.append_history(history, ready, snapshot_id="ready", expected_head=history.entries[-1].content_address)
        history = history_model.append_history(history, regressed, snapshot_id="regressed", expected_head=history.entries[-1].content_address)
        audit = audit_model.audit_history(history, (blocked, ready, regressed))
        query = query_model.query_history(history, resources=query_model.RESOURCES, limit=query_model.MAX_LIMIT)
        query_audit = query_audit_model.audit_query(query, history)
        promoted = query_model.query_history(history, resources=("transitions",), transition_filter="promoted", limit=query_model.MAX_LIMIT)
        self.assertEqual((history.entry_count, history.initial_count, history.promoted_count, history.regressed_count), (3, 1, 1, 1))
        self.assertEqual((history.latest_state, history.latest_release_ready, history.latest_accepted), ("blocked", False, True))
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (16, 16, True))
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (12, 12, True))
        self.assertEqual((promoted.total_count, promoted.returned_count, promoted.truncated), (1, 1, False))
        self.assertEqual(promoted.rows[0].key, "ready")

    def test_expected_head_identity_and_snapshot_guards(self) -> None:
        blocked, ready, _ = _registries()
        history = history_model.build_history(blocked, history_id="d491-guards", snapshot_id="blocked")
        with self.assertRaises(ValidationError):
            history_model.append_history(history, ready, snapshot_id="ready", expected_head="wrong-head")
        history = history_model.append_history(history, ready, snapshot_id="ready", expected_head=history.entries[-1].content_address)
        with self.assertRaises(ValidationError):
            history_model.append_history(history, ready, snapshot_id="second", expected_head=history.entries[-1].content_address)
        with self.assertRaises(ValidationError):
            history_model.append_history(history, ready, snapshot_id="ready", expected_head=history.entries[-1].content_address)

    def test_exact_four_file_persistence_rejects_tampering(self) -> None:
        blocked, _, _ = _registries()
        history = history_model.build_history(blocked, history_id="d491-persistence", snapshot_id="blocked")
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "history"
            history_model.persist_history(history, destination)
            self.assertEqual(tuple(sorted(path.name for path in destination.iterdir())), tuple(sorted(history_model.FILES)))
            loaded = history_model.load_history(destination)
            self.assertEqual(loaded.content_address, history.content_address)
            document = json.loads((destination / "history.json").read_text(encoding="utf-8"))
            document["latest_state"] = "ready"
            (destination / "history.json").write_text(canonical_json(document), encoding="utf-8")
            with self.assertRaises(ValidationError):
                history_model.load_history(destination)


if __name__ == "__main__":
    unittest.main()
