"""Source-free downloaded-data review packet coverage."""

# ruff: noqa: E501

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

from glio_noncode.api import create_server
from glio_noncode.downloaded_data_review_packet import (
    build_from_download,
    load_packet,
    packet_csv,
    packet_json,
    packet_schema,
    query_packet,
    render_packet_markdown,
    verify_packet,
    write_packet,
)
from glio_noncode.downloaded_data_review_packet_audit import (
    audit_json,
    audit_packet,
    capabilities_audit,
    check_schema,
    load_audit,
    query_audit,
    render_audit_markdown,
    verify_audit,
    write_audit,
)
from glio_noncode.downloaded_data_review_packet_contracts import capabilities
from glio_noncode.errors import ValidationError


def _source_bytes() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("data.csv", "record_id,score\nA,1\nB,2\n")
        archive.writestr("metadata.json", '{"source":"fixture","count":2}')
        archive.writestr("SCHEMAS/ignored.schema.json", '{"type":"object"}')
    return output.getvalue()


class DownloadedDataReviewPacketTest(unittest.TestCase):
    def setUp(self) -> None:
        self.packet = build_from_download(_source_bytes(), packet_id="fixture-downloaded-review")
        self.audit = audit_packet(self.packet.packet_bytes)

    def test_deterministic_packet_and_fourteen_check_audit(self) -> None:
        second = build_from_download(_source_bytes(), packet_id="fixture-downloaded-review")
        self.assertEqual(self.packet.packet_bytes, second.packet_bytes)
        self.assertTrue(verify_packet(self.packet).packet_address == self.packet.packet_address)
        self.assertTrue(self.audit.accepted)
        self.assertEqual((self.audit.check_count, self.audit.passed_count, self.audit.failed_count), (14, 14, 0))
        self.assertEqual(verify_audit(self.audit), self.audit)

    def test_source_free_load_queries_and_exports(self) -> None:
        catalog, runtime, runtime_audit, review = load_packet(self.packet.packet_bytes)
        self.assertEqual(catalog.content_address, self.packet.manifest.catalog_address)
        self.assertEqual(runtime.content_address, self.packet.manifest.runtime_address)
        self.assertEqual(runtime_audit.content_address, self.packet.manifest.runtime_audit_address)
        self.assertIn("Downloaded Data Review Packet", review)
        self.assertEqual(query_packet(self.packet.packet_bytes, resource="members")["total"], 4)
        self.assertIn("relative_path", packet_csv(self.packet.packet_bytes))
        self.assertIn("packet_address", packet_json(self.packet))
        self.assertIn("Transport", render_packet_markdown(self.packet))
        self.assertTrue(packet_schema()["properties"]["manifest"])
        self.assertEqual(check_schema()["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertTrue(capabilities()["source_free_after_build"])
        self.assertTrue(capabilities_audit()["independent"])
        loaded_audit = load_audit(audit_json(self.audit).encode("utf-8"))
        self.assertEqual((loaded_audit.content_address, loaded_audit.passed_count, loaded_audit.failed_count), (self.audit.content_address, self.audit.passed_count, self.audit.failed_count))
        self.assertEqual(query_audit(loaded_audit, passed=False)["total"], 0)
        self.assertIn("Check", render_audit_markdown(loaded_audit))

    def test_tampered_payload_is_rejected_by_packet_and_audit(self) -> None:
        with zipfile.ZipFile(io.BytesIO(self.packet.packet_bytes)) as source:
            output = io.BytesIO()
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as target:
                for info in source.infolist():
                    payload = source.read(info)
                    if info.filename == "review.md":
                        payload += b"\ntampered\n"
                    target.writestr(info.filename, payload)
        tampered = output.getvalue()
        with self.assertRaises(ValidationError):
            verify_packet(tampered)
        rejected = audit_packet(tampered)
        self.assertFalse(rejected.accepted)
        self.assertGreater(rejected.failed_count, 0)

    def test_atomic_packet_and_audit_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet_path = root / "review.zip"
            audit_path = root / "audit.json"
            write_packet(self.packet, packet_path)
            write_audit(self.audit, audit_path)
            self.assertTrue(verify_packet(packet_path).packet_address == self.packet.packet_address)
            self.assertTrue(load_audit(audit_path).accepted)
            self.assertEqual(json.loads(audit_path.read_text(encoding="utf-8"))["passed_count"], 14)

    def test_http_surface_builds_verifies_queries_and_audits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "download.zip"
            packet_path = root / "review-packet.zip"
            audit_path = root / "review-audit.json"
            source.write_bytes(_source_bytes())
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def get(path: str, values: dict[str, object]) -> dict[str, object]:
                    query = urlencode({key: str(value) for key, value in values.items()})
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                summary = get(
                    "/v1/downloaded-data/review-packet",
                    {"input": source, "packet_id": "http-review", "destination": packet_path, "format": "summary"},
                )
                self.assertEqual(summary["packet_id"], "http-review")
                self.assertEqual(summary["member_count"], 4)
                verified = get("/v1/downloaded-data/review-packet/verify", {"input": packet_path, "format": "json"})
                self.assertEqual(verified["packet_address"], summary["packet_address"])
                queried = get("/v1/downloaded-data/review-packet/query", {"input": packet_path, "resource": "members", "limit": 2})
                self.assertEqual((queried["total"], len(queried["items"])), (4, 2))
                audited = get(
                    "/v1/downloaded-data/review-packet/audit",
                    {"input": packet_path, "destination": audit_path, "format": "summary"},
                )
                self.assertTrue(audited["accepted"])
                self.assertEqual(audited["passed_count"], 14)
                audit_query = get("/v1/downloaded-data/review-packet/audit/query", {"input": audit_path, "passed": "false"})
                self.assertEqual(audit_query["total"], 0)
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/review-packet/schema", timeout=20) as response:
                    self.assertEqual(json.loads(response.read())["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
