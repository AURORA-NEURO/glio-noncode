"""Regression coverage for recovery execution runtime registries."""

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
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry as registry_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_audit as registry_audit_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_query as registry_query_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_query_audit as registry_query_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit


COMMAND = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history-observatory-archive-transfer-recovery-execution"
API_PATH = "/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query-snapshot/registry/history/observatory/archive/transfer/recovery/execution"
REGISTRY_API_PATH = API_PATH + "/runtime/registry"


class HistoryObservatoryArchiveTransferRecoveryExecutionRuntimeRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_downloaded_data_comparison_query_snapshot_registry_history_observatory import DownloadedDataComparisonQuerySnapshotRegistryHistoryObservatoryTests as observatory_tests

        observatory_tests.setUpClass()
        fixture = observatory_tests()
        history_left, history_right = fixture._histories()
        cls.observatory = observatory_model.build_observatory((history_left, history_right), observatory_id="history-observatory-execution-runtime-registry-fixture")

    @classmethod
    def _execution(cls):
        archive = archive_model.build_archive(cls.observatory, archive_id="history-observatory-execution-runtime-registry-fixture")
        transfer = transfer_model.build_transfer(archive, transfer_id="history-observatory-execution-runtime-registry-fixture", chunk_size=256)
        assembler = transfer_model.TransferAssembler(transfer)
        payload = transfer.payload_bytes()
        assembler.add_chunk(0, payload[0])
        assembler.add_chunk(transfer.chunk_count - 1, payload[transfer.chunk_count - 1])
        recovery = recovery_model.build_recovery(assembler, recovery_id="history-observatory-execution-runtime-registry-plan", checkpointed=True)
        assembler.add_chunk(1, payload[1])
        execution = execution_model.build_execution_from_assembler(recovery, assembler, execution_id="execution-runtime-registry-progress", checkpointed=True)
        return execution

    @classmethod
    def _runtimes(cls):
        execution = cls._execution()
        return (
            runtime_model.build_runtime(execution, runtime_id="execution-runtime-registry-fixture-primary"),
            runtime_model.build_runtime(execution, runtime_id="execution-runtime-registry-fixture-secondary"),
        )

    def test_registry_admission_audit_query_and_round_trips(self):
        primary, secondary = self._runtimes()
        registry = registry_model.build_registry((primary, secondary), registry_id="execution-runtime-registry-fixture")
        audit = registry_audit_model.audit_registry(registry)
        query = registry_query_model.query_registry(registry, resources=registry_query_model.RESOURCES, limit=registry_query_model.MAX_LIMIT)
        query_audit = registry_query_audit_model.audit_query(query, registry)

        self.assertEqual((registry.state, registry.accepted, registry.entry_count), ("ready", True, 2))
        self.assertEqual((registry.accepted_count, registry.ready_count, registry.blocked_count), (2, 2, 0))
        self.assertEqual((audit.check_count, audit.passed), (16, True))
        self.assertEqual((query.total_count, query.returned_count, query.truncated), (len(query.rows), len(query.rows), False))
        self.assertGreater(len(query.rows), 0)
        self.assertEqual((query_audit.check_count, query_audit.passed), (12, True))
        self.assertEqual(registry_model.registry_from_mapping(json.loads(registry_model.registry_json(registry))).content_address, registry.content_address)
        self.assertEqual(registry_audit_model.audit_from_mapping(json.loads(registry_audit_model.audit_json(audit))).content_address, audit.content_address)
        self.assertEqual(registry_query_model.query_from_mapping(json.loads(registry_query_model.query_json(query))).content_address, query.content_address)
        self.assertEqual(registry_query_audit_model.audit_from_mapping(json.loads(registry_query_audit_model.audit_json(query_audit))).content_address, query_audit.content_address)
        self.assertTrue(registry_model.registry_csv(registry).startswith("field,value\n"))
        self.assertIn("# Recovery Execution Runtime Registry", registry_model.render_registry_markdown(registry))

    def test_exact_atomic_persistence_duplicate_and_tamper_rejection(self):
        primary, secondary = self._runtimes()
        registry = registry_model.build_registry((primary, secondary), registry_id="execution-runtime-registry-persisted-fixture")
        with self.assertRaises(ValidationError):
            registry_model.build_registry((primary, primary), registry_id="execution-runtime-registry-duplicate-fixture")
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "registry"
            registry_model.persist_registry(registry, destination)
            self.assertEqual(tuple(sorted(item.name for item in destination.iterdir())), tuple(sorted(registry_model.FILES)))
            loaded = registry_model.load_registry(destination)
            self.assertEqual(loaded.content_address, registry.content_address)
            self.assertEqual(registry_model.registry_json(loaded), registry_model.registry_json(registry))

            entries_path = destination / "entries.json"
            entries_path.write_text(entries_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaises(ValidationError):
                registry_model.load_registry(destination)

            registry_model.persist_registry(registry, destination, overwrite=True)
            (destination / "unexpected.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                registry_model.load_registry(destination)

    def test_cli_api_schemas_and_public_inventory(self):
        primary, secondary = self._runtimes()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            primary_path = root / "primary-runtime"
            secondary_path = root / "secondary-runtime"
            registry_path = root / "registry.json"
            registry_directory = root / "registry"
            query_path = root / "query.json"
            runtime_model.persist_runtime(primary, primary_path)
            runtime_model.persist_runtime(secondary, secondary_path)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([COMMAND + "-runtime-registry", str(primary_path), str(secondary_path), "--registry-id", "execution-runtime-registry-cli", "--destination", str(registry_directory), "--format", "json", "--output", str(registry_path)]), 0)
                self.assertEqual(main([COMMAND + "-runtime-registry-verify", str(registry_directory), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-runtime-registry-audit", str(registry_directory), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-runtime-registry-query", str(registry_directory), "--resource", "states", "--limit", "8", "--format", "json", "--output", str(query_path)]), 0)
                self.assertEqual(main([COMMAND + "-runtime-registry-query-audit", str(query_path), "--registry-input", str(registry_directory), "--format", "summary"]), 0)
                for suffix in ("entry-schema", "entries-schema", "manifest-schema", "summary-schema", "schema", "capabilities", "audit-check-schema", "audit-schema", "audit-capabilities", "query-row-schema", "query-schema", "query-capabilities", "query-audit-check-schema", "query-audit-schema", "query-audit-capabilities"):
                    self.assertEqual(main([COMMAND + "-runtime-registry-" + suffix]), 0)
            self.assertEqual(registry_model.registry_from_mapping(json.loads(registry_path.read_text(encoding="utf-8"))).content_address, registry_model.load_registry(registry_directory).content_address)
            self.assertEqual(json.loads(query_path.read_text(encoding="utf-8"))["registry_id"], "execution-runtime-registry-cli")

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                server.glio_deployment_guard._rate_windows.clear()
                params = urlencode([("runtime_input", str(primary_path)), ("runtime_input", str(secondary_path)), ("registry_id", "execution-runtime-registry-api"), ("destination", str(root / "api-registry")), ("overwrite", "true"), ("format", "json")])
                with urlopen(f"http://127.0.0.1:{server.server_port}{REGISTRY_API_PATH}?{params}", timeout=30) as response:
                    api_registry = json.loads(response.read().decode("utf-8"))
                api_registry_directory = root / "api-registry"
                self.assertEqual((api_registry["registry_id"], api_registry["entry_count"]), ("execution-runtime-registry-api", 2))
                params = urlencode([("input", str(api_registry_directory)), ("format", "json")])
                with urlopen(f"http://127.0.0.1:{server.server_port}{REGISTRY_API_PATH}/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["accepted"])
                params = urlencode([("input", str(api_registry_directory)), ("resource", "states"), ("limit", "8"), ("format", "json")])
                with urlopen(f"http://127.0.0.1:{server.server_port}{REGISTRY_API_PATH}/query?{params}", timeout=30) as response:
                    api_query = json.loads(response.read().decode("utf-8"))
                api_query_path = root / "api-query.json"
                api_query_path.write_text(json.dumps(api_query), encoding="utf-8")
                params = urlencode([("input", str(api_query_path)), ("registry_input", str(api_registry_directory)), ("format", "summary")])
                with urlopen(f"http://127.0.0.1:{server.server_port}{REGISTRY_API_PATH}/query/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["accepted"])
                with urlopen(f"http://127.0.0.1:{server.server_port}{REGISTRY_API_PATH}/entry-schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

        inventory = build_default_public_surface_audit()
        self.assertEqual((inventory.surface_count, inventory.passed_surface_count, inventory.failed_surface_count, inventory.accepted), (1708, 1708, 0, True))
        for schema in (registry_model.entry_schema(), registry_model.entries_schema(), registry_model.manifest_schema(), registry_model.summary_schema(), registry_model.registry_schema(), registry_audit_model.check_schema(), registry_audit_model.audit_schema(), registry_query_model.row_schema(), registry_query_model.query_schema(), registry_query_audit_model.check_schema(), registry_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
