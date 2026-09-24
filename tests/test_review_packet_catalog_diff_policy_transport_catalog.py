"""Deep contracts for source-free catalogs of fixed downloaded-data policy transports."""

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
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff import (
    build_diff,
    catalog_model,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy import (
    release_policy,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_transport import (
    build_transport,
    write_transport,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_transport_catalog import (
    build_transport_catalog,
    query_transport_catalog,
    verify_transport_catalog,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_tr_cat_aud import (
    audit_transport_catalog,
    query_audit,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_gate_aud import (
    audit_policy,
)
from glio_noncode.errors import ValidationError


class DownloadedDataReviewPacketTransportCatalogTest(unittest.TestCase):
    def setUp(self) -> None:
        catalog = catalog_model.build_catalog((), catalog_id="review-packet-catalog-source")
        diff = build_diff(catalog, catalog, diff_id="review-packet-catalog-diff")
        policy = release_policy(diff, policy_id="review-packet-catalog-policy", require_ready=False)
        policy_audit = audit_policy(policy, diff=diff)
        self.packet_a = build_transport(diff, policy, policy_audit, package_id="review-packet-catalog-a")
        self.packet_b = build_transport(diff, policy, policy_audit, package_id="review-packet-catalog-b")
        blocked_policy = release_policy(diff, policy_id="review-packet-catalog-blocked-policy", require_ready=False, require_change=True)
        blocked_audit = audit_policy(blocked_policy, diff=diff)
        self.blocked = build_transport(diff, blocked_policy, blocked_audit, package_id="review-packet-catalog-blocked")

    def test_deterministic_rollup_and_independent_audit(self) -> None:
        first = build_transport_catalog((self.packet_b.package_bytes, self.packet_a.package_bytes, self.blocked.package_bytes), entry_ids=("entry-b", "entry-a", "entry-blocked"), catalog_id="review-packet-catalog")
        second = build_transport_catalog((self.packet_a.package_bytes, self.packet_b.package_bytes, self.blocked.package_bytes), entry_ids=("entry-a", "entry-b", "entry-blocked"), catalog_id="review-packet-catalog")
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(tuple(item.entry_id for item in first.entries), ("entry-a", "entry-b", "entry-blocked"))
        self.assertEqual((first.entry_count, first.accepted_count, first.ready_count, first.blocked_count), (3, 2, 2, 1))
        self.assertEqual(first.total_package_bytes, sum(item.package_byte_count for item in first.entries))
        self.assertEqual(query_transport_catalog(first, resource="accepted")["returned"], 2)
        receipt = audit_transport_catalog(first)
        self.assertEqual((receipt.check_count, receipt.passed_count, receipt.failed_count, receipt.accepted), (16, 16, 0, True))
        self.assertEqual(query_audit(receipt, passed=False)["matched"], 0)

    def test_duplicate_tamper_and_public_bounds_fail_closed(self) -> None:
        with self.assertRaises(ValidationError):
            build_transport_catalog((self.packet_a.package_bytes, self.packet_a.package_bytes), catalog_id="review-packet-catalog-duplicate")
        catalog = build_transport_catalog((self.packet_a.package_bytes,), catalog_id="review-packet-catalog-tamper")
        tampered = catalog.to_dict()
        tampered["total_member_bytes"] += 1
        with self.assertRaises(ValidationError):
            verify_transport_catalog(tampered)
        self.assertNotIn("agent", json.dumps(catalog.to_dict()).lower())
        self.assertNotIn("model", json.dumps(catalog.to_dict()).lower())

    def test_cli_http_and_atomic_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet_a_path, packet_b_path = root / "packet-a.zip", root / "packet-b.zip"
            catalog_path, audit_path = root / "catalog.json", root / "catalog-audit.json"
            write_transport(self.packet_a, packet_a_path)
            write_transport(self.packet_b, packet_b_path)
            def invoke(arguments: list[str]) -> int:
                with contextlib.redirect_stdout(io.StringIO()):
                    return main(arguments)
            self.assertEqual(invoke(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-transport-catalog", str(packet_b_path), str(packet_a_path), "--entry-id", "entry-b", "--entry-id", "entry-a", "--catalog-id", "cli-review-packet-catalog", "--destination", str(catalog_path), "--format", "summary"]), 0)
            self.assertEqual(invoke(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-transport-catalog-verify", str(catalog_path)]), 0)
            self.assertEqual(invoke(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-transport-catalog-query", str(catalog_path), "--resource", "lineage"]), 0)
            self.assertEqual(invoke(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-transport-catalog-audit", str(catalog_path), "--destination", str(audit_path), "--format", "summary"]), 0)
            self.assertEqual(invoke(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-transport-catalog-audit-verify", str(audit_path)]), 0)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def get(path: str, pairs: list[tuple[str, object]]) -> dict[str, object]:
                    query = urlencode([(key, str(value)) for key, value in pairs])
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())
                built = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/transport/catalog", [("package", packet_b_path), ("package", packet_a_path), ("entry_id", "entry-b"), ("entry_id", "entry-a"), ("catalog_id", "http-review-packet-catalog")])
                self.assertEqual((built["entry_count"], built["accepted_count"], built["ready_count"]), (2, 2, 2))
                queried = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/transport/catalog/query", [("input", catalog_path), ("resource", "lineage")])
                self.assertEqual((queried["total"], queried["matched"], queried["returned"]), (2, 2, 2))
                audited = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/transport/catalog/audit", [("input", catalog_path)])
                self.assertEqual((audited["check_count"], audited["failed_count"], audited["accepted"]), (16, 0, True))
                self.assertIn("entry_count", get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/transport/catalog/schema", {}).get("properties", {}))
                self.assertIn("operations", get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/transport/catalog/capabilities", []))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
