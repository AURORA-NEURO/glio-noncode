"""Deep contracts for independent release-evidence bundle audits."""

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
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline import RegistryHistoryReleaseEvidencePipelineFixture


class RegistryHistoryReleaseEvidencePipelineBundleAuditFixture(RegistryHistoryReleaseEvidencePipelineFixture):
    BUNDLE_COMMAND = RegistryHistoryReleaseEvidencePipelineFixture.PIPELINE_COMMAND + "-bundle"
    AUDIT_COMMAND = BUNDLE_COMMAND + "-audit"


class RegistryHistoryReleaseEvidencePipelineBundleAuditBuildTests(RegistryHistoryReleaseEvidencePipelineBundleAuditFixture):
    def test_real_bundle_audit_replays_all_thirteen_checks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = pipeline.build_pipeline(self.directories(root))
            destination = root / "bundle"
            bundle.write_bundle(value, destination)
            result = audit.audit_bundle_directory(destination)
            self.assertTrue(result.accepted)
            self.assertEqual(result.state, "complete")
            self.assertEqual(result.pipeline_address, value.content_address)
            self.assertEqual(result.check_count, len(audit.CHECK_IDS))
            self.assertEqual(result.passed_count, len(audit.CHECK_IDS))
            self.assertEqual(tuple(check.check_id for check in result.checks), audit.CHECK_IDS)
            self.assertTrue(all(check.passed for check in result.checks))
            self.assertEqual(audit.audit_from_mapping(json.loads(audit.audit_json(result))).to_dict(), result.to_dict())
            self.assert_public(result)
            self.assert_public(audit.audit_schema())
            self.assert_public(audit.check_schema())
            self.assert_public(audit.capabilities())

    def test_audit_is_independent_and_reports_extra_noncanonical_and_invalid_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = pipeline.build_pipeline(self.directories(root))
            destination = root / "bundle"
            bundle.write_bundle(value, destination)
            (destination / "extra.json").write_text("{}", encoding="utf-8")
            result = audit.audit_bundle(destination)
            self.assertFalse(result.accepted)
            self.assertFalse(result.checks[0].passed)
            self.assertIn("incomplete", audit.render_audit_markdown(result))
            (destination / "extra.json").unlink()
            stages = destination / bundle.STAGES_NAME
            stages.write_bytes(stages.read_bytes() + b"\n")
            result = audit.audit_bundle_directory(destination)
            self.assertFalse(result.accepted)
            self.assertFalse(result.checks[1].passed)
            self.assertFalse(result.checks[11].passed)
            self.assertEqual(result.check_count, len(audit.CHECK_IDS))
            bundle.write_bundle(value, destination, overwrite=True)
            (destination / bundle.EVIDENCE_NAME).write_bytes(b"not-json")
            result = audit.audit_bundle_directory(destination)
            self.assertFalse(result.accepted)
            self.assertFalse(result.checks[1].passed)
            self.assertFalse(result.checks[9].passed)
            self.assertEqual(result.failed_count, len(audit.CHECK_IDS) - result.passed_count)

    def test_audit_rejects_private_mapping_and_tampered_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = pipeline.build_pipeline(self.directories(root))
            destination = root / "bundle"
            bundle.write_bundle(value, destination)
            result = audit.audit_bundle_directory(destination)
            document = result.to_dict()
            document["checks"][0]["detail"] = "changed"
            with self.assertRaises(ValidationError):
                audit.audit_from_mapping(document)
            self.assertNotIn("path", audit.audit_json(result).lower())
            self.assertNotIn("timestamp", audit.audit_json(result).lower())


class RegistryHistoryReleaseEvidencePipelineBundleAuditCliApiTests(RegistryHistoryReleaseEvidencePipelineBundleAuditFixture):
    def test_cli_audit_and_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            history_dir = self.directories(root)
            destination = root / "bundle"
            bundle_output = root / "bundle.json"
            audit_output = root / "audit.json"
            self.assertEqual(main([self.BUNDLE_COMMAND, "--input", str(history_dir), "--destination", str(destination), "--output", str(bundle_output)]), 0)
            self.assertEqual(main([self.AUDIT_COMMAND, "--input", str(destination), "--format", "json", "--output", str(audit_output)]), 0)
            self.assertTrue(json.loads(audit_output.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(main([self.AUDIT_COMMAND + "-schema"]), 0)
            self.assertEqual(main([self.AUDIT_COMMAND + "-check-schema"]), 0)
            self.assertEqual(main([self.AUDIT_COMMAND + "-capabilities"]), 0)

    def test_http_audit_route_returns_diagnostics_and_contracts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            history_dir = self.directories(root)
            destination = root / "bundle"
            server, thread = self.server()
            try:
                prefix = "http://127.0.0.1:%s/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/release-gate/release-evidence-pipeline/bundle/audit"
                prefix = prefix % server.server_port
                bundle.write_bundle(pipeline.build_pipeline(history_dir), destination)
                with urlopen(prefix + "?" + urlencode({"input": str(destination), "format": "json"})) as response:
                    payload = json.loads(response.read())
                    self.assertTrue(payload["accepted"])
                    self.assertEqual(payload["check_count"], 13)
                with urlopen(prefix + "/schema") as response:
                    self.assertIn("checks", json.loads(response.read())["properties"])
                with urlopen(prefix + "/check-schema") as response:
                    self.assertIn("evidence_address", json.loads(response.read())["properties"])
                with urlopen(prefix + "/capabilities") as response:
                    self.assertIn("independent raw five-file audit", json.loads(response.read())["features"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
