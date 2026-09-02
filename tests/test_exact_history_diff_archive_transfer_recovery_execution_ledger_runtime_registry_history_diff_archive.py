"""Regression coverage for the deterministic history-diff archive boundary."""

from __future__ import annotations

# ruff: noqa: E501, I001

import contextlib
import io
import json
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff as diff_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive as archive_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_audit as archive_audit_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_query as archive_query_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_query_audit as archive_query_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit

import tests.test_exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff as diff_test_module


COMMAND = diff_test_module.COMMAND + "-archive"
API_PATH = diff_test_module.API_PATH + "/archive"


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        diff_test_module.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffTests.setUpClass()

    def _archive(self):
        left, right = diff_test_module.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffTests()._histories()
        diff = diff_model.build_diff(left, right, diff_id="archive-diff")
        return archive_model.build_archive(diff, archive_id="archive-demo")

    def test_fixed_members_determinism_reload_and_independent_audits(self):
        value = self._archive()
        raw = archive_model.archive_bytes(value)
        self.assertEqual(value.files, archive_model.EMBEDDED_FILES)
        self.assertEqual(tuple(item.name for item in value.artifacts), archive_model.EMBEDDED_FILES)
        self.assertEqual(raw, archive_model.archive_bytes(value))
        self.assertEqual((value.archive_size, len(raw)), (len(raw), len(raw)))
        self.assertEqual((len(value.artifacts), value.diff_id, value.diff.item_count), (4, "archive-diff", 2))
        audit = archive_audit_model.audit_archive(value)
        query = archive_query_model.query_archive(value)
        query_audit = archive_query_audit_model.audit_query(query, value)
        self.assertEqual((audit.check_count, audit.passed), (18, True))
        self.assertEqual((query.returned_count, query.total_count, query_audit.check_count, query_audit.passed), (38, 38, 12, True))
        loaded = archive_model.load_archive_bytes(raw)
        self.assertEqual(archive_model.archive_json(loaded), archive_model.archive_json(value))
        self.assertEqual(loaded.content_address, value.content_address)
        self.assertEqual(archive_model.archive_from_mapping(value.to_dict()).content_address, value.content_address)

    def test_zip_boundary_and_member_tamper_rejection(self):
        value = self._archive()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "archive.zip"
            archive_model.write_archive(value, destination)
            self.assertEqual(archive_model.load_archive(destination).content_address, value.content_address)
            tampered = root / "tampered.zip"
            tampered.write_bytes(destination.read_bytes())
            with zipfile.ZipFile(tampered, "a", compression=zipfile.ZIP_STORED) as package:
                package.writestr("unexpected.json", b"{}")
            with self.assertRaises(ValidationError):
                archive_model.load_archive(tampered)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(archive_model.manifest_document(value), separators=(",", ":")), encoding="utf-8")
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["files"], list(archive_model.EMBEDDED_FILES))

    def test_cli_api_schemas_and_public_inventory(self):
        value = self._archive()
        diff = value.diff
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            diff_path = root / "diff"
            archive_path = root / "archive.zip"
            query_path = root / "query.json"
            diff_model.persist_diff(diff, diff_path)
            archive_model.write_archive(value, archive_path)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([COMMAND, str(diff_path), "--archive-id", "cli-archive", "--destination", str(root / "cli.zip"), "--format", "json", "--output", str(root / "archive.json")]), 0)
                self.assertEqual(main([COMMAND + "-verify", str(archive_path), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-audit", str(archive_path), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-query", str(archive_path), "--resource", "nested", "--format", "json", "--output", str(query_path)]), 0)
                self.assertEqual(main([COMMAND + "-query-audit", str(query_path), "--archive-input", str(archive_path), "--format", "summary"]), 0)
                for suffix in ("artifact-schema", "manifest-schema", "schema", "capabilities", "audit-check-schema", "audit-schema", "audit-capabilities", "query-row-schema", "query-schema", "query-capabilities", "query-audit-check-schema", "query-audit-schema", "query-audit-capabilities"):
                    self.assertEqual(main([COMMAND + "-" + suffix]), 0)
            self.assertEqual(json.loads((root / "archive.json").read_text(encoding="utf-8"))["archive_id"], "cli-archive")
            self.assertEqual(json.loads(query_path.read_text(encoding="utf-8"))["returned_count"], 8)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                server.glio_deployment_guard._rate_windows.clear()
                params = urlencode({"input": str(diff_path), "archive_id": "api-archive", "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}?{params}", timeout=30) as response:
                    api_archive = json.loads(response.read().decode("utf-8"))
                self.assertEqual(api_archive["archive_id"], "api-archive")
                params = urlencode({"input": str(archive_path), "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["passed"])
                params = urlencode({"input": str(archive_path), "resource": "nested", "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query?{params}", timeout=30) as response:
                    api_query = json.loads(response.read().decode("utf-8"))
                self.assertEqual(api_query["returned_count"], 8)
                api_query_path = root / "api-query.json"
                api_query_path.write_text(json.dumps(api_query), encoding="utf-8")
                params = urlencode({"input": str(api_query_path), "archive_input": str(archive_path), "format": "summary"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["passed"])
                for suffix in ("artifact-schema", "manifest-schema", "schema", "capabilities", "audit/check-schema", "audit/schema", "audit/capabilities", "query/row-schema", "query/schema", "query/capabilities", "query-audit/check-schema", "query-audit/schema", "query-audit/capabilities"):
                    with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/{suffix}", timeout=30) as response:
                        payload = json.loads(response.read().decode("utf-8"))
                        self.assertTrue(payload)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

        inventory = build_default_public_surface_audit()
        self.assertEqual((inventory.surface_count, inventory.passed_surface_count, inventory.failed_surface_count, inventory.accepted), (2140, 2140, 0, True))
        for schema in (archive_model.artifact_schema(), archive_model.manifest_schema(), archive_model.archive_schema(), archive_audit_model.check_schema(), archive_audit_model.audit_schema(), archive_query_model.row_schema(), archive_query_model.query_schema(), archive_query_audit_model.check_schema(), archive_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
