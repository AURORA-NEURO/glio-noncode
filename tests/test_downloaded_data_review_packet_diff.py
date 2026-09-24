"""Source-free longitudinal downloaded-data review packet diff coverage."""

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
from glio_noncode.cli import main
from glio_noncode.downloaded_data_review_packet import build_from_download
from glio_noncode.downloaded_data_review_packet_diff import (
    build_diff,
    capabilities,
    diff_csv,
    diff_json,
    diff_schema,
    load_diff,
    query_diff,
    render_diff_markdown,
    verify_diff,
    write_diff,
)
from glio_noncode.downloaded_data_review_packet_diff_audit import (
    audit_diff,
    audit_json,
    load_audit,
    query_audit,
    render_audit_markdown,
    verify_audit,
    write_audit,
)
from glio_noncode.downloaded_data_review_packet_diff_audit import (
    capabilities as audit_capabilities,
)
from glio_noncode.errors import ValidationError


def _source_bytes(payload: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("data.csv", payload)
    return output.getvalue()


class DownloadedDataReviewPacketDiffTest(unittest.TestCase):
    def setUp(self) -> None:
        self.left = build_from_download(_source_bytes("record_id,score\nA,1\nB,2\n"), packet_id="diff-fixture")
        self.right = build_from_download(_source_bytes("record_id,score,group\nA,1,x\nB,3,y\nC,4,z\n"), packet_id="diff-fixture")
        self.diff = build_diff(self.left, self.right, diff_id="diff-fixture-compare")
        self.audit = audit_diff(self.diff)

    def test_deterministic_diff_and_independent_audit(self) -> None:
        second = build_diff(self.left, self.right, diff_id="diff-fixture-compare")
        self.assertEqual(diff_json(self.diff), diff_json(second))
        self.assertEqual((len(self.diff.items), self.audit.check_count, self.audit.passed_count, self.audit.failed_count, self.audit.accepted), (12, 14, 14, 0, True))
        self.assertEqual(verify_diff(self.diff).content_address, self.diff.content_address)
        self.assertEqual(verify_audit(self.audit).content_address, self.audit.content_address)

    def test_source_free_queries_and_exports(self) -> None:
        loaded = load_diff(diff_json(self.diff).encode("utf-8"))
        self.assertEqual(loaded.content_address, self.diff.content_address)
        self.assertEqual(query_diff(loaded, change="changed")["matched"], 5)
        self.assertEqual(query_diff(loaded, resource="fields", limit=1)["returned"], 1)
        self.assertIn("identity", diff_csv(loaded, change="added"))
        self.assertIn("Downloaded Data Review Packet Diff", render_diff_markdown(loaded))
        self.assertTrue(diff_schema()["properties"]["items"])
        self.assertTrue(capabilities()["source_free"])
        loaded_audit = load_audit(audit_json(self.audit).encode("utf-8"))
        self.assertEqual(query_audit(loaded_audit, passed=False)["matched"], 0)
        self.assertIn("Audit", render_audit_markdown(loaded_audit))
        self.assertTrue(audit_capabilities()["independent"])

    def test_tampered_diff_is_rejected_and_audit_fails_closed(self) -> None:
        altered = self.diff.to_dict()
        altered["items"] = list(altered["items"])
        altered["items"][0] = dict(altered["items"][0]) | {"change": "removed"}
        with self.assertRaises(ValidationError):
            verify_diff(altered)
        rejected = audit_diff(altered)
        self.assertFalse(rejected.accepted)
        self.assertEqual((rejected.passed_count, rejected.failed_count), (0, 14))

    def test_matching_packet_identity_is_required(self) -> None:
        other = build_from_download(_source_bytes("record_id,score\nA,1\n"), packet_id="other-fixture")
        with self.assertRaisesRegex(ValidationError, "matching packet IDs"):
            build_diff(self.left, other)

    def test_atomic_persistence_cli_and_http_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left_path = root / "left-packet.zip"
            right_path = root / "right-packet.zip"
            diff_path = root / "diff.json"
            audit_path = root / "audit.json"
            left_path.write_bytes(self.left.packet_bytes)
            right_path.write_bytes(self.right.packet_bytes)
            write_diff(self.diff, diff_path)
            write_audit(self.audit, audit_path)
            self.assertEqual(main(["downloaded-data-review-packet-diff", str(left_path), str(right_path), "--diff-id", "cli-diff", "--destination", str(root / "cli-diff.json"), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-audit", str(diff_path), "--format", "summary"]), 0)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def get(path: str, values: dict[str, object]) -> dict[str, object]:
                    query = urlencode({key: str(value) for key, value in values.items()})
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                built = get("/v1/downloaded-data/review-packet/diff", {"left": left_path, "right": right_path, "diff_id": "http-diff", "destination": root / "http-diff.json"})
                self.assertEqual(built["diff_id"], "http-diff")
                queried = get("/v1/downloaded-data/review-packet/diff/query", {"input": root / "http-diff.json", "change": "changed", "limit": 2})
                self.assertEqual((queried["matched"], queried["returned"]), (5, 2))
                audited = get("/v1/downloaded-data/review-packet/diff/audit", {"input": root / "http-diff.json", "destination": root / "http-audit.json"})
                self.assertTrue(audited["accepted"])
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/review-packet/diff/schema", timeout=20) as response:
                    self.assertEqual(json.loads(response.read())["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
