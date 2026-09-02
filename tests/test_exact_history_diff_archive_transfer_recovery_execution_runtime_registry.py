"""Regression coverage for exact history-diff recovery execution runtime registries."""

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

from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_runtime_registry as registry_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_runtime_registry_audit as registry_audit_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_runtime_registry_query as registry_query_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_runtime_registry_query_audit as registry_query_audit_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_runtime as runtime_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_runtime_query as runtime_query_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit

import tests.test_exact_history_diff_archive_transfer_recovery_execution_runtime as runtime_test_module


COMMAND = runtime_test_module.COMMAND + "-registry"
API_PATH = runtime_test_module.API_PATH + "/registry"


class ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runtime_test_module.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeTests.setUpClass()

    def _runtime(self, runtime_id: str):
        runtime_tests = runtime_test_module.execution_test_module.ExactHistoryDiffArchiveTransferRecoveryExecutionTests()
        _, assembler, recovery, payload = runtime_tests._partial()
        assembler.add_chunk(1, payload[1])
        execution = runtime_test_module.execution_model.build_execution_from_assembler(recovery, assembler, execution_id=runtime_id + "-execution", checkpointed=True)
        return runtime_model.build_runtime(execution, runtime_id=runtime_id)

    def test_registry_composes_persists_reloads_and_audits(self):
        first = self._runtime("history-diff-execution-runtime-a")
        second = self._runtime("history-diff-execution-runtime-b")
        registry = registry_model.build_registry((second, first), registry_id="history-diff-runtime-registry")
        registry_audit = registry_audit_model.audit_registry(registry)
        query = registry_query_model.query_registry(registry, resources=registry_query_model.RESOURCES, limit=registry_query_model.MAX_LIMIT)
        query_audit = registry_query_audit_model.audit_query(query, registry)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "registry"
            registry_model.persist_registry(registry, destination)
            loaded = registry_model.load_registry(destination)
            empty = registry_model.build_registry((), registry_id="history-diff-empty-runtime-registry")
            self.assertEqual((registry.state, registry.accepted, registry.entry_count, registry.ready_count), ("ready", True, 2, 2))
            self.assertEqual(tuple(item.runtime_id for item in loaded.entries), ("history-diff-execution-runtime-a", "history-diff-execution-runtime-b"))
            self.assertEqual((registry_audit.check_count, registry_audit.passed, query.total_count, query.returned_count, query_audit.check_count, query_audit.passed), (16, True, query.returned_count, query.returned_count, 12, True))
            self.assertEqual((empty.state, empty.accepted, empty.entry_count), ("empty", True, 0))
            self.assertEqual(loaded.to_dict(), registry.to_dict())
            self.assertEqual(tuple(sorted(item.name for item in destination.iterdir())), tuple(sorted(registry_model.FILES)))
            self.assertEqual(json.loads((destination / "manifest.json").read_text(encoding="utf-8"))["files"], list(registry_model.FILES))
            self.assertEqual(registry_model.registry_from_mapping(json.loads(registry_model.registry_json(registry))).to_dict(), registry.to_dict())

    def test_tampered_registry_and_query_fail_closed(self):
        registry = registry_model.build_registry((self._runtime("history-diff-execution-runtime"),), registry_id="history-diff-runtime-registry")
        tampered = registry.to_dict()
        tampered["accepted_count"] = 0
        with self.assertRaises(ValidationError):
            registry_model.registry_from_mapping(tampered)
        query = registry_query_model.query_registry(registry, resources=("runtimes",), limit=1)
        tampered_query = query.to_dict()
        tampered_query["returned_count"] = 0
        with self.assertRaises(ValidationError):
            registry_query_model.query_from_mapping(tampered_query)
        self.assertNotIn("source_path", registry_model.registry_json(registry))
        self.assertNotIn("payload_bytes", registry_model.registry_json(registry))

    def test_cli_api_schemas_and_public_inventory(self):
        first = self._runtime("history-diff-execution-runtime-a")
        second = self._runtime("history-diff-execution-runtime-b")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first_directory = root / "runtime-a"
            second_directory = root / "runtime-b"
            registry_directory = root / "registry"
            registry_path = root / "registry.json"
            query_path = root / "query.json"
            runtime_model.persist_runtime(first, first_directory)
            runtime_model.persist_runtime(second, second_directory)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([COMMAND, "--runtime-input", str(first_directory), "--runtime-input", str(second_directory), "--registry-id", "history-diff-cli-runtime-registry", "--destination", str(registry_directory), "--overwrite", "--format", "json", "--output", str(registry_path)]), 0)
                self.assertEqual(main([COMMAND + "-verify", str(registry_directory), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-audit", str(registry_directory), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-query", str(registry_directory), "--resource", "runtimes", "--format", "json", "--output", str(query_path)]), 0)
                self.assertEqual(main([COMMAND + "-query-audit", str(query_path), "--registry-input", str(registry_directory), "--format", "summary"]), 0)
                for suffix in ("entry-schema", "entries-schema", "manifest-schema", "summary-schema", "schema", "capabilities", "audit-check-schema", "audit-schema", "audit-capabilities", "query-row-schema", "query-schema", "query-capabilities", "query-audit-check-schema", "query-audit-schema", "query-audit-capabilities"):
                    self.assertEqual(main([COMMAND + "-" + suffix]), 0)
            emitted_registry = json.loads(registry_path.read_text(encoding="utf-8"))
            emitted_query = json.loads(query_path.read_text(encoding="utf-8"))
            self.assertEqual((emitted_registry["state"], emitted_registry["accepted"], emitted_registry["entry_count"]), ("ready", True, 2))
            self.assertEqual((emitted_query["resources"], emitted_query["returned_count"]), (["runtimes"], 2))

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                server.glio_deployment_guard._rate_windows.clear()
                params = urlencode({"input": str(registry_directory), "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}?{params}", timeout=30) as response:
                    api_registry = json.loads(response.read().decode("utf-8"))
                self.assertEqual((api_registry["state"], api_registry["accepted"], api_registry["entry_count"]), ("ready", True, 2))
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["accepted"])
                query_params = urlencode({"input": str(registry_directory), "resource": "states", "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query?{query_params}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["returned_count"], 3)
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

        inventory = build_default_public_surface_audit()
        self.assertEqual((inventory.surface_count, inventory.passed_surface_count, inventory.failed_surface_count, inventory.accepted), (2152, 2152, 0, True))
        for schema in (registry_model.entry_schema(), registry_model.entries_schema(), registry_model.manifest_schema(), registry_model.summary_schema(), registry_model.registry_schema(), registry_audit_model.check_schema(), registry_audit_model.audit_schema(), registry_query_model.row_schema(), registry_query_model.query_schema(), registry_query_audit_model.check_schema(), registry_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
