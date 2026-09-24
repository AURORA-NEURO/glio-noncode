"""Coverage for longitudinal comparisons of packet-package handoff catalogs."""

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

from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog import build_catalog as build_source_catalog
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff import build_diff as build_inner_diff
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy import release_policy as build_inner_policy
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package import build_package as build_inner_package
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog import build_catalog as build_mid_catalog
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff import build_diff as build_mid_diff
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy import release_policy as build_mid_policy
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_audit import audit_policy as build_mid_audit
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package import build_package as build_mid_package

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog import build_catalog as build_recursive_catalog
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff import build_diff as build_recursive_diff
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy import release_policy as build_recursive_policy
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_audit import audit_policy as build_recursive_audit
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package import build_package as build_handoff_package
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog import build_catalog, write_catalog
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff import build_diff, query_diff, verify_diff, write_diff
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_audit import audit_diff, query_audit, write_audit
from glio_noncode.errors import ValidationError


class PacketPackageHandoffCatalogDiffTest(unittest.TestCase):
    def setUp(self) -> None:
        source = build_source_catalog((), catalog_id="handoff-catalog-diff-source")
        inner_diff = build_inner_diff(source, source, diff_id="handoff-catalog-diff-inner-diff")
        inner_policy = build_inner_policy(inner_diff, policy_id="handoff-catalog-diff-inner-policy", require_ready=False)
        inner_a = build_inner_package(inner_diff, inner_policy, package_id="handoff-catalog-diff-inner-a")
        inner_b = build_inner_package(inner_diff, inner_policy, package_id="handoff-catalog-diff-inner-b")
        mid_left = build_mid_catalog((inner_a.package_bytes,), entry_ids=("entry-a",), catalog_id="handoff-catalog-diff-mid")
        mid_right = build_mid_catalog((inner_b.package_bytes,), entry_ids=("entry-a",), catalog_id="handoff-catalog-diff-mid")
        mid_diff = build_mid_diff(mid_left, mid_right, diff_id="handoff-catalog-diff-mid-diff")
        mid_policy = build_mid_policy(mid_diff, policy_id="handoff-catalog-diff-mid-policy")
        mid_audit = build_mid_audit(mid_policy, diff=mid_diff)
        mid_a = build_mid_package(mid_diff, mid_policy, mid_audit, package_id="handoff-catalog-diff-mid-a")
        mid_b = build_mid_package(mid_diff, mid_policy, mid_audit, package_id="handoff-catalog-diff-mid-b")
        recursive_left = build_recursive_catalog((mid_a.package_bytes,), entry_ids=("entry-a",), catalog_id="handoff-catalog-diff")
        recursive_right = build_recursive_catalog((mid_b.package_bytes,), entry_ids=("entry-a",), catalog_id="handoff-catalog-diff")
        recursive_diff = build_recursive_diff(recursive_left, recursive_right, diff_id="handoff-catalog-diff-deep-diff")
        recursive_policy = build_recursive_policy(recursive_diff, policy_id="handoff-catalog-diff-deep-policy")
        recursive_audit = build_recursive_audit(recursive_policy, diff=recursive_diff)
        self.package_a = build_handoff_package(recursive_diff, recursive_policy, recursive_audit, package_id="handoff-catalog-diff-package-a")
        self.package_b = build_handoff_package(recursive_diff, recursive_policy, recursive_audit, package_id="handoff-catalog-diff-package-b")

    def _catalogs(self):
        empty = build_catalog((), catalog_id="handoff-catalog-diff")
        left = build_catalog((self.package_a.package_bytes,), entry_ids=("entry-a",), catalog_id="handoff-catalog-diff")
        right = build_catalog((self.package_b.package_bytes,), entry_ids=("entry-a",), catalog_id="handoff-catalog-diff")
        expanded = build_catalog((self.package_a.package_bytes, self.package_b.package_bytes), entry_ids=("entry-a", "entry-b"), catalog_id="handoff-catalog-diff")
        return empty, left, right, expanded

    def test_added_removed_changed_unchanged_and_audit(self) -> None:
        empty, left, right, expanded = self._catalogs()
        added = build_diff(empty, left, diff_id="handoff-catalog-diff-added")
        removed = build_diff(left, empty, diff_id="handoff-catalog-diff-removed")
        changed = build_diff(left, right, diff_id="handoff-catalog-diff-changed")
        unchanged = build_diff(left, left, diff_id="handoff-catalog-diff-unchanged")
        self.assertEqual((added.added_count, added.removed_count, added.changed_count, added.unchanged_count, added.direction, added.state_transition), (1, 0, 0, 0, "improved", "empty-to-ready"))
        self.assertEqual((removed.added_count, removed.removed_count, removed.direction, removed.state_transition), (0, 1, "regressed", "ready-to-empty"))
        self.assertEqual((changed.added_count, changed.removed_count, changed.changed_count, changed.unchanged_count, changed.direction), (0, 0, 1, 0, "changed"))
        self.assertEqual((unchanged.changed_count, unchanged.unchanged_count, unchanged.direction), (0, 1, "unchanged"))
        self.assertIn("package_id", changed.items[0].changed_fields)
        self.assertEqual(build_diff(expanded, expanded, diff_id="handoff-catalog-diff-expanded").unchanged_count, 2)
        receipt = audit_diff(changed, left=left, right=right)
        self.assertEqual((receipt.check_count, receipt.passed_count, receipt.failed_count, receipt.accepted), (13, 13, 0, True))
        self.assertEqual(query_audit(receipt, passed=False)["matched"], 0)
        self.assertEqual(query_diff(changed, change="changed")["matched"], 1)

    def test_determinism_lineage_mismatch_and_tamper_fail_closed(self) -> None:
        _empty, left, right, _expanded = self._catalogs()
        first = build_diff(left, right, diff_id="handoff-catalog-diff-deterministic")
        second = build_diff(left, right, diff_id="handoff-catalog-diff-deterministic")
        self.assertEqual(first.content_address, second.content_address)
        with self.assertRaises(ValidationError):
            build_diff(left, build_catalog((), catalog_id="other-handoff-catalog"), diff_id="handoff-catalog-diff-mismatch")
        tampered = first.to_dict()
        tampered["direction"] = "regressed"
        with self.assertRaises(ValidationError):
            verify_diff(tampered)

    def test_cli_http_and_atomic_persistence(self) -> None:
        _empty, left, right, _expanded = self._catalogs()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left_path, right_path = root / "left.json", root / "right.json"
            diff_path, audit_path = root / "catalog-diff.json", root / "catalog-diff-audit.json"
            write_catalog(left, left_path)
            write_catalog(right, right_path)
            command = "downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-diff"

            def invoke(arguments: list[str]) -> int:
                with contextlib.redirect_stdout(io.StringIO()):
                    return main(arguments)

            self.assertEqual(invoke([command, str(left_path), str(right_path), "--diff-id", "cli-handoff-catalog-diff", "--destination", str(diff_path), "--format", "summary"]), 0)
            self.assertEqual(invoke([command + "-verify", str(diff_path)]), 0)
            self.assertEqual(invoke([command + "-query", str(diff_path), "--change", "changed"]), 0)
            audit_command = command + "-audit"
            self.assertEqual(invoke([audit_command, str(diff_path), "--left", str(left_path), "--right", str(right_path), "--destination", str(audit_path), "--format", "summary"]), 0)
            self.assertEqual(invoke([audit_command + "-verify", str(audit_path)]), 0)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff"

                def get(path: str, pairs: list[tuple[str, object]]) -> dict[str, object]:
                    query = urlencode([(key, str(value)) for key, value in pairs])
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                built = get(base, [("left", left_path), ("right", right_path), ("diff_id", "http-handoff-catalog-diff")])
                self.assertEqual((built["changed_count"], built["direction"]), (1, "changed"))
                queried = get(base + "/query", [("input", diff_path), ("change", "changed")])
                self.assertEqual((queried["matched"], queried["returned"]), (1, 1))
                audited = get(base + "/audit", [("input", diff_path), ("left", left_path), ("right", right_path)])
                self.assertEqual((audited["check_count"], audited["failed_count"], audited["accepted"]), (13, 0, True))
                schema = get(base + "/schema", [])
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
