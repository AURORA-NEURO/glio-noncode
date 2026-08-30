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
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_audit as resolution_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_query as resolution_query_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_query_audit as resolution_query_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_runtime as resolution_runtime_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_runtime_audit as resolution_runtime_audit_model
from glio_noncode import downloaded_data_profile_contract_diff as diff_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit


class DownloadedDataProfileContractCompatibilityRemediationResolutionTests(unittest.TestCase):
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
        catalog = catalog_model.build_catalog(cls._zip(), catalog_id="resolution-fixture-catalog")
        left_batch = ingestion_model.build_ingest(cls._zip(), batch_id="resolution-fixture-left", record_limit=100)
        selected = tuple(sorted(item.member_name for item in catalog.members if item.member_name.endswith("object.json")))
        right_batch = ingestion_model.build_ingest(cls._zip(), batch_id="resolution-fixture-right", member_names=selected, record_limit=100)
        left = contract_model.build_contract(profile_model.build_profile(left_batch, profile_id="resolution-fixture-left-profile"))
        right = contract_model.build_contract(profile_model.build_profile(right_batch, profile_id="resolution-fixture-right-profile"))
        gate = compatibility_model.evaluate(diff_model.build_diff(left, right, diff_id="resolution-fixture-diff"))
        return remediation_model.build_plan(gate, plan_id="resolution-fixture-plan")

    @staticmethod
    def _assert_public(value: object) -> None:
        forbidden = {"agent", "agent_id", "agent_name", "assistant", "assistant_id", "author", "author_id", "author_name", "email", "language", "model", "model_id", "programming_language"}

        def walk(node: object) -> None:
            if isinstance(node, dict):
                for key, child in node.items():
                    if str(key).casefold() in forbidden:
                        raise AssertionError(f"forbidden public key: {key}")
                    walk(child)
            elif isinstance(node, (tuple, list)):
                for child in node:
                    walk(child)

        walk(value)

    def test_default_resolution_is_review_and_explicit_closure_promotes(self):
        plan = self._plan()
        pending = resolution_model.build_resolution(plan, resolution_id="resolution-fixture-pending")
        self.assertEqual((pending.resolution_count, pending.pending_count, pending.not_applicable_count, pending.required_open_count), (plan.action_count, plan.required_action_count, plan.none_count, plan.required_action_count))
        self.assertEqual((pending.state, pending.decision, pending.accepted, pending.release_ready), ("review", "hold", False, False))
        self.assertEqual(resolution_model.resolution_from_mapping(pending.to_dict()).content_address, pending.content_address)
        audit = resolution_audit_model.audit_resolution(pending)
        self.assertEqual((audit.check_count, audit.passed_count, audit.failed_count, audit.accepted), (12, 12, 0, True))

        statuses = {item.content_address: "resolved" for item in plan.actions if item.required}
        closed = resolution_model.build_resolution(plan, resolution_id="resolution-fixture-closed", statuses=statuses)
        self.assertEqual((closed.required_open_count, closed.pending_count, closed.resolved_count), (0, 0, plan.required_action_count))
        self.assertEqual((closed.state, closed.decision, closed.accepted, closed.release_ready), ("clear", "promote", True, True))
        rejected = resolution_model.build_resolution(plan, resolution_id="resolution-fixture-rejected", statuses={next(item.content_address for item in plan.actions if item.required): "rejected"})
        self.assertEqual((rejected.state, rejected.decision, rejected.accepted), ("blocked", "block", False))
        self._assert_public(closed.to_dict())

    def test_bounded_queries_and_exact_runtime_replay(self):
        plan = self._plan()
        resolution = resolution_model.build_resolution(plan, resolution_id="resolution-query-fixture")
        query = resolution_query_model.query_resolution(resolution, resources=("summary", "entries"), status="pending", required=True, limit=3)
        self.assertEqual((query.total_count, query.matched_count, query.returned_count, query.next_offset, query.truncated), (resolution.resolution_count + 1, resolution.pending_count, 3, 3, True))
        self.assertTrue(all(row.resource == "entries" and row.status == "pending" and row.required for row in query.rows))
        query_audit = resolution_query_audit_model.audit_query(query)
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (12, 12, True))

        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "resolution-runtime"
            runtime = resolution_runtime_model.run_runtime(plan, runtime_id="resolution-fixture-runtime", resolution_id="resolution-query-fixture", resources=("summary", "entries"), status="pending", required=True, limit=3, destination=destination)
            self.assertFalse(runtime.release_ready)
            self.assertEqual(tuple(sorted(path.name for path in destination.iterdir())), tuple(sorted(resolution_runtime_model.FILES)))
            loaded = resolution_runtime_model.load_runtime(destination)
            self.assertEqual(loaded.content_address, runtime.content_address)
            runtime_audit = resolution_runtime_audit_model.audit_runtime(loaded)
            self.assertEqual((runtime_audit.check_count, runtime_audit.passed_count, runtime_audit.accepted), (14, 14, True))
            (destination / "resolution.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                resolution_runtime_model.load_runtime(destination)

    def test_cli_http_and_public_inventory_expose_resolution_surfaces(self):
        plan = self._plan()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan_path = root / "plan.json"
            resolution_path = root / "resolution.json"
            query_path = root / "query.json"
            plan_path.write_text(remediation_model.remediation_json(plan), encoding="utf-8")
            action_address = next(item.content_address for item in plan.actions if item.required)
            self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution", str(plan_path), "--status-update", f"{action_address}=resolved", "--format", "json", "--output", str(resolution_path)]), 2)
            self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-query", str(resolution_path), "--resource", "entries", "--status", "resolved", "--limit", "1", "--format", "json", "--output", str(query_path)]), 0)
            self.assertEqual(json.loads(query_path.read_text(encoding="utf-8"))["returned_count"], 1)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                params = urlencode({"input": str(plan_path), "status_update": f"{action_address}=resolved", "format": "summary"})
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/remediation/resolution?{params}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["resolved_count"], 1)
                query_params = urlencode({"input": str(resolution_path), "resource": "entries", "status": "resolved", "limit": "1", "format": "summary"})
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/query?{query_params}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["returned_count"], 1)
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/runtime/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        audit = build_default_public_surface_audit()
        self.assertTrue(audit.accepted)
        self.assertEqual(len(audit.checks), 1502)
        for schema in (resolution_model.entry_schema(), resolution_model.resolution_schema(), resolution_audit_model.check_schema(), resolution_audit_model.audit_schema(), resolution_query_model.row_schema(), resolution_query_model.query_schema(), resolution_query_audit_model.check_schema(), resolution_query_audit_model.audit_schema(), resolution_runtime_model.manifest_schema(), resolution_runtime_model.runtime_schema(), resolution_runtime_audit_model.check_schema(), resolution_runtime_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self._assert_public(schema)


if __name__ == "__main__":
    unittest.main()
