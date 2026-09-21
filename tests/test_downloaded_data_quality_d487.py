"""Focused regression coverage for D487 gate decision ledgers."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import downloaded_data_quality_d486_history_diff_runtime_policy_scenario_release_gate as gate_model
from glio_noncode import downloaded_data_quality_d487_history_diff_runtime_policy_scenario_release_gate_ledger as ledger_model
from glio_noncode import downloaded_data_quality_d487_history_diff_runtime_policy_scenario_release_gate_ledger_audit as audit_model
from glio_noncode import downloaded_data_quality_d487_history_diff_runtime_policy_scenario_release_gate_ledger_query as query_model
from glio_noncode import downloaded_data_quality_d487_history_diff_runtime_policy_scenario_release_gate_ledger_query_audit as query_audit_model
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json
from tests.test_downloaded_data_quality_d486 import _evidence


def _gates() -> tuple[gate_model.ReleaseGate, gate_model.ReleaseGate]:
    scenario, audit, query, query_audit = _evidence()
    blocked = gate_model.build_gate(scenario, gate_id="d487-blocked-gate", audit=audit, query=query, query_audit=query_audit)
    ready_policy = gate_model.build_policy("d487-ready-gate-policy", scenario.scenario_id, minimum_ready=1, maximum_blocked=1, minimum_added_margin=-1, minimum_removed_margin=0, minimum_changed_margin=0, disallowed_risk_flags=(), require_scenario_accepted=True, require_scenario_release_ready=True, require_audit_accepted=True, require_query_complete=True, require_query_audit_accepted=True)
    ready = gate_model.build_gate(scenario, gate_id="d487-ready-gate", policy=ready_policy, audit=audit, query=query, query_audit=query_audit)
    return blocked, ready


class D487GateDecisionLedgerTests(unittest.TestCase):
    def test_append_lineage_audit_query_and_persistence(self) -> None:
        blocked, ready = _gates()
        policy = ledger_model.build_policy("d487-ledger-policy", "d487-ledger", minimum_decisions=2, minimum_ready=1, maximum_blocked=1, require_same_scenario=True, require_unique_gate_ids=True, require_unique_gate_addresses=True, require_contiguous_sequence=True, require_supersession_links=True, require_final_ready=True, allow_reopened=False)
        ledger = ledger_model.build_ledger((blocked, ready), ledger_id="d487-ledger", policy=policy, decision_ids=("d487-blocked-decision", "d487-ready-decision"), supersedes_decision_ids=("", "d487-blocked-decision"))
        audit = audit_model.audit_ledger(ledger, (blocked, ready))
        query = query_model.query_ledger(ledger, resources=query_model.RESOURCES, limit=query_model.MAX_LIMIT)
        query_audit = query_audit_model.audit_query(query, ledger)
        self.assertTrue(ledger.release_ready)
        self.assertEqual((ledger.transition, ledger.superseded_count, ledger.head_decision_id), ("promoted", 1, "d487-ready-decision"))
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (19, 19, True))
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (12, 12, True))
        self.assertFalse(query.truncated)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "ledger"
            ledger_model.persist_ledger(ledger, destination)
            loaded = ledger_model.load_ledger(destination)
            self.assertEqual(loaded.content_address, ledger.content_address)
            document = json.loads((destination / "summary.json").read_text(encoding="utf-8"))
            document["head_decision_id"] = "tampered"
            (destination / "summary.json").write_text(canonical_json(document), encoding="utf-8")
            with self.assertRaises(ValidationError):
                ledger_model.load_ledger(destination)

    def test_optimistic_head_and_reopen_controls(self) -> None:
        blocked, ready = _gates()
        policy = ledger_model.build_policy("d487-append-policy", "d487-append-ledger", minimum_decisions=2, minimum_ready=1, maximum_blocked=1, require_supersession_links=True, require_final_ready=True, allow_reopened=False)
        first = ledger_model.build_ledger((blocked,), ledger_id="d487-append-ledger", policy=policy, decision_ids=("d487-first",), supersedes_decision_ids=("",))
        appended = ledger_model.append_ledger(first, ready, decision_id="d487-second", expected_head=first.head_entry_address, supersedes_decision_id="d487-first")
        self.assertTrue(appended.release_ready)
        with self.assertRaises(ValidationError):
            ledger_model.append_ledger(first, ready, decision_id="d487-wrong-head", expected_head="wrong-head", supersedes_decision_id="d487-first")
        with self.assertRaises(ValidationError):
            ledger_model.append_ledger(appended, ready, decision_id="d487-second", expected_head=appended.head_entry_address, supersedes_decision_id="d487-first")
        reopened = ledger_model.build_ledger((ready, blocked), ledger_id="d487-reopened-ledger", policy=ledger_model.build_policy("d487-reopened-policy", "d487-reopened-ledger", minimum_decisions=2, minimum_ready=1, maximum_blocked=1, require_supersession_links=True, require_final_ready=False, allow_reopened=False), decision_ids=("d487-ready", "d487-reopened"), supersedes_decision_ids=("", "d487-ready"))
        self.assertIn("reopen_policy", {item.check_id for item in reopened.checks if not item.passed})


if __name__ == "__main__":
    unittest.main()
