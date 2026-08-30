"""Deep tests for downloaded-data ingestion, replay, query, and diff contracts."""

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
from glio_noncode import downloaded_data_ingestion_audit as ingestion_audit_model
from glio_noncode import downloaded_data_ingestion_diff as diff_model
from glio_noncode import downloaded_data_ingestion_diff_audit as diff_audit_model
from glio_noncode import downloaded_data_ingestion_diff_query as diff_query_model
from glio_noncode import downloaded_data_ingestion_diff_query_audit as diff_query_audit_model
from glio_noncode import downloaded_data_ingestion_query as query_model
from glio_noncode import downloaded_data_ingestion_query_audit as query_audit_model
from glio_noncode import downloaded_data_ingestion_runtime as runtime_model
from glio_noncode import downloaded_data_ingestion_runtime_audit as runtime_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError


class DownloadedDataIngestionTests(unittest.TestCase):
    @staticmethod
    def _zip(*, changed: bool = False) -> bytes:
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("data/object.json", json.dumps({"id": "object-1", "kind": "fixture", "count": 2}, separators=(",", ":")))
            archive.writestr("data/rows.json", json.dumps([{"id": "row-1", "value": 4}, {"id": "row-2", "value": 9 if not changed else 10}], separators=(",", ":")))
            archive.writestr("data/events.jsonl", '{"event":"start","ok":true}\n\n{"event":"finish","ok":true}\n')
            archive.writestr("data/table.csv", "id,value\nrow-1,4\nrow-2,9\n")
            archive.writestr("data/table.tsv", "id\tlabel\nrow-1\talpha\n")
            archive.writestr("data/config.yaml", "version: 1\nfeatures:\n  - intake\n  - review\n")
            archive.writestr("docs/notes.md", "not data")
            archive.writestr("src/ignored.json", '{"ignored":true}')
        return stream.getvalue()

    @staticmethod
    def _catalog(raw: bytes) -> catalog_model.DownloadedDataCatalog:
        return catalog_model.build_catalog(raw, catalog_id="ingestion-fixture-catalog")

    def test_ingest_preserves_values_and_lineage_across_formats(self):
        raw = self._zip()
        catalog = self._catalog(raw)
        batch = ingestion_model.build_ingest(raw, catalog=catalog, batch_id="ingestion-fixture-batch", record_limit=100)
        self.assertEqual((batch.selected_member_count, batch.available_record_count, batch.record_count, batch.dropped_record_count, batch.state), (6, 9, 9, 0, "complete"))
        self.assertEqual(tuple(item.ordinal for item in batch.records), tuple(range(1, 10)))
        object_record = next(item for item in batch.records if item.lineage.member_name.endswith("object.json"))
        self.assertEqual(object_record.value["id"], "object-1")
        table_records = tuple(item for item in batch.records if item.lineage.member_name.endswith("table.csv"))
        self.assertEqual((len(table_records), table_records[0].fields, table_records[0].lineage.source_row), (2, ("id", "value"), 2))
        self.assertTrue(all(item.lineage.catalog_address == catalog.content_address for item in batch.records))
        self.assertEqual(ingestion_model.ingest_from_mapping(batch.to_dict()).content_address, batch.content_address)
        self.assertEqual(ingestion_audit_model.audit_ingest(batch).passed_count, 16)

    def test_selection_filters_and_truncation_are_explicit(self):
        raw = self._zip()
        catalog = self._catalog(raw)
        csv_name = next(item.member_name for item in catalog.members if item.suffix == ".csv")
        selection = ingestion_model.build_selection(catalog, selection_id="csv-selection", member_names=(csv_name,), record_limit=1, overflow_policy="truncate")
        batch = ingestion_model.build_ingest(raw, catalog=catalog, selection=selection)
        self.assertEqual((batch.available_record_count, batch.record_count, batch.dropped_record_count, batch.truncated, batch.complete), (2, 1, 1, True, False))
        with self.assertRaises(ValidationError):
            ingestion_model.build_ingest(raw, catalog=catalog, member_names=(csv_name,), record_limit=1, overflow_policy="reject")

    def test_query_and_query_audit_support_resources_and_empty_pages(self):
        batch = ingestion_model.build_ingest(self._zip(), batch_id="query-fixture-batch", record_limit=100)
        result = query_model.query_batch(batch, resources=("summary", "records", "lineage", "values"), member_name="data/table.csv", limit=100)
        self.assertEqual((result.total_count, result.returned_count, result.truncated), (7, 7, False))
        self.assertEqual(query_audit_model.audit_query(result).passed_count, 12)
        empty = query_model.query_batch(batch, resources=("records",), member_name="missing.csv", limit=10)
        self.assertEqual((empty.matched_count, empty.returned_count, empty.truncated), (0, 0, False))
        self.assertTrue(query_audit_model.audit_query(empty).accepted)
        self.assertEqual(query_model.query_from_mapping(result.to_dict()).content_address, result.content_address)

    def test_runtime_persists_exact_files_and_replays(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = runtime_model.run_runtime(self._zip(), runtime_id="ingestion-fixture-runtime", resources=("summary", "records"), limit=50, destination=root / "runtime")
            self.assertTrue(runtime.release_ready)
            self.assertEqual(tuple(sorted(item.name for item in (root / "runtime").iterdir())), tuple(sorted(runtime_model.FILES)))
            loaded = runtime_model.load_runtime(root / "runtime")
            self.assertEqual(loaded.content_address, runtime.content_address)
            self.assertTrue(runtime_audit_model.audit_runtime(loaded).accepted)
            self.assertEqual(runtime_model.runtime_from_mapping(json.loads(runtime_model.runtime_json(runtime))).content_address, runtime.content_address)

    def test_diff_classifies_record_change_and_audits_query(self):
        left = ingestion_model.build_ingest(self._zip(), batch_id="left-batch", record_limit=100)
        right = ingestion_model.build_ingest(self._zip(changed=True), batch_id="right-batch", record_limit=100)
        diff = diff_model.build_diff(left, right, diff_id="fixture-diff")
        self.assertEqual((diff.added_count, diff.removed_count, diff.changed_count, diff.unchanged_count), (0, 0, 1, 8))
        self.assertTrue(diff_audit_model.audit_diff(diff).accepted)
        result = diff_query_model.query_diff(diff, resources=("summary", "changed"), change="changed", limit=20)
        self.assertEqual((result.returned_count, result.rows[-1].change), (2, "changed"))
        self.assertTrue(diff_query_audit_model.audit_query(result).accepted)
        self.assertEqual(diff_model.diff_from_mapping(diff.to_dict()).content_address, diff.content_address)

    def test_tampered_inputs_and_public_schemas_fail_closed(self):
        batch = ingestion_model.build_ingest(self._zip(), batch_id="tamper-batch", record_limit=100)
        altered = batch.to_dict()
        altered["unknown"] = True
        with self.assertRaises(ValidationError):
            ingestion_model.ingest_from_mapping(altered)
        altered_record = batch.records[0].to_dict()
        altered_record["value_size"] += 1
        with self.assertRaises(ValidationError):
            ingestion_model.DownloadedDataRecord.from_mapping(altered_record)
        for schema in (ingestion_model.lineage_schema(), ingestion_model.record_schema(), ingestion_model.selection_schema(), ingestion_model.ingest_schema(), ingestion_audit_model.check_schema(), ingestion_audit_model.audit_schema(), query_model.row_schema(), query_model.query_schema(), query_audit_model.check_schema(), query_audit_model.audit_schema(), diff_model.item_schema(), diff_model.diff_schema(), diff_audit_model.check_schema(), diff_audit_model.audit_schema(), diff_query_model.row_schema(), diff_query_model.query_schema(), diff_query_audit_model.check_schema(), diff_query_audit_model.audit_schema(), runtime_model.manifest_schema(), runtime_model.runtime_schema(), runtime_audit_model.check_schema(), runtime_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertFalse(any(key.casefold() in ingestion_model.FORBIDDEN_PUBLIC_KEYS for key in schema.get("properties", {})))

    def test_cli_http_and_directory_replay_use_the_same_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "download.zip"
            source.write_bytes(self._zip())
            runtime_path = root / "runtime"
            runtime_json = root / "runtime.json"
            self.assertEqual(main(["downloaded-data-ingest", str(source), "--suffix", ".csv", "--resource", "summary", "--resource", "records", "--limit", "2", "--destination", str(runtime_path), "--format", "json", "--output", str(runtime_json)]), 0)
            self.assertEqual(main(["downloaded-data-ingest-query", str(runtime_path), "--resource", "records", "--limit", "2", "--format", "json", "--output", str(root / "query.json")]), 0)
            self.assertEqual(main(["downloaded-data-ingest-runtime-audit", str(runtime_path), "--format", "json", "--output", str(root / "runtime-audit.json")]), 0)
            query = json.loads((root / "query.json").read_text(encoding="utf-8"))
            self.assertEqual((query["total_count"], query["returned_count"], query["truncated"]), (2, 2, False))
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                params = [("input", str(source)), ("suffix", ".csv"), ("resource", "summary"), ("resource", "records"), ("limit", "2"), ("format", "summary")]
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/ingest?{urlencode(params)}", timeout=30) as response:
                    payload = json.loads(response.read())
                self.assertEqual((payload["selected_member_count"], payload["record_count"], payload["query_returned_count"]), (1, 2, 2))
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/ingest/runtime/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
