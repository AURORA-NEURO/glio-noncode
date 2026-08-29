"""Deep contracts for portable release-evidence pipeline bundles."""

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
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline import RegistryHistoryReleaseEvidencePipelineFixture


class RegistryHistoryReleaseEvidencePipelineBundleFixture(RegistryHistoryReleaseEvidencePipelineFixture):
    BUNDLE_COMMAND = RegistryHistoryReleaseEvidencePipelineFixture.PIPELINE_COMMAND + "-bundle"


class RegistryHistoryReleaseEvidencePipelineBundleBuildTests(RegistryHistoryReleaseEvidencePipelineBundleFixture):
    def test_exact_five_file_bundle_replays_pipeline_and_query_views(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = pipeline.build_pipeline(self.directories(root))
            destination = root / "bundle"
            self.assertEqual(bundle.write_bundle(value, destination), destination)
            self.assertEqual({item.name for item in destination.iterdir()}, set(bundle.FILES))
            loaded = bundle.load_bundle(destination)
            self.assertEqual(loaded.to_dict(), bundle.build_bundle(value).to_dict())
            self.assertEqual(bundle.verify_bundle(destination).content_address, loaded.content_address)
            self.assertEqual(bundle.bundle_bytes(value), {name: (destination / name).read_bytes() for name in bundle.FILES})
            self.assert_public(loaded)

    def test_bundle_rejects_extra_noncanonical_and_relinked_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = pipeline.build_pipeline(self.directories(root))
            destination = root / "bundle"
            bundle.write_bundle(value, destination)
            (destination / "extra.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                bundle.load_bundle(destination)
            (destination / "extra.json").unlink()
            query_path = destination / bundle.STAGES_NAME
            query_path.write_bytes(query_path.read_bytes() + b"\n")
            with self.assertRaises(ValidationError):
                bundle.load_bundle(destination)
            bundle.write_bundle(value, destination, overwrite=True)
            manifest_path = destination / bundle.MANIFEST_NAME
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifact_count"] = 2
            manifest_path.write_text(json.dumps(manifest, separators=(",", ":"), sort_keys=True), encoding="utf-8")
            with self.assertRaises(ValidationError):
                bundle.load_bundle(destination)

    def test_bundle_schemas_capabilities_and_limits_are_public(self):
        self.assert_public(bundle.bundle_schema())
        self.assert_public(bundle.manifest_schema())
        self.assert_public(bundle.capabilities())
        self.assertEqual(tuple(bundle.capabilities()["files"]), bundle.FILES)
        self.assertEqual(bundle.capabilities()["limits"]["artifact_count"], len(bundle.ARTIFACT_FILES))


class RegistryHistoryReleaseEvidencePipelineBundleCliApiTests(RegistryHistoryReleaseEvidencePipelineBundleFixture):
    def test_cli_bundle_verify_manifest_and_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            history_dir = self.directories(root)
            destination = root / "bundle"
            output = root / "bundle.json"
            self.assertEqual(main([self.BUNDLE_COMMAND, "--input", str(history_dir), "--destination", str(destination), "--format", "json", "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["pipeline_state"], "ready")
            self.assertEqual(main([self.BUNDLE_COMMAND + "-verify", "--input", str(destination)]), 0)
            self.assertEqual(main([self.BUNDLE_COMMAND + "-manifest", "--input", str(destination)]), 0)
            self.assertEqual(main([self.BUNDLE_COMMAND + "-schema"]), 0)
            self.assertEqual(main([self.BUNDLE_COMMAND + "-manifest-schema"]), 0)
            self.assertEqual(main([self.BUNDLE_COMMAND + "-capabilities"]), 0)

    def test_http_bundle_routes_create_verify_manifest_and_expose_contracts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            history_dir = self.directories(root)
            destination = root / "bundle"
            server, thread = self.server()
            try:
                prefix = "http://127.0.0.1:%s/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/release-gate/release-evidence-pipeline/bundle"
                prefix = prefix % server.server_port
                with urlopen(prefix + "?" + urlencode({"input": str(history_dir), "destination": str(destination), "format": "json"})) as response:
                    self.assertEqual(json.loads(response.read())["pipeline_state"], "ready")
                with urlopen(prefix + "/verify?" + urlencode({"input": str(destination)})) as response:
                    self.assertEqual(json.loads(response.read())["artifact_count"], 4)
                with urlopen(prefix + "/manifest?" + urlencode({"input": str(destination)})) as response:
                    self.assertEqual(json.loads(response.read())["artifact_count"], 4)
                with urlopen(prefix + "/schema") as response:
                    self.assertIn("pipeline", json.loads(response.read())["properties"])
                with urlopen(prefix + "/manifest-schema") as response:
                    self.assertIn("artifacts", json.loads(response.read())["properties"])
                with urlopen(prefix + "/capabilities") as response:
                    self.assertIn("exact five-file persistence", json.loads(response.read())["features"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
