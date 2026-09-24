"""Portable packet coverage for longitudinal release-bundle policy evidence."""

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
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff import build_diff, diff_json
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy import policy_json, release_policy
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_audit import audit_json, audit_policy
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package import (
    build_package,
    load_package,
    package_json,
    package_schema,
    query_package,
    render_package_markdown,
    verify_package,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_audit import audit_package, audit_schema, query_audit
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
        packet_id="policy-package-packets",
        profile="release",
        maximum_added=1,
        maximum_field_changed=256,
    )
    run_audit = audit_run(run.receipt, package=run.package)
    certificate = build_certificate(run.receipt, run.package, run_audit, certificate_id=run_id + "-certificate")
    certificate_audit = audit_certificate(certificate, run=run.receipt, package=run.package, run_audit=run_audit)
    return build_bundle(certificate, run.package, run.receipt, run_audit, certificate_audit, bundle_id=bundle_id)


class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.left = _bundle("policy-package-left-run", "policy-package-left-bundle")
        self.right = _bundle("policy-package-right-run", "policy-package-right-bundle")
        self.diff = build_diff(self.left, self.right, diff_id="policy-package-diff")
        self.policy = release_policy(self.diff, policy_id="policy-package-release", maximum_added=32, maximum_changed=256)
        self.policy_audit = audit_policy(self.policy, diff=self.diff)

    def test_source_free_packet_round_trip_and_independent_audit(self) -> None:
        packet = build_package(self.diff, self.policy, self.policy_audit, package_id="policy-package")
        self.assertEqual(verify_package(packet).package_address, packet.package_address)
        self.assertEqual(load_package(packet)[1].state, "ready")
        self.assertEqual((self.policy_audit.check_count, self.policy_audit.passed_count, self.policy_audit.failed_count), (14, 14, 0))
        packet_audit = audit_package(packet)
        self.assertEqual((packet_audit.check_count, packet_audit.passed_count, packet_audit.failed_count), (15, 15, 0))
        self.assertIn(packet.package_address, package_json(packet))
        self.assertIn("Source-free", render_package_markdown(packet))
        self.assertEqual(query_package(packet, resource="members")["total"], 4)
        self.assertTrue(package_schema()["properties"]["manifest"])
        self.assertTrue(audit_schema()["properties"]["checks"])
        self.assertEqual(query_audit(packet_audit, passed=False)["matched"], 0)

    def test_tampering_fails_closed_and_audit_remains_independent(self) -> None:
        packet = build_package(self.diff, self.policy, self.policy_audit)
        altered = bytearray(packet.package_bytes)
        altered[-1] ^= 1
        with self.assertRaises(ValidationError):
            verify_package(bytes(altered))
        rejected = audit_package(bytes(altered))
        self.assertFalse(rejected.accepted)
        self.assertGreater(rejected.failed_count, 0)

    def test_cli_and_http_surfaces_use_the_same_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diff_path = root / "diff.json"
            policy_path = root / "policy.json"
            audit_path = root / "policy-audit.json"
            package_path = root / "package.zip"
            packet_audit_path = root / "package-audit.json"
            diff_path.write_text(diff_json(self.diff), encoding="utf-8")
            policy_path.write_text(policy_json(self.policy), encoding="utf-8")
            audit_path.write_text(audit_json(self.policy_audit), encoding="utf-8")
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package", str(diff_path), str(policy_path), str(audit_path), "--destination", str(package_path), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-verify", str(package_path)]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-audit", str(package_path), "--destination", str(packet_audit_path), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-audit-query", str(packet_audit_path), "--failed"]), 0)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def get(path: str, values: dict[str, object] | None = None) -> dict[str, object]:
                    query = urlencode({key: str(value) for key, value in (values or {}).items()})
                    suffix = "?" + query if query else ""
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}{suffix}", timeout=20) as response:
                        return json.loads(response.read())

                built = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package", {"diff": diff_path, "policy": policy_path, "policy_audit": audit_path, "package_id": "http-policy-package", "destination": root / "http-package.zip"})
                self.assertEqual(built["policy_state"], "ready")
                queried = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/query", {"input": package_path, "resource": "policy"})
                self.assertEqual(queried["value"]["state"], "ready")
                audited = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/audit", {"input": package_path})
                self.assertTrue(audited["accepted"])
                schema = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/schema")
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
