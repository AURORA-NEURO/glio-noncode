# ruff: noqa: E501, I001

from __future__ import annotations

import io
import json
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import downloaded_data_catalog as catalog_model
from glio_noncode import downloaded_data_ingestion as ingestion_model
from glio_noncode import downloaded_data_profile as profile_model
from glio_noncode import downloaded_data_profile_contract as contract_model
from glio_noncode import downloaded_data_profile_contract_compatibility as compatibility_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation as remediation_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution as resolution_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history as history_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_audit as history_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_query as history_query_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_query_audit as history_query_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_runtime as history_runtime_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_runtime_audit as history_runtime_audit_model
from glio_noncode import downloaded_data_profile_contract_diff as diff_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryTests(unittest.TestCase):
    @staticmethod
    def _zip() -> bytes:
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("data/object.json", json.dumps({"id": "object-secret", "ok": True, "score": 4}, separators=(",", ":")))
            archive.writestr("data/rows.json", json.dumps([{"id": "row-secret", "value": 4}, {"id": "row-two", "value": None}], separators=(",", ":")))
            archive.writestr("data/table.csv", "id,value,label\nrow-1,4,alpha-secret\nrow-2,9,beta\n")
        return stream.getvalue()

    @classmethod
    def _plan(cls):
        catalog = catalog_model.build_catalog(cls._zip(), catalog_id="history-fixture-catalog")
        left_batch = ingestion_model.build_ingest(cls._zip(), batch_id="history-fixture-left", record_limit=100)
        selected = tuple(sorted(item.member_name for item in catalog.members if item.member_name.endswith("object.json")))
        right_batch = ingestion_model.build_ingest(cls._zip(), batch_id="history-fixture-right", member_names=selected, record_limit=100)
        left = contract_model.build_contract(profile_model.build_profile(left_batch, profile_id="history-fixture-left-profile"))
        right = contract_model.build_contract(profile_model.build_profile(right_batch, profile_id="history-fixture-right-profile"))
        gate = compatibility_model.evaluate(diff_model.build_diff(left, right, diff_id="history-fixture-diff"))
        return remediation_model.build_plan(gate, plan_id="history-fixture-plan")

    @staticmethod
    def _snapshots():
        plan = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryTests._plan()
        pending = resolution_model.build_resolution(plan, resolution_id="history-fixture-pending")
        statuses = {item.content_address: "resolved" for item in plan.actions if item.required}
        closed = resolution_model.build_resolution(plan, resolution_id="history-fixture-closed", statuses=statuses)
        rejected = resolution_model.build_resolution(plan, resolution_id="history-fixture-rejected", statuses={next(item.content_address for item in plan.actions if item.required): "rejected"})
        return plan, pending, closed, rejected

    def test_append_only_trends_and_value_free_replay(self):
        _, pending, closed, rejected = self._snapshots()
        history = history_model.build_history((pending, closed), history_id="history-fixture")
        self.assertEqual((history.entry_count, history.latest_required_open_count, history.state, history.decision, history.release_ready), (2, 0, "clear", "promote", True))
        self.assertEqual(tuple(item.transition for item in history.entries), ("initial", "improved"))
        self.assertEqual((history.initial_count, history.improved_count, history.regressed_count, history.unchanged_count), (1, 1, 0, 0))
        self.assertEqual(history_model.history_from_mapping(history.to_dict()).content_address, history.content_address)
        blocked = history_model.build_history((pending, closed, rejected), history_id="history-fixture-blocked")
        self.assertEqual((blocked.entries[-1].transition, blocked.state, blocked.decision, blocked.release_ready), ("regressed", "blocked", "block", False))
        with self.assertRaises(ValidationError):
            history_model.build_history((pending, pending), history_id="history-fixture-duplicate")
        forbidden = history.to_dict()
        self.assertNotIn("agent", {str(key).casefold() for key in forbidden})

    def test_independent_audits_bounded_query_and_exact_six_file_runtime(self):
        _, pending, closed, _ = self._snapshots()
        history = history_model.build_history((pending, closed), history_id="history-fixture")
        audit = history_audit_model.audit_history(history)
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (12, 12, True))
        query = history_query_model.query_history(history, resources=("summary", "entries"), transition="improved", limit=1)
        self.assertEqual((query.total_count, query.matched_count, query.returned_count, query.next_offset, query.truncated), (3, 1, 1, 1, False))
        self.assertEqual((query.rows[0].resolution_id, query.rows[0].transition), ("history-fixture-closed", "improved"))
        query_audit = history_query_audit_model.audit_query(query)
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (10, 10, True))
        runtime = history_runtime_model.build_runtime(history, runtime_id="history-fixture-runtime", transition="improved", limit=1)
        self.assertEqual((runtime.entry_count, runtime.latest_required_open_count, runtime.accepted, runtime.release_ready, runtime.state), (2, 0, True, True, "complete"))
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "history-runtime"
            history_runtime_model.persist_runtime(runtime, destination)
            self.assertEqual(tuple(sorted(path.name for path in destination.iterdir())), tuple(sorted(history_runtime_model.FILES)))
            loaded = history_runtime_model.load_runtime(destination)
            self.assertEqual(loaded.content_address, runtime.content_address)
            runtime_audit = history_runtime_audit_model.audit_runtime(loaded)
            self.assertEqual((runtime_audit.check_count, runtime_audit.passed_count, runtime_audit.accepted), (15, 15, True))
            (destination / "history.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                history_runtime_model.load_runtime(destination)

    def test_cli_http_and_public_inventory_expose_history_surfaces(self):
        _, pending, closed, _ = self._snapshots()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            resolutions_path = root / "resolutions.json"
            history_path = root / "history.json"
            query_path = root / "query.json"
            resolutions_path.write_text(json.dumps({"resolutions": [json.loads(resolution_model.resolution_json(pending)), json.loads(resolution_model.resolution_json(closed))]}), encoding="utf-8")
            self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-history", str(resolutions_path), "--history-id", "history-cli", "--format", "json", "--output", str(history_path)]), 0)
            self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-history-query", str(history_path), "--resource", "entries", "--transition", "improved", "--limit", "1", "--format", "json", "--output", str(query_path)]), 0)
            self.assertEqual(json.loads(query_path.read_text(encoding="utf-8"))["returned_count"], 1)
            runtime_dir = root / "runtime"
            runtime_json = root / "runtime.json"
            self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-history-runtime", str(history_path), "--destination", str(runtime_dir), "--format", "json", "--output", str(runtime_json)]), 0)
            self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-history-runtime-audit", str(runtime_dir), "--format", "json"]), 0)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                params = urlencode({"input": str(history_path), "resource": "entries", "transition": "improved", "limit": "1", "format": "summary"})
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/query?{params}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["returned_count"], 1)
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/runtime/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
        inventory = build_default_public_surface_audit()
        self.assertTrue(inventory.accepted)
        self.assertEqual(len(inventory.checks), 1613)
        for schema in (history_model.entry_schema(), history_model.history_schema(), history_audit_model.check_schema(), history_audit_model.audit_schema(), history_query_model.row_schema(), history_query_model.query_schema(), history_query_audit_model.check_schema(), history_query_audit_model.audit_schema(), history_runtime_model.manifest_schema(), history_runtime_model.runtime_schema(), history_runtime_audit_model.check_schema(), history_runtime_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
