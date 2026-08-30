# ruff: noqa: E501, I001

from __future__ import annotations

import io
import json
import tempfile
import threading
import unittest
import zipfile
from urllib.parse import urlencode
from urllib.request import urlopen
from pathlib import Path

from glio_noncode import downloaded_data_catalog as catalog_model
from glio_noncode import downloaded_data_catalog_audit as audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError


class DownloadedDataCatalogTests(unittest.TestCase):
    @staticmethod
    def _zip() -> bytes:
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("bundle/COUNTS.json", json.dumps({"records": 3, "version": "1"}, separators=(",", ":")))
            archive.writestr("bundle/rows.csv", "id,value\nrow-1,4\nrow-2,9\n")
            archive.writestr("bundle/notes.md", "This prose is not data input.")
            archive.writestr("bundle/src/ignored.json", "{\"not\":\"included\"}")
            archive.writestr("bundle/05_AGENTS/ignored.csv", "id\nnot-used\n")
        return stream.getvalue()

    def _assert_public(self, value: object) -> None:
        forbidden = {"agent", "agent_id", "agent_name", "assistant", "assistant_id", "author", "language", "model", "model_id", "programming_language"}

        def walk(node: object) -> None:
            if isinstance(node, dict):
                for key, child in node.items():
                    self.assertNotIn(str(key).casefold(), forbidden)
                    walk(child)
            elif isinstance(node, (tuple, list)):
                for child in node:
                    walk(child)

        walk(value)

    def test_catalogs_structured_members_without_extracting_code_or_prose(self):
        value = catalog_model.build_catalog(self._zip(), catalog_id="catalog-fixture")
        self.assertEqual((value.member_count, value.json_count, value.delimited_count, value.yaml_count), (2, 1, 1, 0))
        self.assertEqual(tuple(item.member_name for item in value.members), ("bundle/COUNTS.json", "bundle/rows.csv"))
        self.assertEqual(value.member("bundle/rows.csv").record_count, 2)
        self.assertEqual(catalog_model.catalog_from_mapping(value.to_dict()).content_address, value.content_address)
        self.assertTrue(catalog_model.catalog_json(value).startswith("{"))
        self.assertTrue(catalog_model.catalog_csv(value).startswith("ordinal,member_name"))
        self.assertIn("# Downloaded Data Catalog", catalog_model.render_catalog_markdown(value))
        self._assert_public(value.to_dict())

    def test_audit_is_fixed_size_and_replays(self):
        value = catalog_model.build_catalog(self._zip(), catalog_id="audit-fixture")
        audit = audit_model.audit_catalog(value)
        self.assertEqual((audit.check_count, audit.passed_count, audit.failed_count, audit.accepted), (12, 12, 0, True))
        self.assertEqual(tuple(item.check_id for item in audit.checks), audit_model.CHECK_IDS)
        self.assertEqual(audit_model.audit_from_mapping(audit.to_dict()).content_address, audit.content_address)
        self.assertIn("# Downloaded Data Catalog Audit", audit_model.render_audit_markdown(audit))

    def test_unknown_fields_and_unsafe_zip_members_fail_closed(self):
        value = catalog_model.build_catalog(self._zip(), catalog_id="tamper-fixture")
        altered = value.to_dict()
        altered["unknown"] = True
        with self.assertRaises(ValidationError):
            catalog_model.catalog_from_mapping(altered)
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("../escape.json", "{}")
        with self.assertRaises(ValidationError):
            catalog_model.build_catalog(stream.getvalue())

    def test_disk_source_and_public_schemas(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "download.zip"
            source.write_bytes(self._zip())
            value = catalog_model.build_catalog(source)
            self.assertEqual(value.source_name, "download.zip")
        for schema in (catalog_model.member_schema(), catalog_model.catalog_schema(), audit_model.check_schema(), audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self._assert_public(schema)
        self.assertTrue(catalog_model.capabilities()["public"])
        self.assertTrue(audit_model.capabilities()["independent"])

    def test_cli_and_http_surfaces_use_the_same_catalog_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "download.zip"
            source.write_bytes(self._zip())
            catalog_path = root / "catalog.json"
            audit_path = root / "audit.json"
            self.assertEqual(main(["downloaded-data-catalog", str(source), "--format", "json", "--output", str(catalog_path)]), 0)
            self.assertEqual(main(["downloaded-data-catalog-audit", str(catalog_path), "--format", "json", "--output", str(audit_path)]), 0)
            self.assertTrue(json.loads(audit_path.read_text(encoding="utf-8"))["accepted"])
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                query = urlencode({"input": str(source), "format": "summary"})
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/catalog?{query}", timeout=20) as response:
                    payload = json.loads(response.read())
                self.assertEqual((payload["source_name"], payload["member_count"], payload["json_count"]), ("download.zip", 2, 1))
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/catalog/schema", timeout=20) as response:
                    self.assertEqual(json.loads(response.read())["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
