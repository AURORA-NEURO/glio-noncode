"""Deep contracts for bounded release-gate inspection queries."""

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
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate as gate
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_query as query
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff import DiffFixture


class RegistryHistoryReleaseGateQueryFixture(DiffFixture):
    """Build query inputs through the current verified history gate."""

    QUERY_COMMAND = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-observatory-archive-registry-history-release-gate-query"

    def gate_value(self, root: Path, *states: str) -> gate.RegistryHistoryReleaseGate:
        values = tuple(self.one_registry(root, f"query-{index}", state=state) for index, state in enumerate(states))
        return gate.evaluate_history(history.build_history(values, history_id="history:query"))

    def assert_public(self, value) -> None:
        payload = value.to_dict() if hasattr(value, "to_dict") else value
        rendered = canonical_json(payload)
        self.assertNotIn("C:\\", rendered)
        self.assertNotIn("/Users/", rendered)
        forbidden = {"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "user"}

        def walk(node):
            if isinstance(node, dict):
                for key, item in node.items():
                    self.assertNotIn(key.lower(), forbidden)
                    walk(item)
            elif isinstance(node, (list, tuple)):
                for item in node:
                    walk(item)

        walk(payload)

    def server(self):
        from glio_noncode.api import create_server

        server = create_server("127.0.0.1", 0)
        import threading

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread


class RegistryHistoryReleaseGateQueryBuildTests(RegistryHistoryReleaseGateQueryFixture):
    def test_all_resources_and_filters_are_bounded(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.gate_value(Path(temporary), "ready", "held")
            for resource in query.RESOURCES:
                result = query.query_gate(value, resource=resource, limit=1)
                self.assertLessEqual(result.returned_count, 1)
                self.assertEqual(result.gate_address, value.content_address)
                self.assert_public(result)
            failed = query.query_gate(value, resource="failed", passed=False)
            self.assertTrue(all(not record["passed"] for record in failed.records))
            holds = query.query_gate(value, resource="checks", severity="hold")
            self.assertTrue(all(record["severity"] == "hold" for record in holds.records))
            named = query.query_gate(value, resource="checks", check_id="regression-budget")
            self.assertEqual(named.total_count, 1)
            self.assertEqual(named.records[0]["check_id"], "regression-budget")
            searched = query.query_gate(value, resource="checks", text="content-address")
            self.assertEqual(searched.total_count, 1)

    def test_query_object_mapping_replay_pagination_and_exports_are_exact(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.gate_value(Path(temporary), "ready", "held")
            requested = query.RegistryHistoryReleaseGateQuery(resource="checks", passed=False, offset=1, limit=2)
            result = query.query_gate(value, requested)
            replayed = query.query_result_from_mapping(result.to_dict())
            self.assertEqual(replayed.to_dict(), result.to_dict())
            self.assertEqual(query.address_query(result), result.content_address)
            self.assertEqual(query.query_json(replayed), query.query_json(result))
            self.assertIn("check_id", query.query_csv(result))
            self.assertIn("Release Gate Query", query.render_query_markdown(result))
            self.assert_public(query.query_schema())
            self.assert_public(query.query_result_schema())
            self.assert_public(query.capabilities())

    def test_invalid_filters_private_records_and_count_drift_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.gate_value(Path(temporary), "ready", "ready")
            with self.assertRaises(ValidationError):
                query.RegistryHistoryReleaseGateQuery(resource="unknown")
            with self.assertRaises(ValidationError):
                query.RegistryHistoryReleaseGateQuery(severity="unknown")
            with self.assertRaises(ValidationError):
                query.RegistryHistoryReleaseGateQuery(check_id="unknown")
            result = query.query_gate(value, resource="checks")
            with self.assertRaises(ValidationError):
                query.query_result_from_mapping(result.to_dict() | {"records": ({"private": True},)})
            with self.assertRaises(ValidationError):
                query.query_result_from_mapping(result.to_dict() | {"returned_count": result.returned_count + 1})

    def test_downloaded_gate_query_returns_replayable_content_address(self):
        source = Path(tempfile.gettempdir()) / "glio-noncode-history-audit-demo-eb48d6ff52184a0e97a4b81607b93dc2"
        if not source.is_dir():
            self.skipTest("the optional local downloaded-data demo is not present")
        value = gate.evaluate_history_from_directory(source)
        result = query.query_gate(value, resource="passed", check_id="content-address")
        self.assertEqual(result.total_count, 1)
        self.assertTrue(result.records[0]["passed"])
        self.assertEqual(query.query_result_from_mapping(result.to_dict()).content_address, result.content_address)


class RegistryHistoryReleaseGateQueryCliApiTests(RegistryHistoryReleaseGateQueryFixture):
    def directories(self, root: Path) -> Path:
        value = self.one_registry(root, "query-cli")
        registry_dir = root / "registry"
        registry.write_registry(value, registry_dir)
        history_dir = root / "history"
        history.write_history(history.build_history_from_directories((registry_dir, registry_dir), history_id="history:query-cli"), history_dir)
        return history_dir

    def test_cli_query_and_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            history_dir = self.directories(Path(temporary))
            output = Path(temporary) / "query.json"
            self.assertEqual(main([self.QUERY_COMMAND, "--input", str(history_dir), "--resource", "passed", "--check-id", "content-address", "--format", "json", "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["total_count"], 1)
            self.assertEqual(main([self.QUERY_COMMAND.removesuffix("-query") + "-query-schema"]), 0)
            self.assertEqual(main([self.QUERY_COMMAND.removesuffix("-query") + "-query-result-schema"]), 0)
            self.assertEqual(main([self.QUERY_COMMAND.removesuffix("-query") + "-query-capabilities"]), 0)

    def test_http_query_schema_capabilities_and_report_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            history_dir = self.directories(Path(temporary))
            server, thread = self.server()
            try:
                prefix = "http://127.0.0.1:%s/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/release-gate/query"
                prefix = prefix % server.server_port
                params = urlencode({"input": str(history_dir), "resource": "passed", "check_id": "content-address", "format": "json"})
                with urlopen(prefix + "?" + params) as response:
                    payload = json.loads(response.read())
                self.assertEqual(payload["total_count"], 1)
                with urlopen(prefix.replace("/query", "/query-schema")) as response:
                    self.assertFalse(json.loads(response.read())["additionalProperties"])
                with urlopen(prefix.replace("/query", "/query-result-schema")) as response:
                    self.assertIn("records", json.loads(response.read())["properties"])
                with urlopen(prefix.replace("/query", "/query-capabilities")) as response:
                    self.assertEqual(tuple(json.loads(response.read())["resources"]), query.RESOURCES)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
