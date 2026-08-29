"""Deep contracts for bounded bundle-diff audit queries."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry as registry
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history as history
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline as pipeline
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle as bundle
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff as diff
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_audit as audit
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_audit_query as query
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline import RegistryHistoryReleaseEvidencePipelineFixture


class RegistryHistoryReleaseEvidencePipelineBundleDiffAuditQueryFixture(RegistryHistoryReleaseEvidencePipelineFixture):
    BUNDLE_COMMAND = RegistryHistoryReleaseEvidencePipelineFixture.PIPELINE_COMMAND + "-bundle"
    DIFF_COMMAND = BUNDLE_COMMAND + "-diff"
    AUDIT_COMMAND = DIFF_COMMAND + "-audit"
    QUERY_COMMAND = AUDIT_COMMAND + "-query"

    def bundle_for(self, root: Path, name: str) -> Path:
        value = self.one_registry(root, name, registry_id="registry:" + name)
        registry_dir = root / (name + "-registry")
        registry.write_registry(value, registry_dir)
        history_dir = root / (name + "-history")
        history.write_history(history.build_history_from_directories((registry_dir, registry_dir), history_id="history:" + name), history_dir)
        pipeline_value = pipeline.build_pipeline(history_dir)
        bundle_dir = root / (name + "-bundle")
        bundle.write_bundle(pipeline_value, bundle_dir)
        return bundle_dir


class RegistryHistoryReleaseEvidencePipelineBundleDiffAuditQueryBuildTests(RegistryHistoryReleaseEvidencePipelineBundleDiffAuditQueryFixture):
    def test_downloaded_bundle_exposes_passed_and_evidence_views(self):
        source = Path(tempfile.gettempdir()) / "glio-noncode-history-release-evidence-pipeline-bundle-demo"
        if not source.is_dir():
            self.skipTest("the optional local downloaded-data bundle is not present")
        value = query.query_diff(diff.build_diff(source, source), resource="checks", passed=True)
        self.assertEqual(value.total_count, len(audit.CHECK_IDS))
        self.assertTrue(all(record["passed"] is True for record in value.records))
        self.assertEqual(query.query_diff(diff.build_diff(source, source), resource="failed").total_count, 0)
        evidence = query.query_diff(diff.build_diff(source, source), resource="evidence", check_id="content-address")
        self.assertEqual(evidence.total_count, 1)
        self.assertEqual(evidence.records[0]["check_id"], "content-address")
        self.assertEqual(query.address_query(evidence), evidence.content_address)
        self.assertEqual(query.query_result_from_mapping(json.loads(query.query_json(evidence))).to_dict(), evidence.to_dict())

    def test_query_supports_filters_pagination_and_incomplete_raw_mapping(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.bundle_for(root / "baseline", "baseline")
            candidate = self.bundle_for(root / "candidate", "candidate")
            value = query.query_diff(diff.diff_bundle_directories(baseline, candidate), resource="checks", limit=3)
            self.assertEqual(value.total_count, len(audit.CHECK_IDS))
            self.assertEqual(value.returned_count, 3)
            self.assertEqual(value.records[0]["check_id"], audit.CHECK_IDS[0])
            self.assertEqual(query.query_diff(diff.diff_bundle_directories(baseline, candidate), resource="checks", text="NAMESPACE").total_count, 1)
            document = diff.diff_bundle_directories(baseline, candidate).to_dict()
            document["items"][0]["detail"] = "tampered"
            failed = query.query_from_mapping(document, resource="failed")
            self.assertGreater(failed.total_count, 0)
            self.assertTrue(all(record["passed"] is False for record in failed.records))
            self.assertIn("| check_id |", query.render_query_markdown(value))
            self.assertIn("check_id", query.query_csv(value).splitlines()[0])
            for kwargs in ({"check_id": "unknown"}, {"limit": 0}, {"limit": query.MAX_LIMIT + 1}):
                with self.assertRaises(ValidationError):
                    query.query_diff(diff.diff_bundle_directories(baseline, candidate), resource="checks", **kwargs)
            self.assert_public(query.query_schema())
            self.assert_public(query.query_result_schema())
            self.assert_public(query.capabilities())


class RegistryHistoryReleaseEvidencePipelineBundleDiffAuditQueryCliApiTests(RegistryHistoryReleaseEvidencePipelineBundleDiffAuditQueryFixture):
    def test_cli_query_and_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.bundle_for(root / "baseline", "baseline")
            candidate = self.bundle_for(root / "candidate", "candidate")
            output = root / "query.json"
            self.assertEqual(main([self.QUERY_COMMAND, "--baseline", str(baseline), "--candidate", str(candidate), "--resource", "passed", "--format", "json", "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["total_count"], len(audit.CHECK_IDS))
            self.assertEqual(main([self.QUERY_COMMAND + "-query-schema"]), 0)
            self.assertEqual(main([self.QUERY_COMMAND + "-query-result-schema"]), 0)
            self.assertEqual(main([self.QUERY_COMMAND + "-query-capabilities"]), 0)

    def test_http_query_route_and_contracts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.bundle_for(root / "baseline", "baseline")
            candidate = self.bundle_for(root / "candidate", "candidate")
            server, thread = self.server()
            try:
                prefix = "http://127.0.0.1:%s/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/release-gate/release-evidence-pipeline/bundle/diff/audit"
                prefix = prefix % server.server_port
                params = {"baseline": str(baseline), "candidate": str(candidate), "resource": "checks", "passed": "true", "format": "json"}
                with urlopen(prefix + "/query?" + urlencode(params)) as response:
                    payload = json.loads(response.read())
                    self.assertEqual(payload["total_count"], len(audit.CHECK_IDS))
                    self.assertEqual(payload["returned_count"], len(audit.CHECK_IDS))
                with urlopen(prefix + "/query-schema") as response:
                    self.assertIn("check_id", json.loads(response.read())["properties"])
                with urlopen(prefix + "/query-result-schema") as response:
                    self.assertIn("records", json.loads(response.read())["properties"])
                with urlopen(prefix + "/query-capabilities") as response:
                    self.assertIn("check identity filtering", json.loads(response.read())["features"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
