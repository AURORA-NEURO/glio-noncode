"""Deep contracts for independent release-gate package audits."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate as gate
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_package as package
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_package_audit as audit
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_package import RegistryHistoryReleaseGatePackageFixture


class RegistryHistoryReleaseGatePackageAuditFixture(RegistryHistoryReleaseGatePackageFixture):
    AUDIT_COMMAND = RegistryHistoryReleaseGatePackageFixture.PACKAGE_COMMAND + "-audit"

    def package_directory(self, root: Path) -> Path:
        value = self.gate_value(root)
        destination = root / "package"
        package.write_package(value, destination)
        return destination

    def server(self):
        from glio_noncode.api import create_server

        import threading

        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread


class RegistryHistoryReleaseGatePackageAuditBuildTests(RegistryHistoryReleaseGatePackageAuditFixture):
    def test_typed_and_persisted_audits_are_complete_and_replayable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.gate_value(root)
            typed_report = audit.audit_gate(value)
            package_dir = root / "package"
            package.write_package(value, package_dir)
            persisted_report = audit.audit_package_directory(package_dir)
            self.assertEqual(typed_report.to_dict(), persisted_report.to_dict())
            self.assertEqual(persisted_report.state, "complete")
            self.assertEqual((persisted_report.passed_count, persisted_report.failed_count), (audit.MAX_CHECKS, 0))
            self.assertEqual(audit.audit_from_mapping(persisted_report.to_dict()).to_dict(), persisted_report.to_dict())
            self.assertEqual(audit.address_audit(persisted_report), persisted_report.content_address)
            self.assert_public(persisted_report)

    def test_exact_members_and_receipts_are_audited_without_fail_fast(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.gate_value(root)
            package_dir = root / "package"
            package.write_package(value, package_dir)
            (package_dir / "unexpected.json").write_text("{}", encoding="utf-8")
            report = audit.audit_package_directory(package_dir)
            self.assertEqual(report.state, "incomplete")
            self.assertFalse(report.accepted)
            self.assertFalse(report.checks[0].passed)
            (package_dir / "unexpected.json").unlink()
            gate_bytes = (package_dir / package.GATE_NAME).read_bytes()
            (package_dir / package.GATE_NAME).write_bytes(gate_bytes + b"\n")
            report = audit.audit_package_directory(package_dir)
            self.assertFalse(report.checks[1].passed)
            self.assertFalse(report.checks[3].passed)
            with self.assertRaises(ValidationError):
                package.load_package(package_dir)

    def test_manifest_linkage_and_public_boundary_fail_independently(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.gate_value(root)
            package_dir = root / "package"
            package.write_package(value, package_dir)
            manifest_path = package_dir / package.MANIFEST_NAME
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["policy_address"] = "glio-noncode-assurance-history-observatory-archive-registry-history-release-gate-policy:tampered"
            manifest_path.write_text(json.dumps(manifest, separators=(",", ":"), sort_keys=True), encoding="utf-8")
            report = audit.audit_package_directory(package_dir)
            self.assertFalse(report.checks[2].passed)
            self.assertFalse(report.checks[5].passed)

            package.write_package(value, package_dir, overwrite=True)
            gate_path = package_dir / package.GATE_NAME
            gate_document = json.loads(gate_path.read_text(encoding="utf-8"))
            gate_document["agent"] = "forbidden"
            gate_path.write_text(json.dumps(gate_document, separators=(",", ":"), sort_keys=True), encoding="utf-8")
            report = audit.audit_package_directory(package_dir)
            self.assertFalse(report.checks[8].passed)
            self.assertFalse(report.checks[6].passed)

    def test_downloaded_gate_package_audit_is_complete(self):
        source = Path(tempfile.gettempdir()) / "glio-noncode-history-release-gate-package-demo"
        if not source.is_dir():
            self.skipTest("the optional local downloaded-data package demo is not present")
        report = audit.audit_package_directory(source)
        self.assertTrue(report.accepted)
        self.assertEqual(report.passed_count, audit.MAX_CHECKS)
        self.assertEqual(report.gate_address.split(":", 1)[0], gate.GATE_PREFIX)

    def test_schemas_capabilities_and_markdown_are_public(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = audit.audit_gate(self.gate_value(Path(temporary)))
            self.assert_public(audit.audit_schema())
            self.assert_public(audit.check_schema())
            self.assert_public(audit.capabilities())
            self.assertIn("manifest", audit.render_audit_markdown(report))
            self.assertIn("content address", audit.audit_json(report))


class RegistryHistoryReleaseGatePackageAuditCliApiTests(RegistryHistoryReleaseGatePackageAuditFixture):
    def test_cli_audit_and_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package_dir = self.package_directory(root)
            output = root / "audit.json"
            self.assertEqual(main([self.AUDIT_COMMAND, "--input", str(package_dir), "--format", "json", "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["state"], "complete")
            self.assertEqual(main([self.AUDIT_COMMAND, "--input", str(package_dir), "--format", "markdown"]), 0)
            self.assertEqual(main([self.AUDIT_COMMAND + "-schema"]), 0)
            self.assertEqual(main([self.AUDIT_COMMAND + "-check-schema"]), 0)
            self.assertEqual(main([self.AUDIT_COMMAND + "-capabilities"]), 0)

    def test_http_audit_schema_capability_and_report_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package_dir = self.package_directory(root)
            server, thread = self.server()
            try:
                prefix = "http://127.0.0.1:%s/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/release-gate/package/audit"
                prefix = prefix % server.server_port
                with urlopen(prefix + "?" + urlencode({"input": str(package_dir), "format": "json"})) as response:
                    self.assertEqual(json.loads(response.read())["state"], "complete")
                with urlopen(prefix + "/schema") as response:
                    self.assertIn("manifest_address", json.loads(response.read())["properties"])
                with urlopen(prefix + "/check-schema") as response:
                    self.assertIn("check_id", json.loads(response.read())["properties"])
                with urlopen(prefix + "/capabilities") as response:
                    self.assertIn("raw exact-member package audit", json.loads(response.read())["features"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
