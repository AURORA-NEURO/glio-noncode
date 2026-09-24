"""Deep contracts for fixed-transport catalog-diff policy handoff packages."""

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


class FixedTransportCatalogDiffPolicyTransportTest(unittest.TestCase):
    def setUp(self) -> None:
        base_diff = _local_module("*tr_cat_diff.py")
        policy = _local_module("*_tcp.py")
        policy_audit = _local_module("*_tcp_aud.py")
        transport = _local_module("*_tcp_tr.py")
        real_path = Path(".glio-real-demo/real-packet-policy-handoff-review-packet-catalog-diff-policy-review-catalog-v1-fixed-transport-catalog-diff-565.json")
        if not real_path.is_file():
            self.skipTest("real downloaded-data diff fixture is not present")
        self.diff_model = base_diff
        self.policy_model = policy
        self.policy_audit_model = policy_audit
        self.transport = transport
        self.diff = base_diff.load_diff(real_path)
        self.policy = policy.release_policy(self.diff, policy_id="fixed-transport-catalog-diff-policy-release")
        self.audit = policy_audit.audit_policy(self.policy, diff=self.diff)
        self.package = transport.build_package(self.diff, self.policy, self.audit, package_id="fixed-transport-catalog-diff-policy-transport")

    def test_real_downloaded_data_round_trip_is_deterministic_and_source_free(self) -> None:
        diff = self.diff
        policy = self.policy_model.release_policy(diff)
        first = self.transport.build_package(diff, policy)
        second = self.transport.build_package(diff, policy)
        self.assertEqual(first.package_bytes, second.package_bytes)
        self.assertEqual(len(first.manifest.members), 4)
        self.assertTrue(first.manifest.policy_accepted)
        self.assertTrue(first.manifest.audit_accepted)
        self.assertEqual(self.transport.load_package(first)[1].state, "ready")
        self.assertEqual(self.transport.query_package(first, resource="audit")["value"]["check_count"], 16)
        self.assertNotIn("agent", self.transport.package_json(first).lower())
        self.assertNotIn("model", self.transport.package_json(first).lower())
        self.assertNotIn("language", self.transport.package_json(first).lower())

    def test_persistence_tamper_duplicate_and_traversal_rejection(self) -> None:
        transport = self.transport
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "handoff.zip"
            transport.write_package(self.package, destination)
            restored = transport.load_package(destination)
            self.assertEqual(restored[0].summary(), self.diff.summary())
            self.assertEqual(transport.verify_package(destination).package_address, self.package.package_address)
            with self.assertRaises(ValidationError):
                transport.write_package(self.package, destination)

            with zipfile.ZipFile(io.BytesIO(self.package.package_bytes), "r") as source:
                members = [(info.filename, source.read(info.filename)) for info in source.infolist()]

            duplicate = io.BytesIO()
            with zipfile.ZipFile(duplicate, "w", compression=zipfile.ZIP_STORED) as target:
                for name, payload in members:
                    target.writestr(name, payload)
                target.writestr("policy.json", b"{}")
            with self.assertRaises(ValidationError):
                transport.verify_package(duplicate.getvalue())

            traversal = io.BytesIO()
            with zipfile.ZipFile(traversal, "w", compression=zipfile.ZIP_STORED) as target:
                for name, payload in members:
                    target.writestr(name, payload)
                target.writestr("../escape.json", b"{}")
            with self.assertRaises(ValidationError):
                transport.verify_package(traversal.getvalue())

            tampered = io.BytesIO()
            with zipfile.ZipFile(tampered, "w", compression=zipfile.ZIP_STORED) as target:
                for name, payload in members:
                    target.writestr(name, b"{}" if name == "policy.json" else payload)
            with self.assertRaises(ValidationError):
                transport.verify_package(tampered.getvalue())

    def test_cli_http_and_schema_surfaces(self) -> None:
        transport = self.transport
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diff_path = root / "diff.json"
            package_path = root / "handoff.zip"
            self.diff_model.write_diff(self.diff, diff_path)
            command = _legacy_cli._REVIEW_PACKET_TRANSPORT_CATALOG_POLICY_TRANSPORT_567_COMMAND

            def invoke(arguments: list[str]) -> tuple[int, str]:
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = main(arguments)
                return code, output.getvalue()

            self.assertEqual(invoke([command, str(diff_path), "--profile", "release", "--destination", str(package_path), "--format", "summary"])[0], 0)
            self.assertEqual(invoke([command + "-verify", str(package_path)])[0], 0)
            self.assertEqual(invoke([command + "-query", str(package_path), "--resource", "audit"])[0], 0)
            self.assertEqual(invoke([command + "-audit", str(package_path), "--format", "summary"])[0], 0)
            self.assertEqual(invoke([command + "-schema"])[0], 0)
            self.assertEqual(invoke([command + "-manifest-schema"])[0], 0)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/transport/catalog/diff/policy/transport"

                def get(path: str, pairs: list[tuple[str, object]]) -> dict[str, object]:
                    query = urlencode([(key, str(value)) for key, value in pairs])
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                built = get(base, [("input", diff_path), ("profile", "release")])
                self.assertEqual((built["policy_accepted"], built["audit_accepted"], built["member_count"]), (True, True, 4))
                queried = get(base + "/query", [("input", package_path), ("resource", "audit")])
                self.assertEqual(queried["value"]["check_count"], 16)
                audited = get(base + "/audit", [("input", package_path)])
                self.assertEqual((audited["accepted"], audited["check_count"]), (True, 15))
                schema = get(base + "/schema", [])
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
