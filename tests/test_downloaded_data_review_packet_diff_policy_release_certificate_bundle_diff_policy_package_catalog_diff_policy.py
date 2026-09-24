"""Policy-gate coverage for source-free packet-catalog diffs."""

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
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy import release_policy as build_bundle_release_policy
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_audit import audit_policy as audit_bundle_policy
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package import build_package
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog import build_catalog, write_catalog
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff import build_diff
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy import release_policy, strict_policy, policy_json, query_policy, verify_policy
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_audit import audit_policy, audit_schema, query_audit
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
        packet_id="catalog-policy-packets",
        profile="release",
        maximum_added=1,
        maximum_field_changed=256,
    )
    run_audit = audit_run(run.receipt, package=run.package)
    certificate = build_certificate(run.receipt, run.package, run_audit, certificate_id=run_id + "-certificate")
    certificate_audit = audit_certificate(certificate, run=run.receipt, package=run.package, run_audit=run_audit)
    return build_bundle(certificate, run.package, run.receipt, run_audit, certificate_audit, bundle_id=bundle_id)


class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        left_bundle = _bundle("catalog-policy-left-run", "catalog-policy-left-bundle")
        right_bundle = _bundle("catalog-policy-right-run", "catalog-policy-right-bundle")
        bundle_diff = build_bundle_diff(left_bundle, right_bundle, diff_id="catalog-policy-inner")
        ready_bundle_policy = build_bundle_release_policy(bundle_diff, policy_id="catalog-policy-ready-bundle-policy", maximum_changed=256)
        ready_package = build_package(bundle_diff, ready_bundle_policy, audit_bundle_policy(ready_bundle_policy, diff=bundle_diff), package_id="catalog-policy-ready-package")
        blocked_bundle_policy = build_bundle_release_policy(bundle_diff, policy_id="catalog-policy-blocked-bundle-policy", maximum_changed=0)
        blocked_package = build_package(bundle_diff, blocked_bundle_policy, audit_bundle_policy(blocked_bundle_policy, diff=bundle_diff), package_id="catalog-policy-blocked-package")
        self.left = build_catalog((blocked_package,), entry_ids=("review-entry",), catalog_id="catalog-policy")
        self.right = build_catalog((ready_package,), entry_ids=("review-entry",), catalog_id="catalog-policy")
        self.diff = build_diff(self.left, self.right, diff_id="catalog-policy-transition")

    def test_strict_blocks_recovery_and_release_accepts_it(self) -> None:
        strict = strict_policy(self.diff, policy_id="catalog-policy-strict")
        release = release_policy(self.diff, policy_id="catalog-policy-release", maximum_changed=1)
        self.assertEqual((self.diff.direction, self.diff.state_transition), ("improved", "blocked-to-ready"))
        self.assertEqual((strict.accepted, strict.state, strict.failed_count), (False, "blocked", 4))
        self.assertEqual((release.accepted, release.state, release.failed_count), (True, "ready", 0))
        self.assertEqual(verify_policy(json.loads(policy_json(release))).content_address, release.content_address)
        self.assertEqual(query_policy(strict, passed=False)["matched"], 4)
        audit = audit_policy(release, diff=self.diff)
        self.assertEqual((audit.check_count, audit.passed_count, audit.failed_count, audit.accepted), (14, 14, 0, True))
        self.assertEqual(query_audit(audit, passed=False)["matched"], 0)
        self.assertTrue(audit_schema()["properties"]["checks"])

    def test_tampering_and_policy_recomputation_fail_closed(self) -> None:
        release = release_policy(self.diff, policy_id="catalog-policy-release", maximum_changed=1)
        altered = release.to_dict() | {"maximum_changed": 0}
        with self.assertRaises(ValidationError):
            verify_policy(altered)
        rejected = audit_policy(altered, diff=self.diff)
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.failed_count, 14)
        self.assertEqual(audit_policy(release).passed_count, 14)

    def test_cli_http_and_persistence_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left_path = root / "left.json"
            right_path = root / "right.json"
            diff_path = root / "diff.json"
            policy_path = root / "policy.json"
            audit_path = root / "audit.json"
            write_catalog(self.left, left_path)
            write_catalog(self.right, right_path)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff", str(left_path), str(right_path), "--destination", str(diff_path), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy", str(diff_path), "--profile", "release", "--maximum-changed", "1", "--destination", str(policy_path), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-verify", str(policy_path)]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-query", str(policy_path), "--passed"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-audit", str(policy_path), "--diff", str(diff_path), "--destination", str(audit_path), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-audit-query", str(audit_path), "--failed"]), 0)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def get(path: str, values: dict[str, object]) -> dict[str, object]:
                    query = urlencode({key: str(value) for key, value in values.items()})
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy"
                built = get(base, {"input": diff_path, "profile": "release", "maximum_changed": 1, "policy_id": "http-catalog-policy"})
                self.assertTrue(built["accepted"])
                audited = get(base + "/audit", {"input": policy_path, "diff": diff_path})
                self.assertTrue(audited["accepted"])
                schema = get(base + "/schema", {})
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
