"""Deep contracts for independent observability-bundle diff audits."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_diff as diff
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_diff_audit as audit
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_diff import RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffFixture


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditFixture(RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffFixture):
    AUDIT_COMMAND = RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffFixture.DIFF_COMMAND + "-audit"


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditBuildTests(RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditFixture):
    def test_changed_handoff_diff_audit_is_complete_and_replayable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.bundle_for(root / "baseline", "baseline")
            candidate = self.bundle_for(root / "candidate", "candidate")
            value = audit.audit_diff(diff.build_diff(baseline, candidate))
            self.assertTrue(value.complete)
            self.assertTrue(value.accepted)
            self.assertEqual(value.check_count, len(audit.CHECK_IDS))
            self.assertEqual(value.failed_count, 0)
            self.assertEqual(audit.address_audit(value), value.content_address)
            self.assertEqual(audit.audit_from_mapping(json.loads(audit.audit_json(value))).to_dict(), value.to_dict())
            self.assertIn("content address reproduces", audit.render_audit_markdown(value))
            self.assert_public(value.to_dict())
            self.assert_public(audit.audit_schema())
            self.assert_public(audit.check_schema())
            self.assert_public(audit.capabilities())

    def test_malformed_diff_mapping_returns_addressed_incomplete_diagnostics(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = self.bundle_for(Path(temporary), "clean")
            document = diff.build_diff(source, source).to_dict()
            document["items"][0]["detail"] = "tampered"
            value = audit.audit_from_mapping(document)
            self.assertEqual(value.state, "incomplete")
            self.assertFalse(value.accepted)
            self.assertGreater(value.failed_count, 0)
            self.assertEqual(tuple(check.check_id for check in value.checks), audit.CHECK_IDS)
            self.assertEqual(audit.audit_from_mapping(value.to_dict()).to_dict(), value.to_dict())
            with self.assertRaises(ValidationError):
                audit.audit_from_mapping(value.to_dict() | {"extra": True})


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditCliApiTests(RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditFixture):
    def test_cli_audit_and_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.bundle_for(root / "baseline", "baseline")
            candidate = self.bundle_for(root / "candidate", "candidate")
            output = root / "audit.json"
            self.assertEqual(main([self.AUDIT_COMMAND, "--baseline", str(baseline), "--candidate", str(candidate), "--format", "json", "--output", str(output)]), 0)
            self.assertTrue(json.loads(output.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(main([self.AUDIT_COMMAND + "-schema"]), 0)
            self.assertEqual(main([self.AUDIT_COMMAND + "-check-schema"]), 0)
            self.assertEqual(main([self.AUDIT_COMMAND + "-capabilities"]), 0)

    def test_http_audit_route_and_contracts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.bundle_for(root / "baseline", "baseline")
            candidate = self.bundle_for(root / "candidate", "candidate")
            server, thread = self.server()
            try:
                prefix = "http://127.0.0.1:%s/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/release-gate/release-evidence-pipeline/observability/bundle/diff/audit"
                prefix = prefix % server.server_port
                params = {"baseline": str(baseline), "candidate": str(candidate), "format": "json"}
                with urlopen(prefix + "?" + urlencode(params)) as response:
                    payload = json.loads(response.read())
                    self.assertEqual(payload["check_count"], len(audit.CHECK_IDS))
                    self.assertTrue(payload["accepted"])
                with urlopen(prefix + "/schema") as response:
                    self.assertIn("checks", json.loads(response.read())["properties"])
                with urlopen(prefix + "/check-schema") as response:
                    self.assertIn("evidence_address", json.loads(response.read())["properties"])
                with urlopen(prefix + "/capabilities") as response:
                    self.assertIn("semantic receipt field conservation", json.loads(response.read())["features"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
