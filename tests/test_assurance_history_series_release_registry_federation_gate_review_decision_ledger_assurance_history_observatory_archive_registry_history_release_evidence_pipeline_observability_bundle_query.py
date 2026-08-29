"""Deep contracts for queries over persisted observability handoffs."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline as pipeline
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle as bundle
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_query as query
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline import RegistryHistoryReleaseEvidencePipelineFixture


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleQueryFixture(RegistryHistoryReleaseEvidencePipelineFixture):
    QUERY_COMMAND = RegistryHistoryReleaseEvidencePipelineFixture.PIPELINE_COMMAND + "-observability-bundle-query"


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleQueryBuildTests(RegistryHistoryReleaseEvidencePipelineObservabilityBundleQueryFixture):
    def test_persisted_resources_filters_pagination_and_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = pipeline.build_pipeline(self.directories(root))
            destination = root / "observability-bundle"
            bundle.write_bundle(value, destination)
            events = query.query_bundle(destination, resource="events", event_type="stage_evaluated", limit=3)
            self.assertEqual(events.total_count, 5)
            self.assertEqual(events.returned_count, 3)
            self.assertEqual(events.records[0]["stage"], "history-load")
            self.assertEqual(query.query_bundle(destination, resource="metrics", metric_name="release_ready").total_count, 1)
            passed = query.query_bundle(destination, resource="passed", passed=True)
            self.assertEqual(passed.total_count, 13)
            evidence = query.query_bundle(destination, resource="evidence", text="namespace", limit=20)
            self.assertGreaterEqual(evidence.total_count, 1)
            self.assertIn("check_address", evidence.records[0])
            self.assertEqual(query.query_result_from_mapping(json.loads(query.query_json(events))).to_dict(), events.to_dict())
            self.assertEqual(query.address_query(events), events.content_address)
            self.assert_public(events)
            self.assert_public(query.query_schema())
            self.assert_public(query.query_result_schema())
            self.assert_public(query.capabilities())

    def test_query_rejects_tampered_bundle_and_invalid_filters(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = pipeline.build_pipeline(self.directories(root))
            destination = root / "observability-bundle"
            bundle.write_bundle(value, destination)
            observability_path = destination / bundle.OBSERVABILITY_NAME
            observability_path.write_bytes(observability_path.read_bytes() + b"\n")
            with self.assertRaises(ValidationError):
                query.query_bundle(destination, resource="events")
            bundle.write_bundle(value, destination, overwrite=True)
            with self.assertRaises(ValidationError):
                query.query_bundle(destination, resource="events", stage="not-a-stage")
            result = query.query_bundle(destination, resource="events", limit=2)
            candidate = result.to_dict()
            candidate["returned_count"] = 99
            with self.assertRaises(ValidationError):
                query.query_result_from_mapping(candidate)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleQueryCliApiTests(RegistryHistoryReleaseEvidencePipelineObservabilityBundleQueryFixture):
    def test_cli_query_and_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            history_dir = self.directories(root)
            destination = root / "observability-bundle"
            output = root / "query.json"
            self.assertEqual(main([self.QUERY_COMMAND.removesuffix("-query"), "--input", str(history_dir), "--destination", str(destination)]), 0)
            self.assertEqual(main([self.QUERY_COMMAND, "--input", str(destination), "--resource", "passed", "--passed", "--limit", "2", "--format", "json", "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["total_count"], 13)
            self.assertEqual(payload["returned_count"], 2)
            self.assertEqual(main([self.QUERY_COMMAND + "-query-schema"]), 0)
            self.assertEqual(main([self.QUERY_COMMAND + "-query-result-schema"]), 0)
            self.assertEqual(main([self.QUERY_COMMAND + "-query-capabilities"]), 0)

    def test_http_persisted_bundle_query_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            history_dir = self.directories(root)
            destination = root / "observability-bundle"
            server, thread = self.server()
            try:
                prefix = "http://127.0.0.1:%s/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/release-gate/release-evidence-pipeline/observability/bundle"
                prefix = prefix % server.server_port
                with urlopen(prefix + "?" + urlencode({"input": str(history_dir), "destination": str(destination), "format": "json"})) as response:
                    self.assertEqual(json.loads(response.read())["artifact_count"], 8)
                with urlopen(prefix + "/query?" + urlencode({"input": str(destination), "resource": "metrics", "metric-name": "release_ready", "limit": "1"})) as response:
                    payload = json.loads(response.read())
                    self.assertEqual(payload["total_count"], 1)
                    self.assertEqual(payload["records"][0]["name"], "release_ready")
                with urlopen(prefix + "/query-schema") as response:
                    self.assertIn("metric_name", json.loads(response.read())["properties"])
                with urlopen(prefix + "/query-result-schema") as response:
                    self.assertIn("bundle_address", json.loads(response.read())["properties"])
                with urlopen(prefix + "/query-capabilities") as response:
                    self.assertIn("verified persisted-bundle reads", json.loads(response.read())["features"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
