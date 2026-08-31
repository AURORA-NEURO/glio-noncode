"""Regression coverage for federation archive transfer recovery plans."""

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

from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery as recovery_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_audit as recovery_audit_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_query as recovery_query_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_query_audit as recovery_query_audit_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer as transfer_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.public_surface_audit import build_default_public_surface_audit


COMMAND = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history-observatory-archive-transfer-recovery-execution-runtime-registry-federation-archive-transfer-recovery"
API_PATH = "/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query-snapshot/registry/history/observatory/archive/transfer/recovery/execution/runtime/registry/federation/archive/transfer/recovery"


class HistoryObservatoryArchiveTransferRecoveryExecutionRuntimeRegistryFederationArchiveTransferRecoveryTests(unittest.TestCase):
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
        archive = archive_model.build_archive_from_directory(federation_directory, archive_id="downloaded-real-federation-archive-transfer-recovery")
        archive_path = root / "federation.zip"
        archive_model.write_archive(archive, archive_path)
        return archive_model.load_archive(archive_path), archive_path

    def test_partial_recovery_audit_query_and_assemble_decision(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive, _ = self._archive(root)
            transfer = transfer_model.build_transfer(archive, transfer_id="downloaded-real-transfer-recovery", chunk_size=1024)
            payload = transfer.payload_bytes()
            assembler = transfer_model.TransferAssembler(transfer)
            assembler.add_chunk(0, payload[0])
            assembler.add_chunk(transfer.chunk_count - 1, payload[transfer.chunk_count - 1])
            partial_directory = root / "partial"
            transfer_model.write_partial_transfer(assembler, partial_directory)

            recovery = recovery_model.build_recovery_from_directory(partial_directory, recovery_id="downloaded-real-recovery")
            recovery_audit = recovery_audit_model.audit_recovery(recovery)
            query = recovery_query_model.query_recovery(recovery, resources=recovery_query_model.RESOURCES, limit=recovery_query_model.MAX_LIMIT)
            query_audit = recovery_query_audit_model.audit_query(query, recovery)
            complete = recovery_model.build_recovery(transfer, recovery_id="downloaded-real-complete")

            received_bytes = transfer.chunks[0].size + transfer.chunks[-1].size
            self.assertEqual((transfer.archive_size, transfer.chunk_size, transfer.chunk_count), (len(transfer.payload_bytes()[0]) + sum(item.size for item in transfer.chunks[1:]), 1024, 6))
            self.assertEqual((recovery.received_indices, recovery.missing_indices), ((0, 5), (1, 2, 3, 4)))
            self.assertEqual((recovery.state, recovery.decision, recovery.action_count, recovery.next_index), ("partial", "resume", 4, 1))
            self.assertEqual((recovery.received_bytes, recovery.remaining_bytes, recovery.safe_to_resume, recovery.checkpointed), (received_bytes, transfer.archive_size - received_bytes, True, True))
            self.assertTrue(all(action.index in recovery.missing_indices for action in recovery.actions))
            self.assertEqual((recovery_audit.check_count, recovery_audit.passed, query.row_count, query_audit.check_count, query_audit.passed), (15, True, 13, 12, True))
            self.assertEqual((complete.state, complete.decision, complete.action_count, complete.next_index), ("complete", "assemble", 0, -1))
            self.assertTrue(recovery_model.recovery_from_mapping(json.loads(recovery_model.recovery_json(recovery))).to_dict() == recovery.to_dict())

    def test_cli_and_http_recovery_surfaces(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive, archive_path = self._archive(root)
            transfer = transfer_model.build_transfer(archive, transfer_id="cli-recovery-transfer", chunk_size=1024)
            transfer_directory = root / "transfer"
            partial_directory = root / "partial"
            transfer_model.write_transfer(transfer, transfer_directory)
            assembler = transfer_model.TransferAssembler(transfer)
            payload = transfer.payload_bytes()
            assembler.add_chunk(0, payload[0])
            assembler.add_chunk(5, payload[5])
            transfer_model.write_partial_transfer(assembler, partial_directory)
            recovery_json = root / "recovery.json"
            query_json = root / "query.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([COMMAND, str(partial_directory), "--recovery-id", "cli-recovery", "--format", "json", "--output", str(recovery_json)]), 0)
                self.assertEqual(main([COMMAND + "-verify", str(recovery_json), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-audit", str(recovery_json), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-query", str(recovery_json), "--resource", "missing", "--limit", "8", "--format", "json", "--output", str(query_json)]), 0)
                self.assertEqual(main([COMMAND + "-query-audit", str(query_json), "--recovery-input", str(recovery_json), "--format", "summary"]), 0)
                for suffix in ("action-schema", "schema", "capabilities", "audit-check-schema", "audit-schema", "audit-capabilities", "query-row-schema", "query-schema", "query-capabilities", "query-audit-check-schema", "query-audit-schema", "query-audit-capabilities"):
                    self.assertEqual(main([COMMAND + "-" + suffix]), 0)
            self.assertEqual(json.loads(recovery_json.read_text(encoding="utf-8"))["missing_indices"], [1, 2, 3, 4])
            self.assertEqual(json.loads(query_json.read_text(encoding="utf-8"))["row_count"], 4)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                server.glio_deployment_guard._rate_windows.clear()
                base = {"input": str(partial_directory), "recovery_id": "api-recovery", "format": "json"}
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}?{urlencode(base)}", timeout=30) as response:
                    api_recovery = json.loads(response.read().decode("utf-8"))
                self.assertEqual((api_recovery["state"], api_recovery["decision"], api_recovery["missing_indices"]), ("partial", "resume", [1, 2, 3, 4]))
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/audit?{urlencode(base)}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["passed"])
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query?{urlencode(base | {'resource': 'missing', 'limit': '8'})}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["row_count"], 4)
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

        inventory = build_default_public_surface_audit()
        self.assertEqual((inventory.surface_count, inventory.passed_surface_count, inventory.failed_surface_count, inventory.accepted), (1708, 1708, 0, True))
        for schema in (recovery_model.action_schema(), recovery_model.recovery_schema(), recovery_audit_model.check_schema(), recovery_audit_model.audit_schema(), recovery_query_model.row_schema(), recovery_query_model.query_schema(), recovery_query_audit_model.check_schema(), recovery_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
