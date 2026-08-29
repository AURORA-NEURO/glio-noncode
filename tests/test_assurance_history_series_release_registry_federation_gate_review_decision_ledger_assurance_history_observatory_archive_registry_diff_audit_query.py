"""Deep contracts for bounded registry-diff audit inspection queries."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry as registry
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff as diff
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff_audit as audit
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff_audit_query as query
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff import DiffFixture


class RegistryDiffAuditQueryFixture(DiffFixture):
    """Build query inputs through the verified diff and audit boundaries."""

    QUERY_COMMAND = DiffFixture.DIFF_COMMAND + "-audit-query"

    def audit_value(self, root: Path) -> audit.RegistryDiffAudit:
        return audit.audit_diff(diff.build_diff(self.one_registry(root, "query-left"), self.one_registry(root, "query-right")))

    def assert_public(self, value) -> None:
        payload = value.to_dict() if hasattr(value, "to_dict") else value
        rendered = canonical_json(payload)
        self.assertNotIn("C:\\", rendered)
        self.assertNotIn("/Users/", rendered)
        forbidden = {"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"}

        def walk(node):
            if isinstance(node, dict):
                for key, item in node.items():
                    self.assertNotIn(key.lower(), forbidden)
                    walk(item)
            elif isinstance(node, (list, tuple)):
                for item in node:
                    walk(item)

        walk(payload)


class RegistryDiffAuditQueryBuildTests(RegistryDiffAuditQueryFixture):
    def test_all_resources_are_bounded_and_content_addressed(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.audit_value(Path(temporary))
            for resource in query.RESOURCES:
                result = query.query_audit(value, resource=resource)
                self.assertLessEqual(result.returned_count, result.total_count)
                self.assertEqual(query.address_query(result), result.content_address)
                self.assert_public(result)
            self.assertEqual(query.query_audit(value, resource="checks").total_count, audit.MAX_CHECKS)
            self.assertEqual(query.query_audit(value, resource="passed", passed=True).total_count, audit.MAX_CHECKS)
            self.assertEqual(query.query_audit(value, resource="failed", passed=False).total_count, 0)
            self.assertEqual(query.query_audit(value, resource="evidence").total_count, audit.MAX_CHECKS)

    def test_check_identity_pass_state_text_and_pagination_filters(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.audit_value(Path(temporary))
            selected = query.query_audit(value, resource="checks", check_id="content-address")
            self.assertEqual(selected.total_count, 1)
            self.assertEqual(selected.records[0]["check_id"], "content-address")
            self.assertEqual(query.query_audit(value, resource="checks", passed=True, text="address").total_count, 12)
            first = query.query_audit(value, resource="checks", offset=0, limit=5)
            second = query.query_audit(value, resource="checks", offset=5, limit=5)
            self.assertEqual(first.returned_count, 5)
            self.assertEqual(second.returned_count, 5)
            self.assertNotEqual(first.content_address, second.content_address)
            self.assertEqual(query.query_audit(value, resource="checks", offset=500).returned_count, 0)

    def test_query_object_and_keyword_forms_are_exactly_equivalent(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.audit_value(Path(temporary))
            request = query.RegistryDiffAuditQuery(resource="evidence", check_id="source-addresses", limit=4)
            first = query.query_audit(value, request)
            second = query.query_audit(value, resource="evidence", check_id="source-addresses", limit=4)
            self.assertEqual(first.to_dict(), second.to_dict())
            with self.assertRaises(ValidationError):
                query.query_audit(value, request, resource="checks")

    def test_result_mapping_exports_and_schema_are_replayable(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = query.query_audit(self.audit_value(Path(temporary)), resource="evidence")
            loaded = query.query_result_from_mapping(result.to_dict())
            self.assertEqual(loaded.to_dict(), result.to_dict())
            self.assertEqual(query.query_json(loaded), query.query_json(result))
            self.assertIn("evidence_address", query.query_csv(result))
            self.assertIn("Audit Query", query.render_query_markdown(result))
            self.assertFalse(query.query_schema()["additionalProperties"])
            self.assertFalse(query.query_result_schema()["additionalProperties"])
            self.assert_public(query.capabilities())

    def test_real_downloaded_registry_audit_can_be_queried(self):
        source = Path(tempfile.gettempdir()) / "glio-noncode-history-observatory-demo-current" / "registry-v1"
        if not source.is_dir():
            self.skipTest("the optional local downloaded-data demo is not present")
        value = audit.audit_diff(diff.build_diff_from_directories(source, source))
        result = query.query_audit(value, resource="passed", check_id="content-address")
        self.assertEqual(result.total_count, 1)
        self.assertTrue(result.records[0]["passed"])


class RegistryDiffAuditQueryTamperTests(RegistryDiffAuditQueryFixture):
    def test_query_constructor_rejects_bad_filters_and_bounds(self):
        with self.assertRaises(ValidationError):
            query.RegistryDiffAuditQuery(resource="unknown")
        with self.assertRaises(ValidationError):
            query.RegistryDiffAuditQuery(check_id="unknown")
        with self.assertRaises(ValidationError):
            query.RegistryDiffAuditQuery(limit=0)
        with self.assertRaises(ValidationError):
            query.RegistryDiffAuditQuery(limit=query.MAX_LIMIT + 1)
        with self.assertRaises(ValidationError):
            query.RegistryDiffAuditQuery(offset=query.MAX_QUERY_ITEMS + 1)

    def test_result_rejects_private_records_forged_addresses_and_count_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = query.query_audit(self.audit_value(Path(temporary)), resource="checks", limit=1)
            with self.assertRaises(ValidationError):
                query.RegistryDiffAuditQueryResult(result.audit_address, result.query, result.total_count, (result.records[0] | {"private": "secret"},), result.content_address)
            forged = result.to_dict() | {"content_address": query.QUERY_PREFIX + ":forged"}
            with self.assertRaises(ValidationError):
                query.query_result_from_mapping(forged)
            with self.assertRaises(ValidationError):
                query.query_result_from_mapping(result.to_dict() | {"returned_count": 2})

    def test_query_mapping_rejects_unknown_fields_and_non_public_audit_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = query.query_audit(self.audit_value(Path(temporary)))
            with self.assertRaises(ValidationError):
                query.query_result_from_mapping(result.to_dict() | {"source_path": "C:\\hidden"})
            with self.assertRaises(ValidationError):
                query.query_result_from_mapping(result.to_dict() | {"query": result.query.to_dict() | {"private": True}})


class RegistryDiffAuditQueryCliApiTests(RegistryDiffAuditQueryFixture):
    def directories(self, root: Path) -> tuple[Path, Path]:
        baseline = self.one_registry(root, "query-cli-baseline")
        candidate = self.one_registry(root, "query-cli-candidate")
        baseline_dir = root / "baseline"
        candidate_dir = root / "candidate"
        registry.write_registry(baseline, baseline_dir)
        registry.write_registry(candidate, candidate_dir)
        return baseline_dir, candidate_dir

    def server(self):
        from glio_noncode.api import create_server

        server = create_server("127.0.0.1", 0)
        import threading

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def test_cli_query_and_query_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            baseline, candidate = self.directories(Path(temporary))
            output = Path(temporary) / "query.json"
            self.assertEqual(main([self.QUERY_COMMAND, "--baseline", str(baseline), "--candidate", str(candidate), "--resource", "checks", "--passed", "--format", "json", "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["total_count"], audit.MAX_CHECKS)
            self.assertEqual(main([self.QUERY_COMMAND.replace("-query", "") + "-query-schema"]), 0)
            self.assertEqual(main([self.QUERY_COMMAND.replace("-query", "") + "-query-result-schema"]), 0)
            self.assertEqual(main([self.QUERY_COMMAND.replace("-query", "") + "-query-capabilities"]), 0)

    def test_http_query_schema_capabilities_and_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            baseline, candidate = self.directories(Path(temporary))
            server, thread = self.server()
            try:
                prefix = f"http://127.0.0.1:{server.server_port}/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/diff/audit"
                params = {"baseline": str(baseline), "candidate": str(candidate), "resource": "evidence", "limit": "3", "format": "json"}
                with urlopen(prefix + "/query?" + urlencode(params)) as response:
                    payload = json.loads(response.read())
                self.assertEqual(payload["total_count"], audit.MAX_CHECKS)
                self.assertEqual(payload["returned_count"], 3)
                with urlopen(prefix + "/query-schema") as response:
                    self.assertFalse(json.loads(response.read())["additionalProperties"])
                with urlopen(prefix + "/query-result-schema") as response:
                    self.assertFalse(json.loads(response.read())["additionalProperties"])
                with urlopen(prefix + "/query-capabilities") as response:
                    self.assertEqual(tuple(json.loads(response.read())["resources"]), query.RESOURCES)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
