"""Regression coverage for recovery execution runtime registry federations."""

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
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation as federation_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_audit as federation_audit_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_query as federation_query_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_query_audit as federation_query_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit


COMMAND = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history-observatory-archive-transfer-recovery-execution-runtime-registry-federation"
API_PATH = "/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query-snapshot/registry/history/observatory/archive/transfer/recovery/execution/runtime/registry/federation"


class HistoryObservatoryArchiveTransferRecoveryExecutionRuntimeRegistryFederationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_downloaded_data_comparison_query_snapshot_registry_history_observatory import DownloadedDataComparisonQuerySnapshotRegistryHistoryObservatoryTests as observatory_tests

        observatory_tests.setUpClass()
        fixture = observatory_tests()
        history_left, history_right = fixture._histories()
        cls.observatory = observatory_model.build_observatory((history_left, history_right), observatory_id="history-observatory-execution-runtime-registry-federation-fixture")

    @classmethod
    def _registries(cls):
        archive = archive_model.build_archive(cls.observatory, archive_id="history-observatory-execution-runtime-registry-federation-fixture")
        transfer = transfer_model.build_transfer(archive, transfer_id="history-observatory-execution-runtime-registry-federation-fixture", chunk_size=256)
        assembler = transfer_model.TransferAssembler(transfer)
        payload = transfer.payload_bytes()
        assembler.add_chunk(0, payload[0])
        assembler.add_chunk(transfer.chunk_count - 1, payload[transfer.chunk_count - 1])
        recovery = recovery_model.build_recovery(assembler, recovery_id="history-observatory-execution-runtime-registry-federation-plan", checkpointed=True)
        assembler.add_chunk(1, payload[1])
        execution = execution_model.build_execution_from_assembler(recovery, assembler, execution_id="execution-runtime-registry-federation-progress", checkpointed=True)
        primary = runtime_model.build_runtime(execution, runtime_id="execution-runtime-registry-federation-primary")
        secondary = runtime_model.build_runtime(execution, runtime_id="execution-runtime-registry-federation-secondary")
        return (
            registry_model.build_registry((primary,), registry_id="execution-runtime-registry-federation-primary"),
            registry_model.build_registry((secondary,), registry_id="execution-runtime-registry-federation-secondary"),
        )

    def test_federation_admission_audit_query_and_round_trips(self):
        primary, secondary = self._registries()
        federation = federation_model.build_federation((primary, secondary), federation_id="execution-runtime-registry-federation-fixture")
        audit = federation_audit_model.audit_federation(federation)
        query = federation_query_model.query_federation(federation, resources=federation_query_model.RESOURCES, limit=federation_query_model.MAX_LIMIT)
        query_audit = federation_query_audit_model.audit_query(query, federation)
        mixed = federation_model.build_federation((registry_model.build_registry((), registry_id="execution-runtime-registry-federation-empty"), primary), federation_id="execution-runtime-registry-federation-mixed")

        self.assertEqual((federation.state, federation.accepted, federation.member_count, federation.runtime_entry_count), ("ready", True, 2, 2))
        self.assertEqual((federation.accepted_member_count, federation.ready_member_count, federation.empty_member_count, federation.blocked_member_count), (2, 2, 0, 0))
        self.assertEqual((audit.check_count, audit.passed), (18, True))
        self.assertEqual((query.total_count, query.returned_count, query.truncated), (len(query.rows), len(query.rows), False))
        self.assertGreater(len(query.rows), 0)
        self.assertEqual((query_audit.check_count, query_audit.passed), (12, True))
        self.assertEqual((mixed.state, mixed.accepted, mixed.empty_member_count), ("mixed", True, 1))
        self.assertEqual(federation_model.federation_from_mapping(json.loads(federation_model.federation_json(federation))).content_address, federation.content_address)
        self.assertEqual(federation_audit_model.audit_from_mapping(json.loads(federation_audit_model.audit_json(audit))).content_address, audit.content_address)
        self.assertEqual(federation_query_model.query_from_mapping(json.loads(federation_query_model.query_json(query))).content_address, query.content_address)
        self.assertEqual(federation_query_audit_model.audit_from_mapping(json.loads(federation_query_audit_model.audit_json(query_audit))).content_address, query_audit.content_address)
        self.assertTrue(federation_model.federation_csv(federation).startswith("field,value\n"))
        self.assertIn("# Recovery Execution Runtime Registry Federation", federation_model.render_federation_markdown(federation))

    def test_exact_atomic_persistence_duplicate_and_tamper_rejection(self):
        primary, secondary = self._registries()
        federation = federation_model.build_federation((primary, secondary), federation_id="execution-runtime-registry-federation-persisted-fixture")
        with self.assertRaises(ValidationError):
            federation_model.build_federation((primary, primary), federation_id="execution-runtime-registry-federation-duplicate-fixture")
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "federation"
            federation_model.persist_federation(federation, destination)
            self.assertEqual(tuple(sorted(item.name for item in destination.iterdir())), tuple(sorted(federation_model.FILES)))
            loaded = federation_model.load_federation(destination)
            self.assertEqual(loaded.content_address, federation.content_address)
            self.assertEqual(federation_model.federation_json(loaded), federation_model.federation_json(federation))

            members_path = destination / "members.json"
            members_path.write_text(members_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaises(ValidationError):
                federation_model.load_federation(destination)

            federation_model.persist_federation(federation, destination, overwrite=True)
            (destination / "unexpected.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                federation_model.load_federation(destination)

    def test_cli_api_schemas_and_public_inventory(self):
        primary, secondary = self._registries()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            primary_path = root / "primary-registry"
            secondary_path = root / "secondary-registry"
            federation_path = root / "federation.json"
            federation_directory = root / "federation"
            query_path = root / "query.json"
            registry_model.persist_registry(primary, primary_path)
            registry_model.persist_registry(secondary, secondary_path)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([COMMAND, str(primary_path), str(secondary_path), "--federation-id", "execution-runtime-registry-federation-cli", "--destination", str(federation_directory), "--format", "json", "--output", str(federation_path)]), 0)
                self.assertEqual(main([COMMAND + "-verify", str(federation_directory), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-audit", str(federation_directory), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-query", str(federation_directory), "--resource", "states", "--limit", "8", "--format", "json", "--output", str(query_path)]), 0)
                self.assertEqual(main([COMMAND + "-query-audit", str(query_path), "--federation-input", str(federation_directory), "--format", "summary"]), 0)
                for suffix in ("member-schema", "members-schema", "entry-schema", "entries-schema", "manifest-schema", "summary-schema", "schema", "capabilities", "audit-check-schema", "audit-schema", "audit-capabilities", "query-row-schema", "query-schema", "query-capabilities", "query-audit-check-schema", "query-audit-schema", "query-audit-capabilities"):
                    self.assertEqual(main([COMMAND + "-" + suffix]), 0)
            self.assertEqual(federation_model.federation_from_mapping(json.loads(federation_path.read_text(encoding="utf-8"))).content_address, federation_model.load_federation(federation_directory).content_address)
            self.assertEqual(json.loads(query_path.read_text(encoding="utf-8"))["federation_id"], "execution-runtime-registry-federation-cli")

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                server.glio_deployment_guard._rate_windows.clear()
                params = urlencode([("registry_input", str(primary_path)), ("registry_input", str(secondary_path)), ("federation_id", "execution-runtime-registry-federation-api"), ("destination", str(root / "api-federation")), ("overwrite", "true"), ("format", "json")])
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}?{params}", timeout=30) as response:
                    api_federation = json.loads(response.read().decode("utf-8"))
                api_federation_directory = root / "api-federation"
                self.assertEqual((api_federation["federation_id"], api_federation["member_count"]), ("execution-runtime-registry-federation-api", 2))
                params = urlencode([("input", str(api_federation_directory)), ("format", "json")])
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["accepted"])
                params = urlencode([("input", str(api_federation_directory)), ("resource", "states"), ("limit", "8"), ("format", "json")])
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query?{params}", timeout=30) as response:
                    api_query = json.loads(response.read().decode("utf-8"))
                api_query_path = root / "api-query.json"
                api_query_path.write_text(json.dumps(api_query), encoding="utf-8")
                params = urlencode([("input", str(api_query_path)), ("federation_input", str(api_federation_directory)), ("format", "summary")])
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["accepted"])
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/member-schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

        inventory = build_default_public_surface_audit()
        self.assertEqual((inventory.surface_count, inventory.passed_surface_count, inventory.failed_surface_count, inventory.accepted), (1721, 1721, 0, True))
        for schema in (federation_model.member_schema(), federation_model.members_schema(), federation_model.entry_schema(), federation_model.entries_schema(), federation_model.manifest_schema(), federation_model.summary_schema(), federation_model.federation_schema(), federation_audit_model.check_schema(), federation_audit_model.audit_schema(), federation_query_model.row_schema(), federation_query_model.query_schema(), federation_query_audit_model.check_schema(), federation_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
