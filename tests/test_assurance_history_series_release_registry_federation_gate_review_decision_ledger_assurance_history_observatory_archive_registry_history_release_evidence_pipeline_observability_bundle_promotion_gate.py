"""Deep contracts for observability handoff promotion decisions."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_promotion_gate as gate
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_promotion_gate_query as query
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_diff import RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffFixture


class RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGateTests(RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffFixture):
    def test_identical_verified_handoff_is_ready_and_replayable(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = self.bundle_for(Path(temporary), "same")
            value = gate.build_promotion_gate(gate.diff_model.diff_bundle_directories(source, source))
            self.assertEqual(value.state, "ready")
            self.assertTrue(value.accepted)
            self.assertTrue(value.release_ready)
            self.assertEqual(value.passed_count, gate.MAX_CHECKS)
            self.assertEqual(value.failed_count, 0)
            self.assertEqual(value.blocking_failure_count, 0)
            self.assertEqual(value.hold_failure_count, 0)
            self.assertEqual(gate.address_gate(value), value.content_address)
            self.assertEqual(gate.gate_from_mapping(json.loads(gate.gate_json(value))).to_dict(), value.to_dict())
            self.assertEqual(query.query_gate(value, resource="passed", limit=gate.MAX_CHECKS).total_count, gate.MAX_CHECKS)
            self.assert_public(value)

    def test_changed_handoff_is_held_by_default_transition_policy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.bundle_for(root / "baseline", "baseline")
            candidate = self.bundle_for(root / "candidate", "candidate")
            value = gate.build_promotion_gate_from_directories(baseline, candidate)
            self.assertEqual(value.state, "held")
            self.assertTrue(value.accepted)
            self.assertFalse(value.release_ready)
            self.assertEqual(value.blocking_failure_count, 0)
            self.assertGreaterEqual(value.hold_failure_count, 1)
            self.assertFalse(next(check for check in value.checks if check.check_id == "transition-state").passed)
            result = query.query_gate(value, resource="failed", limit=gate.MAX_CHECKS)
            self.assertEqual(result.total_count, value.failed_count)
            self.assertTrue(all(not record["passed"] for record in result.records))
            self.assertIn("held", gate.render_gate_markdown(value))

    def test_policy_can_allow_mixed_transition_but_budget_can_hold(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.bundle_for(root / "baseline", "baseline")
            candidate = self.bundle_for(root / "candidate", "candidate")
            policy = gate.RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionPolicy(allowed_diff_states=("unchanged", "improved", "mixed"), max_changed_items=0)
            value = gate.build_promotion_gate_from_directories(baseline, candidate, policy=policy)
            self.assertEqual(value.state, "held")
            self.assertTrue(next(check for check in value.checks if check.check_id == "transition-state").passed)
            self.assertFalse(next(check for check in value.checks if check.check_id == "changed-artifact-budget").passed)
            self.assertEqual(value.policy.allowed_diff_states, ("unchanged", "improved", "mixed"))

    def test_integrity_failure_is_blocking_and_mapping_is_strict(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = self.bundle_for(Path(temporary), "strict")
            value = gate.build_promotion_gate_from_directories(source, source)
            document = value.to_dict()
            document["checks"][0]["detail"] = "tampered"
            with self.assertRaises(ValidationError):
                gate.gate_from_mapping(document)
            self.assertEqual(gate.address_policy(value.policy), value.policy_address)
            self.assert_public(gate.policy_schema())
            self.assert_public(gate.check_schema())
            self.assert_public(gate.gate_schema())
            self.assert_public(gate.capabilities())

    def test_cli_and_http_surfaces_expose_promotion_gate_and_query(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.bundle_for(root, "same")
            command = self.BUNDLE_COMMAND + "-promotion-gate"
            output = root / "gate.json"
            self.assertEqual(main([command, "--baseline", str(source), "--candidate", str(source), "--format", "json", "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["state"], "ready")
            query_output = root / "query.json"
            self.assertEqual(main([command + "-query", "--baseline", str(source), "--candidate", str(source), "--resource", "passed", "--limit", "2", "--format", "json", "--output", str(query_output)]), 0)
            self.assertEqual(json.loads(query_output.read_text(encoding="utf-8"))["returned_count"], 2)
            self.assertEqual(main([command + "-policy-schema"]), 0)
            self.assertEqual(main([command + "-check-schema"]), 0)
            self.assertEqual(main([command + "-schema"]), 0)
            self.assertEqual(main([command + "-capabilities"]), 0)
            self.assertEqual(main([command + "-query-query-schema"]), 0)
            self.assertEqual(main([command + "-query-query-result-schema"]), 0)
            self.assertEqual(main([command + "-query-query-capabilities"]), 0)

    def test_http_promotion_gate_and_query_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = self.bundle_for(Path(temporary), "same")
            server, thread = self.server()
            try:
                prefix = f"http://127.0.0.1:{server.server_port}/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/release-gate/release-evidence-pipeline/observability/bundle/promotion-gate"
                params = urlencode({"baseline": str(source), "candidate": str(source), "format": "json"})
                with urlopen(prefix + "?" + params) as response:
                    payload = json.loads(response.read())
                    self.assertEqual(payload["state"], "ready")
                    self.assertEqual(payload["check_count"], gate.MAX_CHECKS)
                with urlopen(prefix + "/policy-schema") as response:
                    self.assertIn("allowed_diff_states", json.loads(response.read())["properties"])
                with urlopen(prefix + "/check-schema") as response:
                    self.assertIn("severity", json.loads(response.read())["properties"])
                with urlopen(prefix + "/schema") as response:
                    self.assertIn("release_ready", json.loads(response.read())["properties"])
                with urlopen(prefix + "/capabilities") as response:
                    self.assertIn("explicit promotion policy", json.loads(response.read())["features"])
                query_params = urlencode({"baseline": str(source), "candidate": str(source), "resource": "passed", "limit": "2", "format": "json"})
                with urlopen(prefix + "/query?" + query_params) as response:
                    self.assertEqual(json.loads(response.read())["returned_count"], 2)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
