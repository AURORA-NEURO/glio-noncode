"""Focused regression coverage for D488 gate-decision ledger diffs."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import downloaded_data_quality_d487_history_diff_runtime_policy_scenario_release_gate_ledger as ledger_model
from glio_noncode import downloaded_data_quality_d488_gate_decision_ledger_diff as diff_model
from glio_noncode import downloaded_data_quality_d488_gate_decision_ledger_diff_audit as audit_model
from glio_noncode import downloaded_data_quality_d488_gate_decision_ledger_diff_query as query_model
from glio_noncode import downloaded_data_quality_d488_gate_decision_ledger_diff_query_audit as query_audit_model
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json
from tests.test_downloaded_data_quality_d487 import _gates


def _ledgers() -> tuple[ledger_model.GateDecisionLedger, ledger_model.GateDecisionLedger]:
    blocked, ready = _gates()
    baseline_policy = ledger_model.build_policy(
        "d488-baseline-policy",
        "d488-ledger",
        minimum_decisions=1,
        minimum_ready=0,
        maximum_blocked=1,
        require_supersession_links=False,
        require_final_ready=False,
        allow_reopened=False,
    )
    candidate_policy = ledger_model.build_policy(
        "d488-candidate-policy",
        "d488-ledger",
        minimum_decisions=2,
        minimum_ready=1,
        maximum_blocked=1,
        require_supersession_links=True,
        require_final_ready=True,
        allow_reopened=False,
    )
    baseline = ledger_model.build_ledger(
        (blocked,),
        ledger_id="d488-ledger",
        policy=baseline_policy,
        decision_ids=("d488-blocked-decision",),
        supersedes_decision_ids=("",),
    )
    candidate = ledger_model.build_ledger(
        (blocked, ready),
        ledger_id="d488-ledger",
        policy=candidate_policy,
        decision_ids=("d488-blocked-decision", "d488-ready-decision"),
        supersedes_decision_ids=("", "d488-blocked-decision"),
    )
    return baseline, candidate


class D488GateDecisionLedgerDiffTests(unittest.TestCase):
    def test_diff_audit_query_and_exact_persistence(self) -> None:
        baseline, candidate = _ledgers()
        policy = diff_model.build_policy(
            "d488-diff-policy",
            baseline.ledger_id,
            candidate.ledger_id,
            minimum_items=2,
            maximum_added=1,
            maximum_removed=0,
            maximum_changed=0,
            allowed_directions=("improved",),
            require_same_scenario=True,
            require_append_only=True,
            require_head_change=True,
            require_accepted=True,
        )
        diff = diff_model.build_diff(baseline, candidate, diff_id="d488-ledger-diff", policy=policy)
        audit = audit_model.audit_diff(diff, baseline, candidate)
        query = query_model.query_diff(diff, resources=query_model.RESOURCES, limit=query_model.MAX_LIMIT)
        query_audit = query_audit_model.audit_query(query, diff)

        self.assertEqual((diff.added_count, diff.removed_count, diff.changed_count, diff.unchanged_count), (1, 0, 0, 1))
        self.assertEqual((diff.direction, diff.state_transition), ("improved", "blocked->ready"))
        self.assertTrue(diff.release_ready)
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (16, 16, True))
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (12, 12, True))
        self.assertFalse(query.truncated)

        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "diff"
            diff_model.persist_diff(diff, destination)
            self.assertEqual(tuple(sorted(path.name for path in destination.iterdir())), tuple(sorted(diff_model.FILES)))
            loaded = diff_model.load_diff(destination)
            self.assertEqual(loaded.content_address, diff.content_address)
            document = json.loads((destination / "summary.json").read_text(encoding="utf-8"))
            document["direction"] = "regressed"
            (destination / "summary.json").write_text(canonical_json(document), encoding="utf-8")
            with self.assertRaises(ValidationError):
                diff_model.load_diff(destination)

    def test_policy_budget_failure_and_identity_guard(self) -> None:
        baseline, candidate = _ledgers()
        rejecting_policy = diff_model.build_policy(
            "d488-rejecting-policy",
            baseline.ledger_id,
            candidate.ledger_id,
            minimum_items=2,
            maximum_added=0,
            maximum_removed=0,
            maximum_changed=0,
            allowed_directions=("improved",),
        )
        rejected = diff_model.build_diff(baseline, candidate, diff_id="d488-rejected-diff", policy=rejecting_policy)
        self.assertFalse(rejected.release_ready)
        self.assertIn("added_budget", {item.check_id for item in rejected.checks if not item.passed})

        blocked, ready = _gates()
        other = ledger_model.build_ledger(
            (blocked, ready),
            ledger_id="d488-other-ledger",
            policy=ledger_model.build_policy("d488-other-policy", "d488-other-ledger", minimum_decisions=2, minimum_ready=1, maximum_blocked=1, require_supersession_links=True, require_final_ready=True),
            decision_ids=("d488-other-blocked", "d488-other-ready"),
            supersedes_decision_ids=("", "d488-other-blocked"),
        )
        with self.assertRaises(ValidationError):
            diff_model.build_diff(baseline, other, diff_id="d488-mismatched-diff")


if __name__ == "__main__":
    unittest.main()
