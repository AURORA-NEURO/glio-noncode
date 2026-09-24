"""Deep contracts for longitudinal comparison of fixed transport package catalogs."""

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


class FixedTransportCatalogDiffPolicyPackageCatalogDiffTest(unittest.TestCase):
    def setUp(self) -> None:
        legacy_diff = next(path for path in Path("src/glio_noncode").glob("*_tr_cat_diff.py") if "_tcp_" not in path.name)
        self.diff_model = importlib.import_module(f"glio_noncode.{legacy_diff.stem}")
        self.policy_model = _local_module("*_tcp.py")
        self.transport_model = _local_module("*_tcp_tr.py")
        self.catalog_model = _local_module("*_tcp_tr_cat.py")
        self.diff_catalog_model = _local_module("*_tcp_tr_cat_diff.py")
        self.audit_model = _local_module("*_tcp_tr_cat_diff_aud.py")
        fixture = Path(".glio-real-demo/real-packet-policy-handoff-review-packet-catalog-diff-policy-review-catalog-v1-fixed-transport-catalog-diff-565.json")
        if not fixture.is_file():
            self.skipTest("real downloaded-data diff fixture is not present")
        source_diff = self.diff_model.load_diff(fixture)
        release = self.policy_model.release_policy(source_diff, policy_id="fixed-transport-package-catalog-diff-release")
        packages = {
            name: self.transport_model.build_package(source_diff, release, package_id=f"fixed-transport-package-catalog-diff-{name}")
            for name in ("unchanged", "changed-left", "changed-right", "removed", "added")
        }
        self.left = self.catalog_model.build_catalog(
            (packages["unchanged"].package_bytes, packages["changed-left"].package_bytes, packages["removed"].package_bytes),
            entry_ids=("entry-unchanged", "entry-changed", "entry-removed"),
            catalog_id="fixed-transport-package-catalog-diff-catalog",
        )
        self.right = self.catalog_model.build_catalog(
            (packages["unchanged"].package_bytes, packages["changed-right"].package_bytes, packages["added"].package_bytes),
            entry_ids=("entry-unchanged", "entry-changed", "entry-added"),
            catalog_id="fixed-transport-package-catalog-diff-catalog",
        )
        self.diff = self.diff_catalog_model.build_diff(self.left, self.right, diff_id="fixed-transport-package-catalog-diff")

    def test_four_way_classification_and_real_data_direction(self) -> None:
        self.assertEqual((self.diff.added_count, self.diff.removed_count, self.diff.changed_count, self.diff.unchanged_count), (1, 1, 1, 1))
        self.assertEqual((self.diff.direction, self.diff.state_transition), ("changed", "same-ready"))
        self.assertEqual(tuple(item.entry_id for item in self.diff.items), ("entry-added", "entry-changed", "entry-removed", "entry-unchanged"))
        self.assertEqual(self.diff_catalog_model.verify_diff(self.diff.to_dict()).content_address, self.diff.content_address)
        self.assertEqual(self.diff_catalog_model.query_diff(self.diff, change="changed")["matched"], 1)
        self.assertEqual(self.diff_catalog_model.query_diff(self.diff, change="added")["matched"], 1)
        self.assertEqual(self.diff_catalog_model.query_diff(self.diff, change="removed")["matched"], 1)

    def test_independent_audit_tamper_and_public_boundary(self) -> None:
        receipt = self.audit_model.audit_diff(self.diff, left=self.left, right=self.right)
        self.assertTrue(receipt.accepted)
        self.assertEqual((receipt.check_count, receipt.passed_count, receipt.failed_count), (13, 13, 0))
        self.assertEqual(self.audit_model.verify_audit(receipt.to_dict()).content_address, receipt.content_address)
        self.assertEqual(self.audit_model.query_audit(receipt, passed=False)["matched"], 0)
        tampered = self.diff.to_dict() | {"changed_count": 0}
        with self.assertRaises(ValidationError):
            self.diff_catalog_model.verify_diff(tampered)
        public = json.dumps(self.diff.to_dict()).lower()
        self.assertNotIn("agent", public)
        self.assertNotIn("model", public)
        self.assertNotIn("language", public)

    def test_persistence_cli_http_and_schema_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left_path, right_path = root / "left.json", root / "right.json"
            diff_path, audit_path = root / "diff.json", root / "audit.json"
            self.catalog_model.write_catalog(self.left, left_path)
            self.catalog_model.write_catalog(self.right, right_path)
            self.diff_catalog_model.write_diff(self.diff, diff_path)
            self.audit_model.write_audit(self.audit_model.audit_diff(self.diff, left=self.left, right=self.right), audit_path)
            self.assertEqual(self.catalog_model.verify_catalog(left_path).content_address, self.left.content_address)
            self.assertEqual(self.diff_catalog_model.verify_diff(diff_path).content_address, self.diff.content_address)
            command = _legacy_cli._REVIEW_PACKET_TRANSPORT_CATALOG_POLICY_TRANSPORT_CATALOG_DIFF_569_COMMAND

            def invoke(arguments: list[str]) -> tuple[int, str]:
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = main(arguments)
                return code, output.getvalue()

            self.assertEqual(invoke([command, str(left_path), str(right_path), "--destination", str(diff_path), "--allow-existing", "--format", "summary"])[0], 0)
            self.assertEqual(invoke([command + "-verify", str(diff_path)])[0], 0)
            self.assertEqual(invoke([command + "-audit", str(diff_path), "--left", str(left_path), "--right", str(right_path), "--destination", str(audit_path), "--allow-existing", "--format", "summary"])[0], 0)
            self.assertEqual(invoke([command + "-audit-verify", str(audit_path)])[0], 0)
            self.assertEqual(invoke([command + "-query", str(diff_path), "--change", "changed"])[0], 0)
            self.assertEqual(invoke([command + "-schema"])[0], 0)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff"

                def get(path: str, pairs: list[tuple[str, object]]) -> dict[str, object]:
                    query = urlencode([(key, str(value)) for key, value in pairs])
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                built = get(base, [("left", left_path), ("right", right_path), ("diff_id", "http-fixed-transport-package-catalog-diff")])
                self.assertEqual((built["changed_count"], built["added_count"], built["removed_count"]), (1, 1, 1))
                queried = get(base + "/query", [("input", diff_path), ("change", "changed")])
                self.assertEqual((queried["matched"], queried["returned"]), (1, 1))
                audited = get(base + "/audit", [("input", diff_path), ("left", left_path), ("right", right_path)])
                self.assertEqual((audited["accepted"], audited["passed_count"], audited["check_count"]), (True, 13, 13))
                schema = get(base + "/schema", [])
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
