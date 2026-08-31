"""Regression coverage for federation archive transfer execution receipts."""

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

from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer as transfer_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery as recovery_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution as execution_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_audit as execution_audit_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_query as execution_query_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_query_audit as execution_query_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.public_surface_audit import build_default_public_surface_audit


COMMAND = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history-observatory-archive-transfer-recovery-execution-runtime-registry-federation-archive-transfer-recovery-execution"
API_PATH = "/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query-snapshot/registry/history/observatory/archive/transfer/recovery/execution/runtime/registry/federation/archive/transfer/recovery/execution"


class HistoryObservatoryArchiveTransferRecoveryExecutionRuntimeRegistryFederationArchiveTransferRecoveryExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer import HistoryObservatoryArchiveTransferRecoveryExecutionRuntimeRegistryFederationArchiveTransferTests as transfer_tests

        transfer_tests.setUpClass()
        cls.federation = transfer_tests.federation

    @classmethod
    def _archive(cls, root: Path):
        from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation as federation_model
        from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive as archive_model

        federation_directory = root / "federation"
        federation_model.persist_federation(cls.federation, federation_directory)
        archive = archive_model.build_archive_from_directory(federation_directory, archive_id="downloaded-real-federation-archive-transfer-recovery-execution")
        archive_path = root / "federation.zip"
        archive_model.write_archive(archive, archive_path)
        return archive_model.load_archive(archive_path), archive_path

    def test_receipt_states_conservation_audit_and_query(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive, _ = self._archive(root)
            transfer = transfer_model.build_transfer(archive, transfer_id="downloaded-real-transfer-recovery-execution", chunk_size=1024)
            assembler = transfer_model.TransferAssembler(transfer)
            payload = transfer.payload_bytes()
            assembler.add_chunk(0, payload[0])
            assembler.add_chunk(transfer.chunk_count - 1, payload[transfer.chunk_count - 1])
            partial_directory = root / "partial"
            transfer_model.write_partial_transfer(assembler, partial_directory)
            recovery = recovery_model.build_recovery_from_directory(partial_directory, recovery_id="downloaded-real-recovery-execution")

            planned = execution_model.build_execution(recovery, checkpointed=True)
            in_progress = execution_model.build_execution(recovery, applied_indices=(1, 2), checkpointed=True)
            complete = execution_model.build_execution(recovery, applied_indices=(1, 2, 3, 4), checkpointed=True)
            blocked = execution_model.build_execution(recovery, applied_indices=(1,), rejected_indices=(2,), checkpointed=True)
            execution_audit = execution_audit_model.audit_execution(in_progress)
            query = execution_query_model.query_execution(in_progress, resources=execution_query_model.RESOURCES, limit=execution_query_model.MAX_LIMIT)
            query_audit = execution_query_audit_model.audit_query(query, in_progress)

            self.assertEqual((planned.state, planned.decision, planned.pending_indices), ("planned", "resume", (1, 2, 3, 4)))
            self.assertEqual((in_progress.state, in_progress.decision, in_progress.applied_indices, in_progress.pending_indices), ("in_progress", "resume", (1, 2), (3, 4)))
            self.assertEqual((complete.state, complete.decision, complete.applied_count, complete.safe_to_assemble), ("complete", "assemble", 4, True))
            self.assertEqual((blocked.state, blocked.decision, blocked.rejected_indices, blocked.safe_to_continue), ("blocked", "block", (2,), False))
            self.assertEqual((in_progress.current_received_bytes + in_progress.current_remaining_bytes, in_progress.archive_size), (in_progress.archive_size, in_progress.archive_size))
            self.assertEqual((in_progress.planned_bytes, in_progress.applied_bytes + in_progress.pending_bytes + in_progress.rejected_bytes), (in_progress.archive_size - recovery.received_bytes, in_progress.archive_size - recovery.received_bytes))
            self.assertEqual((execution_audit.check_count, execution_audit.passed, query.returned_count, query_audit.check_count, query_audit.passed), (18, True, query.total_count, 12, True))
            self.assertEqual(execution_model.execution_from_mapping(json.loads(execution_model.execution_json(in_progress))).to_dict(), in_progress.to_dict())

    def test_cli_and_http_execution_surfaces(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive, _ = self._archive(root)
            transfer = transfer_model.build_transfer(archive, transfer_id="cli-recovery-execution-transfer", chunk_size=1024)
            assembler = transfer_model.TransferAssembler(transfer)
            payload = transfer.payload_bytes()
            assembler.add_chunk(0, payload[0])
            assembler.add_chunk(5, payload[5])
            partial_directory = root / "partial"
            transfer_model.write_partial_transfer(assembler, partial_directory)
            recovery = recovery_model.build_recovery_from_directory(partial_directory, recovery_id="cli-recovery-execution")
            recovery_json = root / "recovery.json"
            execution_json = root / "execution.json"
            query_json = root / "query.json"
            recovery_json.write_text(recovery_model.recovery_json(recovery), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([COMMAND, str(recovery_json), "--applied-index", "1", "--applied-index", "2", "--checkpointed", "--format", "json", "--output", str(execution_json)]), 0)
                self.assertEqual(main([COMMAND + "-verify", str(execution_json), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-audit", str(execution_json), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-query", str(execution_json), "--resource", "applied", "--format", "json", "--output", str(query_json)]), 0)
                self.assertEqual(main([COMMAND + "-query-audit", str(query_json), "--execution-input", str(execution_json), "--format", "summary"]), 0)
                for suffix in ("outcome-schema", "schema", "capabilities", "audit-check-schema", "audit-schema", "audit-capabilities", "query-row-schema", "query-schema", "query-capabilities", "query-audit-check-schema", "query-audit-schema", "query-audit-capabilities"):
                    self.assertEqual(main([COMMAND + "-" + suffix]), 0)
            emitted_execution = json.loads(execution_json.read_text(encoding="utf-8"))
            self.assertEqual((emitted_execution["state"], emitted_execution["applied_indices"], emitted_execution["pending_indices"]), ("in_progress", [1, 2], [3, 4]))
            self.assertEqual(json.loads(query_json.read_text(encoding="utf-8"))["returned_count"], 2)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                server.glio_deployment_guard._rate_windows.clear()
                base = {"input": str(execution_json), "format": "json"}
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}?{urlencode(base)}", timeout=30) as response:
                    api_execution = json.loads(response.read().decode("utf-8"))
                self.assertEqual((api_execution["state"], api_execution["applied_indices"]), ("in_progress", [1, 2]))
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/audit?{urlencode(base)}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["passed"])
                query_params = base | {"resource": "applied"}
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query?{urlencode(query_params)}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["returned_count"], 2)
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

        inventory = build_default_public_surface_audit()
        self.assertEqual((inventory.surface_count, inventory.passed_surface_count, inventory.failed_surface_count, inventory.accepted), (1914, 1914, 0, True))
        for schema in (execution_model.outcome_schema(), execution_model.execution_schema(), execution_audit_model.check_schema(), execution_audit_model.audit_schema(), execution_query_model.row_schema(), execution_query_model.query_schema(), execution_query_audit_model.check_schema(), execution_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
