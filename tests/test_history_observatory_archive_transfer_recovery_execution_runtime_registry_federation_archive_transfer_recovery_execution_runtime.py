"""Regression coverage for federation archive recovery execution runtime handoffs."""

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
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_audit as runtime_audit_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_query as runtime_query_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_query_audit as runtime_query_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit


COMMAND = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history-observatory-archive-transfer-recovery-execution-runtime-registry-federation-archive-transfer-recovery-execution-runtime"
API_PATH = "/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query-snapshot/registry/history/observatory/archive/transfer/recovery/execution/runtime/registry/federation/archive/transfer/recovery/execution/runtime"


class HistoryObservatoryArchiveTransferRecoveryExecutionRuntimeRegistryFederationArchiveTransferRecoveryExecutionRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer import HistoryObservatoryArchiveTransferRecoveryExecutionRuntimeRegistryFederationArchiveTransferTests as transfer_tests

        transfer_tests.setUpClass()
        cls.federation = transfer_tests.federation

    @classmethod
    def _execution(cls, root: Path):
        federation_directory = root / "federation"
        federation_model.persist_federation(cls.federation, federation_directory)
        archive = archive_model.build_archive_from_directory(federation_directory, archive_id="downloaded-real-federation-archive-runtime")
        archive_path = root / "federation.zip"
        archive_model.write_archive(archive, archive_path)
        transfer = transfer_model.build_transfer(archive_model.load_archive(archive_path), transfer_id="downloaded-real-transfer-runtime", chunk_size=1024)
        assembler = transfer_model.TransferAssembler(transfer)
        payload = transfer.payload_bytes()
        assembler.add_chunk(0, payload[0])
        assembler.add_chunk(5, payload[5])
        partial_directory = root / "partial"
        transfer_model.write_partial_transfer(assembler, partial_directory)
        recovery = recovery_model.build_recovery_from_directory(partial_directory, recovery_id="downloaded-real-recovery-runtime")
        return execution_model.build_execution(recovery, applied_indices=(1, 2), checkpointed=True)

    def test_runtime_composes_persists_reloads_and_audits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            execution = self._execution(root)
            runtime = runtime_model.build_runtime(execution, runtime_id="downloaded-real-execution-runtime")
            runtime_audit = runtime_audit_model.audit_runtime(runtime)
            query = runtime_query_model.query_runtime(runtime, resources=runtime_query_model.RESOURCES, limit=runtime_query_model.MAX_LIMIT)
            query_audit = runtime_query_audit_model.audit_query(query, runtime)
            runtime_directory = root / "runtime"
            runtime_model.persist_runtime(runtime, runtime_directory)
            loaded = runtime_model.load_runtime(runtime_directory)

            self.assertEqual((runtime.state, runtime.accepted, runtime.stage_count), ("ready", True, 5))
            self.assertEqual(tuple(stage.stage for stage in loaded.stages), runtime_model.STAGES)
            self.assertEqual((runtime_audit.check_count, runtime_audit.passed, query.total_count, query.returned_count, query_audit.check_count, query_audit.passed), (16, True, query.returned_count, query.returned_count, 12, True))
            self.assertEqual(loaded.to_dict(), runtime.to_dict())
            self.assertEqual(tuple(sorted(item.name for item in runtime_directory.iterdir())), tuple(sorted(runtime_model.FILES)))
            self.assertEqual(json.loads((runtime_directory / "manifest.json").read_text(encoding="utf-8"))["files"], list(runtime_model.FILES))
            self.assertEqual(runtime_model.runtime_from_mapping(json.loads(runtime_model.runtime_json(runtime))).to_dict(), runtime.to_dict())
            self.assertEqual(runtime_model.manifest_document(runtime)["runtime_address"], runtime.content_address)

    def test_cli_and_http_runtime_surfaces(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            execution = self._execution(root)
            execution_json = root / "execution.json"
            runtime_json = root / "runtime.json"
            runtime_directory = root / "runtime"
            query_json = root / "query.json"
            execution_json.write_text(execution_model.execution_json(execution), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([COMMAND, str(execution_json), "--destination", str(runtime_directory), "--overwrite", "--format", "json", "--output", str(runtime_json)]), 0)
                self.assertEqual(main([COMMAND + "-verify", str(runtime_directory), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-audit", str(runtime_directory), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-query", str(runtime_directory), "--resource", "stages", "--format", "json", "--output", str(query_json)]), 0)
                self.assertEqual(main([COMMAND + "-query-audit", str(query_json), "--runtime-input", str(runtime_directory), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-schema"]), 0)
            emitted_runtime = json.loads(runtime_json.read_text(encoding="utf-8"))
            emitted_query = json.loads(query_json.read_text(encoding="utf-8"))
            self.assertEqual((emitted_runtime["state"], emitted_runtime["accepted"], emitted_runtime["stage_count"]), ("ready", True, 5))
            self.assertEqual((emitted_query["resources"], emitted_query["returned_count"]), (["stages"], 5))

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                server.glio_deployment_guard._rate_windows.clear()
                base = {"input": str(runtime_directory), "format": "json"}
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}?{urlencode(base)}", timeout=30) as response:
                    api_runtime = json.loads(response.read().decode("utf-8"))
                self.assertEqual((api_runtime["state"], api_runtime["accepted"]), ("ready", True))
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/audit?{urlencode(base)}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["passed"])
                query_params = base | {"resource": "stages"}
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query?{urlencode(query_params)}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["returned_count"], 5)
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

        inventory = build_default_public_surface_audit()
        self.assertEqual((inventory.surface_count, inventory.passed_surface_count, inventory.failed_surface_count, inventory.accepted), (1830, 1830, 0, True))
        for schema in (runtime_model.stage_schema(), runtime_model.manifest_schema(), runtime_model.runtime_schema(), runtime_audit_model.check_schema(), runtime_audit_model.audit_schema(), runtime_query_model.row_schema(), runtime_query_model.query_schema(), runtime_query_audit_model.check_schema(), runtime_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_load_rejects_noncanonical_runtime_member(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = runtime_model.build_runtime(self._execution(root))
            runtime_directory = root / "runtime"
            runtime_model.persist_runtime(runtime, runtime_directory)
            runtime_path = runtime_directory / "runtime.json"
            runtime_path.write_text(runtime_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            with self.assertRaises(ValidationError):
                runtime_model.load_runtime(runtime_directory)


if __name__ == "__main__":
    unittest.main()
