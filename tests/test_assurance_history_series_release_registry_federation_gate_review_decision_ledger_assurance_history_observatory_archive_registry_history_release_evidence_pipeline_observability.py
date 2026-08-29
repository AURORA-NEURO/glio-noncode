"""Deep contracts for timestamp-free release-evidence observability."""

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
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline import RegistryHistoryReleaseEvidencePipelineFixture


class RegistryHistoryReleaseEvidencePipelineObservabilityFixture(RegistryHistoryReleaseEvidencePipelineFixture):
    OBSERVABILITY_COMMAND = RegistryHistoryReleaseEvidencePipelineFixture.PIPELINE_COMMAND + "-observability"


class RegistryHistoryReleaseEvidencePipelineObservabilityBuildTests(RegistryHistoryReleaseEvidencePipelineObservabilityFixture):
    def test_events_and_metrics_are_ordered_linked_and_replayable(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = pipeline.build_pipeline(self.directories(Path(temporary)))
            report = observability.build_observability(value)
            self.assertTrue(report.accepted)
            self.assertTrue(report.pipeline_accepted)
            self.assertEqual(report.state, "ready")
            self.assertEqual(report.event_count, observability.MAX_EVENTS)
            self.assertEqual(report.metric_count, observability.MAX_METRICS)
            self.assertEqual(tuple(event.sequence for event in report.events), (1, 2, 3, 4, 5, 6))
            self.assertEqual(report.events[-1].event_type, "release_decision")
            self.assertEqual(report.events[-1].output_address, value.content_address)
            self.assertEqual(report.metrics[0].name, "snapshot_count")
            self.assertEqual(report.metrics[-1].value, 0)
            self.assertEqual(observability.observability_from_mapping(report.to_dict()).to_dict(), report.to_dict())
            self.assertEqual(observability.address_observability(report), report.content_address)
            self.assertIn("stage_evaluated", observability.observability_json(report))
            self.assertIn("kind", observability.observability_csv(report).splitlines()[0])
            self.assertIn("## Metrics", observability.render_observability_markdown(report))
            self.assert_public(report)

    def test_downloaded_history_observability_preserves_real_pipeline_address(self):
        source = Path(tempfile.gettempdir()) / "glio-noncode-history-audit-demo-eb48d6ff52184a0e97a4b81607b93dc2"
        if not source.is_dir():
            self.skipTest("the optional local downloaded-data demo is not present")
        value = pipeline.build_pipeline(source)
        report = observability.build_observability(value)
        self.assertEqual(report.pipeline_address, value.content_address)
        self.assertEqual(report.metrics[0].value, 2)
        self.assertEqual(report.metrics[2].value, 5)

    def test_event_metric_tamper_and_contract_bounds_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = observability.build_observability(pipeline.build_pipeline(self.directories(Path(temporary))))
            candidate = report.to_dict()
            candidate["events"][1]["accepted"] = False
            with self.assertRaises(ValidationError):
                observability.observability_from_mapping(candidate)
            candidate = report.to_dict()
            candidate["metrics"][0]["value"] = 99
            with self.assertRaises(ValidationError):
                observability.observability_from_mapping(candidate)
            with self.assertRaises(ValidationError):
                observability.RegistryHistoryReleaseEvidencePipelineEvent(0, "stage_evaluated", "release-gate", "ready", True, "input:one", "output:two", "detail", "pending:event")
            self.assert_public(observability.observability_schema())
            self.assert_public(observability.event_schema())
            self.assert_public(observability.metric_schema())
            self.assert_public(observability.capabilities())


class RegistryHistoryReleaseEvidencePipelineObservabilityCliApiTests(RegistryHistoryReleaseEvidencePipelineObservabilityFixture):
    def test_cli_observability_and_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            history_dir = self.directories(root)
            output = root / "observability.json"
            self.assertEqual(main([self.OBSERVABILITY_COMMAND, "--input", str(history_dir), "--format", "json", "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["event_count"], observability.MAX_EVENTS)
            self.assertEqual(main([self.OBSERVABILITY_COMMAND, "--input", str(history_dir), "--format", "csv"]), 0)
            self.assertEqual(main([self.OBSERVABILITY_COMMAND + "-schema"]), 0)
            self.assertEqual(main([self.OBSERVABILITY_COMMAND + "-event-schema"]), 0)
            self.assertEqual(main([self.OBSERVABILITY_COMMAND + "-metric-schema"]), 0)
            self.assertEqual(main([self.OBSERVABILITY_COMMAND + "-capabilities"]), 0)

    def test_http_observability_schema_capability_and_report_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            history_dir = self.directories(root)
            server, thread = self.server()
            try:
                prefix = "http://127.0.0.1:%s/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/release-gate/release-evidence-pipeline/observability"
                prefix = prefix % server.server_port
                with urlopen(prefix + "?" + urlencode({"input": str(history_dir), "format": "json"})) as response:
                    self.assertEqual(json.loads(response.read())["event_count"], observability.MAX_EVENTS)
                with urlopen(prefix + "/schema") as response:
                    self.assertIn("events", json.loads(response.read())["properties"])
                with urlopen(prefix + "/event-schema") as response:
                    self.assertIn("input_address", json.loads(response.read())["properties"])
                with urlopen(prefix + "/metric-schema") as response:
                    self.assertIn("unit", json.loads(response.read())["properties"])
                with urlopen(prefix + "/capabilities") as response:
                    self.assertIn("timestamp-free ordered stage events", json.loads(response.read())["features"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
