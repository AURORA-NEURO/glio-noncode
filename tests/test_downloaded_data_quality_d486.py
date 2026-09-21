"""Focused regression coverage for D486 release gates."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import downloaded_data_quality_d485_history_diff_runtime_policy_scenario as scenario_model
from glio_noncode import downloaded_data_quality_d485_history_diff_runtime_policy_scenario_audit as scenario_audit_model
from glio_noncode import downloaded_data_quality_d485_history_diff_runtime_policy_scenario_query as scenario_query_model
from glio_noncode import downloaded_data_quality_d485_history_diff_runtime_policy_scenario_query_audit as scenario_query_audit_model
from glio_noncode import downloaded_data_quality_d486_history_diff_runtime_policy_scenario_release_gate as gate_model
from glio_noncode import downloaded_data_quality_d486_history_diff_runtime_policy_scenario_release_gate_audit as audit_model
from glio_noncode import downloaded_data_quality_d486_history_diff_runtime_policy_scenario_release_gate_query as query_model
from glio_noncode import downloaded_data_quality_d486_history_diff_runtime_policy_scenario_release_gate_query_audit as query_audit_model
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json
from tests.test_downloaded_data_quality_d485 import _runtimes


def _evidence() -> tuple[scenario_model.PolicyScenario, scenario_audit_model.ScenarioAudit, scenario_query_model.ScenarioQuery, scenario_query_audit_model.QueryAudit]:
    strict, release = _runtimes()
    scenario = scenario_model.build_scenario((strict, release), scenario_id="d486-scenario", policy=scenario_model.build_policy("d486-scenario-policy", minimum_runtimes=2, minimum_ready=1, maximum_blocked=1, require_at_least_one_blocked=True, allow_mixed=True))
    audit = scenario_audit_model.audit_scenario(scenario, (strict, release))
    query = scenario_query_model.query_scenario(scenario, resources=scenario_query_model.RESOURCES, limit=scenario_query_model.MAX_LIMIT)
    query_audit = scenario_query_audit_model.audit_query(query, scenario)
    return scenario, audit, query, query_audit


class D486ReleaseGateTests(unittest.TestCase):
    def test_ready_gate_audit_query_and_persistence(self) -> None:
        scenario, audit, query, query_audit = _evidence()
        policy = gate_model.build_policy("d486-ready-policy", scenario.scenario_id, minimum_ready=1, maximum_blocked=1, minimum_added_margin=-1, minimum_removed_margin=0, minimum_changed_margin=0, disallowed_risk_flags=(), require_scenario_accepted=True, require_scenario_release_ready=True, require_audit_accepted=True, require_query_complete=True, require_query_audit_accepted=True)
        gate = gate_model.build_gate(scenario, gate_id="d486-ready-gate", policy=policy, audit=audit, query=query, query_audit=query_audit)
        gate_audit = audit_model.audit_gate(gate, scenario, audit, query, query_audit)
        gate_query = query_model.query_gate(gate, resources=query_model.RESOURCES, limit=query_model.MAX_LIMIT)
        gate_query_audit = query_audit_model.audit_query(gate_query, gate)
        self.assertTrue(gate.release_ready)
        self.assertEqual((gate_audit.check_count, gate_audit.passed_count, gate_audit.accepted), (18, 18, True))
        self.assertEqual((gate_query_audit.check_count, gate_query_audit.passed_count, gate_query_audit.accepted), (12, 12, True))
        self.assertFalse(gate_query.truncated)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "gate"
            gate_model.persist_gate(gate, destination)
            loaded = gate_model.load_gate(destination)
            self.assertEqual(loaded.content_address, gate.content_address)
            document = json.loads((destination / "summary.json").read_text(encoding="utf-8"))
            document["release_ready"] = False
            (destination / "summary.json").write_text(canonical_json(document), encoding="utf-8")
            with self.assertRaises(ValidationError):
                gate_model.load_gate(destination)

    def test_default_gate_blocks_risks_and_incomplete_query(self) -> None:
        scenario, audit, query, query_audit = _evidence()
        blocked = gate_model.build_gate(scenario, gate_id="d486-blocked-gate", audit=audit, query=query, query_audit=query_audit)
        failed = {item.check_id for item in blocked.checks if not item.passed}
        self.assertFalse(blocked.release_ready)
        self.assertIn("maximum_blocked", failed)
        self.assertIn("risk_allowlist", failed)
        incomplete = scenario_query_model.query_scenario(scenario, resources=scenario_query_model.RESOURCES, limit=1)
        incomplete_audit = scenario_query_audit_model.audit_query(incomplete, scenario)
        incomplete_gate = gate_model.build_gate(scenario, gate_id="d486-incomplete-gate", policy=gate_model.build_policy("d486-incomplete-policy", scenario.scenario_id, maximum_blocked=1, minimum_added_margin=-1, disallowed_risk_flags=(), require_scenario_release_ready=True, require_audit_accepted=False, require_query_complete=True, require_query_audit_accepted=True), audit=audit, query=incomplete, query_audit=incomplete_audit)
        self.assertIn("query_complete", {item.check_id for item in incomplete_gate.checks if not item.passed})


if __name__ == "__main__":
    unittest.main()
