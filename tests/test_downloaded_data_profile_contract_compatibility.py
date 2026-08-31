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
from glio_noncode import downloaded_data_profile_contract_compatibility_audit as compatibility_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_query as compatibility_query_model
from glio_noncode import downloaded_data_profile_contract_compatibility_query_audit as compatibility_query_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_runtime as compatibility_runtime_model
from glio_noncode import downloaded_data_profile_contract_compatibility_runtime_audit as compatibility_runtime_audit_model
from glio_noncode import downloaded_data_profile_contract_diff as diff_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit


class DownloadedDataProfileContractCompatibilityTests(unittest.TestCase):
    @staticmethod
    def _zip() -> bytes:
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("data/object.json", json.dumps({"id": "object-secret", "ok": True, "score": 4}, separators=(",", ":")))
            archive.writestr("data/rows.json", json.dumps([{"id": "row-secret", "value": 4}, {"id": "row-two", "value": None}], separators=(",", ":")))
            archive.writestr("data/table.csv", "id,value,label\nrow-1,4,alpha-secret\nrow-2,9,beta\n")
        return stream.getvalue()

    @classmethod
    def _contracts(cls):
        catalog = catalog_model.build_catalog(cls._zip(), catalog_id="compatibility-fixture-catalog")
        left_batch = ingestion_model.build_ingest(cls._zip(), batch_id="compatibility-fixture-left", record_limit=100)
        selected = tuple(sorted(item.member_name for item in catalog.members if item.member_name.endswith("object.json")))
        right_batch = ingestion_model.build_ingest(cls._zip(), batch_id="compatibility-fixture-right", member_names=selected, record_limit=100)
        return (
            contract_model.build_contract(profile_model.build_profile(left_batch, profile_id="compatibility-fixture-left-profile")),
            contract_model.build_contract(profile_model.build_profile(right_batch, profile_id="compatibility-fixture-right-profile")),
        )

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

    @staticmethod
    def _permissive_policy() -> compatibility_model.DownloadedDataProfileContractCompatibilityPolicy:
        provisional = compatibility_model.DownloadedDataProfileContractCompatibilityPolicy(
            "compatibility-fixture-permissive",
            compatibility_model.OUTCOMES,
            compatibility_model.MAX_FINDINGS,
            compatibility_model.MAX_FINDINGS,
            diff_model.RESOURCES,
            True,
            True,
            False,
            compatibility_model.POLICY_PREFIX + ":pending",
        )
        return compatibility_model.DownloadedDataProfileContractCompatibilityPolicy(
            provisional.policy_id,
            provisional.allowed_outcomes,
            provisional.maximum_review_findings,
            provisional.maximum_breaking_findings,
            provisional.allowed_resources,
            provisional.require_diff_audit,
            provisional.require_diff_query_audit,
            provisional.require_complete_diff_query,
            compatibility_model.address_policy(provisional),
        )

    def test_policy_classification_and_gate_conserve_structural_findings(self):
        left, right = self._contracts()
        diff = diff_model.build_diff(left, right, diff_id="compatibility-fixture-diff")
        policy = compatibility_model.default_policy(policy_id="compatibility-fixture-policy")
        self.assertEqual(compatibility_model.default_policy().content_address, compatibility_model.address_policy(compatibility_model.default_policy()))
        self.assertEqual(compatibility_model.DownloadedDataProfileContractCompatibilityPolicy.from_mapping(policy.to_dict()).content_address, policy.content_address)
        self.assertEqual(len(diff.items), len(compatibility_model.evaluate(diff, policy=policy).findings))
        gate = compatibility_model.evaluate(diff, policy=policy)
        self.assertFalse(gate.accepted)
        self.assertEqual(gate.state, "blocked")
        self.assertEqual(gate.decision, "block")
        self.assertEqual((gate.finding_count, gate.safe_count + gate.review_count + gate.breaking_count), (len(diff.items), len(diff.items)))
        self.assertGreater(gate.breaking_count, 0)
        self.assertGreater(gate.review_count, 0)
        self.assertEqual(compatibility_model.compatibility_from_mapping(gate.to_dict()).content_address, gate.content_address)
        self._assert_public(gate.to_dict())

        permissive = compatibility_model.evaluate(diff, policy=self._permissive_policy(), gate_id="compatibility-fixture-permissive-gate")
        self.assertTrue(permissive.accepted)
        self.assertEqual((permissive.state, permissive.decision), ("eligible", "promote"))

    def test_independent_audits_queries_and_exact_runtime_replay(self):
        left, right = self._contracts()
        diff = diff_model.build_diff(left, right, diff_id="compatibility-runtime-diff")
        gate = compatibility_model.evaluate(diff)
        audit = compatibility_audit_model.audit_gate(gate)
        self.assertEqual((audit.check_count, audit.passed_count, audit.failed_count, audit.accepted), (15, 15, 0, True))
        query = compatibility_query_model.query_gate(gate, resources=("summary", "findings"), outcome="breaking", limit=1)
        self.assertEqual(query.returned_count, 1)
        self.assertTrue(query.truncated)
        self.assertTrue(all(row.resource == "findings" and row.outcome == "breaking" for row in query.rows))
        query_audit = compatibility_query_audit_model.audit_query(query)
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (11, 11, True))
        self.assertEqual(compatibility_query_model.query_from_mapping(query.to_dict()).content_address, query.content_address)
        self._assert_public(query.to_dict())

        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "compatibility-runtime"
            runtime = compatibility_runtime_model.run_runtime(diff, resources=("summary", "findings"), limit=3, destination=destination)
            self.assertFalse(runtime.release_ready)
            self.assertEqual(tuple(sorted(path.name for path in destination.iterdir())), tuple(sorted(compatibility_runtime_model.FILES)))
            loaded = compatibility_runtime_model.load_runtime(destination)
            self.assertEqual(loaded.content_address, runtime.content_address)
            runtime_audit = compatibility_runtime_audit_model.audit_runtime(loaded)
            self.assertEqual((runtime_audit.check_count, runtime_audit.passed_count, runtime_audit.accepted), (13, 13, True))
            (destination / "gate.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                compatibility_runtime_model.load_runtime(destination)

    def test_cli_and_http_expose_compatibility_and_schema_surfaces(self):
        left, right = self._contracts()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left_path = root / "left.json"
            right_path = root / "right.json"
            diff_path = root / "diff.json"
            gate_path = root / "gate.json"
            query_path = root / "query.json"
            audit_path = root / "audit.json"
            left_path.write_text(contract_model.contract_json(left), encoding="utf-8")
            right_path.write_text(contract_model.contract_json(right), encoding="utf-8")
            self.assertEqual(main(["downloaded-data-profile-contract-diff", str(left_path), str(right_path), "--format", "json", "--output", str(diff_path)]), 0)
            self.assertEqual(main(["downloaded-data-profile-contract-compatibility", str(diff_path), "--format", "json", "--output", str(gate_path)]), 2)
            self.assertEqual(main(["downloaded-data-profile-contract-compatibility-query", str(gate_path), "--resource", "findings", "--outcome", "breaking", "--limit", "2", "--format", "json", "--output", str(query_path)]), 0)
            self.assertEqual(main(["downloaded-data-profile-contract-compatibility-audit", str(gate_path), "--format", "json", "--output", str(audit_path)]), 0)
            self.assertTrue(json.loads(gate_path.read_text(encoding="utf-8"))["breaking_count"] > 0)
            self.assertTrue(json.loads(query_path.read_text(encoding="utf-8"))["returned_count"] > 0)
            self.assertTrue(json.loads(audit_path.read_text(encoding="utf-8"))["accepted"])

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                params = {"input": str(diff_path), "format": "summary"}
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility?{urlencode(params)}", timeout=30) as response:
                    http_gate = json.loads(response.read())
                self.assertEqual(http_gate["diff_address"], json.loads(gate_path.read_text(encoding="utf-8"))["diff_address"])
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/query?{urlencode({'input': str(gate_path), 'resource': 'findings', 'outcome': 'breaking', 'limit': '2', 'format': 'summary'})}", timeout=30) as response:
                    self.assertGreater(json.loads(response.read())["returned_count"], 0)
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["$schema"], "https://json-schema.org/draft/2020-12/schema")
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/runtime/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_public_inventory_registers_the_compatibility_plane(self):
        audit = build_default_public_surface_audit()
        self.assertTrue(audit.accepted)
        self.assertEqual(len(audit.checks), 1845)
        for schema in (
            compatibility_model.policy_schema(), compatibility_model.finding_schema(), compatibility_model.compatibility_schema(),
            compatibility_audit_model.check_schema(), compatibility_audit_model.audit_schema(),
            compatibility_query_model.row_schema(), compatibility_query_model.query_schema(),
            compatibility_query_audit_model.check_schema(), compatibility_query_audit_model.audit_schema(),
            compatibility_runtime_model.manifest_schema(), compatibility_runtime_model.runtime_schema(),
            compatibility_runtime_audit_model.check_schema(), compatibility_runtime_audit_model.audit_schema(),
        ):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self._assert_public(schema)


if __name__ == "__main__":
    unittest.main()
