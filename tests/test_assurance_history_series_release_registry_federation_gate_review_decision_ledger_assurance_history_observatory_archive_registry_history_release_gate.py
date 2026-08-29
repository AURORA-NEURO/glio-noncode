"""Deep contracts for policy evaluation over registry histories."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history as history
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_audit as audit
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate as gate
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff import DiffFixture


class RegistryHistoryReleaseGateFixture(DiffFixture):
    """Build gate inputs through verified registry and history boundaries."""

    GATE_COMMAND = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-observatory-archive-registry-history-release-gate"

    def history_value(self, root: Path, *states: str) -> history.RegistryHistory:
        values = tuple(self.one_registry(root, f"snapshot-{index}", state=state) for index, state in enumerate(states))
        return history.build_history(values, history_id="history:gate")

    def assert_public(self, value) -> None:
        payload = value.to_dict() if hasattr(value, "to_dict") else value
        rendered = canonical_json(payload)
        self.assertNotIn("C:\\", rendered)
        self.assertNotIn("/Users/", rendered)
        forbidden = {"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "user"}

        def walk(node):
            if isinstance(node, dict):
                for key, item in node.items():
                    self.assertNotIn(key.lower(), forbidden)
                    walk(item)
            elif isinstance(node, (list, tuple)):
                for item in node:
                    walk(item)

        walk(payload)

    def server(self):
        from glio_noncode.api import create_server

        server = create_server("127.0.0.1", 0)
        import threading

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread


class RegistryHistoryReleaseGateBuildTests(RegistryHistoryReleaseGateFixture):
    def test_default_policy_accepts_the_downloaded_history(self):
        source = Path(tempfile.gettempdir()) / "glio-noncode-history-audit-demo-eb48d6ff52184a0e97a4b81607b93dc2"
        if not source.is_dir():
            self.skipTest("the optional local downloaded-data demo is not present")
        value = gate.evaluate_history_from_directory(source)
        self.assertEqual(value.state, "ready")
        self.assertTrue(value.accepted)
        self.assertTrue(value.release_ready)
        self.assertEqual(value.passed_count, gate.MAX_CHECKS)
        self.assertEqual(gate.address_gate(value), value.content_address)
        self.assert_public(value)

    def test_ready_gate_has_replayable_policy_check_and_gate_addresses(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = gate.evaluate_history(self.history_value(Path(temporary), "ready", "ready"))
            self.assertEqual(value.policy_address, gate.address_policy(value.policy))
            self.assertEqual(tuple(check.check_id for check in value.checks), gate.CHECK_IDS)
            for check in value.checks:
                self.assertEqual(gate.address_check(check), check.content_address)
            self.assertEqual(gate.gate_from_mapping(value.to_dict()).to_dict(), value.to_dict())
            self.assert_public(value.summary())

    def test_minimum_snapshot_policy_failure_is_a_hold(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = gate.evaluate_history(self.history_value(Path(temporary), "ready"))
            self.assertEqual(value.state, "held")
            self.assertFalse(value.accepted)
            self.assertFalse(value.release_ready)
            self.assertFalse(value.checks[0].passed)
            self.assertEqual(value.checks[0].severity, "hold")

    def test_regression_and_final_readiness_policy_failures_remain_a_hold(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = gate.evaluate_history(self.history_value(Path(temporary), "ready", "held"))
            failed = {check.check_id for check in value.checks if not check.passed}
            self.assertEqual(value.state, "held")
            self.assertEqual(failed, {"final-release-ready", "transition-states", "regression-budget"})
            self.assertTrue(all(check.severity == "hold" for check in value.checks if not check.passed))

    def test_incomplete_independent_audit_blocks_the_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.history_value(Path(temporary), "ready", "ready")
            malformed_audit = audit.audit_from_mapping(value.to_dict() | {"snapshot_count": 99})
            result = gate.evaluate_history(value, audit=malformed_audit)
            self.assertEqual(result.state, "blocked")
            self.assertFalse(result.accepted)
            self.assertFalse(next(check for check in result.checks if check.check_id == "audit-complete").passed)
            self.assertEqual(next(check for check in result.checks if check.check_id == "audit-complete").severity, "blocking")

    def test_explicit_budgets_and_transition_allow_list_are_enforced(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.history_value(Path(temporary), "ready", "held")
            policy = gate.RegistryHistoryReleasePolicy(
                policy_id="policy:strict",
                minimum_snapshots=2,
                require_audit_complete=True,
                require_all_snapshots_accepted=False,
                require_final_release_ready=False,
                allowed_transition_states=("unchanged",),
                max_removed_items_per_transition=0,
                max_changed_items_per_transition=0,
                max_regressed_transitions=1,
                max_mixed_transitions=0,
            )
            result = gate.evaluate_history(value, policy)
            self.assertEqual(result.state, "held")
            self.assertFalse(next(check for check in result.checks if check.check_id == "transition-states").passed)
            self.assertTrue(next(check for check in result.checks if check.check_id == "regression-budget").passed)
            self.assertEqual(gate.address_policy(policy), result.policy_address)

    def test_policy_rejects_duplicate_or_noncanonical_transition_states(self):
        with self.assertRaises(ValidationError):
            gate.RegistryHistoryReleasePolicy(allowed_transition_states=("improved", "unchanged"))
        with self.assertRaises(ValidationError):
            gate.RegistryHistoryReleasePolicy(allowed_transition_states=("unchanged", "unchanged"))
        with self.assertRaises(ValidationError):
            gate.RegistryHistoryReleasePolicy.from_mapping(gate.RegistryHistoryReleasePolicy().to_dict() | {"extra": True})

    def test_gate_rejects_private_and_forged_public_mappings(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = gate.evaluate_history(self.history_value(Path(temporary), "ready", "ready"))
            with self.assertRaises(ValidationError):
                gate.gate_from_mapping(value.to_dict() | {"source_path": "C:\\private"})
            forged = value.to_dict() | {"state": "ready" if value.state != "ready" else "held"}
            with self.assertRaises(ValidationError):
                gate.gate_from_mapping(forged)

    def test_exports_schemas_and_capabilities_are_public_and_deterministic(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = gate.evaluate_history(self.history_value(Path(temporary), "ready", "ready"))
            self.assertEqual(gate.gate_json(value), gate.gate_json(gate.gate_from_mapping(value.to_dict())))
            self.assertIn("severity", gate.gate_csv(value))
            self.assertIn("Release Gate", gate.render_gate_markdown(value))
            for schema in (gate.policy_schema(), gate.check_schema(), gate.gate_schema(), gate.capabilities()):
                self.assert_public(schema)
            self.assertEqual(tuple(gate.capabilities()["checks"]), gate.CHECK_IDS)


class RegistryHistoryReleaseGateCliApiTests(RegistryHistoryReleaseGateFixture):
    def directories(self, root: Path) -> Path:
        first = self.one_registry(root, "cli-first")
        first_dir = root / "first"
        from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry as registry

        registry.write_registry(first, first_dir)
        history_dir = root / "history"
        history.write_history(history.build_history_from_directories((first_dir, first_dir), history_id="history:cli"), history_dir)
        return history_dir

    def test_cli_gate_and_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            history_dir = self.directories(root)
            output = root / "gate.json"
            self.assertEqual(main([self.GATE_COMMAND, "--input", str(history_dir), "--format", "json", "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["state"], "ready")
            self.assertEqual(main([self.GATE_COMMAND + "-schema"]), 0)
            self.assertEqual(main([self.GATE_COMMAND + "-policy-schema"]), 0)
            self.assertEqual(main([self.GATE_COMMAND + "-check-schema"]), 0)
            self.assertEqual(main([self.GATE_COMMAND + "-capabilities"]), 0)

    def test_http_gate_schema_capabilities_and_report_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            history_dir = self.directories(Path(temporary))
            server, thread = self.server()
            try:
                prefix = "http://127.0.0.1:%s/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/release-gate"
                prefix = prefix % server.server_port
                params = urlencode({"input": str(history_dir), "format": "json"})
                with urlopen(prefix + "?" + params) as response:
                    payload = json.loads(response.read())
                self.assertEqual(payload["state"], "ready")
                with urlopen(prefix + "/schema") as response:
                    self.assertFalse(json.loads(response.read())["additionalProperties"])
                with urlopen(prefix + "/policy-schema") as response:
                    self.assertIn("minimum_snapshots", json.loads(response.read())["properties"])
                with urlopen(prefix + "/check-schema") as response:
                    self.assertIn("severity", json.loads(response.read())["properties"])
                with urlopen(prefix + "/capabilities") as response:
                    self.assertEqual(tuple(json.loads(response.read())["states"]), gate.STATES)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
