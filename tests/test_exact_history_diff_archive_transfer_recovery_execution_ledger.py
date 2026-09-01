"""Regression coverage for append-only execution ledgers."""

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

from glio_noncode import exact_history_diff_archive_transfer_recovery_execution as execution_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger as ledger_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_audit as ledger_audit_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_query as ledger_query_model
from glio_noncode import exact_history_diff_archive_transfer_recovery_execution_ledger_query_audit as ledger_query_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit

import tests.test_exact_history_diff_archive_transfer_recovery_execution as execution_test_module


COMMAND = execution_test_module.COMMAND + "-ledger"
API_PATH = execution_test_module.API_PATH + "/ledger"


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        execution_test_module.ExactHistoryDiffArchiveTransferRecoveryExecutionTests.setUpClass()

    def _executions(self):
        _, assembler, recovery, payload = execution_test_module.ExactHistoryDiffArchiveTransferRecoveryExecutionTests()._partial()
        planned = execution_model.build_execution(recovery, execution_id="ledger-planned", checkpointed=True)
        assembler.add_chunk(1, payload[1])
        progress = execution_model.build_execution_from_assembler(recovery, assembler, execution_id="ledger-progress")
        for index in range(len(payload)):
            assembler.add_chunk(index, payload[index])
        complete = execution_model.build_execution_from_assembler(recovery, assembler, execution_id="ledger-complete", checkpointed=False)
        blocked = execution_model.build_execution(recovery, rejected_indices=(1,), execution_id="ledger-blocked")
        return planned, progress, complete, blocked

    def test_append_chain_audits_queries_and_persists(self):
        planned, progress, complete, _ = self._executions()
        value = ledger_model.build_ledger((planned, progress, complete), ledger_id="ledger-regression")
        audit = ledger_audit_model.audit_ledger(value)
        query = ledger_query_model.query_ledger(value)
        query_audit = ledger_query_audit_model.audit_query(query, value)
        self.assertEqual((value.entry_count, value.planned_count, value.in_progress_count, value.complete_count, value.blocked_count), (3, 1, 1, 1, 0))
        self.assertEqual((audit.check_count, audit.passed, query.total_count, query.returned_count, query_audit.check_count, query_audit.passed), (18, True, 17, 17, 12, True))

        empty = ledger_model.build_ledger((), ledger_id="ledger-regression")
        first = ledger_model.append_execution(empty, planned, expected_head_address=empty.head_address)
        second = ledger_model.append_execution(first, progress, expected_head_address=first.head_address)
        third = ledger_model.append_execution(second, complete, expected_head_address=second.head_address)
        self.assertEqual([item.to_dict() for item in third.entries], [item.to_dict() for item in value.entries])
        with self.assertRaises(ValidationError):
            ledger_model.append_execution(third, complete, expected_head_address=third.head_address)
        with self.assertRaises(ValidationError):
            ledger_model.append_execution(third, complete, expected_head_address=ledger_model.INITIAL_HEAD)

        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "ledger"
            ledger_model.persist_ledger(value, destination)
            loaded = ledger_model.load_ledger(destination)
            self.assertEqual(loaded.content_address, value.content_address)
            self.assertEqual(ledger_model.ledger_json(loaded), ledger_model.ledger_json(value))
            self.assertEqual(set(item.name for item in destination.iterdir()), set(ledger_model.FILES))
            tampered = destination / "ledger.json"
            tampered.write_bytes(tampered.read_bytes() + b"\n")
            with self.assertRaises(ValidationError):
                ledger_model.load_ledger(destination)

    def test_blocked_and_zero_action_states_remain_auditable(self):
        planned, _, complete, blocked = self._executions()
        blocked_ledger = ledger_model.build_ledger((blocked,), ledger_id="ledger-blocked")
        complete_ledger = ledger_model.build_ledger((complete,), ledger_id="ledger-zero-action")
        blocked_audit = ledger_audit_model.audit_ledger(blocked_ledger)
        complete_audit = ledger_audit_model.audit_ledger(complete_ledger)
        self.assertEqual((blocked_ledger.state, blocked_ledger.latest_decision, blocked_ledger.accepted, blocked_audit.passed), ("blocked", "block", False, True))
        self.assertEqual((complete_ledger.state, complete_ledger.latest_decision, complete_ledger.accepted, complete_audit.passed), ("complete", "assemble", True, True))
        self.assertNotEqual(planned.content_address, complete.content_address)

    def test_cli_api_schemas_and_public_inventory(self):
        planned, progress, complete, _ = self._executions()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            execution_paths = []
            for name, value in (("planned", planned), ("progress", progress), ("complete", complete)):
                path = root / f"{name}.json"
                path.write_text(execution_model.execution_json(value), encoding="utf-8")
                execution_paths.append(path)
            ledger_path = root / "ledger"
            query_path = root / "query.json"
            with contextlib.redirect_stdout(io.StringIO()):
                command = [COMMAND, str(execution_paths[0]), "--execution-input", str(execution_paths[1]), "--execution-input", str(execution_paths[2]), "--ledger-id", "ledger-cli", "--destination", str(ledger_path), "--format", "json", "--output", str(root / "ledger.json")]
                self.assertEqual(main(command), 0)
                self.assertEqual(main([COMMAND + "-verify", str(ledger_path), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-audit", str(ledger_path), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-query", str(ledger_path), "--resource", "transitions", "--limit", "8", "--format", "json", "--output", str(query_path)]), 0)
                self.assertEqual(main([COMMAND + "-query-audit", str(query_path), "--ledger-input", str(ledger_path), "--format", "summary"]), 0)
                for suffix in ("entry-schema", "entries-schema", "manifest-schema", "summary-schema", "schema", "capabilities", "audit-check-schema", "audit-schema", "audit-capabilities", "query-row-schema", "query-schema", "query-capabilities", "query-audit-check-schema", "query-audit-schema", "query-audit-capabilities"):
                    self.assertEqual(main([COMMAND + "-" + suffix]), 0)

            loaded = ledger_model.load_ledger(ledger_path)
            self.assertEqual((loaded.entry_count, loaded.head_address, loaded.state), (3, loaded.entries[-1].content_address, "complete"))
            query = ledger_query_model.query_from_mapping(json.loads(query_path.read_text(encoding="utf-8")))
            self.assertGreater(query.returned_count, 0)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                server.glio_deployment_guard._rate_windows.clear()
                params = urlencode([("execution", str(path)) for path in execution_paths] + [("ledger_id", "ledger-api"), ("format", "json")])
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}?{params}", timeout=30) as response:
                    api_ledger = json.loads(response.read().decode("utf-8"))
                self.assertEqual((api_ledger["entry_count"], api_ledger["state"]), (3, "complete"))
                api_ledger_path = root / "api-ledger.json"
                api_ledger_path.write_text(json.dumps(api_ledger), encoding="utf-8")
                params = urlencode({"input": str(api_ledger_path), "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["passed"])
                params = urlencode({"input": str(api_ledger_path), "resource": "states", "limit": "4", "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query?{params}", timeout=30) as response:
                    api_query = json.loads(response.read().decode("utf-8"))
                self.assertGreater(api_query["returned_count"], 0)
                api_query_path = root / "api-query.json"
                api_query_path.write_text(json.dumps(api_query), encoding="utf-8")
                params = urlencode({"input": str(api_query_path), "ledger_input": str(api_ledger_path), "format": "summary"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["passed"])
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

        inventory = build_default_public_surface_audit()
        self.assertEqual((inventory.surface_count, inventory.passed_surface_count, inventory.failed_surface_count, inventory.accepted), (2126, 2126, 0, True))
        for schema in (ledger_model.entry_schema(), ledger_model.entries_schema(), ledger_model.manifest_schema(), ledger_model.summary_schema(), ledger_model.ledger_schema(), ledger_audit_model.check_schema(), ledger_audit_model.audit_schema(), ledger_query_model.row_schema(), ledger_query_model.query_schema(), ledger_query_audit_model.check_schema(), ledger_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
