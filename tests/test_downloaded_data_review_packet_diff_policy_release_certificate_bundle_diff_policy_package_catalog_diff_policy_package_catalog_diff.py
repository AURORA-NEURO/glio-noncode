"""Longitudinal diff coverage for portable packet-catalog catalogs."""

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
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate import build_certificate
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_audit import audit_certificate
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle import build_bundle
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff import build_diff as build_bundle_diff
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy import release_policy as build_bundle_release_policy, strict_policy as build_bundle_strict_policy
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_audit import audit_policy as audit_bundle_policy
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package import build_package as build_bundle_package
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog import build_catalog as build_inner_catalog
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff import build_diff as build_inner_diff
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy import release_policy as build_catalog_release_policy, strict_policy as build_catalog_strict_policy
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_audit import audit_policy as audit_catalog_policy
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package import build_package
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog import build_catalog, write_catalog
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff import build_diff, diff_json, diff_schema, query_diff, render_diff_markdown, verify_diff
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_audit import audit_diff, audit_schema, query_audit
from glio_noncode.downloaded_data_review_packet_diff_policy_run import build_run
from glio_noncode.downloaded_data_review_packet_diff_policy_run_audit import audit_run
from glio_noncode.errors import ValidationError


def _source_bytes(payload: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("data.csv", payload)
    return output.getvalue()


def _bundle(run_id: str, bundle_id: str):
    run = build_run(_source_bytes("record_id,score\nA,1\nB,2\n"), _source_bytes("record_id,score,group\nA,1,x\nB,3,y\nC,4,z\n"), run_id=run_id, packet_id="portable-catalog-diff-catalogs", profile="release", maximum_added=1, maximum_field_changed=256)
    run_audit = audit_run(run.receipt, package=run.package)
    certificate = build_certificate(run.receipt, run.package, run_audit, certificate_id=run_id + "-certificate")
    certificate_audit = audit_certificate(certificate, run=run.receipt, package=run.package, run_audit=run_audit)
    return build_bundle(certificate, run.package, run.receipt, run_audit, certificate_audit, bundle_id=bundle_id)


class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffTest(unittest.TestCase):
    def setUp(self) -> None:
        left_bundle = _bundle("portable-catalog-diff-left-run", "portable-catalog-diff-left-bundle")
        right_bundle = _bundle("portable-catalog-diff-right-run", "portable-catalog-diff-right-bundle")
        bundle_diff = build_bundle_diff(left_bundle, right_bundle, diff_id="portable-catalog-diff-inner-bundle-diff")
        ready_bundle_policy = build_bundle_release_policy(bundle_diff, policy_id="portable-catalog-diff-ready-bundle-policy", maximum_changed=256)
        blocked_bundle_policy = build_bundle_strict_policy(bundle_diff, policy_id="portable-catalog-diff-blocked-bundle-policy")
        ready_bundle_package = build_bundle_package(bundle_diff, ready_bundle_policy, audit_bundle_policy(ready_bundle_policy, diff=bundle_diff), package_id="portable-catalog-diff-ready-bundle-package")
        blocked_bundle_package = build_bundle_package(bundle_diff, blocked_bundle_policy, audit_bundle_policy(blocked_bundle_policy, diff=bundle_diff), package_id="portable-catalog-diff-blocked-bundle-package")
        inner_left = build_inner_catalog((blocked_bundle_package,), entry_ids=("portable-entry",), catalog_id="portable-catalog-diff-inner-catalog")
        inner_right = build_inner_catalog((ready_bundle_package,), entry_ids=("portable-entry",), catalog_id="portable-catalog-diff-inner-catalog")
        inner_diff = build_inner_diff(inner_left, inner_right, diff_id="portable-catalog-diff-inner-catalog-diff")
        ready_policy = build_catalog_release_policy(inner_diff, policy_id="portable-catalog-diff-ready-policy", maximum_changed=256)
        blocked_policy = build_catalog_strict_policy(inner_diff, policy_id="portable-catalog-diff-blocked-policy")
        self.ready = build_package(inner_diff, ready_policy, audit_catalog_policy(ready_policy, diff=inner_diff), package_id="portable-catalog-diff-ready-package")
        self.ready_two = build_package(inner_diff, ready_policy, audit_catalog_policy(ready_policy, diff=inner_diff), package_id="portable-catalog-diff-ready-two-package")
        self.blocked = build_package(inner_diff, blocked_policy, audit_catalog_policy(blocked_policy, diff=inner_diff), package_id="portable-catalog-diff-blocked-package")

    def test_added_changed_unchanged_rollups_and_independent_audit(self) -> None:
        left = build_catalog((self.blocked, self.ready), entry_ids=("changed-entry", "stable-entry"), catalog_id="portable-catalog-diff-catalog")
        right = build_catalog((self.ready_two, self.ready), entry_ids=("changed-entry", "stable-entry"), catalog_id="portable-catalog-diff-catalog")
        diff = build_diff(left, right, diff_id="portable-catalog-diff")
        self.assertEqual((diff.added_count, diff.removed_count, diff.changed_count, diff.unchanged_count), (0, 0, 1, 1))
        self.assertEqual((diff.left_posture, diff.right_posture, diff.state_transition, diff.direction), ("mixed", "ready", "mixed-to-ready", "improved"))
        self.assertEqual(query_diff(diff, change="changed")["matched"], 1)
        self.assertEqual(query_diff(diff, direction="improved")["matched"], 2)
        self.assertIn("mixed-to-ready", render_diff_markdown(diff))
        self.assertTrue(diff_schema()["properties"]["items"])
        receipt = audit_diff(diff, left=left, right=right)
        self.assertEqual((receipt.check_count, receipt.passed_count, receipt.failed_count, receipt.accepted), (13, 13, 0, True))
        self.assertEqual(query_audit(receipt, passed=False)["matched"], 0)
        self.assertTrue(audit_schema()["properties"]["checks"])

    def test_added_removed_and_tampering_fail_closed(self) -> None:
        left = build_catalog((self.ready,), entry_ids=("removed-entry",), catalog_id="portable-catalog-diff-removal")
        right = build_catalog((self.ready_two,), entry_ids=("added-entry",), catalog_id="portable-catalog-diff-removal")
        diff = build_diff(left, right, diff_id="portable-catalog-diff-added-removed")
        self.assertEqual((diff.added_count, diff.removed_count, diff.changed_count, diff.unchanged_count), (1, 1, 0, 0))
        tampered = json.loads(diff_json(diff))
        tampered["direction"] = "regressed"
        with self.assertRaises(ValidationError):
            verify_diff(tampered)
        rejected = audit_diff(tampered, left=left, right=right)
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.failed_count, 13)
        with self.assertRaises(ValidationError):
            build_diff(left, right, diff_id="bad/id")

    def test_cli_http_and_persistence_surfaces(self) -> None:
        left = build_catalog((self.blocked, self.ready), entry_ids=("changed-entry", "stable-entry"), catalog_id="portable-catalog-diff-surfaces")
        right = build_catalog((self.ready_two, self.ready), entry_ids=("changed-entry", "stable-entry"), catalog_id="portable-catalog-diff-surfaces")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left_path = root / "left-catalog.json"
            right_path = root / "right-catalog.json"
            diff_path = root / "catalog-diff.json"
            audit_path = root / "catalog-diff-audit.json"
            write_catalog(left, left_path)
            write_catalog(right, right_path)
            command = "downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-package-catalog-diff"
            self.assertEqual(main([command, str(left_path), str(right_path), "--diff-id", "cli-portable-catalog-diff", "--destination", str(diff_path), "--format", "summary"]), 0)
            self.assertEqual(main([command + "-verify", str(diff_path)]), 0)
            self.assertEqual(main([command + "-query", str(diff_path), "--change", "changed"]), 0)
            audit_command = command + "-audit"
            self.assertEqual(main([audit_command, str(diff_path), "--left", str(left_path), "--right", str(right_path), "--destination", str(audit_path), "--format", "summary"]), 0)
            self.assertEqual(main([audit_command + "-verify", str(audit_path)]), 0)
            self.assertEqual(main([audit_command + "-query", str(audit_path), "--failed"]), 0)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def get(path: str, pairs: list[tuple[str, object]]) -> dict[str, object]:
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{urlencode([(key, str(value)) for key, value in pairs])}", timeout=20) as response:
                        return json.loads(response.read())

                base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff"
                built = get(base, [("left", left_path), ("right", right_path), ("diff_id", "http-portable-catalog-diff")])
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
