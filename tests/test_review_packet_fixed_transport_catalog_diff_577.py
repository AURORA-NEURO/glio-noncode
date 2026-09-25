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
        self.transport_model = _local_module("*_tcp_tr_cat_diff_pol_tr_cat_diff_pol_tr.py")
        root = Path(".glio-real-demo")
        package_a = self.transport_model.verify_package(root / "demo-real-575-transport.zip")
        package_b = self.transport_model.verify_package(root / "demo-real-575-cli.zip")
        diff_value, policy_value, audit_value, _review = self.transport_model.load_package(package_a)
        package_c = self.transport_model.build_package(diff_value, policy_value, audit_value, package_id="module577-package-c")
        package_d = self.transport_model.build_package(diff_value, policy_value, audit_value, package_id="module577-package-d")
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
