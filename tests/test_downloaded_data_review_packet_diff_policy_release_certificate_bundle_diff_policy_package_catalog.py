"""Catalog coverage for source-free release-bundle policy packets."""

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
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff import build_diff
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy import release_policy, strict_policy, policy_json
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_audit import audit_policy, audit_json
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package import build_package, write_package
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog import (
    build_catalog,
    catalog_json,
    catalog_schema,
    catalog_from_mapping,
    load_catalog,
    query_catalog,
    render_catalog_markdown,
    verify_catalog,
    write_catalog,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_audit import audit_catalog, audit_json as catalog_audit_json, audit_schema, query_audit
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
        packet_id="policy-catalog-packets",
        profile="release",
        maximum_added=1,
        maximum_field_changed=256,
    )
    run_audit = audit_run(run.receipt, package=run.package)
    certificate = build_certificate(run.receipt, run.package, run_audit, certificate_id=run_id + "-certificate")
    certificate_audit = audit_certificate(certificate, run=run.receipt, package=run.package, run_audit=run_audit)
    return build_bundle(certificate, run.package, run.receipt, run_audit, certificate_audit, bundle_id=bundle_id)


class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogTest(unittest.TestCase):
    def setUp(self) -> None:
        left = _bundle("catalog-left-run", "catalog-left-bundle")
        right = _bundle("catalog-right-run", "catalog-right-bundle")
        diff = build_diff(left, right, diff_id="catalog-diff")
        ready = release_policy(diff, policy_id="catalog-ready-policy", maximum_added=32, maximum_changed=256)
        blocked = strict_policy(diff, policy_id="catalog-blocked-policy")
        self.ready = build_package(diff, ready, audit_policy(ready, diff=diff), package_id="catalog-ready-package")
        self.blocked = build_package(diff, blocked, audit_policy(blocked, diff=diff), package_id="catalog-blocked-package")

    def test_rollups_lineage_queries_and_independent_audit(self) -> None:
        catalog = build_catalog((self.ready, self.blocked), entry_ids=("ready-entry", "blocked-entry"), catalog_id="catalog-fixture")
        self.assertEqual((catalog.entry_count, catalog.accepted_count, catalog.ready_count, catalog.blocked_count), (2, 1, 1, 1))
        self.assertEqual(verify_catalog(catalog).content_address, catalog.content_address)
        self.assertEqual(catalog_from_mapping(json.loads(catalog_json(catalog))).content_address, catalog.content_address)
        self.assertEqual(query_catalog(catalog, resource="ready")["matched"], 1)
        self.assertEqual(query_catalog(catalog, resource="blocked")["matched"], 1)
        self.assertEqual(query_catalog(catalog, resource="accepted")["matched"], 1)
        self.assertEqual(query_catalog(catalog, resource="lineage")["returned"], 2)
        self.assertIn("ready-entry", render_catalog_markdown(catalog))
        self.assertTrue(catalog_schema()["properties"]["entries"])
        audit = audit_catalog(catalog)
        self.assertEqual((audit.check_count, audit.passed_count, audit.failed_count, audit.accepted), (15, 15, 0, True))
        self.assertEqual(query_audit(audit, passed=False)["matched"], 0)
        self.assertTrue(audit_schema()["properties"]["checks"])

    def test_duplicates_tampering_and_persistence_fail_closed(self) -> None:
        with self.assertRaises(ValidationError):
            build_catalog((self.ready, self.ready), entry_ids=("same", "same"))
        catalog = build_catalog((self.ready, self.blocked), entry_ids=("ready-entry", "blocked-entry"))
        altered = catalog.to_dict() | {"ready_count": 2}
        with self.assertRaises(ValidationError):
            verify_catalog(altered)
        rejected = audit_catalog(altered)
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.failed_count, 15)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            write_catalog(catalog, path)
            self.assertEqual(load_catalog(path).content_address, catalog.content_address)

    def test_cli_and_http_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ready_path = root / "ready.zip"
            blocked_path = root / "blocked.zip"
            catalog_path = root / "catalog.json"
            audit_path = root / "catalog-audit.json"
            write_package(self.ready, ready_path)
            write_package(self.blocked, blocked_path)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog", str(ready_path), str(blocked_path), "--entry-id", "ready-entry", "--entry-id", "blocked-entry", "--catalog-id", "cli-catalog", "--destination", str(catalog_path), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-verify", str(catalog_path)]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-query", str(catalog_path), "--resource", "blocked"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-audit", str(catalog_path), "--destination", str(audit_path), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-audit-query", str(audit_path), "--failed"]), 0)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def get(path: str, values: dict[str, object] | None = None) -> dict[str, object]:
                    query = urlencode({key: str(value) for key, value in (values or {}).items()})
                    suffix = "?" + query if query else ""
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}{suffix}", timeout=20) as response:
                        return json.loads(response.read())

                built = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog", {"package": ready_path, "entry_id": "ready-entry", "catalog_id": "http-catalog", "destination": root / "http-catalog.json"})
                self.assertEqual(built["entry_count"], 1)
                queried = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/query", {"input": catalog_path, "resource": "ready"})
                self.assertEqual(queried["matched"], 1)
                audited = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/audit", {"input": catalog_path})
                self.assertTrue(audited["accepted"])
                schema = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/schema")
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
