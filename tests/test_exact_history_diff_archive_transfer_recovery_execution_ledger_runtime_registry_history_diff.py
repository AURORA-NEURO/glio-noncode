"""Regression coverage for deterministic history-to-history comparison."""

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

from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry as registry_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history as history_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff as diff_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_audit as diff_audit_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_query as diff_query_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_query_audit as diff_query_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit

import tests.test_exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history as history_test_module
import tests.test_exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry as registry_test_module


COMMAND = history_test_module.COMMAND + "-diff"
API_PATH = history_test_module.API_PATH + "/diff"


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        history_test_module.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryTests.setUpClass()

    def _histories(self):
        ready, blocked = registry_test_module.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryTests()._runtimes()
        registry_id = "history-diff-registry"
        empty = registry_model.build_registry((), registry_id=registry_id)
        ready_registry = registry_model.build_registry((ready,), registry_id=registry_id)
        blocked_registry = registry_model.build_registry((ready, blocked), registry_id=registry_id)
        left = history_model.build_history((empty, ready_registry), history_id="baseline-history")
        right = history_model.build_history((empty, blocked_registry), history_id="candidate-history")
        return left, right

    def test_same_identity_deltas_direction_and_independent_audits(self):
        left, right = self._histories()
        value = diff_model.build_diff(left, right, diff_id="history-diff-demo")
        self.assertEqual((value.item_count, value.added_count, value.removed_count, value.changed_count, value.unchanged_count), (2, 0, 0, 1, 1))
        self.assertEqual(tuple(item.change for item in value.items), ("unchanged", "changed"))
        self.assertEqual(value.direction, "regressed")
        self.assertFalse(value.accepted)
        self.assertEqual((value.manifest.files, tuple(item.name for item in value.manifest.artifacts)), (diff_model.FILES, diff_model.ARTIFACT_FILES))
        audit = diff_audit_model.audit_diff(value)
        query = diff_query_model.query_history_diff(value)
        changed = diff_query_model.query_history_diff(value, resources=("changed",), change="changed")
        query_audit = diff_query_audit_model.audit_query(query, value)
        self.assertEqual((audit.check_count, audit.passed), (16, True))
        self.assertEqual((query.returned_count, query.total_count, query_audit.check_count, query_audit.passed), (query.total_count, query.total_count, 13, True))
        self.assertGreater(query.returned_count, changed.returned_count)
        self.assertTrue(all(row.change == "changed" for row in changed.rows))
        with self.assertRaises(ValidationError):
            diff_model.build_diff(left, history_model.build_history((empty := left.entries[0],), history_id="wrong-registry-history"))
        self.assertEqual(diff_model.diff_from_mapping(value.to_dict()).content_address, value.content_address)

    def test_added_removed_persistence_and_tamper_rejection(self):
        left, right = self._histories()
        empty = registry_model.build_registry((), registry_id=left.registry_id)
        added = diff_model.build_diff(history_model.build_history((empty,), history_id="short-baseline"), right, diff_id="added-diff")
        self.assertEqual((added.added_count, added.changed_count, added.unchanged_count), (1, 0, 1))
        removed = diff_model.build_diff(left, history_model.build_history((empty,), history_id="short-candidate"), diff_id="removed-diff")
        self.assertEqual((removed.removed_count, removed.changed_count, removed.unchanged_count), (1, 0, 1))
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "diff"
            diff_model.persist_diff(added, destination)
            loaded = diff_model.load_diff(destination)
            self.assertEqual(diff_model.diff_json(loaded), diff_model.diff_json(added))
            self.assertEqual(set(item.name for item in destination.iterdir()), set(diff_model.FILES))
            summary_path = destination / "summary.json"
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            payload["accepted"] = True
            summary_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
            with self.assertRaises(ValidationError):
                diff_model.load_diff(destination)
            diff_model.persist_diff(added, destination, overwrite=True)
            (destination / "unexpected.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                diff_model.load_diff(destination)

    def test_cli_api_schemas_and_public_inventory(self):
        left, right = self._histories()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left_path = root / "left-history"
            right_path = root / "right-history"
            diff_path = root / "diff"
            query_path = root / "query.json"
            history_model.persist_history(left, left_path)
            history_model.persist_history(right, right_path)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([COMMAND, str(left_path), "--candidate-input", str(right_path), "--diff-id", "cli-history-diff", "--destination", str(diff_path), "--format", "json", "--output", str(root / "diff.json")]), 0)
                self.assertEqual(main([COMMAND + "-verify", str(diff_path), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-audit", str(diff_path), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-query", str(diff_path), "--resource", "changed", "--change", "changed", "--format", "json", "--output", str(query_path)]), 0)
                self.assertEqual(main([COMMAND + "-query-audit", str(query_path), "--diff-input", str(diff_path), "--format", "summary"]), 0)
                for suffix in ("item-schema", "items-schema", "artifact-schema", "manifest-schema", "summary-schema", "schema", "capabilities", "audit-check-schema", "audit-schema", "audit-capabilities", "query-row-schema", "query-schema", "query-capabilities", "query-audit-check-schema", "query-audit-schema", "query-audit-capabilities"):
                    self.assertEqual(main([COMMAND + "-" + suffix]), 0)
            cli_payload = json.loads((root / "diff.json").read_text(encoding="utf-8"))
            self.assertEqual((cli_payload["changed_count"], cli_payload["direction"], cli_payload["accepted"]), (1, "regressed", False))
            self.assertEqual(json.loads(query_path.read_text(encoding="utf-8"))["returned_count"], 1)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                server.glio_deployment_guard._rate_windows.clear()
                params = urlencode({"input": str(left_path), "candidate_input": str(right_path), "diff_id": "api-history-diff", "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}?{params}", timeout=30) as response:
                    api_diff = json.loads(response.read().decode("utf-8"))
                self.assertEqual((api_diff["changed_count"], api_diff["direction"]), (1, "regressed"))
                params = urlencode({"input": str(diff_path), "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["passed"])
                params = urlencode({"input": str(diff_path), "resource": "changed", "change": "changed", "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query?{params}", timeout=30) as response:
                    api_query = json.loads(response.read().decode("utf-8"))
                self.assertEqual(api_query["returned_count"], 1)
                api_query_path = root / "api-query.json"
                api_query_path.write_text(json.dumps(api_query), encoding="utf-8")
                params = urlencode({"input": str(api_query_path), "diff_input": str(diff_path), "format": "summary"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["passed"])
                for suffix in ("item-schema", "items-schema", "artifact-schema", "manifest-schema", "summary-schema", "schema", "capabilities", "audit/check-schema", "audit/schema", "audit/capabilities", "query/row-schema", "query/schema", "query/capabilities", "query-audit/check-schema", "query-audit/schema", "query-audit/capabilities"):
                    with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/{suffix}", timeout=30) as response:
                        payload = json.loads(response.read().decode("utf-8"))
                        if suffix.endswith("schema"):
                            self.assertEqual(payload["$schema"], "https://json-schema.org/draft/2020-12/schema")
                        else:
                            self.assertTrue(payload)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

        inventory = build_default_public_surface_audit()
        self.assertEqual((inventory.surface_count, inventory.passed_surface_count, inventory.failed_surface_count, inventory.accepted), (2126, 2126, 0, True))
        for schema in (diff_model.item_schema(), diff_model.items_schema(), diff_model.artifact_schema(), diff_model.manifest_schema(), diff_model.summary_schema(), diff_model.diff_schema(), diff_audit_model.check_schema(), diff_audit_model.audit_schema(), diff_query_model.row_schema(), diff_query_model.query_schema(), diff_query_audit_model.check_schema(), diff_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
