"""Deep contracts for independent release-evidence observability audits."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline as pipeline
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability as observability
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_audit as audit
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline import RegistryHistoryReleaseEvidencePipelineFixture


class RegistryHistoryReleaseEvidencePipelineObservabilityAuditFixture(RegistryHistoryReleaseEvidencePipelineFixture):
    AUDIT_COMMAND = RegistryHistoryReleaseEvidencePipelineFixture.PIPELINE_COMMAND + "-observability-audit"


class RegistryHistoryReleaseEvidencePipelineObservabilityAuditBuildTests(RegistryHistoryReleaseEvidencePipelineObservabilityAuditFixture):
    def test_thirteen_checks_prove_ready_observability(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = pipeline.build_pipeline(self.directories(Path(temporary)))
            report = audit.audit_pipeline(value)
            self.assertTrue(report.accepted)
            self.assertTrue(report.complete)
            self.assertEqual(report.state, "complete")
            self.assertEqual(report.check_count, audit.MAX_CHECKS)
            self.assertEqual(report.passed_count, audit.MAX_CHECKS)
            self.assertEqual(report.failed_count, 0)
            self.assertEqual(tuple(check.check_id for check in report.checks), audit.CHECK_IDS)
            self.assertEqual(audit.audit_result_from_mapping(report.to_dict()).to_dict(), report.to_dict())
            self.assertEqual(audit.address_audit(report), report.content_address)
            self.assertIn("transition-linkage", audit.audit_json(report))
            self.assertIn("| Passed |", audit.render_audit_markdown(report))
            self.assert_public(report)

    def test_real_downloaded_history_audit_preserves_observability_address(self):
        source = Path(tempfile.gettempdir()) / "glio-noncode-history-audit-demo-eb48d6ff52184a0e97a4b81607b93dc2"
        if not source.is_dir():
            self.skipTest("the optional local downloaded-data demo is not present")
        report = audit.audit_pipeline_directory(source)
        observation = observability.build_observability(pipeline.build_pipeline(source))
        self.assertTrue(report.accepted)
        self.assertEqual(report.observability_address, observation.content_address)
        self.assertEqual(report.pipeline_address, observation.pipeline_address)

    def test_damaged_mapping_returns_incomplete_diagnostic_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = observability.build_observability(pipeline.build_pipeline(self.directories(Path(temporary))))
            candidate = report.to_dict()
            candidate["events"][2]["output_address"] = "private/local/path"
            damaged = audit.audit_from_mapping(candidate)
            self.assertFalse(damaged.accepted)
            self.assertFalse(damaged.complete)
            self.assertGreater(damaged.failed_count, 0)
            self.assertIn("source-addresses", {check.check_id for check in damaged.checks})
            with self.assertRaises(ValidationError):
                audit.RegistryHistoryReleaseEvidencePipelineObservabilityAudit.from_mapping({"checks": []})
            self.assert_public(audit.audit_schema())
            self.assert_public(audit.check_schema())
            self.assert_public(audit.capabilities())


class RegistryHistoryReleaseEvidencePipelineObservabilityAuditCliApiTests(RegistryHistoryReleaseEvidencePipelineObservabilityAuditFixture):
    def test_cli_audit_and_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            history_dir = self.directories(root)
            output = root / "observability-audit.json"
            self.assertEqual(main([self.AUDIT_COMMAND, "--input", str(history_dir), "--format", "json", "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["passed_count"], audit.MAX_CHECKS)
            self.assertEqual(main([self.AUDIT_COMMAND, "--input", str(history_dir), "--format", "markdown"]), 0)
            self.assertEqual(main([self.AUDIT_COMMAND + "-schema"]), 0)
            self.assertEqual(main([self.AUDIT_COMMAND + "-check-schema"]), 0)
            self.assertEqual(main([self.AUDIT_COMMAND + "-capabilities"]), 0)

    def test_http_audit_schema_capability_and_report_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            history_dir = self.directories(root)
            server, thread = self.server()
            try:
                prefix = "http://127.0.0.1:%s/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/release-gate/release-evidence-pipeline/observability/audit"
                prefix = prefix % server.server_port
                with urlopen(prefix + "?" + urlencode({"input": str(history_dir), "format": "json"})) as response:
                    payload = json.loads(response.read())
                    self.assertEqual(payload["passed_count"], audit.MAX_CHECKS)
                    self.assertTrue(payload["complete"])
                with urlopen(prefix + "/schema") as response:
                    self.assertIn("checks", json.loads(response.read())["properties"])
                with urlopen(prefix + "/check-schema") as response:
                    self.assertIn("check_id", json.loads(response.read())["properties"])
                with urlopen(prefix + "/capabilities") as response:
                    self.assertIn("transition-linkage", json.loads(response.read())["checks"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
