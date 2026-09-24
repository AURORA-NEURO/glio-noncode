"""Coverage for source-free catalogs of packet-package policy handoff packages."""

# ruff: noqa: E501

from __future__ import annotations

import contextlib
import io
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
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package import build_package as build_inner_package
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog import build_catalog, verify_catalog
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff import build_diff
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy import release_policy
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_audit import audit_policy
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package import build_package, write_package
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_audit import audit_catalog, query_audit
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog import build_catalog as build_handoff_catalog
from glio_noncode.errors import ValidationError


class PacketPackagePolicyHandoffCatalogTest(unittest.TestCase):
    def setUp(self) -> None:
        source = build_source_catalog((), catalog_id="packet-policy-handoff-catalog-source")
        inner_diff = build_inner_diff(source, source, diff_id="packet-policy-handoff-catalog-inner-diff")
        inner_policy = build_inner_release_policy(inner_diff, policy_id="packet-policy-handoff-catalog-inner-policy", require_ready=False)
        self.package_a = build_inner_package(inner_diff, inner_policy, package_id="packet-policy-handoff-catalog-a")
        self.package_b = build_inner_package(inner_diff, inner_policy, package_id="packet-policy-handoff-catalog-b")

    def _handoff_packages(self):
        left = build_handoff_catalog((self.package_a.package_bytes,), entry_ids=("entry-a",), catalog_id="packet-policy-handoff-catalog")
        right = build_handoff_catalog((self.package_b.package_bytes,), entry_ids=("entry-a",), catalog_id="packet-policy-handoff-catalog")
        diff = build_diff(left, right, diff_id="packet-policy-handoff-catalog-diff")
        policy = release_policy(diff, policy_id="packet-policy-handoff-catalog-policy")
        audit = audit_policy(policy, diff=diff)
        return (
            build_package(diff, policy, audit, package_id="packet-policy-handoff-package-a"),
            build_package(diff, policy, audit, package_id="packet-policy-handoff-package-b"),
        )

    def test_deterministic_catalog_and_sixteen_check_audit(self) -> None:
        package_a, package_b = self._handoff_packages()
        first = build_catalog((package_b.package_bytes, package_a.package_bytes), entry_ids=("entry-b", "entry-a"), catalog_id="packet-policy-handoff-catalog-index")
        second = build_catalog((package_a.package_bytes, package_b.package_bytes), entry_ids=("entry-a", "entry-b"), catalog_id="packet-policy-handoff-catalog-index")
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(tuple(item.entry_id for item in first.entries), ("entry-a", "entry-b"))
        self.assertEqual((first.entry_count, first.accepted_count, first.ready_count, first.blocked_count), (2, 2, 2, 0))
        self.assertEqual(query_audit(audit_catalog(first), passed=False)["matched"], 0)
        receipt = audit_catalog(first)
        self.assertEqual((receipt.check_count, receipt.passed_count, receipt.failed_count, receipt.accepted), (16, 16, 0, True))

    def test_duplicate_and_tampered_catalogs_fail_closed(self) -> None:
        package_a, _package_b = self._handoff_packages()
        with self.assertRaises(ValidationError):
            build_catalog((package_a.package_bytes, package_a.package_bytes), catalog_id="packet-policy-handoff-catalog-duplicate")
        catalog = build_catalog((package_a.package_bytes,), catalog_id="packet-policy-handoff-catalog-tamper")
        tampered = catalog.to_dict()
        tampered["total_package_bytes"] += 1
        with self.assertRaises(ValidationError):
            verify_catalog(tampered)

    def test_cli_http_and_atomic_persistence(self) -> None:
        package_a, package_b = self._handoff_packages()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package_a_path, package_b_path = root / "handoff-a.zip", root / "handoff-b.zip"
            catalog_path, audit_path = root / "handoff-catalog.json", root / "handoff-catalog-audit.json"
            write_package(package_a, package_a_path)
            write_package(package_b, package_b_path)
            command = "downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog"

            def invoke(arguments: list[str]) -> int:
                with contextlib.redirect_stdout(io.StringIO()):
                    return main(arguments)

            self.assertEqual(invoke([command, str(package_b_path), str(package_a_path), "--entry-id", "entry-b", "--entry-id", "entry-a", "--catalog-id", "cli-handoff-catalog", "--destination", str(catalog_path), "--format", "summary"]), 0)
            self.assertEqual(invoke([command + "-verify", str(catalog_path)]), 0)
            self.assertEqual(invoke([command + "-query", str(catalog_path), "--resource", "lineage"]), 0)
            audit_command = command + "-audit"
            self.assertEqual(invoke([audit_command, str(catalog_path), "--destination", str(audit_path), "--format", "summary"]), 0)
            self.assertEqual(invoke([audit_command + "-verify", str(audit_path)]), 0)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def get(path: str, pairs: list[tuple[str, object]]) -> dict[str, object]:
                    query = urlencode([(key, str(value)) for key, value in pairs])
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog"
                built = get(base, [("package", package_b_path), ("package", package_a_path), ("entry_id", "entry-b"), ("entry_id", "entry-a"), ("catalog_id", "http-handoff-catalog")])
                self.assertEqual((built["entry_count"], built["accepted_count"], built["ready_count"]), (2, 2, 2))
                queried = get(base + "/query", [("input", catalog_path), ("resource", "lineage")])
                self.assertEqual((queried["total"], queried["matched"], queried["returned"]), (2, 2, 2))
                audited = get(base + "/audit", [("input", catalog_path)])
                self.assertEqual((audited["check_count"], audited["failed_count"], audited["accepted"]), (16, 0, True))
                schema = get(base + "/schema", [])
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
