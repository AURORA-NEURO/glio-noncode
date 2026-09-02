"""Regression coverage for durable recovery execution runtime handoffs."""

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

from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory as observatory_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive as archive_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive_transfer as transfer_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive_transfer_recovery as recovery_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution as execution_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime as runtime_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_audit as runtime_audit_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_query as runtime_query_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_query_audit as runtime_query_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit


COMMAND = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history-observatory-archive-transfer-recovery-execution"
API_PATH = "/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query-snapshot/registry/history/observatory/archive/transfer/recovery/execution"
RUNTIME_API_PATH = API_PATH + "/runtime"


class HistoryObservatoryArchiveTransferRecoveryExecutionRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_downloaded_data_comparison_query_snapshot_registry_history_observatory import DownloadedDataComparisonQuerySnapshotRegistryHistoryObservatoryTests as observatory_tests

        observatory_tests.setUpClass()
        fixture = observatory_tests()
        history_left, history_right = fixture._histories()
        cls.observatory = observatory_model.build_observatory((history_left, history_right), observatory_id="history-observatory-execution-runtime-fixture")

    @classmethod
    def _transfer(cls):
        archive = archive_model.build_archive(cls.observatory, archive_id="history-observatory-execution-runtime-fixture")
        return transfer_model.build_transfer(archive, transfer_id="history-observatory-execution-runtime-fixture", chunk_size=256)

    def _execution(self):
        transfer = self._transfer()
        assembler = transfer_model.TransferAssembler(transfer)
        payload = transfer.payload_bytes()
        assembler.add_chunk(0, payload[0])
        assembler.add_chunk(transfer.chunk_count - 1, payload[transfer.chunk_count - 1])
        recovery = recovery_model.build_recovery(assembler, recovery_id="history-observatory-execution-runtime-plan", checkpointed=True)
        assembler.add_chunk(1, payload[1])
        execution = execution_model.build_execution_from_assembler(recovery, assembler, execution_id="execution-runtime-progress", checkpointed=True)
        return transfer, execution

    def test_runtime_stages_audits_queries_and_round_trips(self):
        transfer, execution = self._execution()
        runtime = runtime_model.build_runtime(execution, runtime_id="execution-runtime-fixture")
        runtime_audit = runtime_audit_model.audit_runtime(runtime)
        runtime_query = runtime_query_model.query_runtime(runtime, resources=runtime_query_model.RESOURCES, limit=runtime_query_model.MAX_LIMIT)
        runtime_query_audit = runtime_query_audit_model.audit_query(runtime_query, runtime)

        self.assertEqual((runtime.state, runtime.accepted, runtime.stage_count), ("ready", True, 5))
        self.assertEqual(tuple(stage.stage for stage in runtime.stages), ("execution", "audit", "query", "query-audit", "complete"))
        self.assertEqual((runtime_audit.check_count, runtime_audit.passed), (16, True))
        self.assertEqual((runtime_query.total_count, runtime_query.returned_count, runtime_query.truncated), (len(runtime_query.rows), len(runtime_query.rows), False))
        self.assertGreater(len(runtime_query.rows), 0)
        self.assertEqual((runtime_query_audit.check_count, runtime_query_audit.passed), (12, True))
        self.assertGreater(transfer.chunk_count, 0)

        self.assertEqual(runtime_model.runtime_from_mapping(json.loads(runtime_model.runtime_json(runtime))).content_address, runtime.content_address)
        self.assertEqual(runtime_audit_model.audit_from_mapping(json.loads(runtime_audit_model.audit_json(runtime_audit))).content_address, runtime_audit.content_address)
        self.assertEqual(runtime_query_model.query_from_mapping(json.loads(runtime_query_model.query_json(runtime_query))).content_address, runtime_query.content_address)
        self.assertEqual(runtime_query_audit_model.audit_from_mapping(json.loads(runtime_query_audit_model.audit_json(runtime_query_audit))).content_address, runtime_query_audit.content_address)
        self.assertTrue(runtime_model.runtime_csv(runtime).startswith("runtime_id,execution_id,"))
        self.assertIn("Archive transfer recovery execution runtime", runtime_model.render_runtime_markdown(runtime))

    def test_exact_atomic_persistence_reload_and_tamper_rejection(self):
        _, execution = self._execution()
        runtime = runtime_model.build_runtime(execution, runtime_id="execution-runtime-persisted-fixture")
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "runtime"
            runtime_model.persist_runtime(runtime, destination)
            self.assertEqual(tuple(sorted(item.name for item in destination.iterdir())), tuple(sorted(runtime_model.FILES)))
            loaded = runtime_model.load_runtime(destination)
            self.assertEqual(loaded.content_address, runtime.content_address)
            self.assertEqual(runtime_model.runtime_json(loaded), runtime_model.runtime_json(runtime))

            execution_path = destination / "execution.json"
            execution_path.write_text(execution_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaises(ValidationError):
                runtime_model.load_runtime(destination)

            execution_path.write_text(runtime_model.runtime_json(runtime), encoding="utf-8")
            with self.assertRaises(ValidationError):
                runtime_model.load_runtime(destination)

    def test_cli_api_schemas_and_public_inventory(self):
        _, execution = self._execution()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            execution_path = root / "execution.json"
            runtime_path = root / "runtime.json"
            runtime_directory = root / "runtime"
            query_path = root / "query.json"
            execution_path.write_text(execution_model.execution_json(execution), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([COMMAND + "-runtime", str(execution_path), "--runtime-id", "execution-runtime-cli", "--destination", str(runtime_directory), "--format", "json", "--output", str(runtime_path)]), 0)
                self.assertEqual(main([COMMAND + "-runtime-verify", str(runtime_directory), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-runtime-audit", str(runtime_directory), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-runtime-query", str(runtime_directory), "--resource", "stages", "--limit", "8", "--format", "json", "--output", str(query_path)]), 0)
                self.assertEqual(main([COMMAND + "-runtime-query-audit", str(query_path), "--runtime-input", str(runtime_directory), "--format", "summary"]), 0)
                for suffix in ("stage-schema", "manifest-schema", "schema", "capabilities", "audit-check-schema", "audit-schema", "audit-capabilities", "query-row-schema", "query-schema", "query-capabilities", "query-audit-check-schema", "query-audit-schema", "query-audit-capabilities"):
                    self.assertEqual(main([COMMAND + "-runtime-" + suffix]), 0)
            self.assertEqual(runtime_model.runtime_from_mapping(json.loads(runtime_path.read_text(encoding="utf-8"))).content_address, runtime_model.load_runtime(runtime_directory).content_address)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                server.glio_deployment_guard._rate_windows.clear()
                params = urlencode([("input", str(execution_path)), ("runtime_id", "execution-runtime-api"), ("destination", str(root / "api-runtime")), ("overwrite", "true"), ("format", "json")])
                with urlopen(f"http://127.0.0.1:{server.server_port}{RUNTIME_API_PATH}?{params}", timeout=30) as response:
                    api_runtime = json.loads(response.read().decode("utf-8"))
                api_runtime_directory = root / "api-runtime"
                self.assertEqual(api_runtime["runtime_id"], "execution-runtime-api")
                params = urlencode([("input", str(api_runtime_directory)), ("format", "json")])
                with urlopen(f"http://127.0.0.1:{server.server_port}{RUNTIME_API_PATH}/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["passed"])
                params = urlencode([("input", str(api_runtime_directory)), ("resource", "stages"), ("limit", "8"), ("format", "json")])
                with urlopen(f"http://127.0.0.1:{server.server_port}{RUNTIME_API_PATH}/query?{params}", timeout=30) as response:
                    api_query = json.loads(response.read().decode("utf-8"))
                query_path.write_text(json.dumps(api_query), encoding="utf-8")
                params = urlencode([("input", str(query_path)), ("runtime_input", str(api_runtime_directory)), ("format", "summary")])
                with urlopen(f"http://127.0.0.1:{server.server_port}{RUNTIME_API_PATH}/query/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["passed"])
                with urlopen(f"http://127.0.0.1:{server.server_port}{RUNTIME_API_PATH}/stage-schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

        inventory = build_default_public_surface_audit()
        self.assertEqual((inventory.surface_count, inventory.passed_surface_count, inventory.failed_surface_count, inventory.accepted), (2152, 2152, 0, True))
        for schema in (runtime_model.stage_schema(), runtime_model.manifest_schema(), runtime_model.runtime_schema(), runtime_audit_model.check_schema(), runtime_audit_model.audit_schema(), runtime_query_model.row_schema(), runtime_query_model.query_schema(), runtime_query_audit_model.check_schema(), runtime_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
