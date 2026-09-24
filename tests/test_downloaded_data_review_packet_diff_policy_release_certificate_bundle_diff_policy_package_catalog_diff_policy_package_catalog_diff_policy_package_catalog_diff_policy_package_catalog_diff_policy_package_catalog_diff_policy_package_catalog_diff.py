"""Deep contracts for source-free review-packet catalog comparisons."""

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
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff import (
    build_diff as build_source_diff,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff import (
    catalog_model,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy import (
    release_policy,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package import (
    build_package,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog import (
    build_catalog,
    write_catalog,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff import (
    build_diff,
    query_diff,
    verify_diff,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_audit import (
    audit_diff,
    query_audit,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_policy_audit import (
    audit_policy,
)
from glio_noncode.errors import ValidationError


class ReviewPacketCatalogDiffTest(unittest.TestCase):
    def setUp(self) -> None:
        source = catalog_model.build_catalog((), catalog_id="review-packet-catalog-diff-source")
        source_diff = build_source_diff(source, source, diff_id="review-packet-catalog-diff-source-diff")
        policy = release_policy(source_diff, policy_id="review-packet-catalog-diff-policy", require_ready=False)
        policy_audit = audit_policy(policy, diff=source_diff)
        packet_a = build_package(source_diff, policy, policy_audit, package_id="review-packet-catalog-diff-a")
        packet_b = build_package(source_diff, policy, policy_audit, package_id="review-packet-catalog-diff-b")
        self.left = build_catalog((packet_a.package_bytes,), entry_ids=("entry-a",), catalog_id="review-packet-catalog-diff")
        self.right = build_catalog((packet_b.package_bytes,), entry_ids=("entry-a",), catalog_id="review-packet-catalog-diff")
        self.expanded = build_catalog((packet_a.package_bytes, packet_b.package_bytes), entry_ids=("entry-a", "entry-b"), catalog_id="review-packet-catalog-diff")

    def test_added_removed_changed_unchanged_and_audit(self) -> None:
        changed = build_diff(self.left, self.right, diff_id="review-packet-catalog-diff-changed")
        self.assertEqual((changed.added_count, changed.removed_count, changed.changed_count, changed.unchanged_count), (0, 0, 1, 0))
        self.assertEqual((changed.left_posture, changed.right_posture, changed.state_transition, changed.direction), ("ready", "ready", "same-ready", "changed"))
        self.assertEqual(query_diff(changed, change="changed")["matched"], 1)
        added = build_diff(self.left, self.expanded, diff_id="review-packet-catalog-diff-added")
        removed = build_diff(self.expanded, self.left, diff_id="review-packet-catalog-diff-removed")
        self.assertEqual((added.added_count, added.removed_count), (1, 0))
        self.assertEqual((removed.added_count, removed.removed_count), (0, 1))
        receipt = audit_diff(changed, left=self.left, right=self.right)
        self.assertEqual((receipt.check_count, receipt.passed_count, receipt.failed_count, receipt.accepted), (13, 13, 0, True))
        self.assertEqual(query_audit(receipt, passed=False)["matched"], 0)

    def test_determinism_lineage_mismatch_and_tamper_fail_closed(self) -> None:
        first = build_diff(self.left, self.right, diff_id="review-packet-catalog-diff-deterministic")
        second = build_diff(self.right, self.left, diff_id="review-packet-catalog-diff-deterministic")
        self.assertNotEqual(first.content_address, second.content_address)
        with self.assertRaises(ValidationError):
            build_diff(self.left, build_catalog((), catalog_id="other-catalog"), diff_id="review-packet-catalog-diff-mismatch")
        tampered = first.to_dict()
        tampered["changed_count"] = 0
        with self.assertRaises(ValidationError):
            verify_diff(tampered)
        self.assertNotIn("agent", json.dumps(first.to_dict()).lower())
        self.assertNotIn("model", json.dumps(first.to_dict()).lower())
        self.assertNotIn("language", json.dumps(first.to_dict()).lower())

    def test_cli_http_and_atomic_persistence(self) -> None:
        command = "downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-diff"
        route = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left_path, right_path = root / "left.json", root / "right.json"
            diff_path, audit_path = root / "diff.json", root / "audit.json"
            write_catalog(self.left, left_path)
            write_catalog(self.right, right_path)
            def invoke(arguments: list[str]) -> int:
                with contextlib.redirect_stdout(io.StringIO()):
                    return main(arguments)
            self.assertEqual(invoke([command, str(left_path), str(right_path), "--diff-id", "cli-review-packet-catalog-diff", "--destination", str(diff_path), "--format", "summary"]), 0)
            self.assertEqual(invoke([command + "-verify", str(diff_path)]), 0)
            self.assertEqual(invoke([command + "-query", str(diff_path), "--change", "changed"]), 0)
            self.assertEqual(invoke([command + "-audit", str(diff_path), "--left", str(left_path), "--right", str(right_path), "--destination", str(audit_path), "--format", "summary"]), 0)
            self.assertEqual(invoke([command + "-audit-verify", str(audit_path)]), 0)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def get(path: str, pairs: list[tuple[str, object]]) -> dict[str, object]:
                    query = urlencode([(key, str(value)) for key, value in pairs])
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())
                built = get(route, [("left", left_path), ("right", right_path), ("diff_id", "http-review-packet-catalog-diff")])
                self.assertEqual((built["changed_count"], built["direction"]), (1, "changed"))
                queried = get(route + "/query", [("input", diff_path), ("change", "changed")])
                self.assertEqual((queried["total"], queried["matched"], queried["returned"]), (1, 1, 1))
                audited = get(route + "/audit", [("input", diff_path), ("left", left_path), ("right", right_path)])
                self.assertEqual((audited["check_count"], audited["failed_count"], audited["accepted"]), (13, 0, True))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
