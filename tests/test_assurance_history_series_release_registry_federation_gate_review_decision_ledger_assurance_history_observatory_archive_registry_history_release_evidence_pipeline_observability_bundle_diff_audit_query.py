"""Deep contracts for queries over observability-bundle diff audits."""

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
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_diff_audit_query as query
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_diff import RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffFixture


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQueryFixture(RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffFixture):
    QUERY_COMMAND = RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffFixture.DIFF_COMMAND + "-audit-query"


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQueryBuildTests(RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQueryFixture):
    def test_passed_failed_evidence_and_replay_views_are_bounded(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.bundle_for(root / "baseline", "baseline")
            candidate = self.bundle_for(root / "candidate", "candidate")
            value = diff.build_diff(baseline, candidate)
            passed = query.query_diff(value, resource="passed", limit=3)
            self.assertEqual(passed.total_count, audit.MAX_CHECKS)
            self.assertEqual(passed.returned_count, 3)
            self.assertEqual(query.query_diff(value, resource="failed").total_count, 0)
            self.assertEqual(query.query_diff(value, resource="checks", check_id="content-address").records[0]["passed"], True)
            evidence = query.query_diff(value, resource="evidence", text="address", limit=20)
            self.assertGreaterEqual(evidence.total_count, 1)
            self.assertIn("check_address", evidence.records[0])
            self.assertEqual(query.query_result_from_mapping(json.loads(query.query_json(evidence))).to_dict(), evidence.to_dict())
            self.assertEqual(query.address_query(evidence), evidence.content_address)
            self.assert_public(evidence)
            self.assert_public(query.query_schema())
            self.assert_public(query.query_result_schema())
            self.assert_public(query.capabilities())

    def test_query_rejects_invalid_filters_and_tampered_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.bundle_for(root / "baseline", "baseline")
            candidate = self.bundle_for(root / "candidate", "candidate")
            value = diff.build_diff(baseline, candidate)
            with self.assertRaises(ValidationError):
                query.RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQuery(check_id="missing")
            result = query.query_diff(value, resource="checks", limit=2)
            candidate_result = result.to_dict()
            candidate_result["returned_count"] = 99
            with self.assertRaises(ValidationError):
                query.query_result_from_mapping(candidate_result)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQueryCliApiTests(RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQueryFixture):
    def test_cli_query_and_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.bundle_for(root / "baseline", "baseline")
            candidate = self.bundle_for(root / "candidate", "candidate")
            output = root / "query.json"
            self.assertEqual(main([self.QUERY_COMMAND, "--baseline", str(baseline), "--candidate", str(candidate), "--resource", "passed", "--passed", "--limit", "2", "--format", "json", "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["total_count"], audit.MAX_CHECKS)
            self.assertEqual(payload["returned_count"], 2)
            self.assertEqual(main([self.QUERY_COMMAND + "-query-schema"]), 0)
            self.assertEqual(main([self.QUERY_COMMAND + "-query-result-schema"]), 0)
            self.assertEqual(main([self.QUERY_COMMAND + "-query-capabilities"]), 0)

    def test_http_query_routes_and_contracts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.bundle_for(root / "baseline", "baseline")
            candidate = self.bundle_for(root / "candidate", "candidate")
            server, thread = self.server()
            try:
                prefix = "http://127.0.0.1:%s/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/release-gate/release-evidence-pipeline/observability/bundle/diff/audit"
                prefix = prefix % server.server_port
                with urlopen(prefix + "/query?" + urlencode({"baseline": str(baseline), "candidate": str(candidate), "resource": "passed", "limit": "2"})) as response:
                    payload = json.loads(response.read())
                    self.assertEqual(payload["total_count"], audit.MAX_CHECKS)
                    self.assertEqual(payload["returned_count"], 2)
                with urlopen(prefix + "/query-schema") as response:
                    self.assertIn("check_id", json.loads(response.read())["properties"])
                with urlopen(prefix + "/query-result-schema") as response:
                    self.assertIn("audit_address", json.loads(response.read())["properties"])
                with urlopen(prefix + "/query-capabilities") as response:
                    self.assertIn("evidence-address projection", json.loads(response.read())["features"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
