"""Longitudinal diff coverage for source-free packet catalogs."""

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
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy import release_policy, strict_policy
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_audit import audit_policy
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package import build_package, write_package
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog import build_catalog, catalog_json, write_catalog
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff import build_diff, diff_json, diff_schema, query_diff, render_diff_markdown, verify_diff, write_diff
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_audit import audit_diff, audit_json, audit_schema, query_audit
from glio_noncode.downloaded_data_review_packet_diff_policy_run import build_run
from glio_noncode.downloaded_data_review_packet_diff_policy_run_audit import audit_run
from glio_noncode.errors import ValidationError


def _source_bytes(payload: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("data.csv", payload)
    return output.getvalue()


def _bundle(run_id: str, bundle_id: str):
    run = build_run(
        _source_bytes("record_id,score\nA,1\nB,2\n"),
        _source_bytes("record_id,score,group\nA,1,x\nB,3,y\nC,4,z\n"),
        run_id=run_id,
        packet_id="catalog-diff-packets",
        profile="release",
        maximum_added=1,
        maximum_field_changed=256,
    )
    run_audit = audit_run(run.receipt, package=run.package)
    certificate = build_certificate(run.receipt, run.package, run_audit, certificate_id=run_id + "-certificate")
    certificate_audit = audit_certificate(certificate, run=run.receipt, package=run.package, run_audit=run_audit)
    return build_bundle(certificate, run.package, run.receipt, run_audit, certificate_audit, bundle_id=bundle_id)


class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffTest(unittest.TestCase):
    def setUp(self) -> None:
        left_bundle = _bundle("catalog-diff-left-run", "catalog-diff-left-bundle")
        right_bundle = _bundle("catalog-diff-right-run", "catalog-diff-right-bundle")
        from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff import build_diff as build_bundle_diff
        bundle_diff = build_bundle_diff(left_bundle, right_bundle, diff_id="catalog-diff-inner")
        ready_policy = release_policy(bundle_diff, policy_id="catalog-diff-ready-policy", maximum_added=32, maximum_changed=256)
        blocked_policy = strict_policy(bundle_diff, policy_id="catalog-diff-blocked-policy")
        ready_package = build_package(bundle_diff, ready_policy, audit_policy(ready_policy, diff=bundle_diff), package_id="catalog-diff-ready-package")
        blocked_package = build_package(bundle_diff, blocked_policy, audit_policy(blocked_policy, diff=bundle_diff), package_id="catalog-diff-blocked-package")
        self.left = build_catalog((blocked_package,), entry_ids=("review-entry",), catalog_id="catalog-diff")
        self.right = build_catalog((ready_package,), entry_ids=("review-entry",), catalog_id="catalog-diff")
        self.diff = build_diff(self.left, self.right, diff_id="catalog-diff-ready-transition")

    def test_improvement_round_trip_queries_and_audit(self) -> None:
        self.assertEqual((self.diff.added_count, self.diff.removed_count, self.diff.changed_count, self.diff.unchanged_count), (0, 0, 1, 0))
        self.assertEqual((self.diff.direction, self.diff.state_transition), ("improved", "blocked-to-ready"))
        self.assertEqual(verify_diff(json.loads(diff_json(self.diff))).content_address, self.diff.content_address)
        self.assertEqual(query_diff(self.diff, change="changed")["matched"], 1)
        self.assertEqual(query_diff(self.diff, direction="improved")["matched"], 1)
        self.assertIn("blocked-to-ready", render_diff_markdown(self.diff))
        self.assertTrue(diff_schema()["properties"]["items"])
        audit = audit_diff(self.diff, left=self.left, right=self.right)
        self.assertEqual((audit.check_count, audit.passed_count, audit.failed_count, audit.accepted), (13, 13, 0, True))
        self.assertEqual(query_audit(audit, passed=False)["matched"], 0)
        self.assertTrue(audit_schema()["properties"]["checks"])

    def test_tampering_and_mismatched_catalogs_fail_closed(self) -> None:
        altered = self.diff.to_dict() | {"changed_count": 0}
        with self.assertRaises(ValidationError):
            verify_diff(altered)
        rejected = audit_diff(altered, left=self.left, right=self.right)
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.failed_count, 13)
        with self.assertRaises(ValidationError):
            build_diff(self.left, build_catalog((), catalog_id="other-catalog"), diff_id="mismatch")

    def test_cli_http_and_persistence_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left_path = root / "left.json"
            right_path = root / "right.json"
            diff_path = root / "diff.json"
            audit_path = root / "audit.json"
            write_catalog(self.left, left_path)
            write_catalog(self.right, right_path)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff", str(left_path), str(right_path), "--destination", str(diff_path), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-verify", str(diff_path)]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-query", str(diff_path), "--direction", "improved"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-audit", str(diff_path), "--left", str(left_path), "--right", str(right_path), "--destination", str(audit_path), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-audit-query", str(audit_path), "--failed"]), 0)
            self.assertEqual(write_diff(self.diff, root / "typed-diff.json").content_address, self.diff.content_address)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def get(path: str, values: dict[str, object]) -> dict[str, object]:
                    query = urlencode({key: str(value) for key, value in values.items()})
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                built = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff", {"left": left_path, "right": right_path, "diff_id": "http-catalog-diff", "destination": root / "http-diff.json"})
                self.assertEqual(built["direction"], "improved")
                queried = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/query", {"input": diff_path, "change": "changed"})
                self.assertEqual(queried["matched"], 1)
                audited = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/audit", {"input": diff_path, "left": left_path, "right": right_path})
                self.assertTrue(audited["accepted"])
                schema = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/schema", {})
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
