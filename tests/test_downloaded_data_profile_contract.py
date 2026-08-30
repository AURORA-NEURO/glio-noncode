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

from glio_noncode import downloaded_data_ingestion as ingestion_model
from glio_noncode import downloaded_data_profile as profile_model
from glio_noncode import downloaded_data_profile_contract as contract_model
from glio_noncode import downloaded_data_profile_contract_audit as contract_audit_model
from glio_noncode import downloaded_data_profile_contract_query as contract_query_model
from glio_noncode import downloaded_data_profile_contract_query_audit as contract_query_audit_model
from glio_noncode import downloaded_data_profile_contract_runtime as contract_runtime_model
from glio_noncode import downloaded_data_profile_contract_runtime_audit as contract_runtime_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError


class DownloadedDataProfileContractTests(unittest.TestCase):
    @staticmethod
    def _zip() -> bytes:
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("data/object.json", json.dumps({"id": "object-1", "ok": True, "score": 4.5}, separators=(",", ":")))
            archive.writestr("data/rows.json", json.dumps([{"id": "row-1", "value": 4}, {"id": "row-2", "value": None}], separators=(",", ":")))
            archive.writestr("data/table.csv", "id,value,label\nrow-1,4,alpha\nrow-2,9,beta\n")
            archive.writestr("docs/notes.md", "not a structured data member")
        return stream.getvalue()

    @classmethod
    def _batch(cls) -> ingestion_model.DownloadedDataIngestBatch:
        return ingestion_model.build_ingest(cls._zip(), batch_id="contract-fixture-batch", record_limit=100)

    @classmethod
    def _profile(cls) -> profile_model.DownloadedDataProfile:
        return profile_model.build_profile(cls._batch(), profile_id="contract-fixture-profile")

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

    def test_contract_is_value_free_and_member_local(self):
        contract = contract_model.build_contract(self._profile())
        self.assertEqual((contract.record_count, contract.member_count, contract.field_count), (5, 3, 5))
        self.assertEqual(contract.required_field_count + contract.optional_field_count, contract.field_count)
        self.assertEqual(tuple(item.field_name for item in contract.fields), tuple(sorted(item.field_name for item in contract.fields)))
        self.assertTrue(any(item.state == "sparse" for item in contract.fields))
        self.assertTrue(any(item.state == "mixed" for item in contract.fields))
        self.assertTrue(all(item.required_field_count + item.optional_field_count == item.field_count for item in contract.members))
        self.assertTrue(all(set(item.required_field_names).union(item.optional_field_names) == set(item.field_names) for item in contract.members))
        serialized = contract_model.contract_json(contract)
        for source_value in ("object-1", "row-1", "alpha"):
            self.assertNotIn(source_value, serialized)
        self._assert_public(contract.to_dict())
        self.assertEqual(contract_model.contract_from_mapping(contract.to_dict()).content_address, contract.content_address)

    def test_contract_audit_recomputes_nested_addresses(self):
        contract = contract_model.build_contract(self._profile())
        audit = contract_audit_model.audit_contract(contract)
        self.assertEqual((audit.check_count, audit.passed_count, audit.failed_count, audit.accepted), (12, 12, 0, True))
        self.assertEqual(contract_audit_model.audit_from_mapping(audit.to_dict()).content_address, audit.content_address)
        self.assertIn("member-local required", contract_audit_model.render_audit_markdown(audit))

    def test_query_filters_schema_drift_and_pagination(self):
        contract = contract_model.build_contract(self._profile())
        query = contract_query_model.query_contract(contract, resources=("fields", "issues"), state="sparse", limit=1)
        self.assertEqual(query.returned_count, 1)
        self.assertTrue(query.truncated)
        self.assertTrue(all(row.resource in {"fields", "issues"} and row.state == "sparse" for row in query.rows))
        self.assertTrue(contract_query_audit_model.audit_query(query).accepted)
        all_issues = contract_query_model.query_contract(contract, resources=("issues",), limit=100)
        self.assertTrue(all(row.issue in {"sparse-field", "mixed-field"} for row in all_issues.rows))
        self.assertEqual(contract_query_model.query_from_mapping(all_issues.to_dict()).content_address, all_issues.content_address)

    def test_contract_runtime_persists_exact_files_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = contract_runtime_model.run_runtime(self._batch(), profile_id="contract-fixture-profile", runtime_id="contract-runtime-fixture", limit=1000, destination=root / "runtime")
            self.assertTrue(runtime.release_ready)
            self.assertEqual(tuple(sorted(path.name for path in (root / "runtime").iterdir())), tuple(sorted(contract_runtime_model.FILES)))
            loaded = contract_runtime_model.load_runtime(root / "runtime")
            self.assertEqual(loaded.content_address, runtime.content_address)
            runtime_audit = contract_runtime_audit_model.audit_runtime(loaded)
            self.assertEqual((runtime_audit.check_count, runtime_audit.passed_count, runtime_audit.accepted), (13, 13, True))
            (root / "runtime" / "contract.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                contract_runtime_model.load_runtime(root / "runtime")

    def test_cli_and_http_contract_surfaces_share_the_runtime_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "download.zip"
            source.write_bytes(self._zip())
            ingest_runtime = root / "ingest-runtime"
            contract_runtime = root / "contract-runtime"
            contract_json = root / "contract.json"
            query_json = root / "query.json"
            audit_json = root / "audit.json"
            contract_audit_json = root / "contract-audit.json"
            query_audit_json = root / "query-audit.json"
            self.assertEqual(main(["downloaded-data-ingest", str(source), "--resource", "summary", "--resource", "records", "--destination", str(ingest_runtime), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-profile-contract-runtime", str(ingest_runtime), "--destination", str(contract_runtime), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-profile-contract", str(contract_runtime), "--format", "json", "--output", str(contract_json)]), 0)
            self.assertEqual(main(["downloaded-data-profile-contract-query", str(contract_runtime), "--resource", "issues", "--state", "sparse", "--limit", "4", "--format", "json", "--output", str(query_json)]), 0)
            self.assertEqual(main(["downloaded-data-profile-contract-audit", str(contract_runtime), "--format", "json", "--output", str(contract_audit_json)]), 0)
            self.assertEqual(main(["downloaded-data-profile-contract-query-audit", str(query_json), "--format", "json", "--output", str(query_audit_json)]), 0)
            self.assertEqual(main(["downloaded-data-profile-contract-runtime-audit", str(contract_runtime), "--format", "json", "--output", str(audit_json)]), 0)
            self.assertTrue(json.loads(audit_json.read_text(encoding="utf-8"))["accepted"])
            self.assertTrue(json.loads(contract_audit_json.read_text(encoding="utf-8"))["accepted"])
            self.assertTrue(json.loads(query_audit_json.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(json.loads(contract_json.read_text(encoding="utf-8"))["field_count"], 5)
            self.assertLessEqual(json.loads(query_json.read_text(encoding="utf-8"))["returned_count"], 4)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                params = [("input", str(ingest_runtime)), ("resource", "summary"), ("resource", "issues"), ("limit", "4"), ("format", "summary")]
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/runtime?{urlencode(params)}", timeout=30) as response:
                    payload = json.loads(response.read())
                self.assertEqual((payload["record_count"], payload["field_count"], payload["release_ready"]), (5, 5, True))
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract?{urlencode({'input': str(contract_runtime), 'format': 'summary'})}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["content_address"], json.loads(contract_json.read_text(encoding="utf-8"))["content_address"])
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_unknown_fields_and_public_schemas_fail_closed(self):
        contract = contract_model.build_contract(self._profile())
        altered = contract.to_dict()
        altered["unknown"] = True
        with self.assertRaises(ValidationError):
            contract_model.contract_from_mapping(altered)
        for schema in (
            contract_model.type_schema(), contract_model.field_schema(), contract_model.member_schema(), contract_model.contract_schema(),
            contract_audit_model.check_schema(), contract_audit_model.audit_schema(), contract_query_model.row_schema(), contract_query_model.query_schema(),
            contract_query_audit_model.check_schema(), contract_query_audit_model.audit_schema(), contract_runtime_model.manifest_schema(), contract_runtime_model.runtime_schema(),
            contract_runtime_audit_model.check_schema(), contract_runtime_audit_model.audit_schema(),
        ):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self._assert_public(schema)


if __name__ == "__main__":
    unittest.main()
