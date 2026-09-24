"""Coverage for portable packet-catalog diff policy packages."""

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
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog import build_catalog
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff import build_diff, write_diff
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy import release_policy, write_policy
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_audit import audit_policy, write_audit
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package import build_package, load_package, package_json, query_package, verify_package
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_audit import audit_package, query_audit
from glio_noncode.errors import ValidationError


class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffPolicyPackageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = build_catalog((), catalog_id="packet-catalog-policy-package-empty")
        self.diff = build_diff(self.catalog, self.catalog, diff_id="packet-catalog-policy-package-empty-diff")
        self.policy = release_policy(self.diff, policy_id="packet-catalog-policy-package-release", require_ready=False)
        self.policy_audit = audit_policy(self.policy, diff=self.diff)

    def test_deterministic_round_trip_and_fifteen_check_audit(self) -> None:
        first = build_package(self.diff, self.policy, self.policy_audit, package_id="packet-catalog-policy-package")
        second = build_package(self.diff, self.policy, self.policy_audit, package_id="packet-catalog-policy-package")
        self.assertEqual(first.package_bytes, second.package_bytes)
        self.assertEqual(first.package_address, second.package_address)
        self.assertEqual(len(first.manifest.members), 4)
        self.assertEqual(load_package(first)[0].content_address, self.diff.content_address)
        self.assertEqual(query_package(first, resource="members")["total"], 4)
        receipt = audit_package(first)
        self.assertEqual((receipt.check_count, receipt.passed_count, receipt.failed_count, receipt.accepted), (15, 15, 0, True))
        self.assertEqual(query_audit(receipt, passed=False)["matched"], 0)
        self.assertEqual(json.loads(package_json(first))["package_address"], first.package_address)

    def test_blocked_policy_evidence_is_retained_and_bytes_fail_closed(self) -> None:
        blocked = release_policy(self.diff, policy_id="packet-catalog-policy-package-blocked", require_ready=False, require_change=True)
        blocked_audit = audit_policy(blocked, diff=self.diff)
        package = build_package(self.diff, blocked, blocked_audit, package_id="packet-catalog-policy-package-blocked")
        self.assertEqual((package.manifest.policy_state, package.manifest.policy_accepted, package.manifest.audit_accepted), ("blocked", False, True))
        tampered = package.package_bytes[:-1] + bytes((package.package_bytes[-1] ^ 1,))
        with self.assertRaises(ValidationError):
            verify_package(tampered)

    def test_cli_http_and_persistence_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diff_path = root / "catalog-diff.json"
            policy_path = root / "policy.json"
            policy_audit_path = root / "policy-audit.json"
            package_path = root / "packet-catalog-diff-policy-package.zip"
            package_audit_path = root / "packet-catalog-diff-policy-package-audit.json"
            write_diff(self.diff, diff_path)
            write_policy(self.policy, policy_path)
            write_audit(self.policy_audit, policy_audit_path)
            command = "downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package"
            self.assertEqual(main([command, str(diff_path), str(policy_path), str(policy_audit_path), "--destination", str(package_path), "--format", "summary"]), 0)
            self.assertEqual(main([command + "-verify", str(package_path)]), 0)
            audit_command = command + "-audit"
            self.assertEqual(main([audit_command, str(package_path), "--destination", str(package_audit_path), "--format", "summary"]), 0)
            self.assertEqual(main([audit_command + "-verify", str(package_audit_path)]), 0)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def get(path: str, pairs: list[tuple[str, object]]) -> dict[str, object]:
                    query = urlencode([(key, str(value)) for key, value in pairs])
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package"
                built = get(base, [("diff", diff_path), ("policy", policy_path), ("policy_audit", policy_audit_path)])
                self.assertTrue(built["policy_accepted"])
                queried = get(base + "/query", [("input", package_path), ("resource", "members")])
                self.assertEqual(queried["total"], 4)
                audited = get(base + "/audit", [("input", package_path)])
                self.assertEqual((audited["check_count"], audited["failed_count"], audited["accepted"]), (15, 0, True))
                schema = get(base + "/schema", [])
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
