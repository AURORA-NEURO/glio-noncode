"""Release-certificate coverage for downloaded-data review decisions."""

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
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate import (
    build_certificate,
    capabilities,
    certificate_json,
    certificate_schema,
    query_certificate,
    render_certificate_markdown,
    verify_certificate,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_audit import (
    audit_certificate,
    audit_schema,
    query_audit,
    verify_audit,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_run import build_run
from glio_noncode.errors import ValidationError


def _source_bytes(payload: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("data.csv", payload)
    return output.getvalue()


class DownloadedDataReviewPacketDiffPolicyReleaseCertificateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.left = _source_bytes("record_id,score\nA,1\nB,2\n")
        self.right = _source_bytes("record_id,score,group\nA,1,x\nB,3,y\nC,4,z\n")
        self.ready = build_run(self.left, self.right, run_id="certificate-ready-run", profile="release", maximum_added=1, maximum_field_changed=256)
        self.blocked = build_run(self.left, self.right, run_id="certificate-blocked-run", profile="strict")

    def test_ready_and_blocked_certificates_replay_all_evidence(self) -> None:
        ready = build_certificate(self.ready.receipt, self.ready.package, certificate_id="ready-certificate")
        blocked = build_certificate(self.blocked.receipt, self.blocked.package, certificate_id="blocked-certificate")
        ready_audit = audit_certificate(ready, run=self.ready.receipt, package=self.ready.package)
        blocked_audit = audit_certificate(blocked, run=self.blocked.receipt, package=self.blocked.package)
        self.assertEqual((ready.release_state, ready.release_eligible), ("ready", True))
        self.assertEqual((blocked.release_state, blocked.release_eligible), ("blocked", False))
        self.assertEqual((ready_audit.check_count, ready_audit.passed_count, ready_audit.failed_count, ready_audit.accepted), (15, 15, 0, True))
        self.assertEqual((blocked_audit.check_count, blocked_audit.passed_count, blocked_audit.failed_count, blocked_audit.accepted), (15, 15, 0, True))
        self.assertEqual(verify_certificate(certificate_json(ready).encode("utf-8")).content_address, ready.content_address)
        self.assertEqual(query_certificate(ready, resource="decision")["value"]["release_state"], "ready")
        self.assertIn("Downloaded Data Release Certificate", render_certificate_markdown(ready))
        self.assertTrue(certificate_schema()["properties"]["release_eligible"])
        self.assertTrue(capabilities()["release_eligibility_is_conjunctive"])
        self.assertTrue(audit_schema()["properties"]["checks"])
        self.assertEqual(query_audit(ready_audit, passed=False)["matched"], 0)

    def test_tampering_and_missing_lineage_fail_closed(self) -> None:
        certificate = build_certificate(self.ready.receipt, self.ready.package, certificate_id="tamper-certificate")
        altered = certificate.to_dict() | {"package_byte_count": certificate.package_byte_count + 1}
        with self.assertRaises(ValidationError):
            verify_certificate(altered)
        missing = audit_certificate(certificate)
        self.assertFalse(missing.accepted)
        self.assertEqual(missing.failed_count, 8)

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
            left_path.write_bytes(self.left)
            right_path.write_bytes(self.right)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-run", str(left_path), str(right_path), "--run-id", "cli-certificate-run", "--profile", "release", "--maximum-added", "1", "--maximum-field-changed", "256", "--package-destination", str(package_path), "--run-destination", str(run_path), "--audit-destination", str(run_audit_path), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate", str(run_path), str(package_path), "--run-audit", str(run_audit_path), "--certificate-id", "cli-certificate", "--destination", str(certificate_path), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-verify", str(certificate_path), "--run", str(run_path), "--package", str(package_path), "--run-audit", str(run_audit_path)]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-release-certificate-audit", str(certificate_path), "--run", str(run_path), "--package", str(package_path), "--run-audit", str(run_audit_path), "--destination", str(certificate_audit_path), "--format", "summary"]), 0)
            self.assertTrue(verify_audit(certificate_audit_path).accepted)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def get(path: str, values: dict[str, object]) -> dict[str, object]:
                    query = urlencode({key: str(value) for key, value in values.items()})
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                built = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate", {"run": run_path, "package": package_path, "run_audit": run_audit_path, "certificate_id": "http-certificate", "destination": root / "http-certificate.json"})
                self.assertTrue(built["release_eligible"])
                queried = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/query", {"input": certificate_path, "resource": "decision"})
                self.assertEqual(queried["value"]["release_state"], "ready")
                audited = get("/v1/downloaded-data/review-packet/diff/policy/release-certificate/audit", {"input": certificate_path, "run": run_path, "package": package_path, "run_audit": run_audit_path})
                self.assertTrue(audited["accepted"])
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/review-packet/diff/policy/release-certificate/schema", timeout=20) as response:
                    self.assertEqual(json.loads(response.read())["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
