"""Deep contracts for catalogs of longitudinal catalog-diff policy transports."""

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
    if len(matches) != 1:
        raise RuntimeError(f"expected one local module for {pattern}, got {len(matches)}")
    return importlib.import_module(f"glio_noncode.{matches[0].stem}")


class FixedTransportCatalogDiffPolicyTransportCatalog576Test(unittest.TestCase):
    def setUp(self) -> None:
        legacy_diff_path = next(path for path in Path("src/glio_noncode").glob("*_tr_cat_diff.py") if "_tcp_" not in path.name)
        legacy_diff = importlib.import_module(f"glio_noncode.{legacy_diff_path.stem}")
        policy566 = _local_module("*_tcp.py")
        transport567 = _local_module("*_tcp_tr.py")
        catalog568 = _local_module("*_tcp_tr_cat.py")
        diff569 = _local_module("*_tcp_tr_cat_diff.py")
        policy570 = _local_module("*_tcp_tr_cat_diff_pol.py")
        policy_audit570 = _local_module("*_tcp_tr_cat_diff_pol_aud.py")
        transport571 = _local_module("*_tcp_tr_cat_diff_pol_tr.py")
        catalog572 = _local_module("*_tcp_tr_cat_diff_pol_tr_cat.py")
        diff573 = _local_module("*_tcp_tr_cat_diff_pol_tr_cat_diff.py")
        policy574 = _local_module("*_tcp_tr_cat_diff_pol_tr_cat_diff_pol.py")
        policy_audit574 = _local_module("*_tcp_tr_cat_diff_pol_tr_cat_diff_pol_aud.py")
        transport575 = _local_module("*_tcp_tr_cat_diff_pol_tr_cat_diff_pol_tr.py")
        self.catalog_model = _local_module("*_576.py")
        self.audit_model = _local_module("*_576_aud.py")

        source = legacy_diff.catalog_model.build_catalog((), catalog_id="module576-catalog-source")
        source_diff = legacy_diff.build_diff(source, source, diff_id="module576-catalog-source-diff")
        source_policy = policy566.release_policy(source_diff, policy_id="module576-catalog-source-policy", require_ready=False)
        source_packages = {
            name: transport567.build_package(source_diff, source_policy, package_id=f"module576-source-{name}")
            for name in ("unchanged", "changed-left", "changed-right", "removed", "added")
        }
        left_inner = catalog568.build_catalog(
            (source_packages["unchanged"].package_bytes, source_packages["changed-left"].package_bytes, source_packages["removed"].package_bytes),
            entry_ids=("entry-unchanged", "entry-changed", "entry-removed"),
            catalog_id="module576-inner-catalog",
        )
        right_inner = catalog568.build_catalog(
            (source_packages["unchanged"].package_bytes, source_packages["changed-right"].package_bytes, source_packages["added"].package_bytes),
            entry_ids=("entry-unchanged", "entry-changed", "entry-added"),
            catalog_id="module576-inner-catalog",
        )
        inner_diff = diff569.build_diff(left_inner, right_inner, diff_id="module576-inner-diff")
        inner_policy = policy570.release_fixed_transport_catalog_diff_policy_package_catalog_policy(inner_diff, policy_id="module576-inner-policy")
        inner_audit = policy_audit570.audit_fixed_transport_catalog_diff_policy_package_catalog_policy(inner_policy, diff=inner_diff)
        inner_transports = {
            name: transport571.build_package(inner_diff, inner_policy, inner_audit, package_id=f"module576-inner-{name}")
            for name in ("unchanged", "changed-left", "changed-right", "removed", "added")
        }
        left_outer = catalog572.build_catalog(
            (inner_transports["unchanged"].package_bytes, inner_transports["changed-left"].package_bytes, inner_transports["removed"].package_bytes),
            entry_ids=("entry-unchanged", "entry-changed", "entry-removed"),
            catalog_id="module576-outer-catalog",
        )
        right_outer = catalog572.build_catalog(
            (inner_transports["unchanged"].package_bytes, inner_transports["changed-right"].package_bytes, inner_transports["added"].package_bytes),
            entry_ids=("entry-unchanged", "entry-changed", "entry-added"),
            catalog_id="module576-outer-catalog",
        )
        outer_diff = diff573.build_diff(left_outer, right_outer, diff_id="module576-outer-diff")
        outer_policy = policy574.release_fixed_transport_catalog_diff_policy_package_catalog_policy(outer_diff, policy_id="module576-outer-policy")
        outer_audit = policy_audit574.audit_fixed_transport_catalog_diff_policy_package_catalog_policy(outer_policy, diff=outer_diff)
        self.transport_model = transport575
        self.package_a = transport575.build_package(outer_diff, outer_policy, outer_audit, package_id="module576-transport-a")
        self.package_b = transport575.build_package(outer_diff, outer_policy, outer_audit, package_id="module576-transport-b")
        self.catalog = self.catalog_model.build_catalog(
            (self.package_b.package_bytes, self.package_a.package_bytes),
            entry_ids=("entry-b", "entry-a"),
            catalog_id="module576-transport-catalog",
        )

    def test_deterministic_rollup_and_independent_audit(self) -> None:
        rebuilt = self.catalog_model.build_catalog(
            (self.package_a.package_bytes, self.package_b.package_bytes),
            entry_ids=("entry-a", "entry-b"),
            catalog_id=self.catalog.catalog_id,
        )
        self.assertEqual(rebuilt.content_address, self.catalog.content_address)
        self.assertEqual(tuple(item.entry_id for item in rebuilt.entries), ("entry-a", "entry-b"))
        self.assertEqual((rebuilt.entry_count, rebuilt.accepted_count, rebuilt.ready_count, rebuilt.blocked_count), (2, 2, 2, 0))
        self.assertEqual(rebuilt.total_package_bytes, sum(item.package_byte_count for item in rebuilt.entries))
        self.assertEqual(rebuilt.total_member_bytes, sum(item.member_byte_count for item in rebuilt.entries))
        self.assertEqual(self.catalog_model.query_catalog(rebuilt, resource="accepted")["returned"], 2)
        self.assertEqual(self.catalog_model.query_catalog(rebuilt, resource="lineage")["returned"], 2)
        receipt = self.audit_model.audit_catalog(rebuilt)
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
        tampered = self.catalog.to_dict() | {"total_package_bytes": self.catalog.total_package_bytes + 1}
        with self.assertRaises(ValidationError):
            self.catalog_model.verify_catalog(tampered)
        with self.assertRaises(ValidationError):
            self.catalog_model.build_catalog((self.package_a.package_bytes, self.package_a.package_bytes), catalog_id="module576-duplicate")
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
            command = _legacy_cli._REVIEW_PACKET_TRANSPORT_CATALOG_POLICY_TRANSPORT_CATALOG_576_COMMAND

            def invoke(arguments: list[str]) -> int:
                with contextlib.redirect_stdout(io.StringIO()):
                    return main(arguments)

            self.assertEqual(invoke([command, str(package_b_path), str(package_a_path), "--entry-id", "entry-b", "--entry-id", "entry-a", "--catalog-id", "cli-module576", "--destination", str(catalog_path), "--format", "summary"]), 0)
            self.assertEqual(invoke([command + "-verify", str(catalog_path)]), 0)
            self.assertEqual(invoke([command + "-query", str(catalog_path), "--resource", "lineage"]), 0)
            self.assertEqual(invoke([command + "-audit", str(catalog_path), "--destination", str(audit_path), "--format", "summary"]), 0)
            self.assertEqual(invoke([command + "-audit-verify", str(audit_path)]), 0)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog"

                def get(path: str, pairs: list[tuple[str, object]]) -> dict[str, object]:
                    query = urlencode([(key, str(value)) for key, value in pairs])
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                built = get(base, [("package", package_b_path), ("package", package_a_path), ("entry_id", "entry-b"), ("entry_id", "entry-a"), ("catalog_id", "http-module576")])
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
