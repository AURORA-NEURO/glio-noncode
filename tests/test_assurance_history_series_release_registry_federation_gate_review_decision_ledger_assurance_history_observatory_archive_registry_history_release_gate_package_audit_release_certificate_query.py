"""Deep contracts for release-certificate queries."""

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
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_package_audit_release_certificate_query as query
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_package_audit import RegistryHistoryReleaseGatePackageAuditFixture


class RegistryHistoryReleaseGatePackageAuditCertificateQueryFixture(RegistryHistoryReleaseGatePackageAuditFixture):
    QUERY_COMMAND = RegistryHistoryReleaseGatePackageAuditFixture.AUDIT_COMMAND.replace("-audit", "-audit-certificate-query")


class RegistryHistoryReleaseGatePackageAuditCertificateQueryBuildTests(RegistryHistoryReleaseGatePackageAuditCertificateQueryFixture):
    def test_downloaded_package_certificate_query_is_stable(self):
        source = Path(tempfile.gettempdir()) / "glio-noncode-history-release-gate-package-demo"
        if not source.is_dir():
            self.skipTest("the optional local downloaded-data package demo is not present")
        result = query.query_package_directory(source, resource="checks", limit=20)
        self.assertEqual(result.total_count, certificate.MAX_CHECKS)
        self.assertEqual(result.returned_count, certificate.MAX_CHECKS)
        self.assertEqual(query.query_result_from_mapping(result.to_dict()).to_dict(), result.to_dict())
        self.assertEqual(query.address_query(result), result.content_address)

    def test_resources_and_severity_filters_cover_ready_and_held_decisions(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = audit.audit_gate(self.gate_value(Path(temporary)))
            ready = certificate.evaluate_audit(report)
            self.assertEqual(query.query_certificate(ready, resource="passed").total_count, certificate.MAX_CHECKS)
            self.assertEqual(query.query_certificate(ready, resource="failed").total_count, 0)
            held_policy = certificate.RegistryHistoryReleaseGatePackageAuditCertificatePolicy(minimum_checks=audit.MAX_CHECKS + 1, require_complete=False, require_accepted=False, require_all_checks_passed=False)
            held = certificate.evaluate_audit(report, held_policy)
            holds = query.query_certificate(held, resource="holds", severity="hold")
            self.assertEqual(held.state, "held")
            self.assertEqual(holds.total_count, 1)
            self.assertEqual(holds.records[0]["check_id"], "minimum-checks")

    def test_damaged_package_certificate_query_exposes_blocking_failures(self):
        with tempfile.TemporaryDirectory() as temporary:
            package_dir = self.package_directory(Path(temporary))
            gate_path = package_dir / "gate.json"
            gate_path.write_bytes(gate_path.read_bytes() + b"\n")
            result = query.query_package_directory(package_dir, resource="blocking", limit=20)
            self.assertGreater(result.total_count, 0)
            self.assertTrue(all(record["passed"] is False and record["severity"] == "blocking" for record in result.records))

    def test_bounds_text_and_public_exports(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = certificate.evaluate_audit(audit.audit_gate(self.gate_value(Path(temporary))))
            selected = query.RegistryHistoryReleaseGatePackageAuditCertificateQuery(resource="evidence", text="address", offset=1, limit=3)
            result = query.query_certificate(value, selected)
            self.assertLessEqual(result.returned_count, 3)
            self.assert_public(query.query_schema())
            self.assert_public(query.query_result_schema())
            self.assert_public(query.capabilities())
            with self.assertRaises(ValidationError):
                query.RegistryHistoryReleaseGatePackageAuditCertificateQuery(resource="missing")
            with self.assertRaises(ValidationError):
                query.query_certificate(value, selected, limit=2)


class RegistryHistoryReleaseGatePackageAuditCertificateQueryCliApiTests(RegistryHistoryReleaseGatePackageAuditCertificateQueryFixture):
    def test_cli_query_and_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            package_dir = self.package_directory(Path(temporary))
            output = Path(temporary) / "query.json"
            self.assertEqual(main([self.QUERY_COMMAND, "--input", str(package_dir), "--resource", "checks", "--limit", "2", "--format", "json", "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["returned_count"], 2)
            self.assertEqual(main([self.QUERY_COMMAND, "--input", str(package_dir), "--resource", "failed", "--format", "markdown"]), 0)
            self.assertEqual(main([self.QUERY_COMMAND + "-query-schema"]), 0)
            self.assertEqual(main([self.QUERY_COMMAND + "-query-result-schema"]), 0)
            self.assertEqual(main([self.QUERY_COMMAND + "-query-capabilities"]), 0)

    def test_http_query_schema_capability_and_report_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            package_dir = self.package_directory(Path(temporary))
            server, thread = self.server()
            try:
                prefix = "http://127.0.0.1:%s/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/release-gate/package/audit/certificate/query"
                prefix = prefix % server.server_port
                with urlopen(prefix + "?" + urlencode({"input": str(package_dir), "resource": "checks", "limit": "2", "format": "json"})) as response:
                    self.assertEqual(json.loads(response.read())["returned_count"], 2)
                certificate_prefix = prefix.removesuffix("/query")
                with urlopen(certificate_prefix + "/query-schema") as response:
                    self.assertIn("resource", json.loads(response.read())["properties"])
                with urlopen(certificate_prefix + "/query-result-schema") as response:
                    self.assertIn("records", json.loads(response.read())["properties"])
                with urlopen(certificate_prefix + "/query-capabilities") as response:
                    self.assertIn("blocking", json.loads(response.read())["resources"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
