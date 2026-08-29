"""Deep contracts for bounded registry-history queries."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history as history
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_query as query
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff import DiffFixture


class RegistryHistoryQueryFixture(DiffFixture):
    """Build query inputs through the verified history boundary."""

    QUERY_COMMAND = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-observatory-archive-registry-history-query"

    def value(self, root: Path) -> history.RegistryHistory:
        return history.build_history(tuple(self.one_registry(root, name) for name in ("query-one", "query-two", "query-three")), history_id="query-history")

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


class RegistryHistoryQueryModelTests(RegistryHistoryQueryFixture):
    def test_resources_filters_and_pagination_are_bounded(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.value(Path(temporary))
            self.assertEqual(query.query_history(value, resource="summary").total_count, 1)
            self.assertEqual(query.query_history(value, resource="snapshots").total_count, 3)
            self.assertEqual(query.query_history(value, resource="transitions").total_count, 2)
            self.assertEqual(query.query_history(value, resource="state-changes").total_count, 2)
            self.assertEqual(query.query_history(value, resource="accepted", accepted=True).total_count, 3)
            self.assertEqual(query.query_history(value, resource="release-ready", release_ready=True).total_count, 3)
            self.assertEqual(query.query_history(value, resource="snapshots", state="ready", ordinal=2).total_count, 1)
            first = query.query_history(value, resource="snapshots", offset=0, limit=2)
            second = query.query_history(value, resource="snapshots", offset=2, limit=2)
            self.assertEqual(first.returned_count, 2)
            self.assertEqual(second.returned_count, 1)
            self.assertNotEqual(first.content_address, second.content_address)
            for result in (first, second):
                self.assertEqual(query.address_query(result), result.content_address)
                self.assert_public(result)

    def test_query_object_mapping_exports_and_schema_are_replayable(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.value(Path(temporary))
            request = query.RegistryHistoryQuery(resource="snapshots", accepted=True, text="query", limit=2)
            first = query.query_history(value, request)
            second = query.query_history(value, resource="snapshots", accepted=True, text="query", limit=2)
            self.assertEqual(first.to_dict(), second.to_dict())
            self.assertEqual(query.query_result_from_mapping(first.to_dict()).to_dict(), first.to_dict())
            self.assertEqual(query.query_json(first), query.query_json(second))
            self.assertIn("registry_id", query.query_csv(first))
            self.assertIn("Registry History Query", query.render_query_markdown(first))
            self.assertFalse(query.query_schema()["additionalProperties"])
            self.assertFalse(query.query_result_schema()["additionalProperties"])
            self.assert_public(query.capabilities())

    def test_constructor_and_result_reject_invalid_filters_and_private_records(self):
        with self.assertRaises(ValidationError):
            query.RegistryHistoryQuery(resource="unknown")
        with self.assertRaises(ValidationError):
            query.RegistryHistoryQuery(state="unknown")
        with self.assertRaises(ValidationError):
            query.RegistryHistoryQuery(limit=0)
        with self.assertRaises(ValidationError):
            query.RegistryHistoryQuery(offset=query.MAX_QUERY_ITEMS + 1)
        with tempfile.TemporaryDirectory() as temporary:
            result = query.query_history(self.value(Path(temporary)), resource="snapshots", limit=1)
            with self.assertRaises(ValidationError):
                query.RegistryHistoryQueryResult(result.history_address, result.query, result.total_count, (result.records[0] | {"private": True},), result.content_address)
            with self.assertRaises(ValidationError):
                query.query_result_from_mapping(result.to_dict() | {"returned_count": 2})
            with self.assertRaises(ValidationError):
                query.query_history(self.value(Path(temporary)), result.query, resource="transitions")

    def test_real_downloaded_history_can_be_inspected(self):
        source = Path(tempfile.gettempdir()) / "glio-noncode-history-audit-demo-eb48d6ff52184a0e97a4b81607b93dc2"
        if not source.is_dir():
            temporary_root = Path(tempfile.gettempdir())
            candidates = sorted((*temporary_root.glob("glio-noncode-history-demo-*"), *temporary_root.glob("glio-noncode-history-audit-demo-*")))
            source = next((item for item in candidates if (item / "history.json").is_file()), source)
        if not source.is_dir():
            self.skipTest("the optional local downloaded-data history is not present")
        value = history.load_history(source)
        self.assertEqual(query.query_history(value, resource="snapshots").total_count, 2)
        self.assertEqual(query.query_history(value, resource="transitions", state="unchanged").total_count, 1)


class RegistryHistoryQueryCliApiTests(RegistryHistoryQueryFixture):
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
            destination = Path(temporary) / "history"
            history.write_history(self.value(Path(temporary)), destination)
            output = Path(temporary) / "query.json"
            self.assertEqual(main([self.QUERY_COMMAND, "--input", str(destination), "--resource", "snapshots", "--accepted", "--format", "json", "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["total_count"], 3)
            self.assertEqual(main([self.QUERY_COMMAND.removesuffix("-query") + "-query-schema"]), 0)
            self.assertEqual(main([self.QUERY_COMMAND.removesuffix("-query") + "-query-result-schema"]), 0)
            self.assertEqual(main([self.QUERY_COMMAND.removesuffix("-query") + "-query-capabilities"]), 0)

    def test_http_query_schema_capabilities_and_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "history"
            history.write_history(self.value(Path(temporary)), destination)
            server, thread = self.server()
            try:
                prefix = f"http://127.0.0.1:{server.server_port}/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/query"
                params = {"input": str(destination), "resource": "transitions", "state": "mixed", "format": "json"}
                with urlopen(prefix + "?" + urlencode(params)) as response:
                    payload = json.loads(response.read())
                self.assertIn("total_count", payload)
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
