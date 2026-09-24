"""Deep contracts for policy gates over fixed transport catalog diffs."""

# ruff: noqa: E501

from __future__ import annotations

import ast
import contextlib
import importlib
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import _legacy_cli
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError


def _module_from_test(test_name: str, names: set[str]):
    tree = ast.parse(Path("tests", test_name).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("glio_noncode.downloaded_data") and names.intersection(alias.name for alias in node.names):
            return importlib.import_module(node.module)
    raise RuntimeError(f"could not resolve module for {names}")


def _local_module(pattern: str):
    matches = tuple(Path("src/glio_noncode").glob(pattern))
    if pattern.endswith("tr_cat_diff.py"):
        matches = tuple(path for path in matches if "_tcp_" not in path.name)
    if len(matches) != 1:
        raise RuntimeError(f"expected one local module for {pattern}, got {len(matches)}")
    return importlib.import_module(f"glio_noncode.{matches[0].stem}")


class FixedTransportCatalogPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        base_diff = _module_from_test("test_review_packet_catalog_diff_policy_transport_catalog.py", {"build_diff"})
        base_policy = _module_from_test("test_review_packet_catalog_diff_policy_transport_catalog.py", {"release_policy"})
        base_audit = _module_from_test("test_review_packet_catalog_diff_policy_transport_catalog.py", {"audit_policy"})
        transport = _module_from_test("test_review_packet_catalog_diff_policy_transport_catalog.py", {"build_transport"})
        catalog = _local_module("*transport_catalog.py")
        diff_model = _local_module("*tr_cat_diff.py")
        policy_model = _local_module("*_tcp.py")
        audit_model = _local_module("*_tcp_aud.py")

        source = base_diff.catalog_model.build_catalog((), catalog_id="fixed-transport-policy-source")
        source_diff = base_diff.build_diff(source, source, diff_id="fixed-transport-policy-source-diff")
        source_policy = base_policy.release_policy(source_diff, policy_id="fixed-transport-policy-source-policy", require_ready=False)
        source_audit = base_audit.audit_policy(source_policy, diff=source_diff)
        packet_a = transport.build_transport(source_diff, source_policy, source_audit, package_id="fixed-transport-policy-a")
        packet_b = transport.build_transport(source_diff, source_policy, source_audit, package_id="fixed-transport-policy-b")
        packet_c = transport.build_transport(source_diff, source_policy, source_audit, package_id="fixed-transport-policy-c")
        self.left = catalog.build_transport_catalog((packet_a.package_bytes, packet_b.package_bytes, packet_c.package_bytes), entry_ids=("entry-unchanged", "entry-changed", "entry-removed"), catalog_id="fixed-transport-policy-catalog")
        self.right = catalog.build_transport_catalog((packet_a.package_bytes, packet_c.package_bytes, packet_b.package_bytes), entry_ids=("entry-unchanged", "entry-changed", "entry-added"), catalog_id="fixed-transport-policy-catalog")
        self.diff = diff_model.build_transport_catalog_diff(self.left, self.right, diff_id="fixed-transport-policy-diff")
        self.policy_model = policy_model
        self.audit_model = audit_model

    def test_strict_release_controls_and_independent_audit(self) -> None:
        strict = self.policy_model.strict_transport_catalog_diff_policy(self.diff, policy_id="fixed-transport-strict")
        release = self.policy_model.release_transport_catalog_diff_policy(self.diff, policy_id="fixed-transport-release")
        self.assertFalse(strict.accepted)
        self.assertEqual((strict.state, strict.check_count, strict.failed_count), ("blocked", 15, 6))
        self.assertTrue(release.accepted)
        self.assertEqual((release.state, release.check_count, release.failed_count), ("ready", 15, 0))
        receipt = self.audit_model.audit_transport_catalog_diff_policy(release, diff=self.diff)
        self.assertTrue(receipt.accepted)
        self.assertEqual((receipt.check_count, receipt.passed_count, receipt.failed_count), (16, 16, 0))
        self.assertEqual(self.policy_model.query_transport_catalog_diff_policy(release, passed=False)["matched"], 0)
        self.assertEqual(self.audit_model.query_audit(receipt, passed=False)["matched"], 0)

    def test_persistence_tamper_and_public_boundary(self) -> None:
        policy = self.policy_model.release_transport_catalog_diff_policy(self.diff, policy_id="fixed-transport-persistence")
        receipt = self.audit_model.audit_transport_catalog_diff_policy(policy, diff=self.diff)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diff_path, policy_path, audit_path = root / "diff.json", root / "policy.json", root / "audit.json"
            diff_model = _local_module("*tr_cat_diff.py")
            diff_model.write_transport_catalog_diff(self.diff, diff_path)
            self.policy_model.write_transport_catalog_diff_policy(policy, policy_path)
            self.audit_model.write_audit(receipt, audit_path)
            self.assertEqual(self.policy_model.verify_transport_catalog_diff_policy(policy_path).content_address, policy.content_address)
            self.assertEqual(self.audit_model.verify_audit(audit_path).content_address, receipt.content_address)
            with self.assertRaises(ValidationError):
                self.policy_model.write_transport_catalog_diff_policy(policy, policy_path)
            tampered = policy.to_dict() | {"accepted": False}
            with self.assertRaises(ValidationError):
                self.policy_model.verify_transport_catalog_diff_policy(tampered)
            public = json.dumps(policy.to_dict()).lower()
            self.assertNotIn("agent", public)
            self.assertNotIn("model", public)
            self.assertNotIn("language", public)

    def test_cli_http_and_schema_surfaces(self) -> None:
        policy_model = self.policy_model
        audit_model = self.audit_model
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diff_path, policy_path, audit_path = root / "diff.json", root / "policy.json", root / "audit.json"
            _local_module("*tr_cat_diff.py").write_transport_catalog_diff(self.diff, diff_path)
            command = _legacy_cli._REVIEW_PACKET_TRANSPORT_CATALOG_POLICY_566_COMMAND

            def invoke(arguments: list[str]) -> tuple[int, str]:
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = main(arguments)
                return code, output.getvalue()

            self.assertEqual(invoke([command, str(diff_path), "--profile", "release", "--destination", str(policy_path), "--format", "summary"])[0], 0)
            self.assertEqual(invoke([command + "-verify", str(policy_path)])[0], 0)
            self.assertEqual(invoke([command + "-query", str(policy_path), "--passed"])[0], 0)
            self.assertEqual(invoke([command + "-audit", str(policy_path), "--diff", str(diff_path), "--destination", str(audit_path), "--format", "summary"])[0], 0)
            self.assertEqual(invoke([command + "-audit-verify", str(audit_path)])[0], 0)
            self.assertEqual(invoke([command + "-schema"])[0], 0)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/transport/catalog/diff/policy"

                def get(path: str, pairs: list[tuple[str, object]]) -> dict[str, object]:
                    query = urlencode([(key, str(value)) for key, value in pairs])
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                built = get(base, [("input", diff_path), ("profile", "release"), ("require_ready", "false")])
                self.assertEqual((built["accepted"], built["state"], built["failed_count"]), (True, "ready", 0))
                queried = get(base + "/query", [("input", policy_path), ("passed", "true")])
                self.assertEqual((queried["matched"], queried["returned"]), (15, 15))
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
