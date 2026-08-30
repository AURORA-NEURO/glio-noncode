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
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_audit as remediation_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_query as remediation_query_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_query_audit as remediation_query_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_runtime as remediation_runtime_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_runtime_audit as remediation_runtime_audit_model
from glio_noncode import downloaded_data_profile_contract_diff as diff_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit


class DownloadedDataProfileContractCompatibilityRemediationTests(unittest.TestCase):
    @staticmethod
    def _zip() -> bytes:
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("data/object.json", json.dumps({"id": "object-secret", "ok": True, "score": 4}, separators=(",", ":")))
            archive.writestr("data/rows.json", json.dumps([{"id": "row-secret", "value": 4}, {"id": "row-two", "value": None}], separators=(",", ":")))
            archive.writestr("data/table.csv", "id,value,label\nrow-1,4,alpha-secret\nrow-2,9,beta\n")
        return stream.getvalue()

    @classmethod
    def _gate(cls):
        catalog = catalog_model.build_catalog(cls._zip(), catalog_id="remediation-fixture-catalog")
        left_batch = ingestion_model.build_ingest(cls._zip(), batch_id="remediation-fixture-left", record_limit=100)
        selected = tuple(sorted(item.member_name for item in catalog.members if item.member_name.endswith("object.json")))
        right_batch = ingestion_model.build_ingest(cls._zip(), batch_id="remediation-fixture-right", member_names=selected, record_limit=100)
        left = contract_model.build_contract(profile_model.build_profile(left_batch, profile_id="remediation-fixture-left-profile"))
        right = contract_model.build_contract(profile_model.build_profile(right_batch, profile_id="remediation-fixture-right-profile"))
        return compatibility_model.evaluate(diff_model.build_diff(left, right, diff_id="remediation-fixture-diff"))

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

    def test_plan_classifies_and_conserves_every_gate_finding(self):
        gate = self._gate()
        plan = remediation_model.build_plan(gate, plan_id="remediation-fixture-plan")
        self.assertEqual(plan.action_count, gate.finding_count)
        self.assertEqual(plan.required_action_count, plan.action_count - plan.none_count)
        self.assertEqual(sum(getattr(plan, f"{action}_count") for action in remediation_model.ACTION_KINDS), plan.action_count)
        self.assertEqual((plan.state, plan.decision, plan.accepted), ("blocked", "block", False))
        self.assertTrue(any(item.action == "restore" for item in plan.actions))
        self.assertTrue(any(item.action == "repair" for item in plan.actions))
        self.assertTrue(all(item.required for item in plan.actions if item.outcome != "safe"))
        self.assertEqual(remediation_model.plan_from_mapping(plan.to_dict()).content_address, plan.content_address)
        self._assert_public(plan.to_dict())

    def test_independent_audits_query_filters_and_runtime_replay(self):
        plan = remediation_model.build_plan(self._gate(), plan_id="remediation-runtime-plan")
        plan_audit = remediation_audit_model.audit_plan(plan)
        self.assertEqual((plan_audit.check_count, plan_audit.passed_count, plan_audit.failed_count, plan_audit.accepted), (14, 14, 0, True))
        query = remediation_query_model.query_plan(plan, resources=("summary", "actions"), action="restore", required=True, limit=1)
        self.assertEqual(query.returned_count, 1)
        self.assertTrue(query.truncated)
        self.assertTrue(all(row.resource == "actions" and row.action == "restore" and row.required for row in query.rows))
        query_audit = remediation_query_audit_model.audit_query(query)
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (12, 12, True))
        self.assertEqual(remediation_query_model.query_from_mapping(query.to_dict()).content_address, query.content_address)
        self._assert_public(query.to_dict())

        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "remediation-runtime"
            runtime = remediation_runtime_model.run_runtime(self._gate(), runtime_id="remediation-fixture-runtime", plan_id="remediation-runtime-plan", resources=("summary", "actions"), limit=3, destination=destination)
            self.assertFalse(runtime.release_ready)
            self.assertEqual(tuple(sorted(path.name for path in destination.iterdir())), tuple(sorted(remediation_runtime_model.FILES)))
            loaded = remediation_runtime_model.load_runtime(destination)
            self.assertEqual(loaded.content_address, runtime.content_address)
            runtime_audit = remediation_runtime_audit_model.audit_runtime(loaded)
            self.assertEqual((runtime_audit.check_count, runtime_audit.passed_count, runtime_audit.accepted), (14, 14, True))
            (destination / "plan.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                remediation_runtime_model.load_runtime(destination)

    def test_cli_http_and_public_inventory_expose_the_plane(self):
        gate = self._gate()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            gate_path = root / "gate.json"
            plan_path = root / "plan.json"
            query_path = root / "query.json"
            gate_path.write_text(compatibility_model.compatibility_json(gate), encoding="utf-8")
            self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation", str(gate_path), "--format", "json", "--output", str(plan_path)]), 2)
            self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-query", str(plan_path), "--resource", "actions", "--action", "restore", "--limit", "1", "--format", "json", "--output", str(query_path)]), 0)
            self.assertEqual(json.loads(query_path.read_text(encoding="utf-8"))["returned_count"], 1)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                params = urlencode({"input": str(gate_path), "format": "summary"})
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/remediation?{params}", timeout=30) as response:
                    http_plan = json.loads(response.read())
                self.assertEqual(http_plan["action_count"], json.loads(plan_path.read_text(encoding="utf-8"))["action_count"])
                query_params = urlencode({"input": str(plan_path), "resource": "actions", "action": "restore", "limit": "1", "format": "summary"})
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/remediation/query?{query_params}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["returned_count"], 1)
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/remediation/runtime/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        audit = build_default_public_surface_audit()
        self.assertTrue(audit.accepted)
        self.assertEqual(len(audit.checks), 1291)
        for schema in (remediation_model.action_schema(), remediation_model.plan_schema(), remediation_audit_model.check_schema(), remediation_audit_model.audit_schema(), remediation_query_model.row_schema(), remediation_query_model.query_schema(), remediation_query_audit_model.check_schema(), remediation_query_audit_model.audit_schema(), remediation_runtime_model.manifest_schema(), remediation_runtime_model.runtime_schema(), remediation_runtime_audit_model.check_schema(), remediation_runtime_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self._assert_public(schema)


if __name__ == "__main__":
    unittest.main()
