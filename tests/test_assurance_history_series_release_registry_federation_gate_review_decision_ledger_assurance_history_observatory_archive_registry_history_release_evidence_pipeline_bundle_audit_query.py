"""Deep contracts for release-evidence bundle-audit queries."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline as pipeline
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle as bundle
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_audit as audit
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_audit_query as query
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline import RegistryHistoryReleaseEvidencePipelineFixture


class RegistryHistoryReleaseEvidencePipelineBundleAuditQueryFixture(RegistryHistoryReleaseEvidencePipelineFixture):
    BUNDLE_COMMAND = RegistryHistoryReleaseEvidencePipelineFixture.PIPELINE_COMMAND + "-bundle"
    QUERY_COMMAND = BUNDLE_COMMAND + "-audit-query"


class RegistryHistoryReleaseEvidencePipelineBundleAuditQueryBuildTests(RegistryHistoryReleaseEvidencePipelineBundleAuditQueryFixture):
    def test_query_replays_valid_bundle_checks_and_all_views(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "bundle"
            bundle.write_bundle(pipeline.build_pipeline(self.directories(root)), destination)
            result = query.query_bundle_directory(destination, resource="checks", limit=5)
            self.assertEqual(result.total_count, len(audit.CHECK_IDS))
            self.assertEqual(result.returned_count, 5)
            self.assertEqual(tuple(record["check_id"] for record in result.records), audit.CHECK_IDS[:5])
            self.assertEqual(query.query_audit(audit.audit_bundle_directory(destination), resource="passed").total_count, len(audit.CHECK_IDS))
            self.assertEqual(query.query_bundle_directory(destination, resource="failed").total_count, 0)
            evidence = query.query_bundle_directory(destination, resource="evidence", check_id="content-address")
            self.assertEqual(evidence.total_count, 1)
            self.assertEqual(evidence.records[0]["check_id"], "content-address")
            self.assertEqual(query.query_result_from_mapping(json.loads(query.query_json(result))).to_dict(), result.to_dict())
            self.assertIn("content-address", query.render_query_markdown(evidence))
            self.assertIn("check_id", query.query_csv(evidence).splitlines()[0])
            self.assert_public(result)
            self.assert_public(query.query_schema())
            self.assert_public(query.query_result_schema())
            self.assert_public(query.capabilities())

    def test_failed_and_text_queries_preserve_damaged_bundle_diagnostics(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "bundle"
            bundle.write_bundle(pipeline.build_pipeline(self.directories(root)), destination)
            (destination / bundle.STAGES_NAME).write_bytes((destination / bundle.STAGES_NAME).read_bytes() + b"\n")
            result = query.query_bundle_directory(destination, resource="failed", passed=False)
            self.assertGreater(result.total_count, 0)
            self.assertTrue(all(record["passed"] is False for record in result.records))
            content = query.query_bundle_directory(destination, resource="checks", text="canonical")
            self.assertEqual(content.total_count, 1)
            self.assertEqual(content.records[0]["check_id"], "canonical-json")
            with self.assertRaises(ValidationError):
                query.RegistryHistoryReleaseEvidencePipelineBundleAuditQuery(resource="checks", limit=0)
            with self.assertRaises(ValidationError):
                query.RegistryHistoryReleaseEvidencePipelineBundleAuditQuery(check_id="unknown")


class RegistryHistoryReleaseEvidencePipelineBundleAuditQueryCliApiTests(RegistryHistoryReleaseEvidencePipelineBundleAuditQueryFixture):
    def test_cli_query_and_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            history_dir = self.directories(root)
            destination = root / "bundle"
            query_output = root / "query.json"
            self.assertEqual(main([self.BUNDLE_COMMAND, "--input", str(history_dir), "--destination", str(destination), "--output", str(root / "bundle.json")]), 0)
            self.assertEqual(main([self.QUERY_COMMAND, "--input", str(destination), "--resource", "failed", "--format", "json", "--output", str(query_output)]), 0)
            self.assertEqual(json.loads(query_output.read_text(encoding="utf-8"))["total_count"], 0)
            self.assertEqual(main([self.QUERY_COMMAND + "-query-schema"]), 0)
            self.assertEqual(main([self.QUERY_COMMAND + "-query-result-schema"]), 0)
            self.assertEqual(main([self.QUERY_COMMAND + "-query-capabilities"]), 0)

    def test_http_query_route_supports_failed_filter_and_contracts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            history_dir = self.directories(root)
            destination = root / "bundle"
            bundle.write_bundle(pipeline.build_pipeline(history_dir), destination)
            server, thread = self.server()
            try:
                prefix = "http://127.0.0.1:%s/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/release-gate/release-evidence-pipeline/bundle/audit/query"
                prefix = prefix % server.server_port
                contract_prefix = prefix.removesuffix("/query")
                with urlopen(prefix + "?" + urlencode({"input": str(destination), "resource": "failed"})) as response:
                    self.assertEqual(json.loads(response.read())["total_count"], 0)
                with urlopen(contract_prefix + "/query-schema") as response:
                    self.assertIn("resource", json.loads(response.read())["properties"])
                with urlopen(contract_prefix + "/query-result-schema") as response:
                    self.assertIn("audit_address", json.loads(response.read())["properties"])
                with urlopen(contract_prefix + "/query-capabilities") as response:
                    self.assertIn("damaged-bundle query support", json.loads(response.read())["features"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
