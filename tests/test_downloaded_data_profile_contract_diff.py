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
from glio_noncode import downloaded_data_profile_contract_diff as diff_model
from glio_noncode import downloaded_data_profile_contract_diff_audit as diff_audit_model
from glio_noncode import downloaded_data_profile_contract_diff_query as diff_query_model
from glio_noncode import downloaded_data_profile_contract_diff_query_audit as diff_query_audit_model
from glio_noncode import downloaded_data_profile_contract_diff_runtime as diff_runtime_model
from glio_noncode import downloaded_data_profile_contract_diff_runtime_audit as diff_runtime_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit


class DownloadedDataProfileContractDiffTests(unittest.TestCase):
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
        catalog = catalog_model.build_catalog(cls._zip(), catalog_id="diff-fixture-catalog")
        all_batch = ingestion_model.build_ingest(cls._zip(), batch_id="diff-fixture-left", record_limit=100)
        subset = tuple(sorted(item.member_name for item in catalog.members if item.member_name.endswith("object.json")))
        right_batch = ingestion_model.build_ingest(cls._zip(), batch_id="diff-fixture-right", member_names=subset, record_limit=100)
        return (
            contract_model.build_contract(profile_model.build_profile(all_batch, profile_id="diff-fixture-left-profile")),
            contract_model.build_contract(profile_model.build_profile(right_batch, profile_id="diff-fixture-right-profile")),
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

    def test_diff_replays_added_removed_changed_and_unchanged_rows(self):
        left, right = self._contracts()
        value = diff_model.build_diff(left, right)
        self.assertGreater(value.field_removed_count, 0)
        self.assertGreater(value.field_changed_count, 0)
        self.assertGreater(value.member_removed_count, 0)
        self.assertGreater(value.member_unchanged_count, 0)
        self.assertEqual(value.left_field_count, value.field_removed_count + value.field_changed_count + value.field_unchanged_count)
        self.assertEqual(value.right_field_count, value.field_added_count + value.field_changed_count + value.field_unchanged_count)
        self.assertEqual(diff_model.diff_from_mapping(value.to_dict()).content_address, value.content_address)
        serialized = diff_model.diff_json(value)
        for source_value in ("object-secret", "row-secret", "alpha-secret"):
            self.assertNotIn(source_value, serialized)
        self._assert_public(value.to_dict())

    def test_diff_audit_and_query_audit_are_independent_and_value_free(self):
        left, right = self._contracts()
        diff = diff_model.build_diff(left, right)
        diff_audit = diff_audit_model.audit_diff(diff)
        self.assertEqual((diff_audit.check_count, diff_audit.passed_count, diff_audit.failed_count, diff_audit.accepted), (12, 12, 0, True))
        query = diff_query_model.query_diff(diff, resources=("summary", "fields"), change="removed", limit=1)
        self.assertEqual(query.returned_count, 1)
        self.assertTrue(query.truncated)
        self.assertTrue(all(row.resource == "fields" and row.change == "removed" for row in query.rows))
        query_audit = diff_query_audit_model.audit_query(query)
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (10, 10, True))
        self.assertEqual(diff_query_model.query_from_mapping(query.to_dict()).content_address, query.content_address)
        self._assert_public(query.to_dict())

    def test_runtime_persists_exact_files_and_rejects_tampering(self):
        left, right = self._contracts()
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "diff-runtime"
            runtime = diff_runtime_model.run_runtime(left, right, limit=4, destination=destination)
            self.assertTrue(runtime.release_ready)
            self.assertEqual(tuple(sorted(path.name for path in destination.iterdir())), tuple(sorted(diff_runtime_model.FILES)))
            self.assertEqual(diff_runtime_model.load_runtime(destination).content_address, runtime.content_address)
            runtime_audit = diff_runtime_audit_model.audit_runtime(runtime)
            self.assertEqual((runtime_audit.check_count, runtime_audit.passed_count, runtime_audit.accepted), (13, 13, True))
            (destination / "diff.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                diff_runtime_model.load_runtime(destination)

    def test_cli_and_http_expose_the_same_diff_runtime(self):
        left, right = self._contracts()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left_path = root / "left.json"
            right_path = root / "right.json"
            left_path.write_text(contract_model.contract_json(left), encoding="utf-8")
            right_path.write_text(contract_model.contract_json(right), encoding="utf-8")
            diff_path = root / "diff.json"
            query_path = root / "query.json"
            audit_path = root / "audit.json"
            self.assertEqual(main(["downloaded-data-profile-contract-diff", str(left_path), str(right_path), "--format", "json", "--output", str(diff_path)]), 0)
            self.assertEqual(main(["downloaded-data-profile-contract-diff-query", str(diff_path), "--resource", "fields", "--change", "removed", "--limit", "1", "--format", "json", "--output", str(query_path)]), 0)
            self.assertEqual(main(["downloaded-data-profile-contract-diff-audit", str(diff_path), "--format", "json", "--output", str(audit_path)]), 0)
            payload = json.loads(diff_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["left_field_count"], left.field_count)
            self.assertTrue(json.loads(query_path.read_text(encoding="utf-8"))["truncated"])
            self.assertTrue(json.loads(audit_path.read_text(encoding="utf-8"))["accepted"])
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                params = {"left_input": str(left_path), "right_input": str(right_path), "format": "summary"}
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/diff?{urlencode(params)}", timeout=30) as response:
                    http_diff = json.loads(response.read())
                self.assertEqual((http_diff["left_field_count"], http_diff["right_field_count"]), (left.field_count, right.field_count))
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/diff/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_public_inventory_includes_the_complete_diff_plane(self):
        audit = build_default_public_surface_audit()
        self.assertTrue(audit.accepted)
        self.assertEqual(len(audit.checks), 1860)
        for schema in (diff_model.item_schema(), diff_model.diff_schema(), diff_audit_model.check_schema(), diff_audit_model.audit_schema(), diff_query_model.row_schema(), diff_query_model.query_schema(), diff_query_audit_model.check_schema(), diff_query_audit_model.audit_schema(), diff_runtime_model.manifest_schema(), diff_runtime_model.runtime_schema(), diff_runtime_audit_model.check_schema(), diff_runtime_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self._assert_public(schema)


if __name__ == "__main__":
    unittest.main()
