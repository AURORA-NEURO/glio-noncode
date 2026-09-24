"""Coverage for portable handoff packages over packet-package catalog diff policy decisions."""

# ruff: noqa: E501

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog import build_catalog as build_source_catalog
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff import build_diff as build_inner_diff
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy import release_policy as build_inner_release_policy
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package import build_package as build_inner_package
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog import build_catalog
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff import build_diff, write_diff
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy import policy_json, release_policy, write_policy
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_audit import audit_json, audit_policy, write_audit
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package import build_package, load_package, query_package, verify_package, write_package
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_audit import audit_package, query_audit
from glio_noncode.errors import ValidationError


class PacketPackageCatalogDiffPolicyPackageTest(unittest.TestCase):
    def setUp(self) -> None:
        source = build_source_catalog((), catalog_id="packet-policy-package-source")
        inner_diff = build_inner_diff(source, source, diff_id="packet-policy-package-inner-diff")
        inner_policy = build_inner_release_policy(inner_diff, policy_id="packet-policy-package-inner-policy", require_ready=False)
        self.package_a = build_inner_package(inner_diff, inner_policy, package_id="packet-policy-package-a")
        self.package_b = build_inner_package(inner_diff, inner_policy, package_id="packet-policy-package-b")

    def _evidence(self):
        left = build_catalog((self.package_a.package_bytes,), entry_ids=("entry-a",), catalog_id="packet-policy-package-catalog")
        right = build_catalog((self.package_b.package_bytes,), entry_ids=("entry-a",), catalog_id="packet-policy-package-catalog")
        diff = build_diff(left, right, diff_id="packet-policy-package-diff")
        policy = release_policy(diff, policy_id="packet-policy-package-policy")
        audit = audit_policy(policy, diff=diff)
        return diff, policy, audit

    def test_deterministic_five_member_package_and_sixteen_check_audit(self) -> None:
        diff, policy, audit = self._evidence()
        package = build_package(diff, policy, audit, package_id="packet-policy-package-handoff")
        self.assertEqual(tuple(member.relative_path for member in package.manifest.members), ("catalog-diff.json", "policy.json", "policy-audit.json", "review.md"))
        self.assertEqual(load_package(package)[0].content_address, diff.content_address)
        self.assertEqual(query_package(package, resource="members")["total"], 4)
        receipt = audit_package(package)
        self.assertEqual((receipt.check_count, receipt.passed_count, receipt.failed_count, receipt.accepted), (16, 16, 0, True))
        self.assertEqual(query_audit(receipt, passed=False)["matched"], 0)

    def test_zip_tamper_fails_closed(self) -> None:
        diff, policy, audit = self._evidence()
        package = build_package(diff, policy, audit, package_id="packet-policy-package-tamper")
        tampered = bytearray(package.package_bytes)
        tampered[len(tampered) // 2] ^= 1
        with self.assertRaises(ValidationError):
            verify_package(bytes(tampered))

    def test_cli_http_and_atomic_persistence(self) -> None:
        diff, policy, audit = self._evidence()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diff_path, policy_path, policy_audit_path = root / "diff.json", root / "policy.json", root / "policy-audit.json"
            package_path, package_audit_path = root / "handoff.zip", root / "handoff-audit.json"
            write_diff(diff, diff_path)
            write_policy(policy, policy_path)
            write_audit(audit, policy_audit_path)
            command = "downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package"

            def invoke(arguments: list[str]) -> int:
                with contextlib.redirect_stdout(io.StringIO()):
                    return main(arguments)

            self.assertEqual(invoke([command, str(diff_path), str(policy_path), str(policy_audit_path), "--package-id", "cli-packet-policy-package", "--destination", str(package_path), "--format", "summary"]), 0)
            self.assertEqual(invoke([command + "-verify", str(package_path)]), 0)
            self.assertEqual(invoke([command + "-query", str(package_path), "--resource", "members"]), 0)
            audit_command = command + "-audit"
            self.assertEqual(invoke([audit_command, str(package_path), "--destination", str(package_audit_path), "--format", "summary"]), 0)
            self.assertEqual(invoke([audit_command + "-verify", str(package_audit_path)]), 0)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package"

                def get(path: str, pairs: list[tuple[str, object]]) -> dict[str, object]:
                    query = urlencode([(key, str(value)) for key, value in pairs])
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                built = get(base, [("diff", diff_path), ("policy", policy_path), ("policy_audit", policy_audit_path), ("package_id", "http-packet-policy-package")])
                self.assertEqual((built["member_count"], built["policy_accepted"], built["audit_accepted"]), (4, True, True))
                queried = get(base + "/query", [("package", package_path), ("resource", "members")])
                self.assertEqual(queried["total"], 4)
                audited = get(base + "/audit", [("package", package_path)])
                self.assertEqual((audited["check_count"], audited["failed_count"], audited["accepted"]), (16, 0, True))
                schema = get(base + "/schema", [])
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
