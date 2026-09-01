"""Regression coverage for durable execution-ledger runtime handoffs."""

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

from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger as ledger_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime as runtime_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_audit as runtime_audit_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_query as runtime_query_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_query_audit as runtime_query_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit

import tests.test_exact_history_diff_archive_transfer_recovery_execution_ledger as ledger_test_module


COMMAND = ledger_test_module.COMMAND + "-runtime"
API_PATH = ledger_test_module.API_PATH + "/runtime"


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ledger_test_module.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerTests.setUpClass()

    def _ledgers(self):
        planned, progress, complete, blocked = ledger_test_module.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerTests()._executions()
        return (
            ledger_model.build_ledger((planned, progress, complete), ledger_id="runtime-ready-ledger"),
            ledger_model.build_ledger((planned, progress, complete, blocked), ledger_id="runtime-blocked-ledger"),
        )

    def test_ready_and_blocked_stage_replay(self):
        ready_ledger, blocked_ledger = self._ledgers()
        ready = runtime_model.build_runtime(ready_ledger, runtime_id="ready-runtime")
        blocked = runtime_model.build_runtime(blocked_ledger, runtime_id="blocked-runtime")
        ready_audit = runtime_audit_model.audit_runtime(ready)
        blocked_audit = runtime_audit_model.audit_runtime(blocked)
        ready_query = runtime_query_model.query_runtime(ready)
        blocked_query = runtime_query_model.query_runtime(blocked, resources=("stages", "latest"), limit=8)
        ready_query_audit = runtime_query_audit_model.audit_query(ready_query, ready)
        blocked_query_audit = runtime_query_audit_model.audit_query(blocked_query, blocked)
        self.assertEqual((ready.state, ready.accepted, ready_audit.check_count, ready_audit.passed), ("ready", True, 16, True))
        self.assertEqual((blocked.state, blocked.accepted, blocked_audit.check_count, blocked_audit.passed), ("blocked", False, 16, True))
        self.assertEqual(tuple(item.stage for item in blocked.stages), runtime_model.STAGES)
        self.assertEqual(tuple(item.accepted for item in blocked.stages), (False, True, True, True, False))
        self.assertEqual((ready_query.returned_count, ready_query_audit.check_count, ready_query_audit.passed), (ready_query.total_count, 12, True))
        self.assertEqual((blocked_query.resources, blocked_query.returned_count, blocked_query_audit.passed), (("stages", "latest"), 8, True))
        self.assertEqual(runtime_model.runtime_from_mapping(ready.to_dict()).content_address, ready.content_address)

    def test_exact_package_reload_and_tamper_rejection(self):
        ready_ledger, _ = self._ledgers()
        value = runtime_model.build_runtime(ready_ledger, runtime_id="persisted-runtime")
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "runtime"
            runtime_model.persist_runtime(value, destination)
            loaded = runtime_model.load_runtime(destination)
            self.assertEqual(runtime_model.runtime_json(loaded), runtime_model.runtime_json(value))
            self.assertEqual(set(item.name for item in destination.iterdir()), set(runtime_model.FILES))
            tampered = destination / "runtime.json"
            payload = json.loads(tampered.read_text(encoding="utf-8"))
            payload["state"] = "blocked"
            tampered.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
            with self.assertRaises(ValidationError):
                runtime_model.load_runtime(destination)

            runtime_model.persist_runtime(value, destination, overwrite=True)
            (destination / "unexpected.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                runtime_model.load_runtime(destination)

    def test_cli_api_schemas_and_public_inventory(self):
        ready_ledger, _ = self._ledgers()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ledger_path = root / "ledger.json"
            ledger_path.write_text(ledger_test_module.ledger_model.ledger_json(ready_ledger), encoding="utf-8")
            runtime_path = root / "runtime"
            query_path = root / "query.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([COMMAND, str(ledger_path), "--runtime-id", "cli-runtime", "--destination", str(runtime_path), "--format", "json", "--output", str(root / "runtime.json")]), 0)
                self.assertEqual(main([COMMAND + "-verify", str(runtime_path), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-audit", str(runtime_path), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-query", str(runtime_path), "--resource", "stages", "--limit", "8", "--format", "json", "--output", str(query_path)]), 0)
                self.assertEqual(main([COMMAND + "-query-audit", str(query_path), "--runtime-input", str(runtime_path), "--format", "summary"]), 0)
                for suffix in ("stage-schema", "artifact-schema", "manifest-schema", "summary-schema", "schema", "capabilities", "audit-check-schema", "audit-schema", "audit-capabilities", "query-row-schema", "query-schema", "query-capabilities", "query-audit-check-schema", "query-audit-schema", "query-audit-capabilities"):
                    self.assertEqual(main([COMMAND + "-" + suffix]), 0)

            runtime_payload = json.loads((root / "runtime.json").read_text(encoding="utf-8"))
            self.assertEqual((runtime_payload["state"], runtime_payload["stage_count"]), ("ready", 5))
            self.assertGreater(json.loads(query_path.read_text(encoding="utf-8"))["returned_count"], 0)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                server.glio_deployment_guard._rate_windows.clear()
                params = urlencode({"input": str(ledger_path), "runtime_id": "api-runtime", "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}?{params}", timeout=30) as response:
                    api_runtime = json.loads(response.read().decode("utf-8"))
                self.assertEqual((api_runtime["state"], api_runtime["accepted"]), ("ready", True))
                api_runtime_path = root / "api-runtime.json"
                api_runtime_path.write_text(json.dumps(api_runtime), encoding="utf-8")
                params = urlencode({"input": str(runtime_path), "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["passed"])
                params = urlencode({"input": str(runtime_path), "resource": "latest", "limit": "4", "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query?{params}", timeout=30) as response:
                    api_query = json.loads(response.read().decode("utf-8"))
                self.assertGreater(api_query["returned_count"], 0)
                api_query_path = root / "api-query.json"
                api_query_path.write_text(json.dumps(api_query), encoding="utf-8")
                params = urlencode({"input": str(api_query_path), "runtime_input": str(runtime_path), "format": "summary"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["passed"])
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

        inventory = build_default_public_surface_audit()
        self.assertEqual((inventory.surface_count, inventory.passed_surface_count, inventory.failed_surface_count, inventory.accepted), (2081, 2081, 0, True))
        for schema in (runtime_model.stage_schema(), runtime_model.artifact_schema(), runtime_model.manifest_schema(), runtime_model.summary_schema(), runtime_model.runtime_schema(), runtime_audit_model.check_schema(), runtime_audit_model.audit_schema(), runtime_query_model.row_schema(), runtime_query_model.query_schema(), runtime_query_audit_model.check_schema(), runtime_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
