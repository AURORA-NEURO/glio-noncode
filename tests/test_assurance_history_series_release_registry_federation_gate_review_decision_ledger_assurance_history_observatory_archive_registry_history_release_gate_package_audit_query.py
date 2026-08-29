"""Deep contracts for bounded release-gate package-audit queries."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_package_audit as audit
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_package_audit_query as query
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_package_audit import RegistryHistoryReleaseGatePackageAuditFixture


class RegistryHistoryReleaseGatePackageAuditQueryFixture(RegistryHistoryReleaseGatePackageAuditFixture):
    QUERY_COMMAND = RegistryHistoryReleaseGatePackageAuditFixture.AUDIT_COMMAND + "-query"


class RegistryHistoryReleaseGatePackageAuditQueryBuildTests(RegistryHistoryReleaseGatePackageAuditQueryFixture):
    def test_resources_filters_pagination_and_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            package_dir = self.package_directory(Path(temporary))
            report = audit.audit_package_directory(package_dir)
            summary = query.query_audit(report, resource="summary")
            checks = query.query_audit(report, resource="checks", limit=3)
            passed = query.query_audit(report, resource="passed", passed=True)
            evidence = query.query_audit(report, resource="evidence", check_id="content-address")
            self.assertEqual(summary.total_count, 1)
            self.assertEqual(checks.total_count, audit.MAX_CHECKS)
            self.assertEqual(checks.returned_count, 3)
            self.assertEqual(passed.total_count, audit.MAX_CHECKS)
            self.assertEqual(evidence.total_count, 1)
            self.assertEqual(evidence.records[0]["check_id"], "content-address")
            self.assertEqual(query.query_result_from_mapping(summary.to_dict()).to_dict(), summary.to_dict())
            self.assertEqual(query.address_query(checks), checks.content_address)
            self.assertNotIn("C:\\", canonical_json(checks.to_dict()))

    def test_failed_query_exposes_damaged_package_diagnostics(self):
        with tempfile.TemporaryDirectory() as temporary:
            package_dir = self.package_directory(Path(temporary))
            gate_path = package_dir / "gate.json"
            gate_path.write_bytes(gate_path.read_bytes() + b"\n")
            failed = query.query_package_directory(package_dir, resource="failed", limit=20)
            self.assertGreater(failed.total_count, 0)
            self.assertEqual(failed.total_count, failed.returned_count)
            self.assertTrue(all(record["passed"] is False for record in failed.records))
            self.assertTrue(any("receipt" in record["detail"] or "canonical" in record["detail"] for record in failed.records))

    def test_query_bounds_text_and_query_object_contracts(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = audit.audit_gate(self.gate_value(Path(temporary)))
            selected = query.RegistryHistoryReleaseGatePackageAuditQuery(resource="checks", text="PUBLIC", offset=1, limit=4)
            result = query.query_audit(report, selected)
            self.assertLessEqual(result.returned_count, 4)
            with self.assertRaises(ValidationError):
                query.RegistryHistoryReleaseGatePackageAuditQuery(resource="unknown")
            with self.assertRaises(ValidationError):
                query.query_audit(report, selected, limit=2)
            self.assertTrue(query.capabilities()["limits"]["max_query_items"] >= audit.MAX_CHECKS)

    def test_downloaded_package_query_is_stable(self):
        source = Path(tempfile.gettempdir()) / "glio-noncode-history-release-gate-package-demo"
        if not source.is_dir():
            self.skipTest("the optional local downloaded-data package demo is not present")
        result = query.query_package_directory(source, resource="checks", limit=20)
        self.assertEqual(result.total_count, audit.MAX_CHECKS)
        self.assertEqual(result.returned_count, audit.MAX_CHECKS)
        self.assertTrue(all(record["passed"] for record in result.records))

    def test_schemas_capabilities_and_exports_are_public(self):
        self.assert_public(query.query_schema())
        self.assert_public(query.query_result_schema())
        self.assert_public(query.capabilities())
        with tempfile.TemporaryDirectory() as temporary:
            result = query.query_package_directory(self.package_directory(Path(temporary)), resource="summary")
        self.assertIn("Query", query.render_query_markdown(result))
        self.assertIn("manifest_address", query.query_csv(result))


class RegistryHistoryReleaseGatePackageAuditQueryCliApiTests(RegistryHistoryReleaseGatePackageAuditQueryFixture):
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
                prefix = "http://127.0.0.1:%s/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/release-gate/package/audit/query"
                prefix = prefix % server.server_port
                with urlopen(prefix + "?" + urlencode({"input": str(package_dir), "resource": "checks", "limit": "2", "format": "json"})) as response:
                    self.assertEqual(json.loads(response.read())["returned_count"], 2)
                audit_prefix = prefix.removesuffix("/query")
                with urlopen(audit_prefix + "/query-schema") as response:
                    self.assertIn("resource", json.loads(response.read())["properties"])
                with urlopen(audit_prefix + "/query-result-schema") as response:
                    self.assertIn("records", json.loads(response.read())["properties"])
                with urlopen(audit_prefix + "/query-capabilities") as response:
                    self.assertIn("failed", json.loads(response.read())["resources"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
