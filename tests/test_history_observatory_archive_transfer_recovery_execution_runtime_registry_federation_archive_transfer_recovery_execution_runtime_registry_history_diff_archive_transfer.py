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

from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive as archive_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_audit as archive_audit_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_query as archive_query_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_query_audit as archive_query_audit_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer as transfer_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_audit as transfer_audit_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_query as transfer_query_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_query_audit as transfer_query_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit

import tests.test_history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive as archive_test_module


COMMAND = archive_test_module.COMMAND + "-transfer"
API_PATH = archive_test_module.API_PATH + "/transfer"


class HistoryObservatoryArchiveTransferRecoveryExecutionRuntimeRegistryFederationArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        archive_test_module.HistoryObservatoryArchiveTransferRecoveryExecutionRuntimeRegistryFederationArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveTests.setUpClass()

    @staticmethod
    def _archive(root: Path):
        diff = archive_test_module.HistoryObservatoryArchiveTransferRecoveryExecutionRuntimeRegistryFederationArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveTests._diff(root)
        return archive_model.build_archive(diff, archive_id="downloaded-real-history-diff-archive-transfer")

    def test_transfer_reassembles_out_of_order_and_preserves_partial_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self._archive(root)
            transfer = transfer_model.build_transfer(archive, transfer_id="real-history-diff-transfer", chunk_size=1024)
            audit = transfer_audit_model.audit_transfer(transfer)
            payload = transfer.payload_bytes()
            assembler = transfer_model.HistoryDiffArchiveTransferAssembler(transfer)
            for index in reversed(range(transfer.chunk_count)):
                assembler.add_chunk(index, payload[index])
            query = transfer_query_model.query_assembler(assembler, resources=transfer_query_model.RESOURCES, limit=transfer_query_model.MAX_LIMIT)
            query_audit = transfer_query_audit_model.audit_query(query, transfer)
            partial = transfer_model.HistoryDiffArchiveTransferAssembler(transfer)
            partial.add_chunk(transfer.chunk_count - 1, payload[transfer.chunk_count - 1])
            partial.add_chunk(0, payload[0])
            partial.add_chunk(0, payload[0])
            progress = partial.progress()
            complete_directory = root / "complete-transfer"
            partial_directory = root / "partial-transfer"
            transfer_model.write_transfer(transfer, complete_directory)
            transfer_model.write_partial_transfer(partial, partial_directory)
            reloaded = transfer_model.verify_transfer_directory(complete_directory)
            reloaded_partial = transfer_model.load_partial_transfer(partial_directory)

            self.assertEqual(transfer.chunk_count, 5)
            self.assertEqual(tuple(item.index for item in transfer.chunks), tuple(range(transfer.chunk_count)))
            self.assertEqual(tuple(item.offset for item in transfer.chunks), (0, 1024, 2048, 3072, 4096))
            self.assertEqual((audit.passed_count, audit.check_count, audit.accepted), (18, 18, True))
            self.assertEqual((query.total_count, query.returned_count, query_audit.check_count, query_audit.accepted), (14, 14, 12, True))
            self.assertEqual((progress.received_indices, progress.missing_indices, progress.complete), ((0, 4), (1, 2, 3), False))
            self.assertEqual(reloaded_partial.progress().to_dict(), progress.to_dict())
            self.assertEqual(transfer_model.assemble_transfer_directory(complete_directory), archive_model.archive_bytes(archive))
            self.assertEqual(reloaded.content_address, transfer.content_address)
            self.assertEqual(transfer_model.transfer_from_mapping(transfer.to_dict()).to_dict(), transfer.to_dict())
            self.assertEqual(transfer_model.transfer_json(transfer), transfer_model.transfer_json(transfer_model.build_transfer(archive, transfer_id=transfer.transfer_id, chunk_size=transfer.chunk_size)))
            self.assertNotIn("payload", transfer_model.transfer_json(transfer))
            self.assertNotIn("payload", transfer_model.manifest_json(transfer))

            tampered_chunk = complete_directory / transfer_model.chunk_name(0)
            original = tampered_chunk.read_bytes()
            tampered_chunk.write_bytes(bytes((original[0] ^ 1,)) + original[1:])
            with self.assertRaises(ValidationError):
                transfer_model.load_transfer(complete_directory)

    def test_cli_http_schema_and_public_inventory_surfaces(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self._archive(root)
            diff = archive.diff
            diff_directory = root / "diff"
            archive_path = root / "history-diff.zip"
            transfer_directory = root / "cli-transfer"
            partial_directory = root / "cli-partial"
            query_path = root / "transfer-query.json"
            audit_path = root / "transfer-query-audit.json"
            reassembled_path = root / "reassembled.zip"
            from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff as diff_model

            diff_model.persist_diff(diff, diff_directory)
            archive_model.write_archive(archive, archive_path)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([COMMAND, str(archive_path), "--transfer-id", "cli-real-history-diff-transfer", "--destination", str(transfer_directory), "--format", "json"]), 0)
                transfer = transfer_model.load_transfer(transfer_directory)
                self.assertEqual(main([COMMAND + "-partial", str(archive_path), "--received", "0", "--received", str(transfer.chunk_count - 1), "--destination", str(partial_directory)]), 0)
                self.assertEqual(main([COMMAND + "-verify", str(transfer_directory)]), 0)
                self.assertEqual(main([COMMAND + "-manifest", str(partial_directory)]), 0)
                self.assertEqual(main([COMMAND + "-progress", str(partial_directory)]), 0)
                self.assertEqual(main([COMMAND + "-audit", str(transfer_directory)]), 0)
                self.assertEqual(main([COMMAND + "-assemble", str(transfer_directory), "--archive-output", str(reassembled_path)]), 0)
                self.assertEqual(main([COMMAND + "-query", str(partial_directory), "--resource", "missing", "--format", "json", "--output", str(query_path)]), 0)
                self.assertEqual(main([COMMAND + "-query-audit", str(query_path), "--transfer-input", str(partial_directory), "--format", "json", "--output", str(audit_path)]), 0)
                self.assertEqual(main([COMMAND + "-schema"]), 0)
                self.assertEqual(main([COMMAND + "-chunk-schema"]), 0)
                self.assertEqual(main([COMMAND + "-query-audit-schema"]), 0)

            self.assertEqual(json.loads(query_path.read_text(encoding="utf-8"))["returned_count"], 3)
            self.assertTrue(json.loads(audit_path.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(archive_model.load_archive_bytes(reassembled_path.read_bytes()).content_address, archive.content_address)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                server.glio_deployment_guard._rate_windows.clear()
                base = {"input": str(archive_path), "transfer_id": "api-real-history-diff-transfer", "chunk_size": "1024", "format": "json", "destination": str(root / "api-transfer")}
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}?{urlencode(base)}", timeout=30) as response:
                    api_transfer = json.loads(response.read().decode("utf-8"))
                self.assertEqual((api_transfer["chunk_count"], api_transfer["archive_size"] > 0), (5, True))
                api_directory = root / "api-transfer"
                for suffix in ("/verify", "/manifest", "/progress", "/audit", "/query", "/query/audit"):
                    params = {"input": str(api_directory), "format": "json"}
                    with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}{suffix}?{urlencode(params)}", timeout=30) as response:
                        body = json.loads(response.read().decode("utf-8"))
                    expected_field = "accepted" if suffix in {"/audit", "/query/audit"} else "manifest_address" if suffix == "/manifest" else "content_address"
                    self.assertIn(expected_field, body)
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/assemble?{urlencode({'input': str(api_directory), 'format': 'json'})}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["content_address"], archive.content_address)
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["$schema"], "https://json-schema.org/draft/2020-12/schema")
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query?{urlencode({'input': str(partial_directory), 'resource': 'missing', 'received': 'false', 'format': 'json'})}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["returned_count"], 3)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

        inventory = build_default_public_surface_audit()
        self.assertEqual((inventory.surface_count, inventory.passed_surface_count, inventory.failed_surface_count, inventory.accepted), (1939, 1939, 0, True))
        for schema in (transfer_model.chunk_schema(), transfer_model.manifest_schema(), transfer_model.progress_schema(), transfer_model.transfer_schema(), transfer_audit_model.check_schema(), transfer_audit_model.audit_schema(), transfer_query_model.row_schema(), transfer_query_model.query_schema(), transfer_query_audit_model.check_schema(), transfer_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
