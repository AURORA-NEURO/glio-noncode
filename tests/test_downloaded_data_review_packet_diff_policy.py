"""Policy-gate coverage for source-free downloaded-data review packet diffs."""

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
from glio_noncode.downloaded_data_review_packet_diff import build_diff, write_diff
from glio_noncode.downloaded_data_review_packet_diff_policy import (
    capabilities,
    load_policy,
    policy_csv,
    policy_json,
    policy_schema,
    query_policy,
    release_policy,
    render_policy_markdown,
    strict_policy,
    verify_policy,
    write_policy,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_audit import (
    audit_policy,
    query_audit,
    verify_audit,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_audit import (
    capabilities as audit_capabilities,
)
from glio_noncode.errors import ValidationError


def _source_bytes(payload: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("data.csv", payload)
    return output.getvalue()


class DownloadedDataReviewPacketDiffPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        left = build_from_download(_source_bytes("record_id,score\nA,1\nB,2\n"), packet_id="policy-fixture")
        right = build_from_download(_source_bytes("record_id,score,group\nA,1,x\nB,3,y\nC,4,z\n"), packet_id="policy-fixture")
        self.diff = build_diff(left, right, diff_id="policy-fixture-diff")

    def test_strict_blocks_and_release_accepts_with_explicit_budget(self) -> None:
        strict = strict_policy(self.diff, policy_id="strict-policy")
        release = release_policy(self.diff, policy_id="release-policy", maximum_added=1, maximum_field_changed=256)
        strict_audit = audit_policy(strict)
        release_audit = audit_policy(release)
        self.assertEqual((strict.state, strict.accepted, strict.failed_count), ("blocked", False, 6))
        self.assertEqual((release.state, release.accepted, release.failed_count), ("ready", True, 0))
        self.assertEqual((strict_audit.check_count, strict_audit.passed_count, strict_audit.failed_count, strict_audit.accepted), (13, 13, 0, True))
        self.assertEqual((release_audit.check_count, release_audit.passed_count, release_audit.failed_count, release_audit.accepted), (13, 13, 0, True))

    def test_source_free_round_trip_queries_and_exports(self) -> None:
        value = release_policy(self.diff, policy_id="round-trip", maximum_added=1, maximum_field_changed=256)
        loaded = load_policy(policy_json(value).encode("utf-8"))
        self.assertEqual(verify_policy(loaded).content_address, value.content_address)
        self.assertEqual(query_policy(loaded, passed=False)["matched"], 0)
        self.assertIn("check_id", policy_csv(loaded))
        self.assertIn("Downloaded Data Review Packet Diff Policy", render_policy_markdown(loaded))
        self.assertTrue(policy_schema()["properties"]["checks"])
        self.assertTrue(capabilities()["source_free"])
        self.assertTrue(audit_capabilities()["independent"])
        self.assertEqual(query_audit(audit_policy(value), passed=False)["matched"], 0)

    def test_tampered_policy_fails_closed(self) -> None:
        value = release_policy(self.diff, policy_id="tampered", maximum_added=1, maximum_field_changed=256)
        altered = value.to_dict() | {"maximum_changed": 0}
        with self.assertRaises(ValidationError):
            verify_policy(altered)
        rejected = audit_policy(altered)
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.failed_count, 13)

    def test_atomic_cli_and_http_policy_surfaces(self) -> None:
        value = release_policy(self.diff, policy_id="surface-policy", maximum_added=1, maximum_field_changed=256)
        audit = audit_policy(value)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diff_path = root / "diff.json"
            policy_path = root / "policy.json"
            audit_path = root / "audit.json"
            write_diff(self.diff, diff_path)
            write_policy(value, policy_path)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy", str(diff_path), "--profile", "release", "--maximum-added", "1", "--maximum-field-changed", "256", "--destination", str(root / "cli-policy.json"), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-audit", str(policy_path), "--destination", str(audit_path), "--format", "summary"]), 0)
            self.assertEqual(verify_audit(audit).content_address, audit.content_address)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def get(path: str, values: dict[str, object]) -> dict[str, object]:
                    query = urlencode({key: str(value) for key, value in values.items()})
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                queried = get("/v1/downloaded-data/review-packet/diff/policy/query", {"input": policy_path, "passed": "true", "limit": 3})
                self.assertEqual((queried["matched"], queried["returned"]), (12, 3))
                audited = get("/v1/downloaded-data/review-packet/diff/policy/audit", {"input": policy_path})
                self.assertTrue(audited["accepted"])
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/review-packet/diff/policy/schema", timeout=20) as response:
                    self.assertEqual(json.loads(response.read())["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
