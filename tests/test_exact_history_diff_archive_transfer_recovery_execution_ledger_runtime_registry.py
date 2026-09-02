"""Regression coverage for deterministic ledger-runtime registries."""

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
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_audit as registry_audit_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_query as registry_query_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_query_audit as registry_query_audit_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime as runtime_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit

import tests.test_exact_history_diff_archive_transfer_recovery_execution_ledger_runtime as runtime_test_module


COMMAND = runtime_test_module.COMMAND + "-registry"
API_PATH = runtime_test_module.API_PATH + "/registry"


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runtime_test_module.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeTests.setUpClass()

    def _runtimes(self):
        ready_ledger, blocked_ledger = runtime_test_module.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeTests()._ledgers()
        return (
            runtime_model.build_runtime(ready_ledger, runtime_id="ready-runtime"),
            runtime_model.build_runtime(blocked_ledger, runtime_id="blocked-runtime"),
        )

    def test_admission_order_state_and_audits(self):
        ready, blocked = self._runtimes()
        value = registry_model.build_registry((ready, blocked), registry_id="demo-runtime-registry")
        audit = registry_audit_model.audit_registry(value)
        query = registry_query_model.query_registry(value)
        query_audit = registry_query_audit_model.audit_query(query, value)
        self.assertEqual((value.entry_count, value.accepted_count, value.ready_count, value.blocked_count, value.state, value.accepted), (2, 1, 1, 1, "blocked", False))
        self.assertEqual(tuple(item.runtime_id for item in value.entries), ("blocked-runtime", "ready-runtime"))
        self.assertEqual((audit.check_count, audit.passed), (16, True))
        self.assertEqual((query.returned_count, query.total_count, query_audit.check_count, query_audit.passed), (query.total_count, query.total_count, 12, True))
        with self.assertRaises(ValidationError):
            registry_model.admit_runtime(value, blocked)
        self.assertEqual(registry_model.registry_from_mapping(value.to_dict()).content_address, value.content_address)

    def test_exact_package_reload_and_tamper_rejection(self):
        ready, blocked = self._runtimes()
        value = registry_model.build_registry((ready, blocked), registry_id="persisted-runtime-registry")
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "registry"
            registry_model.persist_registry(value, destination)
            loaded = registry_model.load_registry(destination)
            self.assertEqual(registry_model.registry_json(loaded), registry_model.registry_json(value))
            self.assertEqual(set(item.name for item in destination.iterdir()), set(registry_model.FILES))
            tampered = destination / "summary.json"
            payload = json.loads(tampered.read_text(encoding="utf-8"))
            payload["accepted"] = True
            tampered.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
            with self.assertRaises(ValidationError):
                registry_model.load_registry(destination)
            registry_model.persist_registry(value, destination, overwrite=True)
            (destination / "unexpected.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                registry_model.load_registry(destination)

    def test_cli_api_schemas_and_public_inventory(self):
        ready, _ = self._runtimes()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime_path = root / "runtime.json"
            runtime_path.write_text(runtime_model.runtime_json(ready), encoding="utf-8")
            registry_path = root / "registry"
            query_path = root / "query.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([COMMAND, str(runtime_path), "--registry-id", "cli-runtime-registry", "--destination", str(registry_path), "--format", "json", "--output", str(root / "registry.json")]), 0)
                self.assertEqual(main([COMMAND + "-verify", str(registry_path), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-audit", str(registry_path), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-query", str(registry_path), "--resource", "latest", "--limit", "4", "--format", "json", "--output", str(query_path)]), 0)
                self.assertEqual(main([COMMAND + "-query-audit", str(query_path), "--registry-input", str(registry_path), "--format", "summary"]), 0)
                for suffix in ("entry-schema", "entries-schema", "artifact-schema", "manifest-schema", "summary-schema", "schema", "capabilities", "audit-check-schema", "audit-schema", "audit-capabilities", "query-row-schema", "query-schema", "query-capabilities", "query-audit-check-schema", "query-audit-schema", "query-audit-capabilities"):
                    self.assertEqual(main([COMMAND + "-" + suffix]), 0)
            registry_payload = json.loads((root / "registry.json").read_text(encoding="utf-8"))
            self.assertEqual((registry_payload["entry_count"], registry_payload["state"]), (1, "ready"))
            self.assertGreater(json.loads(query_path.read_text(encoding="utf-8"))["returned_count"], 0)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                server.glio_deployment_guard._rate_windows.clear()
                params = urlencode({"input": str(runtime_path), "registry_id": "api-runtime-registry", "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}?{params}", timeout=30) as response:
                    api_registry = json.loads(response.read().decode("utf-8"))
                self.assertEqual((api_registry["entry_count"], api_registry["state"]), (1, "ready"))
                api_registry_path = root / "api-registry.json"
                api_registry_path.write_text(json.dumps(api_registry), encoding="utf-8")
                params = urlencode({"input": str(registry_path), "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["passed"])
                params = urlencode({"input": str(registry_path), "resource": "latest", "limit": "4", "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query?{params}", timeout=30) as response:
                    api_query = json.loads(response.read().decode("utf-8"))
                self.assertGreater(api_query["returned_count"], 0)
                api_query_path = root / "api-query.json"
                api_query_path.write_text(json.dumps(api_query), encoding="utf-8")
                params = urlencode({"input": str(api_query_path), "registry_input": str(registry_path), "format": "summary"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["passed"])
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

        inventory = build_default_public_surface_audit()
        self.assertEqual((inventory.surface_count, inventory.passed_surface_count, inventory.failed_surface_count, inventory.accepted), (2140, 2140, 0, True))
        for schema in (registry_model.entry_schema(), registry_model.entries_schema(), registry_model.artifact_schema(), registry_model.manifest_schema(), registry_model.summary_schema(), registry_model.registry_schema(), registry_audit_model.check_schema(), registry_audit_model.audit_schema(), registry_query_model.row_schema(), registry_query_model.query_schema(), registry_query_audit_model.check_schema(), registry_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
