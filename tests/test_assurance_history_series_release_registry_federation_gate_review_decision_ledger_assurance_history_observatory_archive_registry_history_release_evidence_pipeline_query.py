"""Deep contracts for consolidated release-evidence pipeline queries."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline as pipeline
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_query as query
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline import RegistryHistoryReleaseEvidencePipelineFixture


class RegistryHistoryReleaseEvidencePipelineQueryFixture(RegistryHistoryReleaseEvidencePipelineFixture):
    QUERY_COMMAND = RegistryHistoryReleaseEvidencePipelineFixture.PIPELINE_COMMAND + "-query"


class RegistryHistoryReleaseEvidencePipelineQueryBuildTests(RegistryHistoryReleaseEvidencePipelineQueryFixture):
    def test_stage_decision_and_evidence_resources_are_bounded_and_replayable(self):
        with tempfile.TemporaryDirectory() as temporary:
            history_dir = self.directories(Path(temporary))
            value = pipeline.build_pipeline(history_dir)
            stages = query.query_pipeline(value, resource="stages", limit=20)
            self.assertEqual(stages.total_count, len(query.STAGE_IDS))
            self.assertEqual(stages.returned_count, len(query.STAGE_IDS))
            self.assertEqual(stages.records[0]["stage"], "history-load")
            self.assertEqual(query.query_pipeline(value, resource="stages", stage="release-gate").records[0]["address"], value.gate_address)
            self.assertEqual(query.query_pipeline(value, resource="decisions", accepted=True).total_count, 3)
            evidence = query.query_pipeline(value, resource="evidence", text="certificate", limit=20)
            self.assertGreaterEqual(evidence.total_count, 1)
            self.assertEqual(query.query_result_from_mapping(json.loads(query.query_json(evidence))).to_dict(), evidence.to_dict())
            self.assertEqual(query.address_query(evidence), evidence.content_address)
            self.assert_public(evidence)

    def test_downloaded_history_query_exposes_the_real_receipt(self):
        source = Path(tempfile.gettempdir()) / "glio-noncode-history-audit-demo-eb48d6ff52184a0e97a4b81607b93dc2"
        if not source.is_dir():
            self.skipTest("the optional local downloaded-data demo is not present")
        result = query.query_history_directory(source, resource="stages", limit=20)
        self.assertEqual(result.total_count, 5)
        self.assertEqual(result.records[-1]["state"], "ready")
        self.assertEqual(result.pipeline_address, pipeline.build_pipeline(source).content_address)

    def test_query_filters_bounds_and_public_contracts(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = pipeline.build_pipeline(self.directories(Path(temporary)))
            selected = query.RegistryHistoryReleaseEvidencePipelineQuery(resource="stages", accepted=True, text="address", offset=1, limit=2)
            result = query.query_pipeline(value, selected)
            self.assertLessEqual(result.returned_count, 2)
            self.assert_public(query.query_schema())
            self.assert_public(query.query_result_schema())
            self.assert_public(query.capabilities())
            self.assertIn("release-certificate", query.capabilities()["stages"])
            with self.assertRaises(ValidationError):
                query.RegistryHistoryReleaseEvidencePipelineQuery(resource="missing")
            with self.assertRaises(ValidationError):
                query.RegistryHistoryReleaseEvidencePipelineQuery(stage="missing")
            with self.assertRaises(ValidationError):
                query.query_pipeline(value, selected, limit=2)


class RegistryHistoryReleaseEvidencePipelineQueryCliApiTests(RegistryHistoryReleaseEvidencePipelineQueryFixture):
    def test_cli_query_and_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            history_dir = self.directories(root)
            output = root / "query.json"
            self.assertEqual(main([self.QUERY_COMMAND, "--input", str(history_dir), "--resource", "stages", "--limit", "2", "--format", "json", "--output", str(output)]), 0)
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
                prefix = "http://127.0.0.1:%s/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/release-gate/release-evidence-pipeline"
                prefix = prefix % server.server_port
                with urlopen(prefix + "/query?" + urlencode({"input": str(history_dir), "resource": "stages", "limit": "2", "format": "json"})) as response:
                    self.assertEqual(json.loads(response.read())["returned_count"], 2)
                with urlopen(prefix + "/query-schema") as response:
                    self.assertIn("stage", json.loads(response.read())["properties"])
                with urlopen(prefix + "/query-result-schema") as response:
                    self.assertIn("pipeline_address", json.loads(response.read())["properties"])
                with urlopen(prefix + "/query-capabilities") as response:
                    self.assertIn("evidence", json.loads(response.read())["resources"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
