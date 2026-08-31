"""Regression coverage for federation history-diff archive transport."""

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

from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive as archive_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_audit as audit_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_query as query_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_query_audit as query_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit
from glio_noncode.serialization import canonical_bytes

import tests.test_history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff as diff_module


COMMAND = diff_module.COMMAND + "-archive"
API_PATH = diff_module.API_PATH + "/archive"


class HistoryObservatoryArchiveTransferRecoveryExecutionRuntimeRegistryFederationArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        diff_module.HistoryObservatoryArchiveTransferRecoveryExecutionRuntimeRegistryFederationArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffTests.setUpClass()

    @classmethod
    def _diff(cls, root: Path):
        left, right = diff_module.HistoryObservatoryArchiveTransferRecoveryExecutionRuntimeRegistryFederationArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffTests._histories(root)
        from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff as diff_model

        return diff_model.build_diff(left, right, diff_id="downloaded-real-history-diff-archive")

    @staticmethod
    def _repack(raw: bytes, *, mutate=None, reverse=False) -> bytes:
        source = io.BytesIO(raw)
        with zipfile.ZipFile(source, "r") as archive:
            members = {name: archive.read(name) for name in archive.namelist()}
        if mutate is not None:
            members = mutate(members)
        names = tuple(reversed(archive_model.FILES)) if reverse else archive_model.FILES
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in names:
                archive.writestr(name, members[name])
        return output.getvalue()

    def test_archive_replays_deterministically_and_rejects_tamper(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            diff = self._diff(root)
            archive = archive_model.build_archive(diff, archive_id="downloaded-real-history-diff-archive")
            raw = archive_model.archive_bytes(archive)
            loaded = archive_model.load_archive_bytes(raw)
            audit = audit_model.audit_archive(loaded)
            query = query_model.query_archive(loaded, resources=query_model.RESOURCES, limit=query_model.MAX_LIMIT)
            query_audit = query_audit_model.audit_query(query, loaded)
            destination = root / "history-diff.zip"
            archive_model.write_archive(archive, destination)
            reloaded = archive_model.verify_archive_file(destination)

            self.assertEqual(list(archive_model.FILES), ["manifest.json", "history-diff/manifest.json", "history-diff/diff.json", "history-diff/items.json", "history-diff/summary.json"])
            self.assertEqual((len(raw), raw == archive_model.archive_bytes(archive), loaded.content_address, reloaded.content_address), (archive.archive_size, True, archive.content_address, archive.content_address))
            self.assertEqual((audit.passed_count, audit.check_count, audit.passed, query.returned_count, query.total_count, query_audit.passed_count, query_audit.check_count, query_audit.passed), (18, 18, True, 48, 48, 13, 13, True))
            self.assertEqual(archive_model.archive_from_mapping(archive.to_dict()).content_address, archive.content_address)
            self.assertEqual(json.loads(archive_model.archive_json(archive))["content_address"], archive.content_address)

            def tamper(members):
                value = json.loads(members["history-diff/summary.json"].decode("utf-8"))
                value["accepted"] = not value["accepted"]
                members["history-diff/summary.json"] = canonical_bytes(value)
                return members

            with self.assertRaises(ValidationError):
                archive_model.load_archive_bytes(self._repack(raw, mutate=tamper))
            with self.assertRaises(ValidationError):
                archive_model.load_archive_bytes(self._repack(raw, reverse=True))

    def test_cli_and_http_archive_surfaces(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            diff = self._diff(root)
            diff_directory = root / "diff"
            archive_path = root / "history-diff.zip"
            query_path = root / "query.json"
            audit_path = root / "audit.json"
            from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff as diff_model

            diff_model.persist_diff(diff, diff_directory)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([COMMAND, str(diff_directory), "--archive-id", "cli-history-diff-archive", "--destination", str(archive_path), "--format", "json"]), 0)
                self.assertEqual(main([COMMAND + "-verify", str(archive_path), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-audit", str(archive_path), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-query", str(archive_path), "--resource", "changes", "--format", "json", "--output", str(query_path)]), 0)
                self.assertEqual(main([COMMAND + "-query-audit", str(query_path), "--archive-input", str(archive_path), "--format", "json", "--output", str(audit_path)]), 0)
                self.assertEqual(main([COMMAND + "-schema"]), 0)
            self.assertEqual(json.loads(query_path.read_text(encoding="utf-8"))["returned_count"], 4)
            self.assertTrue(json.loads(audit_path.read_text(encoding="utf-8"))["accepted"])

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                server.glio_deployment_guard._rate_windows.clear()
                base = {"input": str(diff_directory), "archive_id": "api-history-diff-archive", "format": "json"}
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}?{urlencode(base)}", timeout=30) as response:
                    api_archive = json.loads(response.read().decode("utf-8"))
                self.assertEqual((api_archive["artifact_count"], api_archive["archive_size"] > 0), (4, True))
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/audit?{urlencode({'input': str(archive_path), 'format': 'json'})}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["accepted"])
                query_params = {"input": str(archive_path), "resource": "changes", "format": "json"}
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query?{urlencode(query_params)}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["returned_count"], 4)
                query_audit_params = {"input": str(query_path), "archive_input": str(archive_path), "format": "json"}
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query/audit?{urlencode(query_audit_params)}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["accepted"])
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

        inventory = build_default_public_surface_audit()
        self.assertEqual((inventory.surface_count, inventory.passed_surface_count, inventory.failed_surface_count, inventory.accepted), (1875, 1875, 0, True))
        for schema in (archive_model.artifact_schema(), archive_model.manifest_schema(), archive_model.archive_schema(), audit_model.check_schema(), audit_model.audit_schema(), query_model.row_schema(), query_model.query_schema(), query_audit_model.check_schema(), query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
