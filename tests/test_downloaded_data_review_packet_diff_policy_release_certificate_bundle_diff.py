"""Longitudinal comparison coverage for source-free release bundles."""

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
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff import (
    build_diff,
    capabilities,
    diff_json,
    diff_schema,
    load_diff,
    query_diff,
    render_diff_markdown,
    verify_diff,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_audit import (
    audit_diff,
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


def _bundle(*, run_id: str, profile: str, bundle_id: str, packet_id: str = "diff-packets"):
    run = build_run(
        _source_bytes("record_id,score\nA,1\nB,2\n"),
        _source_bytes("record_id,score,group\nA,1,x\nB,3,y\nC,4,z\n"),
        run_id=run_id,
        packet_id=packet_id,
        profile=profile,
        maximum_added=1,
        maximum_field_changed=256,
    )
    run_audit = audit_run(run.receipt, package=run.package)
    certificate = build_certificate(run.receipt, run.package, run_audit, certificate_id=run_id + "-certificate")
    certificate_audit = audit_certificate(certificate, run=run.receipt, package=run.package, run_audit=run_audit)
    return build_bundle(certificate, run.package, run.receipt, run_audit, certificate_audit, bundle_id=bundle_id)


class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffTest(unittest.TestCase):
    def setUp(self) -> None:
        self.ready = _bundle(run_id="ready-run", profile="release", bundle_id="ready-bundle")
        self.blocked = _bundle(run_id="blocked-run", profile="strict", bundle_id="blocked-bundle")

    def test_same_bundle_is_canonical_and_independently_accepted(self) -> None:
        diff = build_diff(self.ready, self.ready, diff_id="same-diff")
        verified = verify_diff(diff)
        audit = audit_diff(verified, left=self.ready, right=self.ready)
        self.assertEqual((verified.added_count, verified.removed_count, verified.changed_count, verified.unchanged_count), (0, 0, 0, 10))
        self.assertEqual((verified.state_transition, verified.direction), ("same-ready", "unchanged"))
        self.assertTrue(audit.accepted)
        self.assertEqual((audit.check_count, audit.passed_count, audit.failed_count), (13, 13, 0))
        self.assertEqual(load_diff(json.loads(diff_json(diff))).content_address, diff.content_address)
        self.assertEqual(query_diff(diff, resource="members")["matched"], 6)
        self.assertEqual(query_diff(diff, change="changed")["matched"], 0)
        self.assertIn("Downloaded Data Release Bundle Diff", render_diff_markdown(diff))
        self.assertTrue(diff_schema()["properties"]["items"])
        self.assertTrue(capabilities()["source_free"])
        self.assertTrue(audit_schema()["properties"]["checks"])
        self.assertEqual(query_audit(audit, passed=False)["matched"], 0)
        self.assertEqual(verify_audit(audit).content_address, audit.content_address)

    def test_blocked_to_ready_is_improvement_and_tampering_fails_closed(self) -> None:
        diff = build_diff(self.blocked, self.ready, diff_id="transition-diff")
        self.assertEqual((diff.state_transition, diff.direction), ("blocked-to-ready", "improved"))
        self.assertTrue(audit_diff(diff, left=self.blocked, right=self.ready).accepted)
        altered = diff.to_dict()
        altered["direction"] = "regressed"
        with self.assertRaises(ValidationError):
            verify_diff(altered)
        rejected = audit_diff(diff)
        self.assertFalse(rejected.accepted)
        self.assertGreater(rejected.failed_count, 0)

    def test_atomic_cli_and_http_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left = root / "left.zip"
            right = root / "right.zip"
            run = root / "run.json"
            package = root / "package.zip"
            run_audit = root / "run-audit.json"
            certificate = root / "certificate.json"
            certificate_audit = root / "certificate-audit.json"
            bundle = root / "bundle.zip"
            diff = root / "diff.json"
            audit = root / "diff-audit.json"
            left.write_bytes(_source_bytes("record_id,score\nA,1\nB,2\n"))
            right.write_bytes(_source_bytes("record_id,score,group\nA,1,x\nB,3,y\nC,4,z\n"))
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-run", str(left), str(right), "--run-id", "cli-diff-run", "--packet-id", "cli-diff-packets", "--profile", "release", "--maximum-added", "1", "--maximum-field-changed", "256", "--package-destination", str(package), "--run-destination", str(run), "--audit-destination", str(run_audit), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate", str(run), str(package), "--run-audit", str(run_audit), "--certificate-id", "cli-diff-certificate", "--destination", str(certificate), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-audit", str(certificate), "--run", str(run), "--package", str(package), "--run-audit", str(run_audit), "--destination", str(certificate_audit), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle", str(certificate), str(package), str(run), str(run_audit), "--certificate-audit", str(certificate_audit), "--bundle-id", "cli-diff-bundle", "--destination", str(bundle), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff", str(bundle), str(bundle), "--diff-id", "cli-diff", "--destination", str(diff), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-verify", str(diff)]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-audit", str(diff), "--left", str(bundle), "--right", str(bundle), "--destination", str(audit), "--format", "summary"]), 0)
            self.assertTrue(verify_audit(audit).accepted)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def get(path: str, values: dict[str, object] | None = None) -> dict[str, object]:
                    query = urlencode({key: str(value) for key, value in (values or {}).items()})
                    suffix = "?" + query if query else ""
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}{suffix}", timeout=20) as response:
                        return json.loads(response.read())

                built = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff", {"left": bundle, "right": bundle, "diff_id": "http-diff", "destination": root / "http-diff.json"})
                self.assertEqual(built["direction"], "unchanged")
                queried = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/query", {"input": diff, "resource": "certificate"})
                self.assertEqual(queried["matched"], 1)
                audited = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/audit", {"input": diff, "left": bundle, "right": bundle})
                self.assertTrue(audited["accepted"])
                schema = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/schema")
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
