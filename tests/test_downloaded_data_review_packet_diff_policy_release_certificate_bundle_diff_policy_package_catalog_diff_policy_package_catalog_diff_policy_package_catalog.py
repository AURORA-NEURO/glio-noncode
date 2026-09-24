"""Coverage for source-free catalogs of packet-catalog policy packages."""

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
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog import build_catalog as source_catalog
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff import build_diff
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy import release_policy
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package import build_package, write_package
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog import build_catalog, catalog_json, query_catalog, write_catalog
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_audit import audit_catalog, query_audit, write_audit
from glio_noncode.errors import ValidationError


class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffPolicyPackageCatalogTest(unittest.TestCase):
    def setUp(self) -> None:
        source = source_catalog((), catalog_id="packet-catalog-package-catalog-source-empty")
        diff = build_diff(source, source, diff_id="packet-catalog-package-catalog-empty-diff")
        policy = release_policy(diff, policy_id="packet-catalog-package-catalog-release", require_ready=False)
        self.package = build_package(diff, policy, package_id="packet-catalog-policy-package-catalog-entry")

    def test_deterministic_catalog_and_fifteen_check_audit(self) -> None:
        first = build_catalog((self.package,), entry_ids=("entry-a",), catalog_id="packet-catalog-policy-package-catalog")
        second = build_catalog((self.package,), entry_ids=("entry-a",), catalog_id="packet-catalog-policy-package-catalog")
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(catalog_json(first), catalog_json(second))
        self.assertEqual(query_catalog(first, resource="ready")["matched"], 1)
        receipt = audit_catalog(first)
        self.assertEqual((receipt.check_count, receipt.passed_count, receipt.failed_count, receipt.accepted), (15, 15, 0, True))
        self.assertEqual(query_audit(receipt, passed=False)["matched"], 0)

    def test_duplicate_package_identity_fails_closed(self) -> None:
        with self.assertRaises(ValidationError):
            build_catalog((self.package, self.package), entry_ids=("a", "b"), catalog_id="duplicate")

    def test_cli_http_and_persistence_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package_path = root / "packet-catalog-policy-package.zip"
            catalog_path = root / "packet-catalog.json"
            audit_path = root / "packet-catalog-audit.json"
            write_package(self.package, package_path)
            command = "downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog"
            self.assertEqual(main([command, str(package_path), "--entry-id", "entry-a", "--catalog-id", "packet-catalog-policy-package-catalog", "--destination", str(catalog_path), "--format", "summary"]), 0)
            self.assertEqual(main([command + "-verify", str(catalog_path)]), 0)
            audit_command = command + "-audit"
            self.assertEqual(main([audit_command, str(catalog_path), "--destination", str(audit_path), "--format", "summary"]), 0)
            self.assertEqual(main([audit_command + "-verify", str(audit_path)]), 0)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def get(path: str, pairs: list[tuple[str, object]]) -> dict[str, object]:
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{urlencode([(key, str(value)) for key, value in pairs])}", timeout=20) as response:
                        return json.loads(response.read())

                base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog"
                built = get(base, [("package", package_path), ("entry_id", "entry-a")])
                self.assertEqual((built["entry_count"], built["ready_count"], built["accepted_count"]), (1, 1, 1))
                queried = get(base + "/query", [("input", catalog_path), ("resource", "lineage")])
                self.assertEqual(queried["matched"], 1)
                audited = get(base + "/audit", [("input", catalog_path)])
                self.assertEqual((audited["check_count"], audited["failed_count"], audited["accepted"]), (15, 0, True))
                schema = get(base + "/schema", [])
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
