"""Deep contracts for the downloaded-history release-evidence pipeline."""

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
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_package as package
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_package import RegistryHistoryReleaseGatePackageFixture


class RegistryHistoryReleaseEvidencePipelineFixture(RegistryHistoryReleaseGatePackageFixture):
    PIPELINE_COMMAND = RegistryHistoryReleaseGatePackageFixture.PACKAGE_COMMAND.removesuffix("-package") + "-release-evidence-pipeline"

    def directories(self, root: Path) -> Path:
        registry_value = self.one_registry(root, "pipeline-cli")
        registry_dir = root / "registry"
        registry.write_registry(registry_value, registry_dir)
        history_dir = root / "history"
        history.write_history(history.build_history_from_directories((registry_dir, registry_dir), history_id="history:pipeline-cli"), history_dir)
        return history_dir


class RegistryHistoryReleaseEvidencePipelineBuildTests(RegistryHistoryReleaseEvidencePipelineFixture):
    def test_downloaded_history_composes_all_release_evidence_stages(self):
        source = Path(tempfile.gettempdir()) / "glio-noncode-history-audit-demo-eb48d6ff52184a0e97a4b81607b93dc2"
        if not source.is_dir():
            self.skipTest("the optional local downloaded-data demo is not present")
        value = pipeline.build_pipeline(source)
        self.assertTrue(value.accepted)
        self.assertTrue(value.release_ready)
        self.assertEqual(value.state, "ready")
        self.assertEqual(value.snapshot_count, 2)
        self.assertEqual(value.package_file_count, len(package.FILES))
        self.assertEqual(value.gate_state, "ready")
        self.assertEqual(value.package_audit_state, "complete")
        self.assertEqual(value.certificate_state, "ready")
        self.assertEqual(pipeline.pipeline_from_mapping(value.to_dict()).to_dict(), value.to_dict())
        self.assertEqual(pipeline.address_pipeline(value), value.content_address)
        self.assert_public(value)

    def test_durable_destination_replays_the_same_chain(self):
        source = Path(tempfile.gettempdir()) / "glio-noncode-history-audit-demo-eb48d6ff52184a0e97a4b81607b93dc2"
        if not source.is_dir():
            self.skipTest("the optional local downloaded-data demo is not present")
        with tempfile.TemporaryDirectory() as temporary:
            value = pipeline.build_pipeline(source, Path(temporary) / "package")
            self.assertEqual({item.name for item in (Path(temporary) / "package").iterdir()}, set(package.FILES))
            self.assertEqual(value.package_audit_state, "complete")
            self.assertTrue(value.certificate_accepted)
            self.assert_public(value)

    def test_schemas_and_capabilities_are_public(self):
        self.assert_public(pipeline.pipeline_schema())
        self.assert_public(pipeline.capabilities())
        self.assertEqual(pipeline.capabilities()["stages"][-1], "release-certificate")


class RegistryHistoryReleaseEvidencePipelineCliApiTests(RegistryHistoryReleaseEvidencePipelineFixture):
    def test_cli_pipeline_and_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            history_dir = self.directories(root)
            destination = root / "pipeline-package"
            output = root / "pipeline.json"
            self.assertEqual(main([self.PIPELINE_COMMAND, "--input", str(history_dir), "--destination", str(destination), "--format", "json", "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["state"], "ready")
            self.assertEqual(main([self.PIPELINE_COMMAND + "-schema"]), 0)
            self.assertEqual(main([self.PIPELINE_COMMAND + "-capabilities"]), 0)

    def test_http_pipeline_schema_capability_and_report_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            history_dir = self.directories(root)
            server, thread = self.server()
            try:
                prefix = "http://127.0.0.1:%s/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/release-gate/release-evidence-pipeline"
                prefix = prefix % server.server_port
                with urlopen(prefix + "?" + urlencode({"input": str(history_dir), "format": "json"})) as response:
                    self.assertEqual(json.loads(response.read())["state"], "ready")
                with urlopen(prefix + "/schema") as response:
                    self.assertIn("certificate_address", json.loads(response.read())["properties"])
                with urlopen(prefix + "/capabilities") as response:
                    self.assertIn("single-call downloaded-history orchestration", json.loads(response.read())["features"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
