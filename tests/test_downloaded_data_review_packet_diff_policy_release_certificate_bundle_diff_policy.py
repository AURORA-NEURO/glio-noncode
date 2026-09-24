"""Policy-gate coverage for longitudinal release-bundle diffs."""

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
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy import (
    release_policy,
    strict_policy,
    policy_json,
    query_policy,
    verify_policy,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_audit import audit_policy, verify_audit
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
        packet_id="policy-packets",
        profile="release",
        maximum_added=1,
        maximum_field_changed=256,
    )
    run_audit = audit_run(run.receipt, package=run.package)
    certificate = build_certificate(run.receipt, run.package, run_audit, certificate_id=run_id + "-certificate")
    certificate_audit = audit_certificate(certificate, run=run.receipt, package=run.package, run_audit=run_audit)
    return build_bundle(certificate, run.package, run.receipt, run_audit, certificate_audit, bundle_id=bundle_id)


class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.left = _bundle("policy-left-run", "policy-left-bundle")
        self.right = _bundle("policy-right-run", "policy-right-bundle")
        self.diff = build_diff(self.left, self.right, diff_id="policy-diff")

    def test_strict_blocks_and_release_accepts_with_independent_recomputation(self) -> None:
        strict = strict_policy(self.diff)
        release = release_policy(self.diff)
        self.assertEqual((strict.state, strict.accepted), ("blocked", False))
        self.assertEqual((release.state, release.accepted, release.failed_count), ("ready", True, 0))
        self.assertGreater(strict.failed_count, 0)
        audit = audit_policy(release, diff=self.diff)
        self.assertTrue(audit.accepted)
        self.assertEqual((audit.check_count, audit.passed_count, audit.failed_count), (14, 14, 0))
        self.assertEqual(query_policy(release, passed=False)["matched"], 0)
        self.assertEqual(verify_policy(json.loads(policy_json(release))).content_address, release.content_address)

    def test_policy_tampering_and_missing_diff_fail_closed(self) -> None:
        release = release_policy(self.diff)
        altered = release.to_dict()
        altered["maximum_changed"] = 0
        with self.assertRaises(ValidationError):
            verify_policy(altered)
        structural = audit_policy(release)
        self.assertTrue(structural.accepted)
        recomputed = audit_policy(release, diff=self.diff)
        self.assertTrue(recomputed.accepted)
        self.assertFalse(any(key in {"patient_id", "subject_id", "participant_id", "individual_id", "medical_record_number", "contact_name", "email", "phone", "sample_id", "agent", "agent_id", "agent_name", "assistant", "assistant_id", "assistant_name", "generated_by", "produced_by", "model_id", "model_name", "model_version", "author", "author_id", "author_name", "programming_language", "language"} for key in release.to_dict()))

    def test_atomic_cli_and_http_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diff_path = root / "diff.json"
            policy_path = root / "policy.json"
            audit_path = root / "policy-audit.json"
            diff_path.write_text(diff_json(self.diff), encoding="utf-8")
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy", str(diff_path), "--profile", "strict", "--destination", str(root / "strict.json"), "--format", "summary"]), 2)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy", str(diff_path), "--profile", "release", "--destination", str(policy_path), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-verify", str(policy_path)]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-audit", str(policy_path), "--diff", str(diff_path), "--destination", str(audit_path), "--format", "summary"]), 0)
            self.assertTrue(verify_audit(audit_path).accepted)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def get(path: str, values: dict[str, object] | None = None) -> dict[str, object]:
                    query = urlencode({key: str(value) for key, value in (values or {}).items()})
                    suffix = "?" + query if query else ""
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}{suffix}", timeout=20) as response:
                        return json.loads(response.read())

                built = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy", {"input": diff_path, "profile": "release", "destination": root / "http-policy.json"})
                self.assertEqual(built["state"], "ready")
                queried = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/query", {"input": policy_path, "passed": "false"})
                self.assertEqual(queried["matched"], 0)
                audited = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/audit", {"input": policy_path, "diff": diff_path})
                self.assertTrue(audited["accepted"])
                schema = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/schema")
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
