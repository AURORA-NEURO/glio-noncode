"""Deep contracts for catalogs of fixed transport catalog-diff policy packages."""

# ruff: noqa: E501

from __future__ import annotations

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


def _local_module(pattern: str):
    matches = tuple(Path("src/glio_noncode").glob(pattern))
    if pattern.endswith("tr_cat_diff.py"):
        matches = tuple(path for path in matches if not path.name.endswith("_tcp_tr_cat_diff.py"))
    if len(matches) != 1:
        raise RuntimeError(f"expected one local module for {pattern}, got {len(matches)}")
    return importlib.import_module(f"glio_noncode.{matches[0].stem}")


class FixedTransportCatalogDiffPolicyPackageCatalogTest(unittest.TestCase):
    def setUp(self) -> None:
        self.diff_model = _local_module("*_tr_cat_diff.py")
        self.policy_model = _local_module("*_tcp.py")
        self.transport_model = _local_module("*_tcp_tr.py")
        self.catalog_model = _local_module("*_tcp_tr_cat.py")
        self.audit_model = _local_module("*_tcp_tr_cat_aud.py")
        fixture = Path(".glio-real-demo/real-packet-policy-handoff-review-packet-catalog-diff-policy-review-catalog-v1-fixed-transport-catalog-diff-565.json")
        if not fixture.is_file():
            self.skipTest("real downloaded-data diff fixture is not present")
        diff = self.diff_model.load_diff(fixture)
        policy = self.policy_model.release_policy(diff, policy_id="fixed-transport-catalog-diff-policy-catalog-release")
        self.package_a = self.transport_model.build_package(diff, policy, package_id="fixed-transport-catalog-diff-policy-package-a")
        self.package_b = self.transport_model.build_package(diff, policy, package_id="fixed-transport-catalog-diff-policy-package-b")
        self.catalog = self.catalog_model.build_catalog(
            (self.package_b.package_bytes, self.package_a.package_bytes),
            entry_ids=("entry-b", "entry-a"),
            catalog_id="fixed-transport-catalog-diff-policy-package-catalog",
        )

    def test_deterministic_real_data_rollup_and_independent_audit(self) -> None:
        first = self.catalog_model.build_catalog(
            (self.package_a.package_bytes, self.package_b.package_bytes),
            entry_ids=("entry-a", "entry-b"),
            catalog_id=self.catalog.catalog_id,
        )
        self.assertEqual(first.content_address, self.catalog.content_address)
        self.assertEqual(tuple(item.entry_id for item in first.entries), ("entry-a", "entry-b"))
        self.assertEqual((first.entry_count, first.accepted_count, first.ready_count, first.blocked_count), (2, 2, 2, 0))
        self.assertEqual(first.total_package_bytes, sum(item.package_byte_count for item in first.entries))
        self.assertEqual(first.total_member_bytes, sum(item.member_byte_count for item in first.entries))
        self.assertEqual(self.catalog_model.query_catalog(first, resource="accepted")["returned"], 2)
        self.assertEqual(self.catalog_model.query_catalog(first, resource="lineage")["returned"], 2)
        receipt = self.audit_model.audit_catalog(first)
        self.assertEqual((receipt.check_count, receipt.passed_count, receipt.failed_count, receipt.accepted), (16, 16, 0, True))
        self.assertEqual(self.audit_model.query_audit(receipt, passed=False)["matched"], 0)

    def test_persistence_tamper_duplicate_and_public_boundary_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "catalog.json"
            self.catalog_model.write_catalog(self.catalog, destination)
            restored = self.catalog_model.load_catalog(destination)
            self.assertEqual(restored.content_address, self.catalog.content_address)
            with self.assertRaises(ValidationError):
                self.catalog_model.write_catalog(self.catalog, destination)
        tampered = self.catalog.to_dict()
        tampered["total_package_bytes"] += 1
        with self.assertRaises(ValidationError):
            self.catalog_model.verify_catalog(tampered)
        with self.assertRaises(ValidationError):
            self.catalog_model.build_catalog((self.package_a.package_bytes, self.package_a.package_bytes), catalog_id="fixed-transport-catalog-diff-policy-duplicate")
        public = json.dumps(self.catalog.to_dict()).lower()
        self.assertNotIn("agent", public)
        self.assertNotIn("model", public)
        self.assertNotIn("language", public)

    def test_cli_http_and_schema_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package_a_path, package_b_path = root / "package-a.zip", root / "package-b.zip"
            catalog_path, audit_path = root / "catalog.json", root / "catalog-audit.json"
            self.transport_model.write_package(self.package_a, package_a_path)
            self.transport_model.write_package(self.package_b, package_b_path)
            command = _legacy_cli._REVIEW_PACKET_TRANSPORT_CATALOG_POLICY_TRANSPORT_CATALOG_568_COMMAND

            def invoke(arguments: list[str]) -> int:
                with contextlib.redirect_stdout(io.StringIO()):
                    return main(arguments)

            self.assertEqual(invoke([command, str(package_b_path), str(package_a_path), "--entry-id", "entry-b", "--entry-id", "entry-a", "--catalog-id", "cli-fixed-transport-catalog", "--destination", str(catalog_path), "--format", "summary"]), 0)
            self.assertEqual(invoke([command + "-verify", str(catalog_path)]), 0)
            self.assertEqual(invoke([command + "-query", str(catalog_path), "--resource", "lineage"]), 0)
            self.assertEqual(invoke([command + "-audit", str(catalog_path), "--destination", str(audit_path), "--format", "summary"]), 0)
            self.assertEqual(invoke([command + "-audit-verify", str(audit_path)]), 0)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog"

                def get(path: str, pairs: list[tuple[str, object]]) -> dict[str, object]:
                    query = urlencode([(key, str(value)) for key, value in pairs])
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                built = get(base, [("package", package_b_path), ("package", package_a_path), ("entry_id", "entry-b"), ("entry_id", "entry-a"), ("catalog_id", "http-fixed-transport-catalog")])
                self.assertEqual((built["entry_count"], built["accepted_count"], built["ready_count"]), (2, 2, 2))
                queried = get(base + "/query", [("input", catalog_path), ("resource", "lineage")])
                self.assertEqual((queried["total"], queried["matched"], queried["returned"]), (2, 2, 2))
                audited = get(base + "/audit", [("input", catalog_path)])
                self.assertEqual((audited["check_count"], audited["failed_count"], audited["accepted"]), (16, 0, True))
                schema = get(base + "/schema", [])
                self.assertIn("entry_count", schema.get("properties", {}))
                capabilities = get(base + "/capabilities", [])
                self.assertIn("operations", capabilities)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
