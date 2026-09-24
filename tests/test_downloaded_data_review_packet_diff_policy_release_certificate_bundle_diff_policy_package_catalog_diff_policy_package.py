"""Portable packet coverage for packet-catalog diff policy evidence."""

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
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog import build_catalog
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff import build_diff
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy import release_policy, strict_policy, policy_json, write_policy
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_audit import audit_policy, audit_json
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package import build_package, load_package, package_json, package_schema, query_package, render_package_markdown, verify_package, write_package
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_audit import audit_package, audit_schema, query_audit, write_audit
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
        packet_id="catalog-policy-package-packets",
        profile="release",
        maximum_added=1,
        maximum_field_changed=256,
    )
    run_audit = audit_run(run.receipt, package=run.package)
    certificate = build_certificate(run.receipt, run.package, run_audit, certificate_id=run_id + "-certificate")
    certificate_audit = audit_certificate(certificate, run=run.receipt, package=run.package, run_audit=run_audit)
    return build_bundle(certificate, run.package, run.receipt, run_audit, certificate_audit, bundle_id=bundle_id)


class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyPackageTest(unittest.TestCase):
    def setUp(self) -> None:
        left_bundle = _bundle("catalog-policy-package-left-run", "catalog-policy-package-left-bundle")
        right_bundle = _bundle("catalog-policy-package-right-run", "catalog-policy-package-right-bundle")
        bundle_diff = build_bundle_diff(left_bundle, right_bundle, diff_id="catalog-policy-package-inner")
        ready_bundle_policy = build_bundle_release_policy(bundle_diff, policy_id="catalog-policy-package-ready-bundle-policy", maximum_changed=256)
        ready_package = build_bundle_package(bundle_diff, ready_bundle_policy, audit_bundle_policy(ready_bundle_policy, diff=bundle_diff), package_id="catalog-policy-package-ready-package")
        blocked_bundle_policy = build_bundle_strict_policy(bundle_diff, policy_id="catalog-policy-package-blocked-bundle-policy")
        blocked_package = build_bundle_package(bundle_diff, blocked_bundle_policy, audit_bundle_policy(blocked_bundle_policy, diff=bundle_diff), package_id="catalog-policy-package-blocked-package")
        left = build_catalog((blocked_package,), entry_ids=("review-entry",), catalog_id="catalog-policy-package")
        right = build_catalog((ready_package,), entry_ids=("review-entry",), catalog_id="catalog-policy-package")
        self.diff = build_diff(left, right, diff_id="catalog-policy-package-transition")
        self.policy = release_policy(self.diff, policy_id="catalog-policy-package-release", maximum_changed=1)
        self.policy_audit = audit_policy(self.policy, diff=self.diff)
        self.package = build_package(self.diff, self.policy, self.policy_audit, package_id="catalog-policy-package-ready")

    def test_deterministic_round_trip_and_independent_audit(self) -> None:
        self.assertEqual(self.package.manifest.policy_state, "ready")
        self.assertEqual(self.package.manifest.audit_accepted, True)
        self.assertEqual(verify_package(self.package).package_address, self.package.package_address)
        self.assertEqual(len(load_package(self.package)), 4)
        self.assertEqual(query_package(self.package, resource="members")["total"], 4)
        self.assertIn("Source-free after construction", render_package_markdown(self.package))
        self.assertTrue(package_schema()["properties"]["manifest"])
        receipt = audit_package(self.package)
        self.assertEqual((receipt.check_count, receipt.passed_count, receipt.failed_count, receipt.accepted), (15, 15, 0, True))
        self.assertEqual(query_audit(receipt, passed=False)["matched"], 0)
        self.assertTrue(audit_schema()["properties"]["checks"])

    def test_blocked_policy_is_preserved_but_tampering_fails_closed(self) -> None:
        blocked_policy = strict_policy(self.diff, policy_id="catalog-policy-package-strict")
        blocked_audit = audit_policy(blocked_policy, diff=self.diff)
        blocked = build_package(self.diff, blocked_policy, blocked_audit, package_id="catalog-policy-package-blocked")
        self.assertEqual((blocked.manifest.policy_state, blocked.manifest.policy_accepted, blocked.manifest.audit_accepted), ("blocked", False, True))
        tampered = blocked.package_bytes[:-1] + bytes([blocked.package_bytes[-1] ^ 1])
        with self.assertRaises(ValidationError):
            verify_package(tampered)
        rejected = audit_package(tampered)
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.failed_count, 15)

    def test_cli_http_and_persistence_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diff_path = root / "catalog-diff.json"
            policy_path = root / "catalog-policy.json"
            policy_audit_path = root / "catalog-policy-audit.json"
            package_path = root / "catalog-policy-package.zip"
            package_audit_path = root / "catalog-policy-package-audit.json"
            diff_path.write_text(json.dumps(json.loads(self.diff_json()), separators=(",", ":")) + "\n", encoding="utf-8")
            write_policy(self.policy, policy_path)
            policy_audit_path.write_text(audit_json(self.policy_audit), encoding="utf-8")
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-package", str(diff_path), str(policy_path), str(policy_audit_path), "--package-id", "cli-catalog-policy-package", "--destination", str(package_path), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-package-verify", str(package_path)]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-package-query", str(package_path), "--resource", "audit"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-package-audit", str(package_path), "--destination", str(package_audit_path), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-package-audit-query", str(package_audit_path), "--failed"]), 0)
            write_package(self.package, root / "typed-package.zip")
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def get(path: str, values: dict[str, object]) -> dict[str, object]:
                    query = urlencode({key: str(value) for key, value in values.items()})
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package"
                built = get(base, {"diff": diff_path, "policy": policy_path, "policy_audit": policy_audit_path, "package_id": "http-catalog-policy-package"})
                self.assertTrue(built["audit_accepted"])
                queried = get(base + "/query", {"input": package_path, "resource": "members"})
                self.assertEqual(queried["total"], 4)
                audited = get(base + "/audit", {"input": package_path})
                self.assertTrue(audited["accepted"])
                schema = get(base + "/schema", {})
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def diff_json(self) -> str:
        from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff import diff_json
        return diff_json(self.diff)


if __name__ == "__main__":
    unittest.main()
