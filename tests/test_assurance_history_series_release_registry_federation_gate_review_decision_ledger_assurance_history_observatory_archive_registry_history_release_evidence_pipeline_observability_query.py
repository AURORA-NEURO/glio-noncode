"""Deep contracts for release-evidence observability queries."""

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
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_query as query
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline import RegistryHistoryReleaseEvidencePipelineFixture


class RegistryHistoryReleaseEvidencePipelineObservabilityQueryFixture(RegistryHistoryReleaseEvidencePipelineFixture):
    QUERY_COMMAND = RegistryHistoryReleaseEvidencePipelineFixture.PIPELINE_COMMAND + "-observability-query"


class RegistryHistoryReleaseEvidencePipelineObservabilityQueryBuildTests(RegistryHistoryReleaseEvidencePipelineObservabilityQueryFixture):
    def test_event_metric_views_filters_pagination_and_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = pipeline.build_pipeline(self.directories(Path(temporary)))
            report = observability.build_observability(value)
            events = query.query_observability(report, resource="events", event_type="stage_evaluated", accepted=True, limit=3)
            self.assertEqual(events.total_count, 5)
            self.assertEqual(events.returned_count, 3)
            self.assertEqual(events.records[0]["stage"], "history-load")
            self.assertEqual(query.query_observability(report, resource="accepted").total_count, 6)
            self.assertEqual(query.query_observability(report, resource="rejected").total_count, 0)
            metrics = query.query_pipeline(value, resource="metrics", metric_name="snapshot_count", plane="coverage")
            self.assertEqual(metrics.total_count, 1)
            self.assertEqual(metrics.records[0]["value"], 2)
            self.assertEqual(query.query_observability(report, resource="events", text="final release decision").total_count, 1)
            self.assertEqual(query.query_from_mapping(json.loads(query.query_json(events))).to_dict(), events.to_dict())
            self.assertEqual(query.address_query(events), events.content_address)
            self.assert_public(events)

    def test_downloaded_history_query_preserves_real_pipeline_observability(self):
        source = Path(tempfile.gettempdir()) / "glio-noncode-history-audit-demo-eb48d6ff52184a0e97a4b81607b93dc2"
        if not source.is_dir():
            self.skipTest("the optional local downloaded-data demo is not present")
        result = query.query_pipeline_directory(source, resource="metrics", plane="decision", limit=20)
        self.assertEqual(result.total_count, 4)
        self.assertEqual(result.observability_address, observability.build_observability(pipeline.build_pipeline(source)).content_address)
        self.assertEqual({record["name"] for record in result.records}, {"decision_count", "accepted_decision_count", "pipeline_accepted", "release_ready"})

    def test_query_contract_fails_closed_on_tampering_and_unsupported_filters(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = observability.build_observability(pipeline.build_pipeline(self.directories(Path(temporary))))
            with self.assertRaises(ValidationError):
                query.RegistryHistoryReleaseEvidencePipelineObservabilityQuery(metric_name="missing")
            with self.assertRaises(ValidationError):
                query.RegistryHistoryReleaseEvidencePipelineObservabilityQuery(limit=0)
            with self.assertRaises(ValidationError):
                query.query_observability(report, query.RegistryHistoryReleaseEvidencePipelineObservabilityQuery(resource="events"), resource="metrics")
            result = query.query_observability(report, resource="events", limit=2)
            candidate = result.to_dict()
            candidate["records"][0]["detail"] = "tampered"
            with self.assertRaises(ValidationError):
                query.query_from_mapping(candidate)
            self.assert_public(query.query_schema())
            self.assert_public(query.query_result_schema())
            self.assert_public(query.capabilities())


class RegistryHistoryReleaseEvidencePipelineObservabilityQueryCliApiTests(RegistryHistoryReleaseEvidencePipelineObservabilityQueryFixture):
    def test_cli_query_and_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            history_dir = self.directories(root)
            output = root / "observability-query.json"
            self.assertEqual(main([self.QUERY_COMMAND, "--input", str(history_dir), "--resource", "events", "--event-type", "stage_evaluated", "--accepted", "--limit", "2", "--format", "json", "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["returned_count"], 2)
            self.assertEqual(main([self.QUERY_COMMAND, "--input", str(history_dir), "--resource", "metrics", "--plane", "decision", "--format", "csv"]), 0)
            self.assertEqual(main([self.QUERY_COMMAND, "--input", str(history_dir), "--resource", "accepted", "--format", "markdown"]), 0)
            self.assertEqual(main([self.QUERY_COMMAND + "-query-schema"]), 0)
            self.assertEqual(main([self.QUERY_COMMAND + "-query-result-schema"]), 0)
            self.assertEqual(main([self.QUERY_COMMAND + "-query-capabilities"]), 0)

    def test_http_query_schema_capability_and_report_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            history_dir = self.directories(root)
            server, thread = self.server()
            try:
                prefix = "http://127.0.0.1:%s/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/release-gate/release-evidence-pipeline/observability"
                prefix = prefix % server.server_port
                with urlopen(prefix + "/query?" + urlencode({"input": str(history_dir), "resource": "metrics", "metric_name": "snapshot_count", "format": "json"})) as response:
                    payload = json.loads(response.read())
                    self.assertEqual(payload["total_count"], 1)
                    self.assertEqual(payload["records"][0]["name"], "snapshot_count")
                with urlopen(prefix + "/query-schema") as response:
                    self.assertIn("metric_name", json.loads(response.read())["properties"])
                with urlopen(prefix + "/query-result-schema") as response:
                    self.assertIn("observability_address", json.loads(response.read())["properties"])
                with urlopen(prefix + "/query-capabilities") as response:
                    self.assertIn("accepted", json.loads(response.read())["resources"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
