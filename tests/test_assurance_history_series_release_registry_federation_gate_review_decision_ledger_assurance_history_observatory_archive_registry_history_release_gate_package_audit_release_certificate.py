"""Deep contracts for package-audit release certificates."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_package_audit as audit
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_package_audit_release_certificate as certificate
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_package_audit import RegistryHistoryReleaseGatePackageAuditFixture


class RegistryHistoryReleaseGatePackageAuditCertificateFixture(RegistryHistoryReleaseGatePackageAuditFixture):
    CERTIFICATE_COMMAND = RegistryHistoryReleaseGatePackageAuditFixture.AUDIT_COMMAND.replace("-audit", "-audit-certificate")


class RegistryHistoryReleaseGatePackageAuditCertificateBuildTests(RegistryHistoryReleaseGatePackageAuditCertificateFixture):
    def test_downloaded_audit_is_ready_and_replayable(self):
        source = Path(tempfile.gettempdir()) / "glio-noncode-history-release-gate-package-demo"
        if not source.is_dir():
            self.skipTest("the optional local downloaded-data package demo is not present")
        report = audit.audit_package_directory(source)
        value = certificate.evaluate_audit(report)
        self.assertEqual(value.state, "ready")
        self.assertEqual((value.passed_count, value.failed_count), (certificate.MAX_CHECKS, 0))
        self.assertEqual(certificate.certificate_from_mapping(value.to_dict()).to_dict(), value.to_dict())
        self.assertEqual(certificate.address_certificate(value), value.content_address)
        self.assert_public(value)

    def test_incomplete_audit_is_blocked_by_default_policy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package_dir = self.package_directory(root)
            gate_path = package_dir / "gate.json"
            gate_path.write_bytes(gate_path.read_bytes() + b"\n")
            report = audit.audit_package_directory(package_dir)
            value = certificate.evaluate_audit(report)
            self.assertEqual(value.state, "blocked")
            self.assertFalse(value.accepted)
            self.assertTrue(any(not check.passed and check.severity == "blocking" for check in value.checks))

    def test_minimum_check_policy_can_hold_without_blocking(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = audit.audit_gate(self.gate_value(Path(temporary)))
            policy = certificate.RegistryHistoryReleaseGatePackageAuditCertificatePolicy(
                minimum_checks=audit.MAX_CHECKS + 1,
                require_complete=False,
                require_accepted=False,
                require_all_checks_passed=False,
            )
            value = certificate.evaluate_audit(report, policy)
            self.assertEqual(value.state, "held")
            self.assertFalse(value.accepted)
            self.assertEqual(value.checks[0].check_id, "minimum-checks")
            self.assertFalse(value.checks[0].passed)
            self.assertEqual(value.checks[0].severity, "hold")

    def test_policy_and_nested_check_addresses_are_stable(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = certificate.evaluate_audit(audit.audit_gate(self.gate_value(Path(temporary))))
            self.assertEqual(certificate.address_policy(value.policy), value.policy_address)
            self.assertTrue(all(certificate.address_check(check) == check.content_address for check in value.checks))
            self.assertNotIn("C:\\", canonical_json(value.to_dict()))
            with self.assertRaises(ValidationError):
                certificate.RegistryHistoryReleaseGatePackageAuditCertificatePolicy.from_mapping(value.policy.to_dict() | {"agent": "forbidden"})

    def test_schemas_capabilities_and_markdown_are_public(self):
        self.assert_public(certificate.policy_schema())
        self.assert_public(certificate.check_schema())
        self.assert_public(certificate.certificate_schema())
        self.assert_public(certificate.capabilities())
        with tempfile.TemporaryDirectory() as temporary:
            value = certificate.evaluate_audit(audit.audit_gate(self.gate_value(Path(temporary))))
            self.assertIn("Release Certificate", certificate.render_certificate_markdown(value))
            self.assertIn("content_address", certificate.certificate_json(value))


class RegistryHistoryReleaseGatePackageAuditCertificateCliApiTests(RegistryHistoryReleaseGatePackageAuditCertificateFixture):
    def test_cli_certificate_and_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            package_dir = self.package_directory(Path(temporary))
            output = Path(temporary) / "certificate.json"
            self.assertEqual(main([self.CERTIFICATE_COMMAND, "--input", str(package_dir), "--format", "json", "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["state"], "ready")
            self.assertEqual(main([self.CERTIFICATE_COMMAND, "--input", str(package_dir), "--format", "markdown"]), 0)
            self.assertEqual(main([self.CERTIFICATE_COMMAND + "-schema"]), 0)
            self.assertEqual(main([self.CERTIFICATE_COMMAND + "-policy-schema"]), 0)
            self.assertEqual(main([self.CERTIFICATE_COMMAND + "-check-schema"]), 0)
            self.assertEqual(main([self.CERTIFICATE_COMMAND + "-capabilities"]), 0)

    def test_http_certificate_schema_capability_and_report_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            package_dir = self.package_directory(Path(temporary))
            server, thread = self.server()
            try:
                prefix = "http://127.0.0.1:%s/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/release-gate/package/audit/certificate"
                prefix = prefix % server.server_port
                with urlopen(prefix + "?" + urlencode({"input": str(package_dir), "format": "json"})) as response:
                    self.assertEqual(json.loads(response.read())["state"], "ready")
                with urlopen(prefix + "/schema") as response:
                    self.assertIn("policy", json.loads(response.read())["properties"])
                with urlopen(prefix + "/policy-schema") as response:
                    self.assertIn("minimum_checks", json.loads(response.read())["properties"])
                with urlopen(prefix + "/check-schema") as response:
                    self.assertIn("severity", json.loads(response.read())["properties"])
                with urlopen(prefix + "/capabilities") as response:
                    self.assertIn("ready", json.loads(response.read())["states"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
