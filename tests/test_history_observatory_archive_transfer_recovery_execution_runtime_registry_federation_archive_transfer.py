"""Regression coverage for resumable federation-archive transfers."""

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

from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive as archive_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer as transfer_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_audit as transfer_audit_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_query as transfer_query_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_query_audit as transfer_query_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit


COMMAND = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history-observatory-archive-transfer-recovery-execution-runtime-registry-federation-archive-transfer"
API_PATH = "/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query-snapshot/registry/history/observatory/archive/transfer/recovery/execution/runtime/registry/federation/archive/transfer"


class HistoryObservatoryArchiveTransferRecoveryExecutionRuntimeRegistryFederationArchiveTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive import HistoryObservatoryArchiveTransferRecoveryExecutionRuntimeRegistryFederationArchiveTests as archive_tests

        archive_tests.setUpClass()
        cls.federation = archive_tests._federation()

    @classmethod
    def _archive(cls, root: Path):
        federation_directory = root / "federation"
        from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation as federation_model

        federation_model.persist_federation(cls.federation, federation_directory)
        archive = archive_model.build_archive_from_directory(federation_directory, archive_id="downloaded-real-federation-archive-transfer")
        archive_path = root / "federation.zip"
        archive_model.write_archive(archive, archive_path)
        return archive_model.load_archive(archive_path), archive_path

    def test_real_downloaded_archive_chunks_resume_audit_query_and_reassemble(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive, archive_path = self._archive(root)
            value = transfer_model.build_transfer(archive, transfer_id="downloaded-real-transfer", chunk_size=1024)
            payload = value.payload_bytes()
            assembler = transfer_model.TransferAssembler(value)
            assembler.add_chunk(value.chunk_count - 1, payload[value.chunk_count - 1])
            assembler.add_chunk(0, payload[0])
            self.assertEqual((value.archive_size, value.chunk_size, value.chunk_count), (len(archive_model.archive_bytes(archive)), 1024, 6))
            self.assertEqual(assembler.received_indices(), (0, 5))
            self.assertEqual(assembler.progress().missing_indices, (1, 2, 3, 4))
            partial_directory = root / "partial"
            transfer_model.write_partial_transfer(assembler, partial_directory)
            reloaded_partial = transfer_model.load_partial_transfer(partial_directory)
            self.assertEqual(reloaded_partial.received_indices(), (0, 5))
            query = transfer_query_model.query_assembler(reloaded_partial, resources=transfer_query_model.RESOURCES, limit=transfer_query_model.MAX_LIMIT)
            query_audit = transfer_query_audit_model.audit_query(query, value)
            audit = transfer_audit_model.audit_transfer(value)
            self.assertEqual((audit.check_count, audit.passed_count, audit.failed_count, audit.passed), (18, 18, 0, True))
            self.assertEqual((query.total_count, query.returned_count, query.truncated), (16, 16, False))
            self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.failed_count, query_audit.passed), (12, 12, 0, True))
            for index, raw in payload.items():
                reloaded_partial.add_chunk(index, raw)
            self.assertEqual(reloaded_partial.finalize(), archive_model.archive_bytes(archive))
            complete_directory = root / "complete"
            transfer_model.write_transfer(value, complete_directory)
            self.assertEqual(transfer_model.load_transfer(complete_directory).content_address, value.content_address)
            self.assertEqual(transfer_model.assemble_transfer_directory(complete_directory), archive_model.archive_bytes(archive))
            self.assertEqual(transfer_model.verify_partial_transfer(partial_directory).received_indices, (0, 5))
            self.assertEqual(archive_path.read_bytes(), archive_model.archive_bytes(archive))

    def test_exact_transfer_directory_vocabulary_and_fail_closed_recovery(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive, _ = self._archive(root)
            value = transfer_model.build_transfer(archive, transfer_id="transfer-safety", chunk_size=1024)
            destination = root / "complete"
            transfer_model.write_transfer(value, destination)
            self.assertEqual(tuple(sorted(item.relative_to(destination).as_posix() for item in destination.rglob("*"))), ("chunks", "chunks/chunk-00000000.bin", "chunks/chunk-00000001.bin", "chunks/chunk-00000002.bin", "chunks/chunk-00000003.bin", "chunks/chunk-00000004.bin", "chunks/chunk-00000005.bin", "manifest.json"))
            with self.assertRaises(ValidationError):
                transfer_model.write_transfer(value, destination)
            manifest = (destination / "manifest.json").read_bytes()
            (destination / "manifest.json").write_bytes(manifest + b"\n")
            with self.assertRaises(ValidationError):
                transfer_model.load_transfer(destination)
            transfer_model.write_transfer(value, destination, overwrite=True)
            with (destination / "chunks" / "chunk-00000000.bin").open("ab") as chunk_file:
                chunk_file.write(b"x")
            with self.assertRaises(ValidationError):
                transfer_model.load_transfer(destination)
            transfer_model.write_transfer(value, destination, overwrite=True)
            (destination / "unexpected.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                transfer_model.load_transfer(destination)
            transfer_model.write_transfer(value, destination, overwrite=True)
            (destination / "chunks" / "chunk-00000005.bin").unlink()
            with self.assertRaises(ValidationError):
                transfer_model.load_transfer(destination)

    def test_cli_http_schemas_partial_transport_and_public_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive, archive_path = self._archive(root)
            transfer_directory = root / "cli-transfer"
            transfer_json = root / "cli-transfer.json"
            query_json = root / "cli-query.json"
            partial_directory = root / "cli-partial"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([COMMAND, str(archive_path), "--transfer-id", "cli-transfer", "--chunk-size", "1024", "--destination", str(transfer_directory), "--format", "json", "--output", str(transfer_json)]), 0)
                self.assertEqual(main([COMMAND + "-verify", str(transfer_directory), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-audit", str(transfer_directory), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-partial", str(archive_path), "--transfer-id", "cli-transfer", "--chunk-size", "1024", "--index", "5", "--index", "0", "--destination", str(partial_directory), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-query", str(partial_directory), "--partial", "--resource", "received", "--limit", "8", "--format", "json", "--output", str(query_json)]), 0)
                self.assertEqual(main([COMMAND + "-query-audit", str(query_json), "--transfer-input", str(transfer_directory), "--format", "summary"]), 0)
                for suffix in ("chunk-schema", "schema", "manifest-schema", "progress-schema", "audit-check-schema", "audit-schema", "audit-capabilities", "query-row-schema", "query-schema", "query-capabilities", "query-audit-check-schema", "query-audit-schema", "query-audit-capabilities"):
                    self.assertEqual(main([COMMAND + "-" + suffix]), 0)
            self.assertEqual(json.loads(transfer_json.read_text(encoding="utf-8"))["chunk_count"], 6)
            self.assertEqual(json.loads(query_json.read_text(encoding="utf-8"))["received_indices"], [0, 5])

            api_transfer_directory = root / "api-transfer"
            api_query_path = root / "api-query.json"
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                server.glio_deployment_guard._rate_windows.clear()
                base_params = {"input": str(archive_path), "transfer_id": "api-transfer", "chunk_size": "1024", "destination": str(api_transfer_directory), "overwrite": "true", "format": "json"}
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}?{urlencode(base_params)}", timeout=30) as response:
                    api_transfer = json.loads(response.read().decode("utf-8"))
                self.assertEqual((api_transfer["transfer_id"], api_transfer["chunk_count"]), ("api-transfer", 6))
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/partial?{urlencode({'input': str(archive_path), 'transfer_id': 'api-transfer', 'chunk_size': '1024', 'received_index': ['0', '5'], 'destination': str(root / 'api-partial'), 'overwrite': 'true', 'format': 'json'}, doseq=True)}", timeout=30) as response:
                    api_progress = json.loads(response.read().decode("utf-8"))
                self.assertEqual(api_progress["received_indices"], [0, 5])
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/verify?{urlencode({'input': str(api_transfer_directory), 'format': 'json'})}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["transfer_id"], "api-transfer")
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/audit?{urlencode({'input': str(api_transfer_directory), 'format': 'json'})}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["accepted"])
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query?{urlencode({'input': str(root / 'api-partial'), 'partial': 'true', 'resource': 'received', 'limit': '8', 'format': 'json'})}", timeout=30) as response:
                    api_query = json.loads(response.read().decode("utf-8"))
                api_query_path.write_text(json.dumps(api_query), encoding="utf-8")
                self.assertEqual(api_query["received_indices"], [0, 5])
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query/audit?{urlencode({'input': str(api_query_path), 'transfer_input': str(api_transfer_directory), 'format': 'json'})}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["accepted"])
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["$schema"], "https://json-schema.org/draft/2020-12/schema")
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/progress-schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["title"], "Runtime registry federation archive transfer progress")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

        inventory = build_default_public_surface_audit()
        self.assertEqual((inventory.surface_count, inventory.passed_surface_count, inventory.failed_surface_count, inventory.accepted), (1779, 1779, 0, True))
        for schema in (transfer_model.chunk_schema(), transfer_model.transfer_schema(), transfer_model.manifest_schema(), transfer_model.progress_schema(), transfer_audit_model.check_schema(), transfer_audit_model.audit_schema(), transfer_query_model.row_schema(), transfer_query_model.query_schema(), transfer_query_audit_model.check_schema(), transfer_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
