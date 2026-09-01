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

from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery as recovery_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery_audit as recovery_audit_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery_query as recovery_query_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery_query_audit as recovery_query_audit_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer as transfer_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit

import tests.test_history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer as transfer_test_module


COMMAND = transfer_test_module.COMMAND + "-recovery"
API_PATH = transfer_test_module.API_PATH + "/recovery"


class HistoryObservatoryArchiveTransferRecoveryExecutionRuntimeRegistryFederationArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveTransferRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        transfer_test_module.HistoryObservatoryArchiveTransferRecoveryExecutionRuntimeRegistryFederationArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveTransferTests.setUpClass()

    @staticmethod
    def _archive(root: Path):
        return transfer_test_module.HistoryObservatoryArchiveTransferRecoveryExecutionRuntimeRegistryFederationArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveTransferTests._archive(root)

    def test_recovery_conserves_partial_and_complete_transfer_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self._archive(root)
            transfer = transfer_model.build_transfer(archive, transfer_id="real-history-diff-recovery-transfer", chunk_size=1024)
            payload = transfer.payload_bytes()
            partial = transfer_model.HistoryDiffArchiveTransferAssembler(transfer)
            partial.add_chunk(transfer.chunk_count - 1, payload[transfer.chunk_count - 1])
            partial.add_chunk(0, payload[0])
            partial.add_chunk(0, payload[0])
            recovery = recovery_model.build_recovery(partial, recovery_id="real-history-diff-recovery", checkpointed=True)
            audit = recovery_audit_model.audit_recovery(recovery)
            query = recovery_query_model.query_recovery(recovery, resources=recovery_query_model.RESOURCES, limit=recovery_query_model.MAX_LIMIT)
            query_audit = recovery_query_audit_model.audit_query(query, recovery)
            complete = recovery_model.build_recovery(transfer, recovery_id="real-history-diff-complete-recovery", checkpointed=True)
            complete_audit = recovery_audit_model.audit_recovery(complete)

            self.assertEqual((transfer.archive_size > 0, transfer.chunk_count), (True, 5))
            self.assertEqual((recovery.state, recovery.decision, recovery.received_indices, recovery.missing_indices, recovery.action_count, recovery.next_index), ("partial", "resume", (0, 4), (1, 2, 3), 3, 1))
            self.assertEqual((recovery.received_bytes, recovery.remaining_bytes), (transfer.chunks[0].size + transfer.chunks[-1].size, transfer.archive_size - transfer.chunks[0].size - transfer.chunks[-1].size))
            self.assertEqual((audit.passed_count, audit.check_count, audit.accepted), (17, 17, True))
            self.assertEqual((query.row_count, query_audit.passed_count, query_audit.check_count, query_audit.accepted), (12, 12, 12, True))
            self.assertEqual((complete.state, complete.decision, complete.action_count, complete.next_index, complete_audit.accepted), ("complete", "assemble", 0, -1, True))
            self.assertEqual(recovery_model.recovery_from_mapping(recovery.to_dict()).to_dict(), recovery.to_dict())
            self.assertEqual(recovery_model.recovery_json(recovery), recovery_model.recovery_json(recovery_model.recovery_from_mapping(recovery.to_dict())))
            self.assertNotIn("payload", recovery_model.recovery_json(recovery))
            self.assertNotIn("source_path", recovery_model.recovery_json(recovery))
            tampered = recovery.to_dict()
            tampered["missing_indices"] = (1, 2)
            with self.assertRaises(ValidationError):
                recovery_model.recovery_from_mapping(tampered)

    def test_cli_http_schema_and_public_inventory_surfaces(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self._archive(root)
            transfer = transfer_model.build_transfer(archive, transfer_id="cli-real-history-diff-recovery-transfer", chunk_size=1024)
            payload = transfer.payload_bytes()
            partial = transfer_model.HistoryDiffArchiveTransferAssembler(transfer)
            partial.add_chunk(0, payload[0])
            partial.add_chunk(transfer.chunk_count - 1, payload[transfer.chunk_count - 1])
            partial_directory = root / "partial-transfer"
            transfer_model.write_partial_transfer(partial, partial_directory)
            recovery_path = root / "recovery.json"
            audit_path = root / "recovery-audit.json"
            query_path = root / "recovery-query.json"
            query_audit_path = root / "recovery-query-audit.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([COMMAND, str(partial_directory), "--recovery-id", "cli-real-history-diff-recovery", "--format", "json", "--output", str(recovery_path)]), 0)
                self.assertEqual(main([COMMAND + "-verify", str(recovery_path), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-audit", str(recovery_path), "--format", "json", "--output", str(audit_path)]), 0)
                self.assertEqual(main([COMMAND + "-query", str(recovery_path), "--resource", "missing", "--format", "json", "--output", str(query_path)]), 0)
                self.assertEqual(main([COMMAND + "-query-audit", str(query_path), "--recovery-input", str(recovery_path), "--format", "json", "--output", str(query_audit_path)]), 0)
                self.assertEqual(main([COMMAND + "-action-schema"]), 0)
                self.assertEqual(main([COMMAND + "-schema"]), 0)
                self.assertEqual(main([COMMAND + "-query-audit-schema"]), 0)

            self.assertEqual(json.loads(recovery_path.read_text(encoding="utf-8"))["missing_indices"], [1, 2, 3])
            self.assertTrue(json.loads(audit_path.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(json.loads(query_path.read_text(encoding="utf-8"))["row_count"], 3)
            self.assertTrue(json.loads(query_audit_path.read_text(encoding="utf-8"))["accepted"])

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                server.glio_deployment_guard._rate_windows.clear()
                base = {"input": str(partial_directory), "recovery_id": "api-real-history-diff-recovery", "format": "json"}
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}?{urlencode(base)}", timeout=30) as response:
                    api_recovery = json.loads(response.read().decode("utf-8"))
                self.assertEqual((api_recovery["state"], api_recovery["action_count"]), ("partial", 3))
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/verify?{urlencode({'input': str(recovery_path), 'format': 'json'})}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["recovery_id"], "cli-real-history-diff-recovery")
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/audit?{urlencode({'input': str(recovery_path), 'format': 'json'})}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["accepted"])
                query_params = {"input": str(recovery_path), "resource": "missing", "format": "json"}
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query?{urlencode(query_params)}", timeout=30) as response:
                    api_query = json.loads(response.read().decode("utf-8"))
                self.assertEqual(api_query["row_count"], 3)
                query_audit_params = {"input": str(query_path), "recovery_input": str(recovery_path), "format": "json"}
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query/audit?{urlencode(query_audit_params)}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["accepted"])
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["$schema"], "https://json-schema.org/draft/2020-12/schema")
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query-audit-schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

        inventory = build_default_public_surface_audit()
        self.assertEqual((inventory.surface_count, inventory.passed_surface_count, inventory.failed_surface_count, inventory.accepted), (2097, 2097, 0, True))
        for schema in (recovery_model.action_schema(), recovery_model.recovery_schema(), recovery_audit_model.check_schema(), recovery_audit_model.audit_schema(), recovery_query_model.row_schema(), recovery_query_model.query_schema(), recovery_query_audit_model.check_schema(), recovery_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
