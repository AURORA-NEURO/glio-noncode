"""Policy coverage for portable packet-catalog longitudinal diffs."""

# ruff: noqa: E501

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog import build_catalog, write_catalog
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff import build_diff, write_diff
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy import policy_json, query_policy, release_policy, strict_policy, verify_policy
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_audit import audit_policy, audit_schema, query_audit
from glio_noncode.errors import ValidationError


class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.left = build_catalog((), catalog_id="portable-catalog-policy-empty")
        self.right = build_catalog((), catalog_id="portable-catalog-policy-empty")
        self.diff = build_diff(self.left, self.right, diff_id="portable-catalog-policy-empty-diff")

    def test_strict_release_and_independent_audit_decisions(self) -> None:
        strict = strict_policy(self.diff, policy_id="portable-catalog-policy-strict")
        release = release_policy(self.diff, policy_id="portable-catalog-policy-release", require_ready=False)
        self.assertEqual((strict.state, strict.accepted), ("blocked", False))
        self.assertEqual((release.state, release.accepted), ("ready", True))
        self.assertGreater(strict.failed_count, 0)
        self.assertEqual(query_policy(release, passed=False)["matched"], 0)
        receipt = audit_policy(release, diff=self.diff)
        self.assertEqual((receipt.check_count, receipt.passed_count, receipt.failed_count, receipt.accepted), (14, 14, 0, True))
        self.assertEqual(query_audit(receipt, passed=False)["matched"], 0)
        self.assertTrue(audit_schema()["properties"]["checks"])

    def test_controls_and_tampering_fail_closed(self) -> None:
        blocked = release_policy(self.diff, policy_id="portable-catalog-policy-required-change", require_ready=False, require_change=True)
        self.assertEqual((blocked.state, blocked.accepted), ("blocked", False))
        tampered = json.loads(policy_json(blocked))
        tampered["accepted"] = True
        with self.assertRaises(ValidationError):
            verify_policy(tampered)
        rejected = audit_policy(tampered, diff=self.diff)
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.failed_count, 14)

    def test_cli_http_and_persistence_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left_path = root / "left-catalog.json"
            right_path = root / "right-catalog.json"
            diff_path = root / "catalog-diff.json"
            policy_path = root / "catalog-policy.json"
            audit_path = root / "catalog-policy-audit.json"
            write_catalog(self.left, left_path)
            write_catalog(self.right, right_path)
            write_diff(self.diff, diff_path)
            command = "downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy"
            self.assertEqual(main([command, str(diff_path), "--profile", "release", "--disallow-unchanged", "--destination", str(policy_path), "--format", "summary"]), 2)
            self.assertEqual(main([command + "-verify", str(policy_path)]), 2)
            self.assertEqual(main([command + "-query", str(policy_path), "--failed"]), 0)
            audit_command = command + "-audit"
            self.assertEqual(main([audit_command, str(policy_path), "--diff", str(diff_path), "--destination", str(audit_path), "--format", "summary"]), 0)
            self.assertEqual(main([audit_command + "-verify", str(audit_path)]), 0)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def get(path: str, pairs: list[tuple[str, object]]) -> dict[str, object]:
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{urlencode([(key, str(value)) for key, value in pairs])}", timeout=20) as response:
                        return json.loads(response.read())

                base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy"
                built = get(base, [("input", diff_path), ("profile", "release"), ("disallow_unchanged", "true")])
                self.assertEqual(built["state"], "blocked")
                queried = get(base + "/query", [("input", policy_path), ("failed", "true")])
                self.assertGreater(queried["matched"], 0)
                audited = get(base + "/audit", [("input", policy_path), ("diff", diff_path)])
                self.assertTrue(audited["accepted"])
                schema = get(base + "/schema", [])
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
