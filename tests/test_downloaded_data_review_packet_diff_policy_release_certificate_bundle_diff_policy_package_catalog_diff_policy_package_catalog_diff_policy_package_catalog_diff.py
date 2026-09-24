"""Longitudinal diff coverage for portable packet-package catalogs."""

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
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff import build_diff as build_packet_diff
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy import release_policy
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package import build_package
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog import build_catalog, write_catalog
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff import build_diff, diff_json, diff_schema, query_diff, render_diff_markdown, verify_diff
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_audit import audit_diff, audit_schema, query_audit
from glio_noncode.errors import ValidationError


class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffTest(unittest.TestCase):
    def setUp(self) -> None:
        source = build_source_catalog((), catalog_id="packet-package-catalog-diff-source")
        packet_diff = build_packet_diff(source, source, diff_id="packet-package-catalog-diff-inner")
        policy = release_policy(packet_diff, policy_id="packet-package-catalog-diff-policy", require_ready=False)
        self.package_a = build_package(packet_diff, policy, package_id="packet-package-catalog-diff-package-a")
        self.package_b = build_package(packet_diff, policy, package_id="packet-package-catalog-diff-package-b")

    def test_added_changed_and_independent_audit(self) -> None:
        left = build_catalog((self.package_a.package_bytes,), entry_ids=("entry-a",), catalog_id="packet-package-catalog-diff")
        right = build_catalog((self.package_b.package_bytes,), entry_ids=("entry-a",), catalog_id="packet-package-catalog-diff")
        diff = build_diff(left, right, diff_id="packet-package-catalog-diff")
        self.assertEqual((diff.added_count, diff.removed_count, diff.changed_count, diff.unchanged_count), (0, 0, 1, 0))
        self.assertEqual((diff.left_posture, diff.right_posture, diff.state_transition), ("ready", "ready", "same-ready"))
        self.assertEqual(query_diff(diff, change="changed")["matched"], 1)
        self.assertIn("same-ready", render_diff_markdown(diff))
        self.assertTrue(diff_schema()["properties"]["items"])
        receipt = audit_diff(diff, left=left, right=right)
        self.assertEqual((receipt.check_count, receipt.passed_count, receipt.failed_count, receipt.accepted), (13, 13, 0, True))
        self.assertEqual(query_audit(receipt, passed=False)["matched"], 0)
        self.assertTrue(audit_schema()["properties"]["checks"])

    def test_added_removed_and_tampering_fail_closed(self) -> None:
        left = build_catalog((), catalog_id="packet-package-catalog-diff-add-remove")
        right = build_catalog((self.package_a.package_bytes,), entry_ids=("entry-a",), catalog_id="packet-package-catalog-diff-add-remove")
        diff = build_diff(left, right, diff_id="packet-package-catalog-diff-add")
        self.assertEqual((diff.added_count, diff.removed_count, diff.changed_count, diff.unchanged_count), (1, 0, 0, 0))
        self.assertEqual((diff.left_posture, diff.right_posture, diff.state_transition, diff.direction), ("empty", "ready", "empty-to-ready", "improved"))
        tampered = json.loads(diff_json(diff))
        tampered["direction"] = "regressed"
        with self.assertRaises(ValidationError):
            verify_diff(tampered)
        rejected = audit_diff(tampered, left=left, right=right)
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.failed_count, 13)

    def test_cli_http_and_persistence_surfaces(self) -> None:
        left = build_catalog((self.package_a.package_bytes,), entry_ids=("entry-a",), catalog_id="packet-package-catalog-diff-surfaces")
        right = build_catalog((self.package_b.package_bytes,), entry_ids=("entry-a",), catalog_id="packet-package-catalog-diff-surfaces")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left_path = root / "left-catalog.json"
            right_path = root / "right-catalog.json"
            diff_path = root / "catalog-diff.json"
            audit_path = root / "catalog-diff-audit.json"
            write_catalog(left, left_path)
            write_catalog(right, right_path)
            command = "downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-diff"
            self.assertEqual(main([command, str(left_path), str(right_path), "--diff-id", "cli-packet-package-catalog-diff", "--destination", str(diff_path), "--format", "summary"]), 0)
            self.assertEqual(main([command + "-verify", str(diff_path)]), 0)
            self.assertEqual(main([command + "-query", str(diff_path), "--change", "changed"]), 0)
            audit_command = command + "-audit"
            self.assertEqual(main([audit_command, str(diff_path), "--left", str(left_path), "--right", str(right_path), "--destination", str(audit_path), "--format", "summary"]), 0)
            self.assertEqual(main([audit_command + "-verify", str(audit_path)]), 0)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def get(path: str, pairs: list[tuple[str, object]]) -> dict[str, object]:
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{urlencode([(key, str(value)) for key, value in pairs])}", timeout=20) as response:
                        return json.loads(response.read())

                base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff"
                built = get(base, [("left", left_path), ("right", right_path), ("diff_id", "http-packet-package-catalog-diff")])
                self.assertEqual(built["changed_count"], 1)
                queried = get(base + "/query", [("input", diff_path), ("change", "changed")])
                self.assertEqual(queried["matched"], 1)
                audited = get(base + "/audit", [("input", diff_path), ("left", left_path), ("right", right_path)])
                self.assertTrue(audited["accepted"])
                schema = get(base + "/schema", [])
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
