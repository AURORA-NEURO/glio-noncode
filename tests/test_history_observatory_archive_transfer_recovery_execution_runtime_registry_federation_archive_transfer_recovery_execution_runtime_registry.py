"""Regression coverage for federation recovery execution runtime registries."""

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

from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation as federation_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive as archive_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer as transfer_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery as recovery_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution as execution_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime as runtime_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry as registry_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_audit as registry_audit_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_query as registry_query_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_query_audit as registry_query_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit


COMMAND = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history-observatory-archive-transfer-recovery-execution-runtime-registry-federation-archive-transfer-recovery-execution-runtime-registry"
API_PATH = "/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query-snapshot/registry/history/observatory/archive/transfer/recovery/execution/runtime/registry/federation/archive/transfer/recovery/execution/runtime/registry"


class HistoryObservatoryArchiveTransferRecoveryExecutionRuntimeRegistryFederationArchiveTransferRecoveryExecutionRuntimeRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime import HistoryObservatoryArchiveTransferRecoveryExecutionRuntimeRegistryFederationArchiveTransferRecoveryExecutionRuntimeTests as runtime_tests

        runtime_tests.setUpClass()
        cls.federation = runtime_tests.federation

    @classmethod
    def _execution(cls, root: Path):
        federation_directory = root / "federation"
        federation_model.persist_federation(cls.federation, federation_directory)
        archive = archive_model.build_archive_from_directory(federation_directory, archive_id="downloaded-real-federation-registry")
        archive_path = root / "federation.zip"
        archive_model.write_archive(archive, archive_path)
        transfer = transfer_model.build_transfer(archive_model.load_archive(archive_path), transfer_id="downloaded-real-transfer-registry", chunk_size=1024)
        assembler = transfer_model.TransferAssembler(transfer)
        payload = transfer.payload_bytes()
        assembler.add_chunk(0, payload[0])
        assembler.add_chunk(5, payload[5])
        partial_directory = root / "partial"
        transfer_model.write_partial_transfer(assembler, partial_directory)
        recovery = recovery_model.build_recovery_from_directory(partial_directory, recovery_id="downloaded-real-recovery-registry")
        return execution_model.build_execution(recovery, applied_indices=(1, 2), checkpointed=True)

    def test_registry_composes_persists_reloads_and_audits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            execution = self._execution(root)
            first = runtime_model.build_runtime(execution, runtime_id="downloaded-real-execution-runtime-a")
            second = runtime_model.build_runtime(execution, runtime_id="downloaded-real-execution-runtime-b")
            registry = registry_model.build_registry((second, first), registry_id="downloaded-real-runtime-registry")
            registry_audit = registry_audit_model.audit_registry(registry)
            query = registry_query_model.query_registry(registry, resources=registry_query_model.RESOURCES, limit=registry_query_model.MAX_LIMIT)
            query_audit = registry_query_audit_model.audit_query(query, registry)
            registry_directory = root / "registry"
            registry_model.persist_registry(registry, registry_directory)
            loaded = registry_model.load_registry(registry_directory)
            empty = registry_model.build_registry((), registry_id="downloaded-empty-runtime-registry")

            self.assertEqual((registry.state, registry.accepted, registry.entry_count, registry.ready_count), ("ready", True, 2, 2))
            self.assertEqual(tuple(item.runtime_id for item in loaded.entries), ("downloaded-real-execution-runtime-a", "downloaded-real-execution-runtime-b"))
            self.assertEqual((registry_audit.check_count, registry_audit.passed, query.total_count, query.returned_count, query_audit.check_count, query_audit.passed), (16, True, query.returned_count, query.returned_count, 12, True))
            self.assertEqual((empty.state, empty.accepted, empty.entry_count), ("empty", True, 0))
            self.assertEqual(loaded.to_dict(), registry.to_dict())
            self.assertEqual(tuple(sorted(item.name for item in registry_directory.iterdir())), tuple(sorted(registry_model.FILES)))
            self.assertEqual(json.loads((registry_directory / "manifest.json").read_text(encoding="utf-8"))["files"], list(registry_model.FILES))
            self.assertEqual(registry_model.registry_from_mapping(json.loads(registry_model.registry_json(registry))).to_dict(), registry.to_dict())
            self.assertEqual(registry_model.manifest_json(registry.manifest), registry_model.manifest_json(registry.manifest))

    def test_cli_and_http_registry_surfaces(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            execution = self._execution(root)
            first = runtime_model.build_runtime(execution, runtime_id="downloaded-real-execution-runtime-a")
            second = runtime_model.build_runtime(execution, runtime_id="downloaded-real-execution-runtime-b")
            first_directory = root / "runtime-a"
            second_directory = root / "runtime-b"
            runtime_model.persist_runtime(first, first_directory)
            runtime_model.persist_runtime(second, second_directory)
            registry_directory = root / "registry"
            registry_json = root / "registry.json"
            query_json = root / "query.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([COMMAND, "--runtime-input", str(first_directory), "--runtime-input", str(second_directory), "--registry-id", "downloaded-cli-runtime-registry", "--destination", str(registry_directory), "--overwrite", "--format", "json", "--output", str(registry_json)]), 0)
                self.assertEqual(main([COMMAND + "-verify", str(registry_directory), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-audit", str(registry_directory), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-query", str(registry_directory), "--resource", "runtimes", "--format", "json", "--output", str(query_json)]), 0)
                query_summary_output = io.StringIO()
                with contextlib.redirect_stdout(query_summary_output):
                    self.assertEqual(main([COMMAND + "-query", str(registry_directory), "--resource", "runtimes", "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-query-audit", str(query_json), "--registry-input", str(registry_directory), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-schema"]), 0)
            emitted_registry = json.loads(registry_json.read_text(encoding="utf-8"))
            emitted_query = json.loads(query_json.read_text(encoding="utf-8"))
            emitted_query_summary = json.loads(query_summary_output.getvalue())
            self.assertEqual((emitted_registry["state"], emitted_registry["accepted"], emitted_registry["entry_count"]), ("ready", True, 2))
            self.assertEqual((emitted_query["resources"], emitted_query["returned_count"]), (["runtimes"], 2))
            self.assertEqual((emitted_query_summary["resources"], emitted_query_summary["returned_count"], "rows" in emitted_query_summary), (["runtimes"], 2, False))

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                server.glio_deployment_guard._rate_windows.clear()
                base = {"input": str(registry_directory), "format": "json"}
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}?{urlencode(base)}", timeout=30) as response:
                    api_registry = json.loads(response.read().decode("utf-8"))
                self.assertEqual((api_registry["state"], api_registry["accepted"], api_registry["entry_count"]), ("ready", True, 2))
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/audit?{urlencode(base)}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["accepted"])
                query_params = base | {"resource": "states"}
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query?{urlencode(query_params)}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["returned_count"], 3)
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

        inventory = build_default_public_surface_audit()
        self.assertEqual((inventory.surface_count, inventory.passed_surface_count, inventory.failed_surface_count, inventory.accepted), (2113, 2113, 0, True))
        for schema in (registry_model.entry_schema(), registry_model.entries_schema(), registry_model.manifest_schema(), registry_model.summary_schema(), registry_model.registry_schema(), registry_audit_model.check_schema(), registry_audit_model.audit_schema(), registry_query_model.row_schema(), registry_query_model.query_schema(), registry_query_audit_model.check_schema(), registry_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_registry_load_rejects_noncanonical_member(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            execution = self._execution(root)
            runtime = runtime_model.build_runtime(execution, runtime_id="downloaded-real-execution-runtime")
            registry = registry_model.build_registry((runtime,), registry_id="downloaded-real-runtime-registry")
            registry_directory = root / "registry"
            registry_model.persist_registry(registry, registry_directory)
            registry_path = registry_directory / "registry.json"
            registry_path.write_text(registry_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            with self.assertRaises(ValidationError):
                registry_model.load_registry(registry_directory)


if __name__ == "__main__":
    unittest.main()
