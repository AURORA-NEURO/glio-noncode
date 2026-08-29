"""Deep contracts for release-evidence observability handoff diffs."""

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
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle as bundle
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_diff as diff
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline import RegistryHistoryReleaseEvidencePipelineFixture


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffFixture(RegistryHistoryReleaseEvidencePipelineFixture):
    BUNDLE_COMMAND = RegistryHistoryReleaseEvidencePipelineFixture.PIPELINE_COMMAND + "-observability-bundle"
    DIFF_COMMAND = BUNDLE_COMMAND + "-diff"

    def bundle_for(self, root: Path, name: str) -> Path:
        value = self.one_registry(root, name, registry_id="registry:" + name)
        registry_dir = root / (name + "-registry")
        registry.write_registry(value, registry_dir)
        history_dir = root / (name + "-history")
        history.write_history(history.build_history_from_directories((registry_dir, registry_dir), history_id="history:" + name), history_dir)
        bundle_dir = root / (name + "-bundle")
        bundle.write_bundle(pipeline.build_pipeline(history_dir), bundle_dir)
        return bundle_dir


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffBuildTests(RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffFixture):
    def test_identical_handoff_is_unchanged_and_replayable(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = self.bundle_for(Path(temporary), "same")
            value = diff.build_diff(source, source)
            self.assertEqual(value.state, "unchanged")
            self.assertEqual(value.changed_count, 0)
            self.assertEqual(value.unchanged_count, len(bundle.FILES))
            self.assertEqual(value.changed_fields, ())
            self.assertEqual(tuple(item.name for item in value.items), bundle.FILES)
            self.assertEqual(diff.address_diff(value), value.content_address)
            self.assertEqual(diff.diff_from_mapping(json.loads(diff.diff_json(value))).to_dict(), value.to_dict())
            self.assert_public(value)

    def test_changed_handoff_exposes_semantic_and_byte_transitions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.bundle_for(root / "baseline", "baseline")
            candidate = self.bundle_for(root / "candidate", "candidate")
            value = diff.diff_bundle_directories(baseline, candidate, diff_id="observability-bundle-diff:test")
            self.assertEqual(value.state, "mixed")
            self.assertGreater(value.changed_count, 0)
            self.assertEqual(value.changed_count + value.unchanged_count, len(bundle.FILES))
            self.assertIn("observability_address", value.changed_fields)
            self.assertIn("content_address", value.changed_fields)
            self.assertTrue(all(item.action == "changed" for item in value.items))
            self.assertTrue(all(item.content_address == diff.address_diff_item(item) for item in value.items))
            self.assertIn("Observability", diff.render_diff_markdown(value))
            self.assertIn("baseline_hash", diff.diff_csv(value).splitlines()[0])
            self.assert_public(diff.diff_schema())
            self.assert_public(diff.item_schema())
            self.assert_public(diff.capabilities())

    def test_diff_requires_strict_verified_inputs_and_rejects_tampered_mapping(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = self.bundle_for(Path(temporary), "strict")
            observability_path = source / bundle.OBSERVABILITY_NAME
            observability_path.write_bytes(observability_path.read_bytes() + b"\n")
            with self.assertRaises(ValidationError):
                diff.build_diff(source, source)
            clean = self.bundle_for(Path(temporary) / "clean", "clean")
            value = diff.build_diff(clean, clean)
            document = value.to_dict()
            document["items"][0]["detail"] = "tampered"
            with self.assertRaises(ValidationError):
                diff.diff_from_mapping(document)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffCliApiTests(RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffFixture):
    def test_cli_diff_and_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.bundle_for(root / "baseline", "baseline")
            candidate = self.bundle_for(root / "candidate", "candidate")
            output = root / "diff.json"
            self.assertEqual(main([self.DIFF_COMMAND, "--baseline", str(baseline), "--candidate", str(candidate), "--format", "json", "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["item_count"], len(bundle.FILES))
            self.assertEqual(main([self.DIFF_COMMAND + "-schema"]), 0)
            self.assertEqual(main([self.DIFF_COMMAND + "-item-schema"]), 0)
            self.assertEqual(main([self.DIFF_COMMAND + "-capabilities"]), 0)

    def test_http_diff_route_and_contracts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.bundle_for(root / "baseline", "baseline")
            candidate = self.bundle_for(root / "candidate", "candidate")
            server, thread = self.server()
            try:
                prefix = "http://127.0.0.1:%s/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/release-gate/release-evidence-pipeline/observability/bundle/diff"
                prefix = prefix % server.server_port
                with urlopen(prefix + "?" + urlencode({"baseline": str(baseline), "candidate": str(candidate), "format": "json"})) as response:
                    payload = json.loads(response.read())
                    self.assertEqual(payload["item_count"], len(bundle.FILES))
                    self.assertEqual(payload["state"], "mixed")
                with urlopen(prefix + "/schema") as response:
                    self.assertIn("candidate_observability_address", json.loads(response.read())["properties"])
                with urlopen(prefix + "/item-schema") as response:
                    self.assertIn("candidate_hash", json.loads(response.read())["properties"])
                with urlopen(prefix + "/capabilities") as response:
                    self.assertIn("strict verified observability-bundle comparison", json.loads(response.read())["features"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
