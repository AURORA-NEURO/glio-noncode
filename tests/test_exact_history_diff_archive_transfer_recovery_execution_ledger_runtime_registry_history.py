"""Regression coverage for append-only ledger-runtime registry history."""

from __future__ import annotations

# ruff: noqa: E501, I001

import contextlib
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry as registry_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history as history_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_audit as history_audit_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_query as history_query_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_query_audit as history_query_audit_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime as runtime_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit

import tests.test_exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry as registry_test_module


COMMAND = registry_test_module.COMMAND + "-history"
API_PATH = registry_test_module.API_PATH + "/history"


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry_test_module.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryTests.setUpClass()

    def _history(self):
        ready, blocked = registry_test_module.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryTests()._runtimes()
        registry_id = "history-registry"
        empty = registry_model.build_registry((), registry_id=registry_id)
        ready_registry = registry_model.build_registry((ready,), registry_id=registry_id)
        blocked_registry = registry_model.build_registry((ready, blocked), registry_id=registry_id)
        return history_model.build_history((empty, ready_registry, blocked_registry), history_id="history-demo"), (empty, ready_registry, blocked_registry)

    def test_transitions_ancestry_and_independent_audits(self):
        value, registries = self._history()
        self.assertEqual(value.entry_count, 3)
        self.assertEqual(tuple(item.transition for item in value.entries), ("initial", "improved", "regressed"))
        self.assertEqual(tuple(item.previous_registry_address for item in value.entries), ("", registries[0].content_address, registries[1].content_address))
        self.assertEqual((value.state, value.accepted), ("blocked", False))
        audit = history_audit_model.audit_history(value)
        query = history_query_model.query_history(value)
        query_audit = history_query_audit_model.audit_query(query, value)
        self.assertEqual((audit.check_count, audit.passed), (16, True))
        self.assertEqual((query.returned_count, query.total_count, query_audit.check_count, query_audit.passed), (query.total_count, query.total_count, 12, True))
        improved_query = history_query_model.query_history(value, resources=("transitions",), transition="improved")
        self.assertEqual(tuple(item.value for item in improved_query.rows), (1,))

    def test_append_is_copy_on_write_and_rejects_duplicate_snapshots(self):
        _, registries = self._history()
        base = history_model.build_history(registries[:2], history_id="append-history")
        appended = history_model.append_registry(base, registries[2])
        self.assertEqual((base.entry_count, appended.entry_count), (2, 3))
        self.assertEqual(appended.entries[-1].registry_address, registries[2].content_address)
        with self.assertRaises(ValidationError):
            history_model.append_registry(appended, registries[2])
        with self.assertRaises(ValidationError):
            history_model.build_history((registries[0], registries[0]), history_id="duplicate-history")
        self.assertEqual(history_model.history_from_mapping(appended.to_dict()).content_address, appended.content_address)

    def test_exact_package_reload_and_tamper_rejection(self):
        value, _ = self._history()
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "history"
            history_model.persist_history(value, destination)
            loaded = history_model.load_history(destination)
            self.assertEqual(history_model.history_json(loaded), history_model.history_json(value))
            self.assertEqual(set(item.name for item in destination.iterdir()), set(history_model.FILES))
            tampered = destination / "summary.json"
            payload = json.loads(tampered.read_text(encoding="utf-8"))
            payload["accepted"] = True
            tampered.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
            with self.assertRaises(ValidationError):
                history_model.load_history(destination)
            history_model.persist_history(value, destination, overwrite=True)
            (destination / "unexpected.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                history_model.load_history(destination)

    def test_cli_api_schemas_and_public_inventory(self):
        value, registries = self._history()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry_paths = []
            for index, registry in enumerate(registries):
                path = root / f"registry-{index}"
                registry_model.persist_registry(registry, path)
                registry_paths.append(path)
            history_path = root / "history"
            query_path = root / "query.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([COMMAND, str(registry_paths[0]), "--registry-input", str(registry_paths[1]), "--registry-input", str(registry_paths[2]), "--history-id", "cli-history", "--destination", str(history_path), "--format", "json", "--output", str(root / "history.json")]), 0)
                self.assertEqual(main([COMMAND + "-verify", str(history_path), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-audit", str(history_path), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-query", str(history_path), "--resource", "transitions", "--transition", "improved", "--format", "json", "--output", str(query_path)]), 0)
                self.assertEqual(main([COMMAND + "-query-audit", str(query_path), "--history-input", str(history_path), "--format", "summary"]), 0)
                for suffix in ("entry-schema", "entries-schema", "artifact-schema", "manifest-schema", "summary-schema", "schema", "capabilities", "audit-check-schema", "audit-schema", "audit-capabilities", "query-row-schema", "query-schema", "query-capabilities", "query-audit-check-schema", "query-audit-schema", "query-audit-capabilities"):
                    self.assertEqual(main([COMMAND + "-" + suffix]), 0)
            cli_payload = json.loads((root / "history.json").read_text(encoding="utf-8"))
            self.assertEqual((cli_payload["entry_count"], cli_payload["state"], cli_payload["accepted"]), (3, "blocked", False))
            self.assertEqual(json.loads(query_path.read_text(encoding="utf-8"))["returned_count"], 1)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                server.glio_deployment_guard._rate_windows.clear()
                params = urlencode([("registry_input", str(registry_paths[0])), ("registry_input", str(registry_paths[1])), ("registry_input", str(registry_paths[2])), ("history_id", "api-history"), ("format", "json")])
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}?{params}", timeout=30) as response:
                    api_history = json.loads(response.read().decode("utf-8"))
                self.assertEqual((api_history["entry_count"], api_history["state"]), (3, "blocked"))
                api_history_path = root / "api-history.json"
                api_history_path.write_text(json.dumps(api_history), encoding="utf-8")
                params = urlencode({"input": str(history_path), "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["passed"])
                params = urlencode({"input": str(history_path), "resource": "latest", "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query?{params}", timeout=30) as response:
                    api_query = json.loads(response.read().decode("utf-8"))
                self.assertGreater(api_query["returned_count"], 0)
                api_query_path = root / "api-query.json"
                api_query_path.write_text(json.dumps(api_query), encoding="utf-8")
                params = urlencode({"input": str(api_query_path), "history_input": str(history_path), "format": "summary"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["passed"])
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

        inventory = build_default_public_surface_audit()
        self.assertEqual((inventory.surface_count, inventory.passed_surface_count, inventory.failed_surface_count, inventory.accepted), (2126, 2126, 0, True))
        for schema in (history_model.entry_schema(), history_model.entries_schema(), history_model.artifact_schema(), history_model.manifest_schema(), history_model.summary_schema(), history_model.history_schema(), history_audit_model.check_schema(), history_audit_model.audit_schema(), history_query_model.row_schema(), history_query_model.query_schema(), history_query_audit_model.check_schema(), history_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
