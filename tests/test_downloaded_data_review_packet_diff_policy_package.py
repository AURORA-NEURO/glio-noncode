"""Portable packaging coverage for downloaded-data diff policy evidence."""

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
from glio_noncode.downloaded_data_review_packet_diff import build_diff, diff_json
from glio_noncode.downloaded_data_review_packet_diff_policy import (
    policy_json,
    release_policy,
    strict_policy,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_audit import audit_json, audit_policy
from glio_noncode.downloaded_data_review_packet_diff_policy_package import (
    build_package,
    capabilities,
    load_package,
    package_json,
    package_schema,
    query_package,
    render_package_markdown,
    verify_package,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_package_audit import (
    audit_package,
    audit_schema,
    query_audit,
)
from glio_noncode.errors import ValidationError


def _source_bytes(payload: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("data.csv", payload)
    return output.getvalue()


class DownloadedDataReviewPacketDiffPolicyPackageTest(unittest.TestCase):
    def setUp(self) -> None:
        left = build_from_download(_source_bytes("record_id,score\nA,1\nB,2\n"), packet_id="package-fixture")
        right = build_from_download(_source_bytes("record_id,score,group\nA,1,x\nB,3,y\nC,4,z\n"), packet_id="package-fixture")
        self.diff = build_diff(left, right, diff_id="package-fixture-diff")
        self.ready_policy = release_policy(self.diff, policy_id="package-ready", maximum_added=1, maximum_field_changed=256)
        self.blocked_policy = strict_policy(self.diff, policy_id="package-blocked")

    def test_ready_and_blocked_decisions_round_trip_source_free(self) -> None:
        ready = build_package(self.diff, self.ready_policy, audit_policy(self.ready_policy), package_id="ready-package")
        blocked = build_package(self.diff, self.blocked_policy, audit_policy(self.blocked_policy), package_id="blocked-package")
        self.assertEqual(verify_package(ready).package_address, ready.package_address)
        self.assertIn(ready.package_address, package_json(ready))
        self.assertEqual(load_package(ready)[1].state, "ready")
        self.assertEqual(load_package(blocked)[1].state, "blocked")
        self.assertEqual((audit_package(ready).check_count, audit_package(ready).passed_count, audit_package(ready).failed_count), (14, 14, 0))
        self.assertEqual(query_package(blocked, resource="policy")["value"]["state"], "blocked")
        self.assertIn("Source-free", render_package_markdown(ready))
        self.assertTrue(package_schema()["properties"]["manifest"])
        self.assertTrue(capabilities()["policy_state_preserved"])
        self.assertTrue(audit_schema()["properties"]["checks"])
        self.assertEqual(query_audit(audit_package(ready), passed=False)["matched"], 0)

    def test_tampering_fails_closed_and_audit_is_independent(self) -> None:
        package = build_package(self.diff, self.ready_policy, audit_policy(self.ready_policy))
        altered = bytearray(package.package_bytes)
        altered[-1] ^= 1
        with self.assertRaises(ValidationError):
            verify_package(bytes(altered))
        rejected = audit_package(bytes(altered))
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.failed_count, 14)

    def test_atomic_cli_and_http_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diff_path = root / "diff.json"
            policy_path = root / "policy.json"
            audit_path = root / "audit.json"
            package_path = root / "package.zip"
            diff_path.write_text(diff_json(self.diff), encoding="utf-8")
            policy_path.write_text(policy_json(self.ready_policy), encoding="utf-8")
            audit_path.write_text(audit_json(audit_policy(self.ready_policy)), encoding="utf-8")
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-package", str(diff_path), str(policy_path), "--audit", str(audit_path), "--destination", str(package_path), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-package-verify", str(package_path)]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-package-audit", str(package_path), "--format", "summary"]), 0)
            self.assertEqual(verify_package(package_path).package_address, build_package(self.diff, self.ready_policy, audit_policy(self.ready_policy)).package_address)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def get(path: str, values: dict[str, object]) -> dict[str, object]:
                    query = urlencode({key: str(value) for key, value in values.items()})
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                built = get("/v1/downloaded-data/review-packet/diff/policy/package", {"diff": diff_path, "policy": policy_path, "audit": audit_path, "package_id": "http-package", "destination": root / "http-package.zip"})
                self.assertEqual(built["policy_state"], "ready")
                queried = get("/v1/downloaded-data/review-packet/diff/policy/package/query", {"input": package_path, "resource": "policy"})
                self.assertEqual(queried["value"]["state"], "ready")
                audited = get("/v1/downloaded-data/review-packet/diff/policy/package/audit", {"input": package_path})
                self.assertTrue(audited["accepted"])
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/review-packet/diff/policy/package/schema", timeout=20) as response:
                    self.assertEqual(json.loads(response.read())["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
