"""Deep contracts for longitudinal diffs of fixed transport catalogs."""

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


class FixedTransportCatalogDiff577Test(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog_model = _local_module("*_576.py")
        self.diff_model = importlib.import_module("glio_noncode.downloaded_data_review_packet_fixed_transport_catalog_diff_577")
        self.audit_model = importlib.import_module("glio_noncode.downloaded_data_review_packet_fixed_transport_catalog_diff_577_aud")
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
        self.transport_model = _local_module("*_tcp_tr_cat_diff_pol_tr_cat_diff_pol_tr.py")
        source = legacy_diff.catalog_model.build_catalog((), catalog_id="module577-catalog-source")
        source_diff = legacy_diff.build_diff(source, source, diff_id="module577-catalog-source-diff")
        source_policy = policy566.release_policy(source_diff, policy_id="module577-catalog-source-policy", require_ready=False)
        source_packages = {name: transport567.build_package(source_diff, source_policy, package_id=f"module577-source-{name}") for name in ("unchanged", "changed-left", "changed-right", "removed", "added")}
        left_inner = catalog568.build_catalog((source_packages["unchanged"].package_bytes, source_packages["changed-left"].package_bytes, source_packages["removed"].package_bytes), entry_ids=("entry-unchanged", "entry-changed", "entry-removed"), catalog_id="module577-inner-catalog")
        right_inner = catalog568.build_catalog((source_packages["unchanged"].package_bytes, source_packages["changed-right"].package_bytes, source_packages["added"].package_bytes), entry_ids=("entry-unchanged", "entry-changed", "entry-added"), catalog_id="module577-inner-catalog")
        inner_diff = diff569.build_diff(left_inner, right_inner, diff_id="module577-inner-diff")
        inner_policy = policy570.release_fixed_transport_catalog_diff_policy_package_catalog_policy(inner_diff, policy_id="module577-inner-policy")
        inner_audit = policy_audit570.audit_fixed_transport_catalog_diff_policy_package_catalog_policy(inner_policy, diff=inner_diff)
        inner_transports = {name: transport571.build_package(inner_diff, inner_policy, inner_audit, package_id=f"module577-inner-{name}") for name in ("unchanged", "changed-left", "changed-right", "removed", "added")}
        left_outer = catalog572.build_catalog((inner_transports["unchanged"].package_bytes, inner_transports["changed-left"].package_bytes, inner_transports["removed"].package_bytes), entry_ids=("entry-unchanged", "entry-changed", "entry-removed"), catalog_id="module577-outer-catalog")
        right_outer = catalog572.build_catalog((inner_transports["unchanged"].package_bytes, inner_transports["changed-right"].package_bytes, inner_transports["added"].package_bytes), entry_ids=("entry-unchanged", "entry-changed", "entry-added"), catalog_id="module577-outer-catalog")
        outer_diff = diff573.build_diff(left_outer, right_outer, diff_id="module577-outer-diff")
        outer_policy = policy574.release_fixed_transport_catalog_diff_policy_package_catalog_policy(outer_diff, policy_id="module577-outer-policy")
        outer_audit = policy_audit574.audit_fixed_transport_catalog_diff_policy_package_catalog_policy(outer_policy, diff=outer_diff)
        package_a = self.transport_model.build_package(outer_diff, outer_policy, outer_audit, package_id="module577-package-a")
        package_b = self.transport_model.build_package(outer_diff, outer_policy, outer_audit, package_id="module577-package-b")
        package_c = self.transport_model.build_package(outer_diff, outer_policy, outer_audit, package_id="module577-package-c")
        package_d = self.transport_model.build_package(outer_diff, outer_policy, outer_audit, package_id="module577-package-d")
        self.left_catalog = self.catalog_model.build_catalog((package_b.package_bytes, package_c.package_bytes, package_a.package_bytes), entry_ids=("entry-changed", "entry-removed", "entry-unchanged"), catalog_id="module577-catalog")
        self.right_catalog = self.catalog_model.build_catalog((package_d.package_bytes, package_c.package_bytes, package_a.package_bytes), entry_ids=("entry-changed", "entry-added", "entry-unchanged"), catalog_id="module577-catalog")
        self.diff = self.diff_model.build_diff(self.left_catalog, self.right_catalog, diff_id="module577-diff")

    def test_all_change_classes_and_independent_audit(self) -> None:
        self.assertEqual((self.diff.added_count, self.diff.removed_count, self.diff.changed_count, self.diff.unchanged_count), (1, 1, 1, 1))
        self.assertEqual((self.diff.direction, self.diff.state_transition), ("changed", "same-ready"))
        rebuilt = self.diff_model.build_diff(self.left_catalog, self.right_catalog, diff_id=self.diff.diff_id)
        self.assertEqual(rebuilt.content_address, self.diff.content_address)
        receipt = self.audit_model.audit_diff(self.diff, left=self.left_catalog, right=self.right_catalog)
        self.assertEqual((receipt.check_count, receipt.passed_count, receipt.failed_count, receipt.accepted), (13, 13, 0, True))
        self.assertEqual(self.audit_model.query_audit(receipt, passed=False)["matched"], 0)
        self.assertEqual(self.diff_model.query_diff(self.diff, change="added")["returned"], 1)

    def test_persistence_tamper_and_public_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diff_path, audit_path = root / "diff.json", root / "audit.json"
            self.diff_model.write_diff(self.diff, diff_path)
            restored = self.diff_model.load_diff(diff_path)
            self.assertEqual(restored.content_address, self.diff.content_address)
            receipt = self.audit_model.audit_diff(restored)
            self.audit_model.write_audit(receipt, audit_path)
            self.assertEqual(self.audit_model.load_audit(audit_path).content_address, receipt.content_address)
            with self.assertRaises(ValidationError):
                self.diff_model.verify_diff(self.diff.to_dict() | {"direction": "improved"})
            with self.assertRaises(ValidationError):
                self.diff_model.verify_diff(self.diff.to_dict() | {"agent": "forbidden"})

    def test_cli_http_and_schema_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left_path, right_path = root / "left.json", root / "right.json"
            diff_path, audit_path = root / "diff.json", root / "audit.json"
            self.catalog_model.write_catalog(self.left_catalog, left_path)
            self.catalog_model.write_catalog(self.right_catalog, right_path)
            command = _legacy_cli._REVIEW_PACKET_TRANSPORT_CATALOG_POLICY_TRANSPORT_CATALOG_DIFF_577_COMMAND

            def invoke(arguments: list[str]) -> int:
                with contextlib.redirect_stdout(io.StringIO()):
                    return main(arguments)

            self.assertEqual(invoke([command, str(left_path), str(right_path), "--diff-id", "cli-module577", "--destination", str(diff_path), "--format", "summary"]), 0)
            self.assertEqual(invoke([command + "-verify", str(diff_path)]), 0)
            self.assertEqual(invoke([command + "-query", str(diff_path), "--change", "added"]), 0)
            self.assertEqual(invoke([command + "-audit", str(diff_path), "--destination", str(audit_path), "--format", "summary"]), 0)
            self.assertEqual(invoke([command + "-audit-verify", str(audit_path)]), 0)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff"

                def get(path: str, pairs: list[tuple[str, object]]) -> dict[str, object]:
                    query = urlencode([(key, str(value)) for key, value in pairs])
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                built = get(base, [("left", left_path), ("right", right_path), ("diff_id", "http-module577")])
                self.assertEqual((built["added_count"], built["removed_count"], built["changed_count"], built["unchanged_count"]), (1, 1, 1, 1))
                queried = get(base + "/query", [("input", diff_path), ("change", "added")])
                self.assertEqual((queried["matched"], queried["returned"]), (1, 1))
                audited = get(base + "/audit", [("input", diff_path)])
                self.assertEqual((audited["check_count"], audited["failed_count"], audited["accepted"]), (13, 0, True))
                schema = get(base + "/schema", [])
                self.assertIn("items", schema.get("properties", {}))
                self.assertIn("operations", get(base + "/capabilities", {}))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
