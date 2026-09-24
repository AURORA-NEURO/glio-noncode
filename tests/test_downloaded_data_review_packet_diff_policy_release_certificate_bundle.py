"""Portable release-bundle coverage for downloaded-data review decisions."""

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
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle import (
    build_bundle,
    bundle_json,
    bundle_schema,
    capabilities,
    load_bundle,
    query_bundle,
    render_bundle_markdown,
    verify_bundle,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_audit import (
    audit_bundle,
    audit_schema,
    query_audit,
    verify_audit,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_run import build_run
from glio_noncode.downloaded_data_review_packet_diff_policy_run_audit import audit_run
from glio_noncode.errors import ValidationError


def _source_bytes(payload: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("data.csv", payload)
    return output.getvalue()


class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleTest(unittest.TestCase):
    def setUp(self) -> None:
        left = _source_bytes("record_id,score\nA,1\nB,2\n")
        right = _source_bytes("record_id,score,group\nA,1,x\nB,3,y\nC,4,z\n")
        self.run = build_run(left, right, run_id="bundle-run", profile="release", maximum_added=1, maximum_field_changed=256)
        self.run_audit = audit_run(self.run.receipt, package=self.run.package)
        self.certificate = build_certificate(self.run.receipt, self.run.package, self.run_audit, certificate_id="bundle-certificate")
        self.certificate_audit = audit_certificate(self.certificate, run=self.run.receipt, package=self.run.package, run_audit=self.run_audit)

    def test_deterministic_bundle_replays_nested_release_chain(self) -> None:
        bundle = build_bundle(self.certificate, self.run.package, self.run.receipt, self.run_audit, self.certificate_audit, bundle_id="ready-bundle")
        audit = audit_bundle(bundle)
        self.assertEqual((bundle.manifest.release_state, bundle.manifest.release_eligible), ("ready", True))
        self.assertEqual((audit.check_count, audit.passed_count, audit.failed_count, audit.accepted), (16, 16, 0, True))
        self.assertEqual(verify_bundle(bundle).bundle_address, bundle.bundle_address)
        self.assertEqual(load_bundle(bundle)[0].content_address, self.certificate.content_address)
        self.assertEqual(query_bundle(bundle, resource="certificate")["value"]["release_state"], "ready")
        self.assertIn("Downloaded Data Release Certificate Bundle", render_bundle_markdown(bundle))
        self.assertTrue(bundle_schema()["properties"]["manifest"])
        self.assertTrue(capabilities()["nested_package_preserved"])
        self.assertTrue(audit_schema()["properties"]["checks"])
        self.assertEqual(query_audit(audit, passed=False)["matched"], 0)
        self.assertIn(bundle.bundle_address, bundle_json(bundle))

    def test_tampering_fails_closed_and_preserves_audit_failure_evidence(self) -> None:
        bundle = build_bundle(self.certificate, self.run.package, self.run.receipt, self.run_audit, self.certificate_audit, bundle_id="tamper-bundle")
        altered = bytearray(bundle.bundle_bytes)
        altered[-1] ^= 1
        with self.assertRaises(ValidationError):
            verify_bundle(bytes(altered))
        rejected = audit_bundle(bytes(altered))
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.failed_count, 16)

    def test_atomic_cli_and_http_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left_path = root / "left.zip"
            right_path = root / "right.zip"
            run_path = root / "run.json"
            package_path = root / "package.zip"
            run_audit_path = root / "run-audit.json"
            certificate_path = root / "certificate.json"
            certificate_audit_path = root / "certificate-audit.json"
            bundle_path = root / "bundle.zip"
            bundle_audit_path = root / "bundle-audit.json"
            left_path.write_bytes(_source_bytes("record_id,score\nA,1\nB,2\n"))
            right_path.write_bytes(_source_bytes("record_id,score,group\nA,1,x\nB,3,y\nC,4,z\n"))
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-run", str(left_path), str(right_path), "--run-id", "cli-bundle-run", "--profile", "release", "--maximum-added", "1", "--maximum-field-changed", "256", "--package-destination", str(package_path), "--run-destination", str(run_path), "--audit-destination", str(run_audit_path), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate", str(run_path), str(package_path), "--run-audit", str(run_audit_path), "--certificate-id", "cli-bundle-certificate", "--destination", str(certificate_path), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-audit", str(certificate_path), "--run", str(run_path), "--package", str(package_path), "--run-audit", str(run_audit_path), "--destination", str(certificate_audit_path), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle", str(certificate_path), str(package_path), str(run_path), str(run_audit_path), "--certificate-audit", str(certificate_audit_path), "--bundle-id", "cli-bundle", "--destination", str(bundle_path), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-verify", str(bundle_path)]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-audit", str(bundle_path), "--destination", str(bundle_audit_path), "--format", "summary"]), 0)
            self.assertTrue(verify_audit(bundle_audit_path).accepted)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def get(path: str, values: dict[str, object]) -> dict[str, object]:
                    query = urlencode({key: str(value) for key, value in values.items()})
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                built = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle", {"certificate": certificate_path, "package": package_path, "run": run_path, "run_audit": run_audit_path, "certificate_audit": certificate_audit_path, "bundle_id": "http-bundle", "destination": root / "http-bundle.zip"})
                self.assertTrue(built["release_eligible"])
                queried = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/query", {"input": bundle_path, "resource": "certificate"})
                self.assertEqual(queried["value"]["release_state"], "ready")
                audited = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/audit", {"input": bundle_path})
                self.assertTrue(audited["accepted"])
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/schema", timeout=20) as response:
                    self.assertEqual(json.loads(response.read())["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
