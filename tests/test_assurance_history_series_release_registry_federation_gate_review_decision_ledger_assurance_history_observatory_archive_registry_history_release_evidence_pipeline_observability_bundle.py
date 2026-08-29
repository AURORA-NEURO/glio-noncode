"""Deep contracts for durable release-evidence observability handoffs."""

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
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline import RegistryHistoryReleaseEvidencePipelineFixture


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleFixture(RegistryHistoryReleaseEvidencePipelineFixture):
    BUNDLE_COMMAND = RegistryHistoryReleaseEvidencePipelineFixture.PIPELINE_COMMAND + "-observability-bundle"


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleBuildTests(RegistryHistoryReleaseEvidencePipelineObservabilityBundleFixture):
    def test_exact_nine_file_handoff_replays_every_projection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = pipeline.build_pipeline(self.directories(root))
            destination = root / "observability-bundle"
            self.assertEqual(bundle.write_bundle(value, destination), destination)
            self.assertEqual({item.name for item in destination.iterdir()}, set(bundle.FILES))
            loaded = bundle.load_bundle(destination)
            self.assertEqual(loaded.to_dict(), bundle.build_bundle(value).to_dict())
            self.assertEqual(bundle.verify_bundle(destination).content_address, loaded.content_address)
            self.assertEqual(bundle.bundle_bytes(value), {name: (destination / name).read_bytes() for name in bundle.FILES})
            self.assertEqual(loaded.artifact_count, 8)
            self.assertEqual(len(loaded.query_addresses), 5)
            self.assertTrue(loaded.audit_accepted)
            self.assert_public(loaded)

    def test_handoff_rejects_extra_noncanonical_and_relinked_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = pipeline.build_pipeline(self.directories(root))
            destination = root / "observability-bundle"
            bundle.write_bundle(value, destination)
            (destination / "extra.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                bundle.load_bundle(destination)
            (destination / "extra.json").unlink()
            observability_path = destination / bundle.OBSERVABILITY_NAME
            observability_path.write_bytes(observability_path.read_bytes() + b"\n")
            with self.assertRaises(ValidationError):
                bundle.load_bundle(destination)
            bundle.write_bundle(value, destination, overwrite=True)
            manifest_path = destination / bundle.MANIFEST_NAME
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["audit_accepted"] = False
            manifest_path.write_text(json.dumps(manifest, separators=(",", ":"), sort_keys=True), encoding="utf-8")
            with self.assertRaises(ValidationError):
                bundle.load_bundle(destination)

    def test_schemas_capabilities_and_limits_describe_the_closed_handoff(self):
        self.assert_public(bundle.bundle_schema())
        self.assert_public(bundle.manifest_schema())
        capabilities = bundle.capabilities()
        self.assert_public(capabilities)
        self.assertEqual(tuple(capabilities["files"]), bundle.FILES)
        self.assertEqual(capabilities["limits"]["artifact_count"], len(bundle.ARTIFACT_FILES))
        self.assertIn("independent observability audit capture", capabilities["features"])


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCliApiTests(RegistryHistoryReleaseEvidencePipelineObservabilityBundleFixture):
    def test_cli_creates_verifies_and_exposes_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            history_dir = self.directories(root)
            destination = root / "observability-bundle"
            output = root / "bundle.json"
            self.assertEqual(main([self.BUNDLE_COMMAND, "--input", str(history_dir), "--destination", str(destination), "--format", "json", "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["artifact_count"], 8)
            self.assertEqual(main([self.BUNDLE_COMMAND + "-verify", "--input", str(destination)]), 0)
            self.assertEqual(main([self.BUNDLE_COMMAND + "-manifest", "--input", str(destination)]), 0)
            self.assertEqual(main([self.BUNDLE_COMMAND + "-schema"]), 0)
            self.assertEqual(main([self.BUNDLE_COMMAND + "-manifest-schema"]), 0)
            self.assertEqual(main([self.BUNDLE_COMMAND + "-capabilities"]), 0)

    def test_http_creates_verifies_and_exposes_contract_routes(self):
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
                with urlopen(prefix + "/verify?" + urlencode({"input": str(destination)})) as response:
                    self.assertEqual(json.loads(response.read())["audit_accepted"], True)
                with urlopen(prefix + "/manifest?" + urlencode({"input": str(destination)})) as response:
                    self.assertEqual(json.loads(response.read())["artifact_count"], 8)
                with urlopen(prefix + "/schema") as response:
                    self.assertIn("observability", json.loads(response.read())["properties"])
                with urlopen(prefix + "/manifest-schema") as response:
                    self.assertIn("audit_address", json.loads(response.read())["properties"])
                with urlopen(prefix + "/capabilities") as response:
                    self.assertIn("exact nine-file persistence", json.loads(response.read())["features"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
