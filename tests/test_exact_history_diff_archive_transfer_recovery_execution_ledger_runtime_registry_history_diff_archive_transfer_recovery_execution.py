"""Regression coverage for exact recovery execution receipts."""

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

from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_transfer_recovery as recovery_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_transfer_recovery_execution as execution_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_transfer_recovery_execution_audit as execution_audit_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_transfer_recovery_execution_query as execution_query_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_transfer_recovery_execution_query_audit as execution_query_audit_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_transfer as transfer_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit

import tests.test_exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_transfer_recovery as recovery_test_module


COMMAND = recovery_test_module.COMMAND + "-execution"
API_PATH = recovery_test_module.API_PATH + "/execution"


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        recovery_test_module.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryTests.setUpClass()

    def _archive(self):
        return recovery_test_module.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryTests()._archive()

    def _transfer(self):
        return transfer_model.build_transfer(self._archive(), transfer_id="execution-transfer", chunk_size=1024)

    def _recovery(self):
        transfer = self._transfer()
        receiver = transfer_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferAssembler(transfer_model.transfer_from_mapping(transfer.to_dict()))
        payload = transfer.payload_bytes()
        for index in (0, transfer.chunk_count - 1):
            receiver.add_chunk(index, payload[index])
        return recovery_model.build_recovery(receiver, recovery_id="execution-recovery", checkpointed=True)

    def test_execution_states_conserve_outcomes_bytes_and_addresses(self):
        recovery = self._recovery()
        first = recovery.missing_indices[0]
        progress = execution_model.build_execution(recovery, applied_indices=(first,), execution_id="progress-execution", checkpointed=True)
        complete = execution_model.build_execution(recovery, applied_indices=recovery.missing_indices, execution_id="complete-execution", checkpointed=True)
        blocked = execution_model.build_execution(recovery, rejected_indices=(first,), execution_id="blocked-execution", checkpointed=True)
        self.assertEqual((progress.state, progress.decision, progress.safe_to_continue, progress.safe_to_assemble), ("in_progress", "resume", True, False))
        self.assertEqual((complete.state, complete.decision, complete.safe_to_continue, complete.safe_to_assemble, complete.next_index), ("complete", "assemble", True, True, -1))
        self.assertEqual((blocked.state, blocked.decision, blocked.safe_to_continue, blocked.safe_to_assemble), ("blocked", "block", False, False))
        for value in (progress, complete, blocked):
            self.assertEqual(value.planned_bytes, value.applied_bytes + value.pending_bytes + value.rejected_bytes)
            self.assertEqual(value.current_received_bytes + value.current_remaining_bytes, value.archive_size)
            self.assertEqual(set(value.current_received_indices) | set(value.current_missing_indices), set(range(value.chunk_count)))
            self.assertEqual(tuple(outcome.index for outcome in value.outcomes), value.planned_indices)
            self.assertEqual(execution_model.execution_from_mapping(value.to_dict()).content_address, value.content_address)
            audit = execution_audit_model.audit_execution(value)
            self.assertEqual((audit.check_count, audit.passed), (18, True))
        self.assertEqual((progress.applied_indices, progress.pending_indices, progress.rejected_indices), ((first,), tuple(index for index in recovery.missing_indices if index != first), ()))
        query = execution_query_model.query_execution(progress)
        query_audit = execution_query_audit_model.audit_query(query, progress)
        self.assertEqual((query.total_count, query.returned_count, query_audit.check_count, query_audit.passed), (query.total_count, query.returned_count, 12, True))
        pending_query = execution_query_model.query_execution(progress, resources=("outcomes",), status="pending")
        self.assertEqual(pending_query.returned_count, len(progress.pending_indices))
        self.assertEqual(execution_query_model.query_from_mapping(query.to_dict()).content_address, query.content_address)
        self.assertEqual(execution_query_audit_model.audit_from_mapping(query_audit.to_dict()).content_address, query_audit.content_address)
        self.assertIn("execution_id", execution_model.execution_json(progress))
        self.assertIn("status", execution_model.execution_csv(progress))
        self.assertIn("Safe to assemble", execution_model.render_execution_markdown(progress))
        self.assertIn("Rows", execution_query_model.render_query_markdown(query))
        self.assertIn("Checks", execution_query_audit_model.render_audit_markdown(query_audit))

    def test_execution_negative_controls_reject_unconserved_state(self):
        recovery = self._recovery()
        first = recovery.missing_indices[0]
        with self.assertRaises(ValidationError):
            execution_model.build_execution(recovery, applied_indices=(recovery.received_indices[0],))
        with self.assertRaises(ValidationError):
            execution_model.build_execution(recovery, applied_indices=(first,), rejected_indices=(first,))
        value = execution_model.build_execution(recovery, applied_indices=(first,), checkpointed=True)
        invalid = value.to_dict()
        invalid["applied_bytes"] += 1
        with self.assertRaises(ValidationError):
            execution_model.execution_from_mapping(invalid)
        invalid = value.to_dict()
        invalid["outcomes"] = tuple(dict(item, status="rejected") if item["index"] == first else item for item in invalid["outcomes"])
        with self.assertRaises(ValidationError):
            execution_model.execution_from_mapping(invalid)
        with self.assertRaises(ValidationError):
            execution_query_model.query_execution(value, resources=("summary",), status="unsupported")

    def test_cli_api_schemas_and_public_inventory(self):
        recovery = self._recovery()
        first = recovery.missing_indices[0]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            recovery_path = root / "recovery.json"
            execution_path = root / "execution.json"
            query_path = root / "query.json"
            recovery_path.write_text(recovery_model.recovery_json(recovery), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([COMMAND, str(recovery_path), "--execution-id", "cli-execution", "--applied-index", str(first), "--checkpointed", "--format", "json", "--output", str(execution_path)]), 0)
                self.assertEqual(main([COMMAND + "-verify", str(execution_path), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-audit", str(execution_path), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-query", str(execution_path), "--resource", "pending", "--status", "pending", "--format", "json", "--output", str(query_path)]), 0)
                self.assertEqual(main([COMMAND + "-query-audit", str(query_path), "--execution-input", str(execution_path), "--format", "summary"]), 0)
                for suffix in ("outcome-schema", "schema", "capabilities", "audit-check-schema", "audit-schema", "audit-capabilities", "query-row-schema", "query-schema", "query-capabilities", "query-audit-check-schema", "query-audit-schema", "query-audit-capabilities"):
                    self.assertEqual(main([COMMAND + "-" + suffix]), 0)
            self.assertEqual(json.loads(execution_path.read_text(encoding="utf-8"))["state"], "in_progress")
            self.assertEqual(json.loads(query_path.read_text(encoding="utf-8"))["returned_count"], len(recovery.missing_indices) - 1)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                server.glio_deployment_guard._rate_windows.clear()
                params = urlencode({"input": str(recovery_path), "execution_id": "api-execution", "applied_index": str(first), "checkpointed": "true", "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}?{params}", timeout=30) as response:
                    api_execution = json.loads(response.read().decode("utf-8"))
                self.assertEqual(api_execution["state"], "in_progress")
                params = urlencode({"input": str(execution_path), "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/verify?{params}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["execution_id"], "cli-execution")
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["passed"])
                params = urlencode({"input": str(execution_path), "resource": "pending", "status": "pending", "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query?{params}", timeout=30) as response:
                    api_query = json.loads(response.read().decode("utf-8"))
                self.assertEqual(api_query["returned_count"], len(recovery.missing_indices) - 1)
                api_query_path = root / "api-query.json"
                api_query_path.write_text(json.dumps(api_query), encoding="utf-8")
                params = urlencode({"input": str(api_query_path), "execution_input": str(execution_path), "format": "summary"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["passed"])
                for suffix in ("outcome-schema", "schema", "capabilities", "audit/check-schema", "audit/schema", "audit/capabilities", "query/row-schema", "query/schema", "query/capabilities", "query-audit/check-schema", "query-audit/schema", "query-audit/capabilities"):
                    with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/{suffix}", timeout=30) as response:
                        self.assertTrue(json.loads(response.read().decode("utf-8")))
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

        inventory = build_default_public_surface_audit()
        self.assertEqual(len(inventory.checks), inventory.surface_count)
        self.assertEqual(inventory.passed_surface_count, inventory.surface_count)
        self.assertEqual(inventory.failed_surface_count, 0)
        self.assertTrue(inventory.accepted)
        for schema in (execution_model.outcome_schema(), execution_model.execution_schema(), execution_audit_model.check_schema(), execution_audit_model.audit_schema(), execution_query_model.row_schema(), execution_query_model.query_schema(), execution_query_audit_model.check_schema(), execution_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
