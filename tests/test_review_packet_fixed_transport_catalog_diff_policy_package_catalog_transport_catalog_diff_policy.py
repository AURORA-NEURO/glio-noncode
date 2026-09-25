"""Deep contracts for policy gates over longitudinal fixed package-catalog transport diffs."""

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


class FixedTransportPackageCatalogDiffPolicyTest(unittest.TestCase):
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
        self.diff_model = _local_module("*_tcp_tr_cat_diff_pol_tr_cat_diff.py")
        self.policy_model = _local_module("*_tcp_tr_cat_diff_pol_tr_cat_diff_pol.py")
        self.audit_model = _local_module("*_tcp_tr_cat_diff_pol_tr_cat_diff_pol_aud.py")

        source = legacy_diff.catalog_model.build_catalog((), catalog_id="module574-policy-source")
        source_diff = legacy_diff.build_diff(source, source, diff_id="module574-policy-source-diff")
        source_policy = policy566.release_policy(source_diff, policy_id="module574-policy-source-policy", require_ready=False)
        source_packages = {
            name: transport567.build_package(source_diff, source_policy, package_id=f"module574-source-{name}")
            for name in ("unchanged", "changed-left", "changed-right", "removed", "added")
        }
        left_base = catalog568.build_catalog(
            (source_packages["unchanged"].package_bytes, source_packages["changed-left"].package_bytes, source_packages["removed"].package_bytes),
            entry_ids=("entry-unchanged", "entry-changed", "entry-removed"),
            catalog_id="module574-inner-catalog",
        )
        right_base = catalog568.build_catalog(
            (source_packages["unchanged"].package_bytes, source_packages["changed-right"].package_bytes, source_packages["added"].package_bytes),
            entry_ids=("entry-unchanged", "entry-changed", "entry-added"),
            catalog_id="module574-inner-catalog",
        )
        inner_diff = diff569.build_diff(left_base, right_base, diff_id="module574-inner-diff")
        inner_policy = policy570.release_fixed_transport_catalog_diff_policy_package_catalog_policy(inner_diff, policy_id="module574-inner-policy")
        inner_audit = policy_audit570.audit_fixed_transport_catalog_diff_policy_package_catalog_policy(inner_policy, diff=inner_diff)
        packages = {
            name: transport571.build_package(inner_diff, inner_policy, inner_audit, package_id=f"module574-transport-{name}")
            for name in ("unchanged", "changed-left", "changed-right", "removed", "added")
        }
        left = catalog572.build_catalog(
            (packages["unchanged"].package_bytes, packages["changed-left"].package_bytes, packages["removed"].package_bytes),
            entry_ids=("entry-unchanged", "entry-changed", "entry-removed"),
            catalog_id="module574-outer-catalog",
        )
        right = catalog572.build_catalog(
            (packages["unchanged"].package_bytes, packages["changed-right"].package_bytes, packages["added"].package_bytes),
            entry_ids=("entry-unchanged", "entry-changed", "entry-added"),
            catalog_id="module574-outer-catalog",
        )
        self.diff = self.diff_model.build_diff(left, right, diff_id="module574-outer-diff")

    def test_strict_release_and_independent_audit(self) -> None:
        strict = self.policy_model.strict_fixed_transport_catalog_diff_policy_package_catalog_policy(self.diff, policy_id="module574-strict")
        release = self.policy_model.release_fixed_transport_catalog_diff_policy_package_catalog_policy(self.diff, policy_id="module574-release")
        self.assertFalse(strict.accepted)
        self.assertEqual((strict.state, strict.check_count, strict.passed_count, strict.failed_count), ("blocked", 15, 9, 6))
        self.assertTrue(release.accepted)
        self.assertEqual((release.state, release.check_count, release.passed_count, release.failed_count), ("ready", 15, 15, 0))
        receipt = self.audit_model.audit_fixed_transport_catalog_diff_policy_package_catalog_policy(release, diff=self.diff)
        self.assertTrue(receipt.accepted)
        self.assertEqual((receipt.check_count, receipt.passed_count, receipt.failed_count), (16, 16, 0))
        self.assertEqual(self.policy_model.query_fixed_transport_catalog_diff_policy_package_catalog_policy(release, passed=False)["matched"], 0)
        self.assertEqual(self.audit_model.query_audit(receipt, passed=False)["matched"], 0)

    def test_persistence_tamper_and_public_boundary(self) -> None:
        policy = self.policy_model.release_fixed_transport_catalog_diff_policy_package_catalog_policy(self.diff, policy_id="module574-persistence")
        receipt = self.audit_model.audit_fixed_transport_catalog_diff_policy_package_catalog_policy(policy, diff=self.diff)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diff_path, policy_path, audit_path = root / "diff.json", root / "policy.json", root / "audit.json"
            self.diff_model.write_diff(self.diff, diff_path)
            self.policy_model.write_fixed_transport_catalog_diff_policy_package_catalog_policy(policy, policy_path)
            self.audit_model.write_audit(receipt, audit_path)
            self.assertEqual(self.policy_model.verify_fixed_transport_catalog_diff_policy_package_catalog_policy(policy_path).content_address, policy.content_address)
            self.assertEqual(self.audit_model.verify_audit(audit_path).content_address, receipt.content_address)
            with self.assertRaises(ValidationError):
                self.policy_model.write_fixed_transport_catalog_diff_policy_package_catalog_policy(policy, policy_path)
            with self.assertRaises(ValidationError):
                self.policy_model.verify_fixed_transport_catalog_diff_policy_package_catalog_policy(policy.to_dict() | {"accepted": False})
            with self.assertRaises(ValidationError):
                self.policy_model.verify_fixed_transport_catalog_diff_policy_package_catalog_policy(policy.to_dict() | {"language": "en"})
            public = json.dumps(policy.to_dict()).lower()
            self.assertNotIn("agent", public)
            self.assertNotIn("model", public)
            self.assertNotIn("language", public)

    def test_cli_http_schema_and_capabilities(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diff_path, policy_path, audit_path = root / "diff.json", root / "policy.json", root / "audit.json"
            self.diff_model.write_diff(self.diff, diff_path)
            command = _legacy_cli._REVIEW_PACKET_TRANSPORT_CATALOG_POLICY_TRANSPORT_CATALOG_DIFF_POLICY_574_COMMAND

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
            self.assertEqual(invoke([command + "-check-schema"])[0], 0)
            self.assertEqual(invoke([command + "-capabilities"])[0], 0)
            self.assertEqual(invoke([command + "-audit-capabilities"])[0], 0)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy"

                def get(path: str, pairs: list[tuple[str, object]] = ()) -> dict[str, object]:
                    query = urlencode([(key, str(value)) for key, value in pairs])
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                built = get(base, [("input", diff_path), ("profile", "release"), ("destination", policy_path), ("overwrite", "true")])
                self.assertEqual((built["accepted"], built["state"], built["check_count"], built["failed_count"]), (True, "ready", 15, 0))
                queried = get(base + "/query", [("input", policy_path), ("passed", "true")])
                self.assertEqual((queried["matched"], queried["returned"]), (15, 15))
                audited = get(base + "/audit", [("input", policy_path), ("diff", diff_path), ("destination", audit_path), ("overwrite", "true")])
                self.assertEqual((audited["accepted"], audited["passed_count"], audited["check_count"]), (True, 16, 16))
                schema = get(base + "/schema")
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
                capabilities = get(base + "/capabilities")
                self.assertEqual(len(capabilities["check_ids"]), 15)
                self.assertTrue(capabilities["source_free"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
