"""Regression coverage for history-diff archive transfer recovery execution runtime registry history."""

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

from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_runtime_registry as registry_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_runtime_registry_history as history_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_runtime_registry_history_audit as history_audit_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_runtime_registry_history_query as history_query_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_runtime_registry_history_query_audit as history_query_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit


import tests.test_exact_history_diff_archive_transfer_recovery_execution_runtime_registry as registry_module


COMMAND = registry_module.COMMAND + "-history"
API_PATH = registry_module.API_PATH + "/history"


class ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry_module.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryTests.setUpClass()

    @classmethod
    def _registries(cls, root: Path):
        registry_tests = registry_module.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryTests()
        runtime = registry_tests._runtime("downloaded-real-history-runtime")
        registry_id = "downloaded-real-history-registry"
        return (
            registry_model.build_registry((), registry_id=registry_id),
            registry_model.build_registry((runtime,), registry_id=registry_id),
        )

    def test_history_replays_transitions_audits_queries_and_persistence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            empty, ready = self._registries(root)
            history = history_model.build_history((empty, ready), history_id="downloaded-real-history")
            audit = history_audit_model.audit_history(history)
            query = history_query_model.query_history(history, resources=history_query_model.RESOURCES, limit=history_query_model.MAX_LIMIT)
            query_audit = history_query_audit_model.audit_query(query, history)
            destination = root / "history"
            history_model.persist_history(history, destination)
            loaded = history_model.load_history(destination)

            self.assertEqual((history.state, history.accepted, history.entry_count, history.initial_count, history.improved_count), ("ready", True, 2, 1, 1))
            self.assertEqual(tuple(item.transition for item in history.entries), ("initial", "improved"))
            self.assertEqual((audit.check_count, audit.passed, query.total_count, query.returned_count, query_audit.check_count, query_audit.passed), (16, True, 40, 40, 12, True))
            self.assertEqual(loaded.to_dict(), history.to_dict())
            self.assertEqual(tuple(sorted(item.name for item in destination.iterdir())), tuple(sorted(history_model.FILES)))
            self.assertEqual(json.loads((destination / "manifest.json").read_text(encoding="utf-8"))["files"], list(history_model.FILES))
            self.assertEqual(history_model.history_from_mapping(json.loads(history_model.history_json(history))).to_dict(), history.to_dict())

            history_path = destination / "history.json"
            history_path.write_text(history_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            with self.assertRaises(ValidationError):
                history_model.load_history(destination)

    def test_cli_and_http_history_surfaces(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            empty, ready = self._registries(root)
            empty_directory = root / "empty-registry"
            ready_directory = root / "ready-registry"
            registry_model.persist_registry(empty, empty_directory)
            registry_model.persist_registry(ready, ready_directory)
            history_directory = root / "history"
            history_json = root / "history.json"
            query_json = root / "query.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([COMMAND, "--registry-input", str(empty_directory), "--registry-input", str(ready_directory), "--history-id", "downloaded-cli-history", "--destination", str(history_directory), "--overwrite", "--format", "json", "--output", str(history_json)]), 0)
                self.assertEqual(main([COMMAND + "-verify", str(history_directory), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-audit", str(history_directory), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-query", str(history_directory), "--resource", "transitions", "--format", "json", "--output", str(query_json)]), 0)
                query_summary_output = io.StringIO()
                with contextlib.redirect_stdout(query_summary_output):
                    self.assertEqual(main([COMMAND + "-query", str(history_directory), "--resource", "transitions", "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-query-audit", str(query_json), "--history-input", str(history_directory), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-schema"]), 0)
            emitted_history = json.loads(history_json.read_text(encoding="utf-8"))
            emitted_query = json.loads(query_json.read_text(encoding="utf-8"))
            emitted_query_summary = json.loads(query_summary_output.getvalue())
            self.assertEqual((emitted_history["state"], emitted_history["accepted"], emitted_history["entry_count"]), ("ready", True, 2))
            self.assertEqual((emitted_query["resources"], emitted_query["returned_count"]), (["transitions"], 5))
            self.assertEqual((emitted_query_summary["resources"], emitted_query_summary["returned_count"], "rows" in emitted_query_summary), (["transitions"], 5, False))

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                server.glio_deployment_guard._rate_windows.clear()
                base = {"input": str(history_directory), "format": "json"}
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}?{urlencode(base)}", timeout=30) as response:
                    api_history = json.loads(response.read().decode("utf-8"))
                self.assertEqual((api_history["state"], api_history["accepted"], api_history["entry_count"]), ("ready", True, 2))
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/audit?{urlencode(base)}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["accepted"])
                query_params = base | {"resource": "transitions"}
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query?{urlencode(query_params)}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["returned_count"], 5)
                query_audit_params = {"input": str(query_json), "history_input": str(history_directory), "format": "json"}
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query/audit?{urlencode(query_audit_params)}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["accepted"])
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

        inventory = build_default_public_surface_audit()
        self.assertEqual((inventory.surface_count, inventory.passed_surface_count, inventory.failed_surface_count, inventory.accepted), (1997, 1997, 0, True))
        for schema in (history_model.entry_schema(), history_model.entries_schema(), history_model.manifest_schema(), history_model.summary_schema(), history_model.history_schema(), history_audit_model.check_schema(), history_audit_model.audit_schema(), history_query_model.row_schema(), history_query_model.query_schema(), history_query_audit_model.check_schema(), history_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_empty_history_is_explicitly_unaccepted_and_addressed(self):
        history = history_model.build_history((), history_id="downloaded-empty-history")
        audit = history_audit_model.audit_history(history)
        query = history_query_model.query_history(history, resources=("summary", "snapshots", "transitions"), limit=history_query_model.MAX_LIMIT)
        query_audit = history_query_audit_model.audit_query(query, history)
        self.assertEqual((history.state, history.accepted, history.entry_count, history.latest_registry_address), ("empty", False, 0, ""))
        self.assertEqual((audit.check_count, audit.passed, query_audit.check_count, query_audit.passed), (16, True, 12, True))
        self.assertEqual(query.total_count, 16 + 0 + 5)
        self.assertTrue(history.content_address.startswith(history_model.HISTORY_PREFIX + ":"))


if __name__ == "__main__":
    unittest.main()
