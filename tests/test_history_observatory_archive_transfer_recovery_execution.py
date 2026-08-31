"""Regression coverage for recovery execution over real downloaded-data fixtures."""

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

from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive as archive_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive_transfer as transfer_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive_transfer_recovery as recovery_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution as execution_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_audit as execution_audit_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_query as execution_query_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_query_audit as execution_query_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit


COMMAND = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history-observatory-archive-transfer-recovery-execution"
API_PATH = "/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query-snapshot/registry/history/observatory/archive/transfer/recovery/execution"


class HistoryObservatoryArchiveTransferRecoveryExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_downloaded_data_comparison_query_snapshot_registry_history_observatory import DownloadedDataComparisonQuerySnapshotRegistryHistoryObservatoryTests as observatory_tests

        observatory_tests.setUpClass()
        fixture = observatory_tests()
        history_left, history_right = fixture._histories()
        from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory as observatory_model

        cls.observatory = observatory_model.build_observatory((history_left, history_right), observatory_id="history-observatory-execution-fixture")

    @classmethod
    def _transfer(cls):
        archive = archive_model.build_archive(cls.observatory, archive_id="history-observatory-execution-fixture")
        return transfer_model.build_transfer(archive, transfer_id="history-observatory-execution-fixture", chunk_size=256)

    def _partial(self):
        transfer = self._transfer()
        assembler = transfer_model.TransferAssembler(transfer)
        payload = transfer.payload_bytes()
        assembler.add_chunk(0, payload[0])
        assembler.add_chunk(transfer.chunk_count - 1, payload[transfer.chunk_count - 1])
        return transfer, assembler, recovery_model.build_recovery(assembler, recovery_id="history-observatory-execution-plan", checkpointed=True), payload

    def test_execution_progress_complete_blocked_and_independent_audits(self):
        transfer, assembler, recovery, payload = self._partial()
        planned = execution_model.build_execution(recovery, execution_id="execution-planned", checkpointed=True)
        planned_audit = execution_audit_model.audit_execution(planned)
        self.assertEqual((planned.state, planned.decision, planned.pending_count, planned.safe_to_assemble), ("planned", "resume", transfer.chunk_count - 2, False))
        self.assertEqual((planned_audit.check_count, planned_audit.passed), (18, True))

        assembler.add_chunk(1, payload[1])
        progress = execution_model.build_execution_from_assembler(recovery, assembler, execution_id="execution-progress")
        progress_audit = execution_audit_model.audit_execution(progress)
        query = execution_query_model.query_execution(progress, resources=("summary", "outcomes", "applied", "pending", "state", "bounds"), offset=1, limit=5)
        query_audit = execution_query_audit_model.audit_query(query, progress)
        self.assertEqual((progress.state, progress.applied_indices, progress.pending_count), ("in_progress", (1,), transfer.chunk_count - 3))
        self.assertEqual(progress.current_received_bytes, sum(transfer.chunks[index].size for index in (0, 1, transfer.chunk_count - 1)))
        self.assertEqual((progress_audit.check_count, progress_audit.passed), (18, True))
        self.assertEqual((query.total_count, query.returned_count, query.truncated, query_audit.check_count, query_audit.passed), (43, 5, True, 12, True))

        assembler.add_chunks(payload)
        complete = execution_model.build_execution_from_assembler(recovery, assembler, execution_id="execution-complete", checkpointed=False)
        self.assertEqual((complete.state, complete.decision, complete.pending_count, complete.rejected_count, complete.safe_to_assemble), ("complete", "assemble", 0, 0, True))
        self.assertTrue(execution_audit_model.audit_execution(complete).passed)

        blocked = execution_model.build_execution(recovery, rejected_indices=(1,), execution_id="execution-blocked")
        self.assertEqual((blocked.state, blocked.decision, blocked.safe_to_continue, blocked.rejected_indices), ("blocked", "block", False, (1,)))
        self.assertTrue(execution_audit_model.audit_execution(blocked).passed)
        self.assertEqual(execution_model.execution_from_mapping(json.loads(execution_model.execution_json(progress))).content_address, progress.content_address)
        self.assertEqual(execution_audit_model.audit_from_mapping(json.loads(execution_audit_model.audit_json(progress_audit))).content_address, progress_audit.content_address)
        self.assertEqual(execution_query_model.query_from_mapping(json.loads(execution_query_model.query_json(query))).content_address, query.content_address)
        self.assertEqual(execution_query_audit_model.audit_from_mapping(json.loads(execution_query_audit_model.audit_json(query_audit))).content_address, query_audit.content_address)

    def test_tampered_execution_and_query_fail_closed(self):
        _, _, recovery, _ = self._partial()
        value = execution_model.build_execution(recovery, applied_indices=(1,), execution_id="execution-tamper")
        tampered = value.to_dict()
        tampered["decision"] = "assemble"
        with self.assertRaises(ValidationError):
            execution_model.execution_from_mapping(tampered)
        query = execution_query_model.query_execution(value, resources=("outcomes",), limit=2)
        tampered_query = query.to_dict()
        tampered_query["returned_count"] = 1
        with self.assertRaises(ValidationError):
            execution_query_model.query_from_mapping(tampered_query)

    def test_cli_api_schemas_and_public_inventory(self):
        _, _, recovery, _ = self._partial()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            recovery_path = root / "recovery.json"
            execution_path = root / "execution.json"
            query_path = root / "query.json"
            recovery_path.write_text(recovery_model.recovery_json(recovery), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([COMMAND, str(recovery_path), "--execution-id", "execution-cli", "--applied-index", "1", "--checkpointed", "--format", "json", "--output", str(execution_path)]), 0)
                self.assertEqual(main([COMMAND + "-verify", str(execution_path), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-audit", str(execution_path), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-query", str(execution_path), "--resource", "applied", "--resource", "pending", "--limit", "8", "--format", "json", "--output", str(query_path)]), 0)
                self.assertEqual(main([COMMAND + "-query-audit", str(query_path), "--execution-input", str(execution_path), "--format", "summary"]), 0)
                for suffix in ("outcome-schema", "schema", "capabilities", "audit-check-schema", "audit-schema", "audit-capabilities", "query-row-schema", "query-schema", "query-capabilities", "query-audit-check-schema", "query-audit-schema", "query-audit-capabilities"):
                    self.assertEqual(main([COMMAND + "-" + suffix]), 0)
            execution = execution_model.execution_from_mapping(json.loads(execution_path.read_text(encoding="utf-8")))
            query = execution_query_model.query_from_mapping(json.loads(query_path.read_text(encoding="utf-8")))
            self.assertEqual((execution.execution_id, execution.state, execution.applied_indices), ("execution-cli", "in_progress", (1,)))
            self.assertGreater(query.returned_count, 0)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                server.glio_deployment_guard._rate_windows.clear()
                params = urlencode([("input", str(recovery_path)), ("execution_id", "execution-api"), ("applied_index", "1"), ("format", "json")])
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}?{params}", timeout=30) as response:
                    api_execution = json.loads(response.read().decode("utf-8"))
                self.assertEqual((api_execution["execution_id"], api_execution["applied_indices"]), ("execution-api", [1]))
                execution_path.write_text(json.dumps(api_execution), encoding="utf-8")
                params = urlencode([("input", str(execution_path)), ("resource", "applied"), ("limit", "8"), ("format", "json")])
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query?{params}", timeout=30) as response:
                    api_query = json.loads(response.read().decode("utf-8"))
                query_path.write_text(json.dumps(api_query), encoding="utf-8")
                params = urlencode([("input", str(query_path)), ("execution_input", str(execution_path)), ("format", "summary")])
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query/audit?{params}", timeout=30) as response:
                    api_query_audit = json.loads(response.read().decode("utf-8"))
                self.assertTrue(api_query_audit["passed"])
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/outcome-schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

        inventory = build_default_public_surface_audit()
        self.assertEqual((inventory.surface_count, inventory.passed_surface_count, inventory.failed_surface_count, inventory.accepted), (1860, 1860, 0, True))
        for schema in (execution_model.outcome_schema(), execution_model.execution_schema(), execution_audit_model.check_schema(), execution_audit_model.audit_schema(), execution_query_model.row_schema(), execution_query_model.query_schema(), execution_query_audit_model.check_schema(), execution_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
