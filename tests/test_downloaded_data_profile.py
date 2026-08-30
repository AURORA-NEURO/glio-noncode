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
from glio_noncode import downloaded_data_profile_audit as profile_audit_model
from glio_noncode import downloaded_data_profile_query as profile_query_model
from glio_noncode import downloaded_data_profile_query_audit as profile_query_audit_model
from glio_noncode import downloaded_data_profile_runtime as profile_runtime_model
from glio_noncode import downloaded_data_profile_runtime_audit as profile_runtime_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError


class DownloadedDataProfileTests(unittest.TestCase):
    @staticmethod
    def _zip(*, empty: bool = False) -> bytes:
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("data/object.json", json.dumps({"id": "object-1", "ok": True, "score": 4.5}, separators=(",", ":")))
            archive.writestr("data/rows.json", "[]" if empty else json.dumps([{"id": "row-1", "value": 4}, {"id": "row-2", "value": None}], separators=(",", ":")))
            archive.writestr("data/table.csv", "id,value,label\nrow-1,4,alpha\nrow-2,9,beta\n")
            archive.writestr("docs/notes.md", "not a structured data member")
        return stream.getvalue()

    @staticmethod
    def _batch(raw: bytes | None = None) -> ingestion_model.DownloadedDataIngestBatch:
        return ingestion_model.build_ingest(raw or DownloadedDataProfileTests._zip(), batch_id="profile-fixture-batch", record_limit=100)

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

    def test_profile_is_value_free_and_conserves_real_record_facts(self):
        batch = self._batch()
        profile = profile_model.build_profile(batch, profile_id="profile-fixture")
        self.assertEqual((profile.record_count, profile.member_count, profile.field_count), (batch.record_count, 3, 5))
        self.assertGreater(profile.total_value_bytes, 0)
        self.assertTrue(all(item.content_address.startswith(profile_model.FIELD_PREFIX) for item in profile.fields))
        serialized = profile_model.profile_json(profile)
        self.assertNotIn("object-1", serialized)
        self.assertNotIn("row-1", serialized)
        self._assert_public(profile.to_dict())
        self.assertEqual(profile_model.profile_from_mapping(profile.to_dict()).content_address, profile.content_address)

    def test_fixed_audit_query_and_zero_count_type_rows(self):
        profile = profile_model.build_profile(self._batch(), profile_id="audit-query-fixture")
        audit = profile_audit_model.audit_profile(profile)
        self.assertEqual((audit.check_count, audit.passed_count, audit.failed_count, audit.accepted), (12, 12, 0, True))
        query = profile_query_model.query_profile(profile, resources=("summary", "members", "fields", "types"), limit=1000)
        self.assertGreaterEqual(query.returned_count, profile.member_count + profile.field_count + 1)
        self.assertTrue(any(row.resource == "types" and row.count == 0 for row in query.rows))
        query_audit = profile_query_audit_model.audit_query(query)
        self.assertTrue(query_audit.accepted)
        self.assertEqual(profile_query_model.query_from_mapping(query.to_dict()).content_address, query.content_address)
        self.assertEqual(profile_query_audit_model.audit_from_mapping(query_audit.to_dict()).content_address, query_audit.content_address)

    def test_empty_profile_has_a_valid_zero_summary(self):
        profile = profile_model.build_profile(self._batch(self._zip(empty=True)), profile_id="empty-profile")
        query = profile_query_model.query_profile(profile, resources=("summary",), limit=10)
        self.assertEqual((profile.record_count, profile.member_count, profile.field_count, query.returned_count), (3, 2, 5, 1))
        self.assertTrue(profile_query_audit_model.audit_query(query).accepted)

    def test_runtime_persists_exact_files_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = profile_runtime_model.run_runtime(self._batch(), runtime_id="profile-runtime-fixture", limit=200, destination=root / "profile-runtime")
            self.assertTrue(runtime.release_ready)
            self.assertEqual(tuple(sorted(path.name for path in (root / "profile-runtime").iterdir())), tuple(sorted(profile_runtime_model.FILES)))
            loaded = profile_runtime_model.load_runtime(root / "profile-runtime")
            self.assertEqual(loaded.content_address, runtime.content_address)
            runtime_audit = profile_runtime_audit_model.audit_runtime(loaded)
            self.assertEqual((runtime_audit.check_count, runtime_audit.passed_count, runtime_audit.accepted), (12, 12, True))
            self.assertEqual(profile_runtime_audit_model.audit_from_mapping(runtime_audit.to_dict()).content_address, runtime_audit.content_address)
            (root / "profile-runtime" / "profile.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                profile_runtime_model.load_runtime(root / "profile-runtime")

    def test_cli_and_http_profile_surfaces_share_the_runtime_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "download.zip"
            source.write_bytes(self._zip())
            ingest_runtime = root / "ingest-runtime"
            profile_runtime = root / "profile-runtime"
            profile_json = root / "profile.json"
            query_json = root / "query.json"
            audit_json = root / "audit.json"
            self.assertEqual(main(["downloaded-data-ingest", str(source), "--resource", "summary", "--resource", "records", "--destination", str(ingest_runtime), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-profile-runtime", str(ingest_runtime), "--destination", str(profile_runtime), "--format", "json", "--output", str(profile_json)]), 0)
            self.assertEqual(main(["downloaded-data-profile-query", str(profile_runtime), "--resource", "fields", "--limit", "4", "--format", "json", "--output", str(query_json)]), 0)
            self.assertEqual(main(["downloaded-data-profile-audit", str(profile_runtime), "--format", "json", "--output", str(audit_json)]), 0)
            self.assertEqual(main(["downloaded-data-profile-runtime-audit", str(profile_runtime), "--format", "json", "--output", str(root / "runtime-audit.json")]), 0)
            self.assertTrue(json.loads(audit_json.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(json.loads(profile_json.read_text(encoding="utf-8"))["field_count"], 5)
            self.assertEqual(json.loads(query_json.read_text(encoding="utf-8"))["returned_count"], 4)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                params = [("input", str(ingest_runtime)), ("resource", "summary"), ("resource", "fields"), ("limit", "4"), ("format", "summary")]
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/runtime?{urlencode(params)}", timeout=30) as response:
                    payload = json.loads(response.read())
                self.assertEqual((payload["record_count"], payload["field_count"], payload["query_returned_count"]), (5, 5, 4))
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_unknown_fields_and_public_schemas_fail_closed(self):
        profile = profile_model.build_profile(self._batch(), profile_id="tamper-profile")
        altered = profile.to_dict()
        altered["unknown"] = True
        with self.assertRaises(ValidationError):
            profile_model.profile_from_mapping(altered)
        for schema in (
            profile_model.type_count_schema(), profile_model.shape_count_schema(), profile_model.field_schema(), profile_model.member_schema(), profile_model.profile_schema(),
            profile_audit_model.check_schema(), profile_audit_model.audit_schema(), profile_query_model.row_schema(), profile_query_model.query_schema(),
            profile_query_audit_model.check_schema(), profile_query_audit_model.audit_schema(), profile_runtime_model.manifest_schema(), profile_runtime_model.runtime_schema(),
            profile_runtime_audit_model.check_schema(), profile_runtime_audit_model.audit_schema(),
        ):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self._assert_public(schema)


if __name__ == "__main__":
    unittest.main()
