"""Deep contracts for observability-audit query projections."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline as pipeline
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_audit as audit
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_audit_query as query
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline import RegistryHistoryReleaseEvidencePipelineFixture


class RegistryHistoryReleaseEvidencePipelineObservabilityAuditQueryFixture(RegistryHistoryReleaseEvidencePipelineFixture):
    QUERY_COMMAND = RegistryHistoryReleaseEvidencePipelineFixture.PIPELINE_COMMAND + "-observability-audit-query"


class RegistryHistoryReleaseEvidencePipelineObservabilityAuditQueryBuildTests(RegistryHistoryReleaseEvidencePipelineObservabilityAuditQueryFixture):
    def test_failed_passed_evidence_and_replay_views_are_bounded(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = audit.audit_pipeline(pipeline.build_pipeline(self.directories(Path(temporary))))
            checks = query.query_audit(value, resource="checks", limit=20)
            self.assertEqual(checks.total_count, audit.MAX_CHECKS)
            self.assertEqual(checks.returned_count, audit.MAX_CHECKS)
            self.assertEqual(query.query_audit(value, resource="passed").total_count, audit.MAX_CHECKS)
            self.assertEqual(query.query_audit(value, resource="failed").total_count, 0)
            self.assertEqual(query.query_audit(value, resource="checks", check_id="transition-linkage").records[0]["passed"], True)
            evidence = query.query_audit(value, resource="evidence", text="namespace", limit=20)
            self.assertGreaterEqual(evidence.total_count, 1)
            self.assertEqual(query.query_result_from_mapping(json.loads(query.query_json(evidence))).to_dict(), evidence.to_dict())
            self.assertEqual(query.address_query(evidence), evidence.content_address)
            self.assert_public(evidence)

    def test_real_downloaded_history_query_preserves_audit_address(self):
        source = Path(tempfile.gettempdir()) / "glio-noncode-history-audit-demo-eb48d6ff52184a0e97a4b81607b93dc2"
        if not source.is_dir():
            self.skipTest("the optional local downloaded-data demo is not present")
        result = query.query_observability_audit_directory(source, resource="passed", limit=20)
        expected = audit.audit_pipeline_directory(source)
        self.assertEqual(result.total_count, audit.MAX_CHECKS)
        self.assertEqual(result.audit_address, expected.content_address)

    def test_query_rejects_unsupported_filters_and_tampered_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = audit.audit_pipeline(pipeline.build_pipeline(self.directories(Path(temporary))))
            with self.assertRaises(ValidationError):
                query.RegistryHistoryReleaseEvidencePipelineObservabilityAuditQuery(check_id="missing")
            with self.assertRaises(ValidationError):
                query.RegistryHistoryReleaseEvidencePipelineObservabilityAuditQuery(limit=0)
            selected = query.RegistryHistoryReleaseEvidencePipelineObservabilityAuditQuery(resource="checks")
            with self.assertRaises(ValidationError):
                query.query_audit(value, selected, resource="failed")
            result = query.query_audit(value, resource="checks", limit=2)
            candidate = result.to_dict()
            candidate["records"][0]["passed"] = False
            with self.assertRaises(ValidationError):
                query.query_result_from_mapping(candidate)
            self.assert_public(query.query_schema())
            self.assert_public(query.query_result_schema())
            self.assert_public(query.capabilities())


class RegistryHistoryReleaseEvidencePipelineObservabilityAuditQueryCliApiTests(RegistryHistoryReleaseEvidencePipelineObservabilityAuditQueryFixture):
    def test_cli_query_and_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            history_dir = self.directories(root)
            output = root / "audit-query.json"
            self.assertEqual(main([self.QUERY_COMMAND, "--input", str(history_dir), "--resource", "passed", "--limit", "2", "--format", "json", "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["returned_count"], 2)
            self.assertEqual(main([self.QUERY_COMMAND, "--input", str(history_dir), "--resource", "evidence", "--format", "markdown"]), 0)
            self.assertEqual(main([self.QUERY_COMMAND + "-query-schema"]), 0)
            self.assertEqual(main([self.QUERY_COMMAND + "-query-result-schema"]), 0)
            self.assertEqual(main([self.QUERY_COMMAND + "-query-capabilities"]), 0)

    def test_http_query_schema_capability_and_report_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            history_dir = self.directories(root)
            server, thread = self.server()
            try:
                prefix = "http://127.0.0.1:%s/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/release-gate/release-evidence-pipeline/observability/audit"
                prefix = prefix % server.server_port
                with urlopen(prefix + "/query?" + urlencode({"input": str(history_dir), "resource": "passed", "limit": "2", "format": "json"})) as response:
                    payload = json.loads(response.read())
                    self.assertEqual(payload["returned_count"], 2)
                with urlopen(prefix + "/query-schema") as response:
                    self.assertIn("check_id", json.loads(response.read())["properties"])
                with urlopen(prefix + "/query-result-schema") as response:
                    self.assertIn("audit_address", json.loads(response.read())["properties"])
                with urlopen(prefix + "/query-capabilities") as response:
                    self.assertIn("failed", json.loads(response.read())["resources"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
