"""Source-free catalog coverage for portable catalog-diff policy packets."""

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
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package import build_package, write_package
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog import build_catalog as build_inner_catalog
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff import build_diff as build_inner_diff
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy import release_policy as build_catalog_release_policy, strict_policy as build_catalog_strict_policy
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_audit import audit_policy as audit_catalog_policy
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog import build_catalog, catalog_json, catalog_schema, query_catalog, render_catalog_markdown, verify_catalog
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_audit import audit_catalog, audit_schema, query_audit
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
        packet_id="catalog-of-catalog-policy-packets",
        profile="release",
        maximum_added=1,
        maximum_field_changed=256,
    )
    run_audit = audit_run(run.receipt, package=run.package)
    certificate = build_certificate(run.receipt, run.package, run_audit, certificate_id=run_id + "-certificate")
    certificate_audit = audit_certificate(certificate, run=run.receipt, package=run.package, run_audit=run_audit)
    return build_bundle(certificate, run.package, run.receipt, run_audit, certificate_audit, bundle_id=bundle_id)


class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyPackageCatalogTest(unittest.TestCase):
    def setUp(self) -> None:
        left_bundle = _bundle("catalog-of-catalog-left-run", "catalog-of-catalog-left-bundle")
        right_bundle = _bundle("catalog-of-catalog-right-run", "catalog-of-catalog-right-bundle")
        bundle_diff = build_bundle_diff(left_bundle, right_bundle, diff_id="catalog-of-catalog-inner-diff")
        ready_bundle_policy = build_bundle_release_policy(bundle_diff, policy_id="catalog-of-catalog-ready-bundle-policy", maximum_changed=256)
        blocked_bundle_policy = build_bundle_strict_policy(bundle_diff, policy_id="catalog-of-catalog-blocked-bundle-policy")
        ready_bundle_package = build_bundle_package(bundle_diff, ready_bundle_policy, audit_bundle_policy(ready_bundle_policy, diff=bundle_diff), package_id="catalog-of-catalog-ready-bundle-package")
        blocked_bundle_package = build_bundle_package(bundle_diff, blocked_bundle_policy, audit_bundle_policy(blocked_bundle_policy, diff=bundle_diff), package_id="catalog-of-catalog-blocked-bundle-package")
        left_catalog = build_inner_catalog((blocked_bundle_package,), entry_ids=("catalog-of-catalog-entry",), catalog_id="catalog-of-catalog-inner")
        right_catalog = build_inner_catalog((ready_bundle_package,), entry_ids=("catalog-of-catalog-entry",), catalog_id="catalog-of-catalog-inner")
        catalog_diff = build_inner_diff(left_catalog, right_catalog, diff_id="catalog-of-catalog-inner-diff")
        ready_policy = build_catalog_release_policy(catalog_diff, policy_id="catalog-of-catalog-ready-policy", maximum_changed=256)
        blocked_policy = build_catalog_strict_policy(catalog_diff, policy_id="catalog-of-catalog-blocked-policy")
        self.ready = build_package(catalog_diff, ready_policy, audit_catalog_policy(ready_policy, diff=catalog_diff), package_id="catalog-of-catalog-ready-package")
        self.blocked = build_package(catalog_diff, blocked_policy, audit_catalog_policy(blocked_policy, diff=catalog_diff), package_id="catalog-of-catalog-blocked-package")

    def test_rollups_queries_persistence_and_independent_audit(self) -> None:
        catalog = build_catalog((self.blocked, self.ready), entry_ids=("blocked-entry", "ready-entry"), catalog_id="catalog-of-catalog")
        self.assertEqual((catalog.entry_count, catalog.accepted_count, catalog.ready_count, catalog.blocked_count), (2, 1, 1, 1))
        self.assertEqual(verify_catalog(catalog).content_address, catalog.content_address)
        self.assertEqual(query_catalog(catalog, resource="ready")["matched"], 1)
        self.assertEqual(query_catalog(catalog, resource="blocked")["matched"], 1)
        self.assertEqual(query_catalog(catalog, resource="lineage")["returned"], 2)
        self.assertIn("Ready / blocked", render_catalog_markdown(catalog))
        self.assertTrue(catalog_schema()["properties"]["entries"])
        receipt = audit_catalog(catalog)
        self.assertEqual((receipt.check_count, receipt.passed_count, receipt.failed_count, receipt.accepted), (15, 15, 0, True))
        self.assertEqual(query_audit(receipt, passed=False)["matched"], 0)
        self.assertTrue(audit_schema()["properties"]["checks"])

    def test_identity_collisions_and_tampering_fail_closed(self) -> None:
        with self.assertRaises(ValidationError):
            build_catalog((self.ready, self.blocked), entry_ids=("same-entry", "same-entry"))
        catalog = build_catalog((self.ready,), catalog_id="catalog-of-catalog-single")
        tampered = json.loads(catalog_json(catalog))
        tampered["ready_count"] = 0
        with self.assertRaises(ValidationError):
            verify_catalog(tampered)
        rejected = audit_catalog(tampered)
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.failed_count, 15)

    def test_cli_http_and_persistence_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            blocked_path = root / "blocked-package.zip"
            ready_path = root / "ready-package.zip"
            catalog_path = root / "packet-catalog.json"
            audit_path = root / "packet-catalog-audit.json"
            write_package(self.blocked, blocked_path)
            write_package(self.ready, ready_path)
            command = "downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-package-catalog"
            self.assertEqual(main([command, str(blocked_path), str(ready_path), "--entry-id", "blocked-entry", "--entry-id", "ready-entry", "--catalog-id", "cli-catalog-of-catalog", "--destination", str(catalog_path), "--format", "summary"]), 0)
            self.assertEqual(main([command + "-verify", str(catalog_path)]), 0)
            self.assertEqual(main([command + "-query", str(catalog_path), "--resource", "ready"]), 0)
            audit_command = command + "-audit"
            self.assertEqual(main([audit_command, str(catalog_path), "--destination", str(audit_path), "--format", "summary"]), 0)
            self.assertEqual(main([audit_command + "-verify", str(audit_path)]), 0)
            self.assertEqual(main([audit_command + "-query", str(audit_path), "--failed"]), 0)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def get(path: str, pairs: list[tuple[str, object]]) -> dict[str, object]:
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{urlencode([(key, str(value)) for key, value in pairs])}", timeout=20) as response:
                        return json.loads(response.read())

                base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog"
                built = get(base, [("package", blocked_path), ("package", ready_path), ("entry_id", "blocked-entry"), ("entry_id", "ready-entry"), ("catalog_id", "http-catalog-of-catalog")])
                self.assertEqual(built["entry_count"], 2)
                queried = get(base + "/query", [("input", catalog_path), ("resource", "ready")])
                self.assertEqual(queried["matched"], 1)
                audited = get(base + "/audit", [("input", catalog_path)])
                self.assertTrue(audited["accepted"])
                schema = get(base + "/schema", [])
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
