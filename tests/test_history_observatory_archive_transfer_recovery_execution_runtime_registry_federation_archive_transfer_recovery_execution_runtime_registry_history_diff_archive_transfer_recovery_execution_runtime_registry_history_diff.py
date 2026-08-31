"""Regression coverage for exact history-diff archive-transfer recovery-execution runtime-registry history comparison."""

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

from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery_execution_runtime_registry_history_diff as diff_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery_execution_runtime_registry_history_diff_audit as diff_audit_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery_execution_runtime_registry_history_diff_query as diff_query_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery_execution_runtime_registry_history_diff_query_audit as diff_query_audit_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery_execution_runtime_registry_history as history_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit

import tests.test_history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery_execution_runtime_registry_history as history_module


COMMAND = history_module.COMMAND + "-diff"
API_PATH = history_module.API_PATH + "/diff"


class HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        history_module.HistoryObservatoryArchiveTransferRecoveryExecutionRuntimeRegistryFederationArchiveTransferRecoveryExecutionRuntimeRegistryHistoryTests.setUpClass()

    @classmethod
    def _histories(cls, root: Path):
        empty, ready = history_module.HistoryObservatoryArchiveTransferRecoveryExecutionRuntimeRegistryFederationArchiveTransferRecoveryExecutionRuntimeRegistryHistoryTests._registries(root)
        return (
            history_model.build_history((empty,), history_id="downloaded-diff-left"),
            history_model.build_history((empty, ready), history_id="downloaded-diff-right"),
        )

    def test_diff_replays_changes_audits_queries_and_persistence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left, right = self._histories(root)
            diff = diff_model.build_diff(left, right, diff_id="downloaded-real-history-diff")
            audit = diff_audit_model.audit_diff(diff)
            query = diff_query_model.query_history_diff(diff, resources=diff_query_model.RESOURCES, limit=diff_query_model.MAX_LIMIT)
            query_audit = diff_query_audit_model.audit_query(query, diff)
            destination = root / "diff"
            diff_model.persist_diff(diff, destination)
            loaded = diff_model.load_diff(destination)

            self.assertEqual((diff.item_count, diff.added_count, diff.removed_count, diff.changed_count, diff.unchanged_count), (2, 1, 0, 0, 1))
            self.assertEqual(tuple(item.change for item in diff.items), ("unchanged", "added"))
            self.assertEqual((audit.check_count, audit.passed, query.total_count, query.returned_count, query_audit.check_count, query_audit.passed), (16, True, 30, 30, 13, True))
            self.assertEqual(loaded.to_dict(), diff.to_dict())
            self.assertEqual(tuple(sorted(item.name for item in destination.iterdir())), tuple(sorted(diff_model.FILES)))
            self.assertEqual(json.loads((destination / "manifest.json").read_text(encoding="utf-8"))["files"], list(diff_model.FILES))
            self.assertEqual(diff_model.diff_from_mapping(json.loads(diff_model.diff_json(diff))).to_dict(), diff.to_dict())

            diff_path = destination / "diff.json"
            diff_path.write_text(diff_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            with self.assertRaises(ValidationError):
                diff_model.load_diff(destination)

    def test_cli_and_http_diff_surfaces(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left, right = self._histories(root)
            left_directory = root / "left-history"
            right_directory = root / "right-history"
            history_model.persist_history(left, left_directory)
            history_model.persist_history(right, right_directory)
            diff_directory = root / "diff"
            diff_json = root / "diff.json"
            query_json = root / "query.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([COMMAND, str(left_directory), str(right_directory), "--diff-id", "downloaded-cli-history-diff", "--destination", str(diff_directory), "--overwrite", "--format", "json", "--output", str(diff_json)]), 0)
                self.assertEqual(main([COMMAND + "-verify", str(diff_directory), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-audit", str(diff_directory), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-query", str(diff_directory), "--change", "added", "--format", "json", "--output", str(query_json)]), 0)
                self.assertEqual(main([COMMAND + "-query-audit", str(query_json), "--diff-input", str(diff_directory), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-schema"]), 0)
            emitted_diff = json.loads(diff_json.read_text(encoding="utf-8"))
            emitted_query = json.loads(query_json.read_text(encoding="utf-8"))
            self.assertEqual((emitted_diff["item_count"], emitted_diff["added_count"], emitted_diff["accepted"]), (2, 1, True))
            self.assertEqual((emitted_query["change_filter"], emitted_query["returned_count"]), ("added", 2))

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                server.glio_deployment_guard._rate_windows.clear()
                base = {"left_input": str(left_directory), "right_input": str(right_directory), "diff_id": "downloaded-api-history-diff", "format": "json"}
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}?{urlencode(base)}", timeout=30) as response:
                    api_diff = json.loads(response.read().decode("utf-8"))
                self.assertEqual((api_diff["item_count"], api_diff["added_count"], api_diff["accepted"]), (2, 1, True))
                diff_input = str(diff_directory)
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/audit?{urlencode({"input": diff_input, "format": "json"})}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["accepted"])
                query_params = {"input": diff_input, "change": "added", "format": "json"}
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query?{urlencode(query_params)}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["returned_count"], 2)
                query_audit_params = {"input": str(query_json), "diff_input": diff_input, "format": "json"}
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query/audit?{urlencode(query_audit_params)}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["accepted"])
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

        inventory = build_default_public_surface_audit()
        self.assertEqual((inventory.surface_count, inventory.passed_surface_count, inventory.failed_surface_count, inventory.accepted), (1954, 1954, 0, True))
        for schema in (diff_model.item_schema(), diff_model.items_schema(), diff_model.manifest_schema(), diff_model.summary_schema(), diff_model.diff_schema(), diff_audit_model.check_schema(), diff_audit_model.audit_schema(), diff_query_model.row_schema(), diff_query_model.query_schema(), diff_query_audit_model.check_schema(), diff_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
