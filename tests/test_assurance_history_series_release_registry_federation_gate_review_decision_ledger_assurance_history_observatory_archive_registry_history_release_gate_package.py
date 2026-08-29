"""Deep contracts for durable release-gate packages."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry as registry
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history as history
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate as gate
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_package as package
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff import DiffFixture


class RegistryHistoryReleaseGatePackageFixture(DiffFixture):
    """Build package inputs from verified history and gate values."""

    PACKAGE_COMMAND = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-observatory-archive-registry-history-release-gate-package"

    def gate_value(self, root: Path) -> gate.RegistryHistoryReleaseGate:
        registry_value = self.one_registry(root, "package")
        history_value = history.build_history((registry_value, registry_value), history_id="history:package")
        return gate.evaluate_history(history_value)

    def assert_public(self, value) -> None:
        payload = value.to_dict() if hasattr(value, "to_dict") else value
        rendered = canonical_json(payload)
        self.assertNotIn("C:\\", rendered)
        self.assertNotIn("/Users/", rendered)
        forbidden = {"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "user"}

        def walk(node):
            if isinstance(node, dict):
                for key, item in node.items():
                    self.assertNotIn(key.lower(), forbidden)
                    walk(item)
            elif isinstance(node, (list, tuple)):
                for item in node:
                    walk(item)

        walk(payload)

    def server(self):
        from glio_noncode.api import create_server

        server = create_server("127.0.0.1", 0)
        import threading

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread


class RegistryHistoryReleaseGatePackageBuildTests(RegistryHistoryReleaseGatePackageFixture):
    def test_exact_three_file_persistence_and_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.gate_value(root)
            destination = root / "package"
            self.assertEqual(package.write_package(value, destination), destination)
            self.assertEqual({item.name for item in destination.iterdir()}, set(package.FILES))
            loaded = package.load_package(destination)
            self.assertEqual(loaded.to_dict(), value.to_dict())
            self.assertEqual(package.verify_package(destination).content_address, value.content_address)
            self.assertEqual(package.package_bytes(value), {name: (destination / name).read_bytes() for name in package.FILES})
            self.assertEqual(package.package_manifest_json(loaded), (destination / package.MANIFEST_NAME).read_text(encoding="utf-8"))
            with self.assertRaises(ValidationError):
                package.write_package(value, destination)
            package.write_package(value, destination, overwrite=True)

    def test_manifest_policy_and_gate_linkage_is_replayed(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.gate_value(Path(temporary))
            payload = package.package_bytes(value)
            manifest = json.loads(payload[package.MANIFEST_NAME])
            policy = json.loads(payload[package.POLICY_NAME])
            persisted_gate = json.loads(payload[package.GATE_NAME])
            self.assertEqual(tuple(manifest["files"]), package.FILES[1:])
            self.assertEqual(manifest["gate_address"], value.content_address)
            self.assertEqual(manifest["policy_address"], value.policy_address)
            self.assertEqual(policy, persisted_gate["policy"])
            self.assertEqual(manifest["artifact_count"], 2)
            self.assert_public(manifest)
            self.assert_public(policy)

    def test_tampered_extra_noncanonical_and_unlinked_artifacts_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.gate_value(root)
            destination = root / "package"
            package.write_package(value, destination)
            (destination / "extra.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                package.load_package(destination)
            (destination / "extra.json").unlink()
            gate_bytes = (destination / package.GATE_NAME).read_bytes()
            (destination / package.GATE_NAME).write_bytes(gate_bytes + b"\n")
            with self.assertRaises(ValidationError):
                package.load_package(destination)
            (destination / package.GATE_NAME).write_bytes(gate_bytes)
            policy_document = json.loads((destination / package.POLICY_NAME).read_text(encoding="utf-8"))
            policy_document["policy_id"] = "policy:tampered"
            (destination / package.POLICY_NAME).write_text(json.dumps(policy_document, separators=(",", ":")), encoding="utf-8")
            with self.assertRaises(ValidationError):
                package.load_package(destination)

    def test_downloaded_history_gate_package_round_trips(self):
        source = Path(tempfile.gettempdir()) / "glio-noncode-history-audit-demo-eb48d6ff52184a0e97a4b81607b93dc2"
        if not source.is_dir():
            self.skipTest("the optional local downloaded-data demo is not present")
        value = gate.evaluate_history_from_directory(source)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "downloaded-gate"
            package.write_package(value, destination)
            loaded = package.load_package(destination)
            self.assertEqual(loaded.state, "ready")
            self.assertEqual(loaded.content_address, value.content_address)
            self.assert_public(loaded)

    def test_schemas_and_capabilities_are_public(self):
        for value in (package.package_schema(), package.manifest_schema(), package.capabilities()):
            self.assert_public(value)
        self.assertEqual(tuple(package.capabilities()["files"]), package.FILES)


class RegistryHistoryReleaseGatePackageCliApiTests(RegistryHistoryReleaseGatePackageFixture):
    def directories(self, root: Path) -> Path:
        value = self.one_registry(root, "package-cli")
        registry_dir = root / "registry"
        registry.write_registry(value, registry_dir)
        history_dir = root / "history"
        history.write_history(history.build_history_from_directories((registry_dir, registry_dir), history_id="history:package-cli"), history_dir)
        return history_dir

    def test_cli_package_verify_manifest_and_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            history_dir = self.directories(root)
            package_dir = root / "package"
            output = root / "summary.json"
            self.assertEqual(main([self.PACKAGE_COMMAND, "--input", str(history_dir), "--destination", str(package_dir), "--format", "json", "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["state"], "ready")
            self.assertEqual(main([self.PACKAGE_COMMAND + "-verify", "--input", str(package_dir)]), 0)
            self.assertEqual(main([self.PACKAGE_COMMAND + "-manifest", "--input", str(package_dir)]), 0)
            self.assertEqual(main([self.PACKAGE_COMMAND + "-schema"]), 0)
            self.assertEqual(main([self.PACKAGE_COMMAND + "-manifest-schema"]), 0)
            self.assertEqual(main([self.PACKAGE_COMMAND + "-capabilities"]), 0)

    def test_http_package_schema_capabilities_and_report_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            history_dir = self.directories(root)
            package_dir = root / "http-package"
            server, thread = self.server()
            try:
                prefix = "http://127.0.0.1:%s/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/release-gate/package"
                prefix = prefix % server.server_port
                params = urlencode({"input": str(history_dir), "destination": str(package_dir), "format": "json"})
                with urlopen(prefix + "?" + params) as response:
                    payload = json.loads(response.read())
                self.assertEqual(payload["state"], "ready")
                with urlopen(prefix + "/verify?input=" + str(package_dir)) as response:
                    self.assertEqual(json.loads(response.read())["state"], "ready")
                with urlopen(prefix + "/manifest?input=" + str(package_dir)) as response:
                    self.assertEqual(json.loads(response.read())["artifact_count"], 2)
                with urlopen(prefix + "/schema") as response:
                    self.assertFalse(json.loads(response.read())["additionalProperties"])
                with urlopen(prefix + "/manifest-schema") as response:
                    self.assertIn("manifest_address", json.loads(response.read())["properties"])
                with urlopen(prefix + "/capabilities") as response:
                    self.assertEqual(tuple(json.loads(response.read())["files"]), package.FILES)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
