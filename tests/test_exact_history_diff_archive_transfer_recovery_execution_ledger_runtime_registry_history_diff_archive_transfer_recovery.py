"""Regression coverage for deterministic archive-transfer recovery plans."""

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

from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive as archive_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_transfer as transfer_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_transfer_recovery as recovery_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_transfer_recovery_audit as recovery_audit_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_transfer_recovery_query as recovery_query_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_transfer_recovery_query_audit as recovery_query_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit

import tests.test_exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive as archive_test_module


COMMAND = archive_test_module.COMMAND + "-transfer-recovery"
API_PATH = archive_test_module.API_PATH + "/transfer/recovery"


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        archive_test_module.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTests.setUpClass()

    def _archive(self):
        return archive_test_module.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTests()._archive()

    def _transfer(self):
        return transfer_model.build_transfer(self._archive(), transfer_id="recovery-transfer", chunk_size=1024)

    def _partial_assembler(self, value):
        receiver = transfer_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferAssembler(transfer_model.transfer_from_mapping(value.to_dict()))
        payload = value.payload_bytes()
        selected = (0,) if value.chunk_count == 1 else (0, value.chunk_count - 1)
        for index in selected:
            receiver.add_chunk(index, payload[index])
        return receiver, selected

    def test_complete_and_partial_states_are_conserved_and_audited(self):
        value = self._transfer()
        complete = recovery_model.build_recovery(value, recovery_id="complete-recovery")
        receiver, selected = self._partial_assembler(value)
        partial = recovery_model.build_recovery(receiver, recovery_id="partial-recovery", checkpointed=True)
        complete_audit = recovery_audit_model.audit_recovery(complete)
        partial_audit = recovery_audit_model.audit_recovery(partial)
        complete_query = recovery_query_model.query_recovery(complete)
        partial_query = recovery_query_model.query_recovery(partial)
        complete_query_audit = recovery_query_audit_model.audit_query(complete_query, complete)
        partial_query_audit = recovery_query_audit_model.audit_query(partial_query, partial)
        self.assertEqual((complete.state, complete.decision, complete.action_count, complete.next_index), ("complete", "assemble", 0, -1))
        self.assertEqual((partial.state, partial.decision, partial.received_indices, partial.missing_indices, partial.action_count, partial.next_index), ("partial", "resume", selected, tuple(index for index in range(value.chunk_count) if index not in selected), value.chunk_count - len(selected), selected[-1] + 1 if selected == (0,) else 1))
        self.assertEqual(partial.received_bytes + partial.remaining_bytes, partial.archive_size)
        self.assertEqual(tuple(action.index for action in partial.actions), partial.missing_indices)
        self.assertEqual((complete_audit.check_count, complete_audit.passed, partial_audit.check_count, partial_audit.passed), (18, True, 18, True))
        self.assertEqual((complete_query_audit.check_count, complete_query_audit.passed, partial_query_audit.check_count, partial_query_audit.passed), (12, True, 12, True))
        self.assertEqual(recovery_model.recovery_from_mapping(partial.to_dict()).content_address, partial.content_address)
        self.assertEqual(recovery_audit_model.audit_from_mapping(partial_audit.to_dict()).content_address, partial_audit.content_address)
        self.assertEqual(recovery_query_model.query_from_mapping(partial_query.to_dict()).content_address, partial_query.content_address)

    def test_recovery_negative_controls_reject_unconserved_state(self):
        value = self._transfer()
        receiver, _ = self._partial_assembler(value)
        partial = recovery_model.build_recovery(receiver, recovery_id="negative-recovery", checkpointed=True)
        invalid = partial.to_dict()
        invalid["missing_indices"] = tuple(partial.missing_indices[:-1])
        with self.assertRaises(ValidationError):
            recovery_model.recovery_from_mapping(invalid)
        invalid = partial.to_dict()
        invalid["received_bytes"] = partial.received_bytes + 1
        with self.assertRaises(ValidationError):
            recovery_model.recovery_from_mapping(invalid)
        invalid = partial.to_dict()
        invalid["actions"] = tuple(partial.actions[1:])
        with self.assertRaises(ValidationError):
            recovery_model.recovery_from_mapping(invalid)

    def test_cli_api_schemas_and_public_inventory(self):
        value = self._transfer()
        receiver, _ = self._partial_assembler(value)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            transfer_path = root / "transfer"
            partial_path = root / "partial"
            transfer_json_path = root / "transfer.json"
            recovery_json_path = root / "recovery.json"
            query_path = root / "query.json"
            transfer_model.write_transfer(value, transfer_path)
            transfer_json_path.write_text(transfer_model.transfer_json(value), encoding="utf-8")
            transfer_model.write_partial_transfer(receiver, partial_path)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([COMMAND, str(partial_path), "--recovery-id", "cli-recovery", "--format", "json", "--output", str(recovery_json_path)]), 0)
                self.assertEqual(main([COMMAND + "-verify", str(recovery_json_path), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-audit", str(recovery_json_path), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-query", str(recovery_json_path), "--resource", "missing", "--format", "json", "--output", str(query_path)]), 0)
                self.assertEqual(main([COMMAND + "-query-audit", str(query_path), "--recovery-input", str(recovery_json_path), "--format", "summary"]), 0)
                for suffix in ("action-schema", "schema", "capabilities", "audit-check-schema", "audit-schema", "audit-capabilities", "query-row-schema", "query-schema", "query-capabilities", "query-audit-check-schema", "query-audit-schema", "query-audit-capabilities"):
                    self.assertEqual(main([COMMAND + "-" + suffix]), 0)
            self.assertEqual(json.loads(recovery_json_path.read_text(encoding="utf-8"))["state"], "partial")
            self.assertEqual(json.loads(query_path.read_text(encoding="utf-8"))["returned_count"], value.chunk_count - 2)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                server.glio_deployment_guard._rate_windows.clear()
                params = urlencode({"input": str(partial_path), "recovery_id": "api-recovery", "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}?{params}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["recovery_id"], "api-recovery")
                params = urlencode({"input": str(recovery_json_path), "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/verify?{params}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["state"], "partial")
                params = urlencode({"input": str(recovery_json_path), "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["passed"])
                params = urlencode({"input": str(recovery_json_path), "resource": "missing", "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query?{params}", timeout=30) as response:
                    api_query = json.loads(response.read().decode("utf-8"))
                self.assertEqual(api_query["returned_count"], value.chunk_count - 2)
                api_query_path = root / "api-query.json"
                api_query_path.write_text(json.dumps(api_query), encoding="utf-8")
                params = urlencode({"input": str(api_query_path), "recovery_input": str(recovery_json_path), "format": "summary"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["passed"])
                for suffix in ("action-schema", "schema", "capabilities", "audit/check-schema", "audit/schema", "audit/capabilities", "query/row-schema", "query/schema", "query/capabilities", "query-audit/check-schema", "query-audit/schema", "query-audit/capabilities"):
                    with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/{suffix}", timeout=30) as response:
                        self.assertTrue(json.loads(response.read().decode("utf-8")))
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

        inventory = build_default_public_surface_audit()
        self.assertEqual((inventory.surface_count, inventory.passed_surface_count, inventory.failed_surface_count, inventory.accepted), (2152, 2152, 0, True))
        for schema in (recovery_model.action_schema(), recovery_model.recovery_schema(), recovery_audit_model.check_schema(), recovery_audit_model.audit_schema(), recovery_query_model.row_schema(), recovery_query_model.query_schema(), recovery_query_audit_model.check_schema(), recovery_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
