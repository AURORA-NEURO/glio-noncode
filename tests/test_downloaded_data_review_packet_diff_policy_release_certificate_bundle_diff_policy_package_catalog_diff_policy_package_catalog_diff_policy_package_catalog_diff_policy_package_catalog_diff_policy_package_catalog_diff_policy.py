"""Coverage for policy gates over longitudinal review-packet catalog diffs."""

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
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff import (
    build_diff,
    catalog_model,
    write_diff,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy import (
    build_policy,
    policy_csv,
    policy_json,
    query_policy,
    release_policy,
    render_policy_markdown,
    strict_policy,
    verify_policy,
    write_policy,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_policy_audit import (
    audit_policy,
    query_audit,
    verify_audit,
    write_audit,
)
from glio_noncode.errors import ValidationError


class HandoffCatalogDiffPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        left = catalog_model.build_catalog((), catalog_id="handoff-catalog-policy-test")
        right = catalog_model.build_catalog((), catalog_id="handoff-catalog-policy-test")
        self.diff = build_diff(left, right, diff_id="handoff-catalog-policy-test-diff")

    def test_ready_blocked_replay_and_independent_audit(self) -> None:
        accepted = release_policy(self.diff, policy_id="handoff-catalog-policy-release", require_ready=False)
        self.assertTrue(accepted.accepted)
        self.assertEqual((accepted.state, accepted.check_count, accepted.failed_count), ("ready", 15, 0))
        self.assertEqual(verify_policy(accepted.to_dict()).content_address, accepted.content_address)
        receipt = audit_policy(accepted, diff=self.diff)
        self.assertTrue(receipt.accepted)
        self.assertEqual((receipt.check_count, receipt.passed_count, receipt.failed_count), (16, 16, 0))
        self.assertEqual(verify_audit(receipt.to_dict()).content_address, receipt.content_address)
        self.assertEqual(query_policy(accepted, passed=False)["matched"], 0)
        self.assertEqual(query_audit(receipt, passed=False)["matched"], 0)
        self.assertIn("Review-packet Catalog Diff Policy", render_policy_markdown(accepted))
        self.assertIn("check_id", policy_csv(accepted))
        self.assertIn('"accepted":true', policy_json(accepted))

        blocked = build_policy(self.diff, policy_id="handoff-catalog-policy-blocked", require_ready=False, require_change=True)
        self.assertFalse(blocked.accepted)
        self.assertEqual(blocked.state, "blocked")
        blocked_audit = audit_policy(blocked, diff=self.diff)
        self.assertTrue(blocked_audit.accepted)
        self.assertEqual(blocked_audit.passed_count, 16)
        with self.assertRaises(ValidationError):
            verify_policy(accepted.to_dict() | {"accepted": False})

    def test_strict_controls_and_atomic_persistence(self) -> None:
        strict = strict_policy(self.diff, policy_id="handoff-catalog-policy-strict")
        self.assertFalse(strict.accepted)
        self.assertEqual(strict.state, "blocked")
        self.assertIn("policy-ready-requirement", {item.check_id for item in strict.checks})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy_path = root / "policy.json"
            audit_path = root / "audit.json"
            write_policy(strict, policy_path)
            write_audit(audit_policy(strict), audit_path)
            self.assertEqual(verify_policy(policy_path).content_address, strict.content_address)
            self.assertEqual(verify_audit(audit_path).content_address, audit_policy(strict).content_address)
            with self.assertRaises(ValidationError):
                write_policy(strict, policy_path)
            with self.assertRaises(ValidationError):
                write_audit(audit_policy(strict), audit_path)

    def test_cli_http_schema_and_query_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diff_path = root / "diff.json"
            policy_path = root / "policy.json"
            audit_path = root / "audit.json"
            write_diff(self.diff, diff_path)
            command = "downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy"

            def invoke(arguments: list[str]) -> tuple[int, str]:
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = main(arguments)
                return code, output.getvalue()

            code, _summary = invoke([command, str(diff_path), "--profile", "release", "--require-change", "--destination", str(policy_path), "--format", "summary"])
            self.assertEqual(code, 2)
            self.assertTrue(policy_path.is_file())
            self.assertEqual(invoke([command + "-verify", str(policy_path)])[0], 2)
            self.assertEqual(invoke([command + "-query", str(policy_path), "--failed"])[0], 0)
            audit_command = command + "-audit"
            self.assertEqual(invoke([audit_command, str(policy_path), "--diff", str(diff_path), "--destination", str(audit_path), "--format", "summary"])[0], 0)
            self.assertEqual(invoke([audit_command + "-verify", str(audit_path)])[0], 0)
            self.assertEqual(invoke([command + "-schema"])[0], 0)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy"

                def get(path: str, pairs: list[tuple[str, object]]) -> dict[str, object]:
                    query = urlencode([(key, str(value)) for key, value in pairs])
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                built = get(base, [("input", diff_path), ("profile", "release"), ("require_ready", "false")])
                self.assertEqual((built["accepted"], built["state"], built["failed_count"]), (True, "ready", 0))
                queried = get(base + "/query", [("input", policy_path), ("passed", "true")])
                self.assertEqual((queried["matched"], queried["returned"]), (13, 13))
                audited = get(base + "/audit", [("input", policy_path), ("diff", diff_path)])
                self.assertEqual((audited["accepted"], audited["passed_count"], audited["check_count"]), (True, 16, 16))
                schema = get(base + "/schema", [])
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
