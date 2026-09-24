"""Deep contracts for package-catalog policy handoff transports."""

# ruff: noqa: E501

from __future__ import annotations

import contextlib
import importlib
import io
import json
import tempfile
import threading
import unittest
import zipfile
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


class FixedTransportPackageCatalogPolicyTransportTest(unittest.TestCase):
    def setUp(self) -> None:
        legacy_diff_path = next(path for path in Path("src/glio_noncode").glob("*_tr_cat_diff.py") if not path.name.endswith("_tcp_tr_cat_diff.py"))
        legacy_diff = importlib.import_module(f"glio_noncode.{legacy_diff_path.stem}")
        policy566 = _local_module("*_tcp.py")
        transport567 = _local_module("*_tcp_tr.py")
        catalog568 = _local_module("*_tcp_tr_cat.py")
        diff569 = _local_module("*_tcp_tr_cat_diff.py")
        self.policy_model = _local_module("*_tcp_tr_cat_diff_pol.py")
        self.policy_audit_model = _local_module("*_tcp_tr_cat_diff_pol_aud.py")
        self.transport = _local_module("*_tcp_tr_cat_diff_pol_tr.py")
        self.transport_audit = _local_module("*_tcp_tr_cat_diff_pol_tr_aud.py")
        source = legacy_diff.catalog_model.build_catalog((), catalog_id="module571-transport-source")
        source_diff = legacy_diff.build_diff(source, source, diff_id="module571-transport-source-diff")
        source_policy = policy566.release_policy(source_diff, policy_id="module571-transport-source-policy", require_ready=False)
        packages = {
            name: transport567.build_package(source_diff, source_policy, package_id=f"module571-transport-{name}")
            for name in ("unchanged", "changed-left", "changed-right", "removed", "added")
        }
        left = catalog568.build_catalog(
            (packages["unchanged"].package_bytes, packages["changed-left"].package_bytes, packages["removed"].package_bytes),
            entry_ids=("entry-unchanged", "entry-changed", "entry-removed"),
            catalog_id="module571-transport-catalog",
        )
        right = catalog568.build_catalog(
            (packages["unchanged"].package_bytes, packages["changed-right"].package_bytes, packages["added"].package_bytes),
            entry_ids=("entry-unchanged", "entry-changed", "entry-added"),
            catalog_id="module571-transport-catalog",
        )
        self.diff_model = diff569
        self.diff = diff569.build_diff(left, right, diff_id="module571-transport-diff")
        self.policy = self.policy_model.release_fixed_transport_catalog_diff_policy_package_catalog_policy(self.diff, policy_id="module571-transport-policy")
        self.policy_audit = self.policy_audit_model.audit_fixed_transport_catalog_diff_policy_package_catalog_policy(self.policy, diff=self.diff)
        self.package = self.transport.build_package(self.diff, self.policy, self.policy_audit, package_id="module571-transport-package")

    def test_deterministic_round_trip_and_independent_audit(self) -> None:
        first = self.transport.build_package(self.diff, self.policy, self.policy_audit, package_id="module571-transport-package")
        second = self.transport.build_package(self.diff, self.policy, self.policy_audit, package_id="module571-transport-package")
        self.assertEqual(first.package_bytes, second.package_bytes)
        self.assertEqual((len(first.manifest.members), first.manifest.policy_accepted, first.manifest.audit_accepted), (4, True, True))
        self.assertEqual(self.transport.load_package(first)[1].state, "ready")
        self.assertEqual(self.transport.query_package(first, resource="audit")["value"]["check_count"], 16)
        receipt = self.transport_audit.audit_package(first)
        self.assertTrue(receipt.accepted)
        self.assertEqual((receipt.check_count, receipt.passed_count, receipt.failed_count), (15, 15, 0))
        public = self.transport.package_json(first).lower()
        self.assertNotIn("agent", public)
        self.assertNotIn("model", public)
        self.assertNotIn("language", public)

    def test_persistence_tamper_duplicate_and_traversal_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "handoff.zip"
            self.transport.write_package(self.package, destination)
            restored = self.transport.load_package(destination)
            self.assertEqual(restored[0].summary(), self.diff.summary())
            self.assertEqual(self.transport.verify_package(destination).package_address, self.package.package_address)
            with self.assertRaises(ValidationError):
                self.transport.write_package(self.package, destination)
            with zipfile.ZipFile(io.BytesIO(self.package.package_bytes), "r") as source:
                members = [(info.filename, source.read(info.filename)) for info in source.infolist()]
            duplicate = io.BytesIO()
            with zipfile.ZipFile(duplicate, "w", compression=zipfile.ZIP_STORED) as target:
                for name, payload in members:
                    target.writestr(name, payload)
                target.writestr("policy.json", b"{}")
            with self.assertRaises(ValidationError):
                self.transport.verify_package(duplicate.getvalue())
            traversal = io.BytesIO()
            with zipfile.ZipFile(traversal, "w", compression=zipfile.ZIP_STORED) as target:
                for name, payload in members:
                    target.writestr(name, payload)
                target.writestr("../escape.json", b"{}")
            with self.assertRaises(ValidationError):
                self.transport.verify_package(traversal.getvalue())
            tampered = io.BytesIO()
            with zipfile.ZipFile(tampered, "w", compression=zipfile.ZIP_STORED) as target:
                for name, payload in members:
                    target.writestr(name, b"{}" if name == "policy.json" else payload)
            with self.assertRaises(ValidationError):
                self.transport.verify_package(tampered.getvalue())

    def test_cli_http_schema_and_capabilities(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diff_path = root / "diff.json"
            package_path = root / "handoff.zip"
            self.diff_model.write_diff(self.diff, diff_path)
            command = _legacy_cli._REVIEW_PACKET_TRANSPORT_CATALOG_POLICY_TRANSPORT_CATALOG_DIFF_POLICY_TRANSPORT_571_COMMAND

            def invoke(arguments: list[str]) -> tuple[int, str]:
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = main(arguments)
                return code, output.getvalue()

            self.assertEqual(invoke([command, str(diff_path), "--profile", "release", "--destination", str(package_path), "--format", "summary"])[0], 0)
            self.assertEqual(invoke([command + "-verify", str(package_path)])[0], 0)
            self.assertEqual(invoke([command + "-load", str(package_path)])[0], 0)
            self.assertEqual(invoke([command + "-query", str(package_path), "--resource", "policy"])[0], 0)
            self.assertEqual(invoke([command + "-audit", str(package_path), "--format", "summary"])[0], 0)
            self.assertEqual(invoke([command + "-schema"])[0], 0)
            self.assertEqual(invoke([command + "-manifest-schema"])[0], 0)
            self.assertEqual(invoke([command + "-audit-capabilities"])[0], 0)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport"

                def get(path: str, pairs: list[tuple[str, object]] = ()) -> dict[str, object]:
                    query = urlencode([(key, str(value)) for key, value in pairs])
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                built = get(base, [("input", diff_path), ("profile", "release"), ("package_id", "module571-http"), ("destination", package_path), ("overwrite", "true")])
                self.assertEqual((built["policy_accepted"], built["audit_accepted"], built["member_count"]), (True, True, 4))
                loaded = get(base + "/load", [("input", package_path)])
                self.assertEqual(sorted(loaded), ["audit", "diff", "policy", "review"])
                queried = get(base + "/query", [("input", package_path), ("resource", "policy")])
                self.assertEqual((queried["resource"], queried["value"]["check_count"]), ("policy", 15))
                audited = get(base + "/audit", [("input", package_path)])
                self.assertEqual((audited["accepted"], audited["check_count"]), (True, 15))
                schema = get(base + "/schema")
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
