"""Coverage for strict and release gates over packet-package catalog diffs."""

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
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog import build_catalog as build_source_catalog
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff import build_diff as build_inner_diff
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy import release_policy as build_inner_release_policy
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package import build_package
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog import build_catalog, write_catalog
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff import build_diff, diff_json, write_diff
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy import release_policy, strict_policy, policy_json, write_policy, query_policy, verify_policy
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_audit import audit_policy, audit_json, write_audit, query_audit
from glio_noncode.errors import ValidationError


class PacketPackageCatalogDiffPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        source = build_source_catalog((), catalog_id="packet-package-catalog-policy-source")
        inner_diff = build_inner_diff(source, source, diff_id="packet-package-catalog-policy-inner")
        inner_policy = build_inner_release_policy(inner_diff, policy_id="packet-package-catalog-policy-inner-policy", require_ready=False)
        self.package_a = build_package(inner_diff, inner_policy, package_id="packet-package-catalog-policy-package-a")
        self.package_b = build_package(inner_diff, inner_policy, package_id="packet-package-catalog-policy-package-b")

    def _catalogs(self, catalog_id: str = "packet-package-catalog-policy"):
        left = build_catalog((self.package_a.package_bytes,), entry_ids=("entry-a",), catalog_id=catalog_id)
        right = build_catalog((self.package_b.package_bytes,), entry_ids=("entry-a",), catalog_id=catalog_id)
        return left, right

    def test_strict_release_and_independent_audit(self) -> None:
        left, right = self._catalogs()
        diff = build_diff(left, right, diff_id="packet-package-catalog-policy-diff")
        strict = strict_policy(diff, policy_id="strict-packet-package-catalog-policy")
        release = release_policy(diff, policy_id="release-packet-package-catalog-policy")
        self.assertEqual((diff.changed_count, diff.direction, diff.state_transition), (1, "changed", "same-ready"))
        self.assertFalse(strict.accepted)
        self.assertTrue(release.accepted)
        self.assertEqual((release.check_count, release.failed_count), (15, 0))
        receipt = audit_policy(release, diff=diff)
        self.assertEqual((receipt.check_count, receipt.passed_count, receipt.failed_count, receipt.accepted), (16, 16, 0, True))
        self.assertEqual(query_policy(strict, passed=False)["matched"], 4)
        self.assertEqual(query_audit(receipt, passed=False)["matched"], 0)

    def test_required_change_and_tamper_fail_closed(self) -> None:
        left, right = self._catalogs("packet-package-catalog-policy-controls")
        diff = build_diff(left, right, diff_id="packet-package-catalog-policy-controls-diff")
        required = release_policy(diff, policy_id="required-packet-package-catalog-policy", required_changes=("changed",), maximum_total_changes=1)
        self.assertTrue(required.accepted)
        rejected = release_policy(diff, policy_id="blocked-packet-package-catalog-policy", required_changes=("added",), maximum_total_changes=0)
        self.assertFalse(rejected.accepted)
        tampered = json.loads(policy_json(required))
        tampered["maximum_total_changes"] = 0
        with self.assertRaises(ValidationError):
            verify_policy(tampered)
        self.assertFalse(audit_policy(tampered, diff=diff).accepted)

    def test_cli_http_and_atomic_persistence(self) -> None:
        left, right = self._catalogs("packet-package-catalog-policy-surfaces")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left_path, right_path, diff_path = root / "left.json", root / "right.json", root / "diff.json"
            policy_path, audit_path = root / "policy.json", root / "audit.json"
            write_catalog(left, left_path)
            write_catalog(right, right_path)
            write_diff(build_diff(left, right, diff_id="surface-packet-package-catalog-policy-diff"), diff_path)
            command = "downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy"
            self.assertEqual(main([command, str(diff_path), "--profile", "release", "--maximum-total-changes", "1", "--destination", str(policy_path), "--format", "summary"]), 0)
            self.assertEqual(main([command + "-verify", str(policy_path)]), 0)
            self.assertEqual(main([command + "-query", str(policy_path), "--failed"]), 0)
            audit_command = command + "-audit"
            self.assertEqual(main([audit_command, str(policy_path), "--diff", str(diff_path), "--destination", str(audit_path), "--format", "summary"]), 0)
            self.assertEqual(main([audit_command + "-verify", str(audit_path)]), 0)
            self.assertEqual(write_policy(release_policy(build_diff(left, right), policy_id="persisted-policy"), root / "persisted-policy.json").policy_id, "persisted-policy")
            self.assertEqual(write_audit(audit_policy(release_policy(build_diff(left, right), policy_id="persisted-policy-2")), root / "persisted-audit.json").check_count, 16)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy"
                def get(path: str, pairs: list[tuple[str, object]]) -> dict[str, object]:
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{urlencode([(key, str(value)) for key, value in pairs])}", timeout=20) as response:
                        return json.loads(response.read())
                built = get(base, [("input", diff_path), ("profile", "release"), ("maximum_total_changes", 1)])
                self.assertTrue(built["accepted"])
                audited = get(base + "/audit", [("input", policy_path), ("diff", diff_path)])
                self.assertTrue(audited["accepted"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
