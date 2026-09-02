"""Regression coverage for the addressed execution-ledger archive transfer."""

from __future__ import annotations

# ruff: noqa: E501, I001

import contextlib
import io
import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive as archive_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_transfer as transfer_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_transfer_audit as transfer_audit_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_transfer_query as transfer_query_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_transfer_query_audit as transfer_query_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit

import tests.test_exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive as archive_test_module


COMMAND = archive_test_module.COMMAND + "-transfer"
API_PATH = archive_test_module.API_PATH + "/transfer"


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        archive_test_module.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTests.setUpClass()

    def _archive(self):
        return archive_test_module.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTests()._archive()

    def _transfer(self):
        return transfer_model.build_transfer(self._archive(), transfer_id="transfer-demo", chunk_size=1024)

    def test_deterministic_chunks_reverse_assembly_and_independent_audits(self):
        archive = self._archive()
        value = transfer_model.build_transfer(archive, transfer_id="transfer-demo", chunk_size=1024)
        payload = value.payload_bytes()
        self.assertGreater(value.chunk_count, 1)
        self.assertEqual(value.chunk_count, (value.archive_size + value.chunk_size - 1) // value.chunk_size)
        self.assertEqual(sum(chunk.size for chunk in value.chunks), value.archive_size)
        self.assertEqual(tuple(payload), tuple(chunk.index for chunk in value.chunks))
        self.assertEqual(transfer_model.address_transfer(value), value.content_address)
        receiver = transfer_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferAssembler(
            transfer_model.transfer_from_mapping(value.to_dict())
        )
        for index in reversed(range(value.chunk_count)):
            receiver.add_chunk(index, payload[index])
        receiver.add_chunk(0, payload[0])
        self.assertTrue(receiver.is_complete())
        self.assertEqual(receiver.finalize(), archive_model.archive_bytes(archive))
        audit = transfer_audit_model.audit_transfer(value)
        query = transfer_query_model.query_transfer(value)
        query_audit = transfer_query_audit_model.audit_query(query, value)
        self.assertEqual((audit.check_count, audit.passed), (18, True))
        self.assertEqual((query.returned_count, query.total_count, query_audit.check_count, query_audit.passed), (query.total_count, query.total_count, 12, True))
        self.assertEqual(transfer_model.transfer_from_mapping(value.to_dict()).content_address, value.content_address)
        self.assertEqual(transfer_model.manifest_json(value), transfer_model.manifest_json(value))

    def test_complete_partial_persistence_and_negative_controls(self):
        value = self._transfer()
        payload = value.payload_bytes()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            complete = root / "complete"
            partial = root / "partial"
            transfer_model.write_transfer(value, complete)
            loaded = transfer_model.load_transfer(complete)
            self.assertEqual(loaded.content_address, value.content_address)
            self.assertEqual(transfer_model.assemble_transfer_directory(complete), archive_model.archive_bytes(self._archive()))

            receiver = transfer_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferAssembler(transfer_model.transfer_from_mapping(value.to_dict()))
            selected = (0,) if value.chunk_count == 1 else (0, value.chunk_count - 1)
            for index in selected:
                receiver.add_chunk(index, payload[index])
            transfer_model.write_partial_transfer(receiver, partial)
            partial_loaded = transfer_model.load_partial_transfer(partial)
            progress = partial_loaded.progress()
            self.assertEqual(progress.received_indices, selected)
            self.assertEqual(progress.received_bytes, sum(len(payload[index]) for index in selected))
            self.assertFalse(progress.complete)
            self.assertEqual(set(progress.received_indices) | set(progress.missing_indices), set(range(value.chunk_count)))

            tampered = root / "tampered"
            shutil.copytree(complete, tampered)
            chunk_path = tampered / transfer_model.chunk_name(0)
            raw = chunk_path.read_bytes()
            chunk_path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
            with self.assertRaises(ValidationError):
                transfer_model.load_transfer(tampered)

            extra = root / "extra"
            shutil.copytree(complete, extra)
            (extra / "unexpected.bin").write_bytes(b"unexpected")
            with self.assertRaises(ValidationError):
                transfer_model.load_transfer(extra)

            missing = root / "missing"
            shutil.copytree(complete, missing)
            (missing / transfer_model.chunk_name(value.chunk_count - 1)).unlink()
            with self.assertRaises(ValidationError):
                transfer_model.load_transfer(missing)

            conflict = transfer_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferAssembler(transfer_model.transfer_from_mapping(value.to_dict()))
            conflict.add_chunk(0, payload[0])
            changed = bytes([payload[0][0] ^ 1]) + payload[0][1:]
            with self.assertRaises(ValidationError):
                conflict.add_chunk(0, changed)

    def test_cli_api_schemas_and_public_inventory(self):
        value = self._transfer()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "archive.zip"
            transfer_path = root / "transfer"
            partial_path = root / "partial"
            transfer_json_path = root / "transfer.json"
            query_path = root / "query.json"
            archive_model.write_archive(self._archive(), archive_path)
            receiver = transfer_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferAssembler(transfer_model.transfer_from_mapping(value.to_dict()))
            receiver.add_chunk(0, value.payload_bytes()[0])
            transfer_model.write_partial_transfer(receiver, partial_path)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([COMMAND, str(archive_path), "--transfer-id", "cli-transfer", "--destination", str(transfer_path), "--format", "json", "--output", str(transfer_json_path)]), 0)
                self.assertEqual(main([COMMAND + "-verify", str(transfer_path), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-manifest", str(transfer_path), "--format", "json"]), 0)
                self.assertEqual(main([COMMAND + "-progress", str(partial_path), "--format", "json"]), 0)
                self.assertEqual(main([COMMAND + "-assemble", str(transfer_path), "--format", "summary", "--archive-output", str(root / "assembled.zip")]), 0)
                self.assertEqual(main([COMMAND + "-audit", str(transfer_path), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-query", str(transfer_path), "--resource", "chunks", "--format", "json", "--output", str(query_path)]), 0)
                self.assertEqual(main([COMMAND + "-query-audit", str(query_path), "--transfer-input", str(transfer_path), "--format", "summary"]), 0)
                for suffix in ("chunk-schema", "manifest-schema", "progress-schema", "schema", "capabilities", "audit-check-schema", "audit-schema", "audit-capabilities", "query-row-schema", "query-schema", "query-capabilities", "query-audit-check-schema", "query-audit-schema", "query-audit-capabilities"):
                    self.assertEqual(main([COMMAND + "-" + suffix]), 0)
            self.assertEqual(json.loads(transfer_json_path.read_text(encoding="utf-8"))["transfer_id"], "cli-transfer")
            self.assertEqual(json.loads(query_path.read_text(encoding="utf-8"))["returned_count"], value.chunk_count)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                server.glio_deployment_guard._rate_windows.clear()
                params = urlencode({"input": str(archive_path), "transfer_id": "api-transfer", "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}?{params}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["transfer_id"], "api-transfer")
                params = urlencode({"input": str(transfer_path), "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/verify?{params}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["transfer_id"], "cli-transfer")
                params = urlencode({"input": str(partial_path), "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/progress?{params}", timeout=30) as response:
                    self.assertFalse(json.loads(response.read().decode("utf-8"))["complete"])
                params = urlencode({"input": str(transfer_path), "resource": "chunks", "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query?{params}", timeout=30) as response:
                    api_query = json.loads(response.read().decode("utf-8"))
                self.assertEqual(api_query["returned_count"], value.chunk_count)
                api_query_path = root / "api-query.json"
                api_query_path.write_text(json.dumps(api_query), encoding="utf-8")
                params = urlencode({"input": str(api_query_path), "transfer_input": str(transfer_path), "format": "summary"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["passed"])
                for suffix in ("chunk-schema", "manifest-schema", "progress-schema", "schema", "capabilities", "audit/check-schema", "audit/schema", "audit/capabilities", "query/row-schema", "query/schema", "query/capabilities", "query-audit/check-schema", "query-audit/schema", "query-audit/capabilities"):
                    with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/{suffix}", timeout=30) as response:
                        self.assertTrue(json.loads(response.read().decode("utf-8")))
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

        inventory = build_default_public_surface_audit()
        self.assertEqual((inventory.surface_count, inventory.passed_surface_count, inventory.failed_surface_count, inventory.accepted), (2140, 2140, 0, True))
        for schema in (transfer_model.chunk_schema(), transfer_model.manifest_schema(), transfer_model.progress_schema(), transfer_model.transfer_schema(), transfer_audit_model.check_schema(), transfer_audit_model.audit_schema(), transfer_query_model.row_schema(), transfer_query_model.query_schema(), transfer_query_audit_model.check_schema(), transfer_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
