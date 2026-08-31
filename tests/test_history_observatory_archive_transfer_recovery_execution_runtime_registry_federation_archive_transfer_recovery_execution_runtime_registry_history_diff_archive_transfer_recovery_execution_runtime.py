"""Regression coverage for history-diff recovery execution runtime handoffs."""

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

from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery_execution as execution_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery_execution_runtime as runtime_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery_execution_runtime_audit as runtime_audit_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery_execution_runtime_query as runtime_query_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery_execution_runtime_query_audit as runtime_query_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit

import tests.test_history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery_execution as execution_test_module


COMMAND = execution_test_module.COMMAND + "-runtime"
API_PATH = execution_test_module.API_PATH + "/runtime"


class HistoryObservatoryArchiveTransferRecoveryExecutionRuntimeRegistryFederationArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveTransferRecoveryExecutionRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        execution_test_module.HistoryObservatoryArchiveTransferRecoveryExecutionRuntimeRegistryFederationArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveTransferRecoveryExecutionTests.setUpClass()

    def _runtime(self):
        execution_tests = execution_test_module.HistoryObservatoryArchiveTransferRecoveryExecutionRuntimeRegistryFederationArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveTransferRecoveryExecutionTests()
        _, assembler, recovery, payload = execution_tests._partial()
        assembler.add_chunk(1, payload[1])
        execution = execution_model.build_execution_from_assembler(recovery, assembler, execution_id="runtime-execution", checkpointed=True)
        return runtime_model.build_runtime(execution, runtime_id="history-diff-execution-runtime")

    def test_runtime_composes_persists_reloads_and_audits(self):
        runtime = self._runtime()
        audit = runtime_audit_model.audit_runtime(runtime)
        query = runtime_query_model.query_runtime(runtime, resources=runtime_query_model.RESOURCES, limit=runtime_query_model.MAX_LIMIT)
        query_audit = runtime_query_audit_model.audit_query(query, runtime)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "runtime"
            runtime_model.persist_runtime(runtime, destination)
            loaded = runtime_model.load_runtime(destination)
            self.assertEqual((runtime.state, runtime.accepted, runtime.stage_count), ("ready", True, 5))
            self.assertEqual((audit.check_count, audit.passed, query.total_count, query.returned_count, query_audit.check_count, query_audit.passed), (16, True, query.returned_count, query.returned_count, 12, True))
            self.assertEqual(loaded.to_dict(), runtime.to_dict())
            self.assertEqual(tuple(sorted(item.name for item in destination.iterdir())), tuple(sorted(runtime_model.FILES)))
            self.assertEqual(runtime_model.runtime_from_mapping(json.loads(runtime_model.runtime_json(runtime))).to_dict(), runtime.to_dict())
            self.assertEqual(runtime_model.manifest_document(runtime)["runtime_address"], runtime.content_address)

    def test_tampered_runtime_and_query_fail_closed(self):
        runtime = self._runtime()
        tampered = runtime.to_dict()
        tampered["state"] = "blocked"
        with self.assertRaises(ValidationError):
            runtime_model.runtime_from_mapping(tampered)
        query = runtime_query_model.query_runtime(runtime, resources=("stages",), limit=2)
        tampered_query = query.to_dict()
        tampered_query["returned_count"] = 1
        with self.assertRaises(ValidationError):
            runtime_query_model.query_from_mapping(tampered_query)
        self.assertNotIn("source_path", runtime_model.runtime_json(runtime))
        self.assertNotIn("payload_bytes", runtime_model.runtime_json(runtime))

    def test_cli_api_schemas_and_public_inventory(self):
        runtime = self._runtime()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            execution_path = root / "execution.json"
            runtime_path = root / "runtime.json"
            runtime_directory = root / "runtime"
            query_path = root / "query.json"
            execution_path.write_text(execution_model.execution_json(runtime.execution), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([COMMAND, str(execution_path), "--runtime-id", runtime.runtime_id, "--destination", str(runtime_directory), "--overwrite", "--format", "json", "--output", str(runtime_path)]), 0)
                self.assertEqual(main([COMMAND + "-verify", str(runtime_directory), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-audit", str(runtime_directory), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-query", str(runtime_directory), "--resource", "stages", "--format", "json", "--output", str(query_path)]), 0)
                self.assertEqual(main([COMMAND + "-query-audit", str(query_path), "--runtime-input", str(runtime_directory), "--format", "summary"]), 0)
                for suffix in ("stage-schema", "manifest-schema", "schema", "capabilities", "audit-check-schema", "audit-schema", "audit-capabilities", "query-row-schema", "query-schema", "query-capabilities", "query-audit-check-schema", "query-audit-schema", "query-audit-capabilities"):
                    self.assertEqual(main([COMMAND + "-" + suffix]), 0)
            emitted_runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
            emitted_query = json.loads(query_path.read_text(encoding="utf-8"))
            self.assertEqual((emitted_runtime["state"], emitted_runtime["accepted"], emitted_runtime["stage_count"]), ("ready", True, 5))
            self.assertEqual((emitted_query["resources"], emitted_query["returned_count"]), (["stages"], 5))

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                server.glio_deployment_guard._rate_windows.clear()
                params = urlencode({"input": str(runtime_directory), "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}?{params}", timeout=30) as response:
                    api_runtime = json.loads(response.read().decode("utf-8"))
                self.assertEqual((api_runtime["state"], api_runtime["accepted"]), ("ready", True))
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["passed"])
                query_params = urlencode({"input": str(runtime_directory), "resource": "stages", "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query?{query_params}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["returned_count"], 5)
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

        inventory = build_default_public_surface_audit()
        self.assertEqual((inventory.surface_count, inventory.passed_surface_count, inventory.failed_surface_count, inventory.accepted), (1984, 1984, 0, True))
        for schema in (runtime_model.stage_schema(), runtime_model.manifest_schema(), runtime_model.runtime_schema(), runtime_audit_model.check_schema(), runtime_audit_model.audit_schema(), runtime_query_model.row_schema(), runtime_query_model.query_schema(), runtime_query_audit_model.check_schema(), runtime_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
