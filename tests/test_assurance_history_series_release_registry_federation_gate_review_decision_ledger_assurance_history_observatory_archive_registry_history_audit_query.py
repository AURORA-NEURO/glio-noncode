"""Deep contracts for bounded registry-history-audit queries."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history as history
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_audit as audit
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_audit_query as query
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff import DiffFixture


class RegistryHistoryAuditQueryFixture(DiffFixture):
    """Build audit-query inputs through the verified history boundaries."""

    QUERY_COMMAND = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-observatory-archive-registry-history-audit-query"

    def audit_value(self, root: Path) -> audit.RegistryHistoryAudit:
        registries = tuple(self.one_registry(root, name) for name in ("audit-query-one", "audit-query-two", "audit-query-three"))
        return audit.audit_history(history.build_history(registries, history_id="audit-query-history"))

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


class RegistryHistoryAuditQueryModelTests(RegistryHistoryAuditQueryFixture):
    def test_resources_filters_and_pagination_are_deterministic(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.audit_value(Path(temporary))
            self.assertEqual(query.query_audit(value, resource="summary").total_count, 1)
            self.assertEqual(query.query_audit(value, resource="checks").total_count, audit.MAX_CHECKS)
            self.assertEqual(query.query_audit(value, resource="passed", passed=True).total_count, audit.MAX_CHECKS)
            self.assertEqual(query.query_audit(value, resource="failed", passed=False).total_count, 0)
            self.assertEqual(query.query_audit(value, resource="evidence").total_count, audit.MAX_CHECKS)
            selected = query.query_audit(value, resource="checks", check_id="content-address")
            self.assertEqual(selected.total_count, 1)
            first = query.query_audit(value, resource="checks", offset=0, limit=5)
            second = query.query_audit(value, resource="checks", offset=5, limit=5)
            self.assertEqual(first.returned_count, 5)
            self.assertEqual(second.returned_count, 5)
            self.assertNotEqual(first.content_address, second.content_address)
            self.assert_public(first)

    def test_query_object_mapping_exports_and_schema_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.audit_value(Path(temporary))
            request = query.RegistryHistoryAuditQuery(resource="evidence", check_id="nested-addresses", limit=2)
            first = query.query_audit(value, request)
            second = query.query_audit(value, resource="evidence", check_id="nested-addresses", limit=2)
            self.assertEqual(first.to_dict(), second.to_dict())
            self.assertEqual(query.query_result_from_mapping(first.to_dict()).to_dict(), first.to_dict())
            self.assertEqual(query.query_json(first), query.query_json(second))
            self.assertIn("evidence_address", query.query_csv(first))
            self.assertIn("Registry History Audit Query", query.render_query_markdown(first))
            self.assertFalse(query.query_schema()["additionalProperties"])
            self.assertFalse(query.query_result_schema()["additionalProperties"])
            self.assert_public(query.capabilities())

    def test_invalid_filters_and_private_result_records_are_rejected(self):
        with self.assertRaises(ValidationError):
            query.RegistryHistoryAuditQuery(resource="unknown")
        with self.assertRaises(ValidationError):
            query.RegistryHistoryAuditQuery(check_id="unknown")
        with self.assertRaises(ValidationError):
            query.RegistryHistoryAuditQuery(limit=0)
        with self.assertRaises(ValidationError):
            query.RegistryHistoryAuditQuery(offset=query.MAX_QUERY_ITEMS + 1)
        with tempfile.TemporaryDirectory() as temporary:
            result = query.query_audit(self.audit_value(Path(temporary)), resource="checks", limit=1)
            with self.assertRaises(ValidationError):
                query.RegistryHistoryAuditQueryResult(result.audit_address, result.query, result.total_count, (result.records[0] | {"private": True},), result.content_address)
            with self.assertRaises(ValidationError):
                query.query_result_from_mapping(result.to_dict() | {"returned_count": 2})
            with self.assertRaises(ValidationError):
                query.query_audit(self.audit_value(Path(temporary)), result.query, resource="failed")

    def test_real_downloaded_history_audit_can_be_queried(self):
        source = Path(tempfile.gettempdir()) / "glio-noncode-history-audit-demo-eb48d6ff52184a0e97a4b81607b93dc2"
        if not source.is_dir():
            self.skipTest("the optional local downloaded-data history is not present")
        value = audit.audit_history(history.load_history(source))
        result = query.query_audit(value, resource="passed", check_id="content-address")
        self.assertEqual(result.total_count, 1)
        self.assertTrue(result.records[0]["passed"])


class RegistryHistoryAuditQueryCliApiTests(RegistryHistoryAuditQueryFixture):
    def server(self):
        from glio_noncode.api import create_server

        server = create_server("127.0.0.1", 0)
        import threading

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def test_cli_query_and_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "history"
            history.write_history(history.build_history(tuple(self.one_registry(Path(temporary), name) for name in ("cli-a", "cli-b")), history_id="cli-audit-history"), destination)
            output = Path(temporary) / "query.json"
            self.assertEqual(main([self.QUERY_COMMAND, "--input", str(destination), "--resource", "passed", "--passed", "--format", "json", "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["total_count"], audit.MAX_CHECKS)
            base = self.QUERY_COMMAND.removesuffix("-query")
            self.assertEqual(main([base + "-query-schema"]), 0)
            self.assertEqual(main([base + "-query-result-schema"]), 0)
            self.assertEqual(main([base + "-query-capabilities"]), 0)

    def test_http_query_schema_capabilities_and_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "history"
            history.write_history(history.build_history(tuple(self.one_registry(Path(temporary), name) for name in ("http-a", "http-b")), history_id="http-audit-history"), destination)
            server, thread = self.server()
            try:
                prefix = f"http://127.0.0.1:{server.server_port}/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/audit/query"
                params = {"input": str(destination), "resource": "evidence", "passed": "true", "limit": "3", "format": "json"}
                with urlopen(prefix + "?" + urlencode(params)) as response:
                    payload = json.loads(response.read())
                self.assertEqual(payload["total_count"], audit.MAX_CHECKS)
                self.assertEqual(payload["returned_count"], 3)
                with urlopen(prefix.replace("/query", "/query-schema")) as response:
                    self.assertFalse(json.loads(response.read())["additionalProperties"])
                with urlopen(prefix.replace("/query", "/query-result-schema")) as response:
                    self.assertFalse(json.loads(response.read())["additionalProperties"])
                with urlopen(prefix.replace("/query", "/query-capabilities")) as response:
                    self.assertEqual(tuple(json.loads(response.read())["resources"]), query.RESOURCES)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
