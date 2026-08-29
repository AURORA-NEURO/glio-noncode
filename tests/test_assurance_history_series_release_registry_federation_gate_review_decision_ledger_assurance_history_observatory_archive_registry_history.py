"""Deep contracts for ordered observatory registry snapshot histories."""

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
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff import DiffFixture


class RegistryHistoryFixture(DiffFixture):
    """Build history snapshots through the verified registry package."""

    HISTORY_COMMAND = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-observatory-archive-registry-history"

    def snapshots(self, root: Path, *names: str, state: str = "ready") -> tuple[registry.ObservatoryArchiveRegistry, ...]:
        return tuple(self.one_registry(root, name, state=state) for name in names)

    def assert_public(self, value) -> None:
        payload = value.to_dict() if hasattr(value, "to_dict") else value
        rendered = canonical_json(payload)
        self.assertNotIn("C:\\", rendered)
        self.assertNotIn("/Users/", rendered)
        forbidden = {"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"}

        def walk(node):
            if isinstance(node, dict):
                for key, item in node.items():
                    self.assertNotIn(key.lower(), forbidden)
                    walk(item)
            elif isinstance(node, (list, tuple)):
                for item in node:
                    walk(item)

        walk(payload)


class RegistryHistoryBuildTests(RegistryHistoryFixture):
    def test_three_snapshots_create_adjacent_ordered_transitions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            values = self.snapshots(root, "first", "second", "third")
            result = history.build_history(values, history_id="history:three")
            self.assertEqual(result.snapshot_count, 3)
            self.assertEqual(result.transition_count, 2)
            self.assertEqual(tuple(item.ordinal for item in result.snapshots), (1, 2, 3))
            self.assertEqual(tuple(item.ordinal for item in result.transitions), (1, 2))
            self.assertEqual(tuple(item.baseline_ordinal for item in result.transitions), (1, 2))
            self.assertEqual(tuple(item.candidate_ordinal for item in result.transitions), (2, 3))
            self.assertEqual(result.start_registry_address, result.snapshots[0].registry_address)
            self.assertEqual(result.end_registry_address, result.snapshots[-1].registry_address)
            self.assertEqual(sum(result.state_counts.values()), 2)
            self.assertEqual(history.address_history(result), result.content_address)
            self.assert_public(result)

    def test_same_downloaded_registry_replays_as_unchanged_history(self):
        source = Path(tempfile.gettempdir()) / "glio-noncode-history-observatory-demo-current" / "registry-v1"
        if not source.is_dir():
            self.skipTest("the optional local downloaded-data demo is not present")
        result = history.build_history_from_directories((source, source), history_id="history:downloaded")
        self.assertEqual(result.snapshot_count, 2)
        self.assertEqual(result.transition_count, 1)
        self.assertEqual(result.transitions[0].state, "unchanged")
        self.assertEqual(result.state_counts["unchanged"], 1)
        self.assertTrue(result.accepted)

    def test_snapshot_and_transition_addresses_are_replayable(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = history.build_history(self.snapshots(Path(temporary), "addresses", "addresses-next"))
            for item in result.snapshots:
                self.assertEqual(history.address_snapshot(item), item.snapshot_address)
            for item in result.transitions:
                self.assertEqual(history.address_transition(item), item.transition_address)
            self.assert_public(result.summary())

    def test_history_mapping_and_exports_are_exact(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = history.build_history(self.snapshots(Path(temporary), "mapping-a", "mapping-b"))
            loaded = history.history_from_mapping(result.to_dict())
            self.assertEqual(loaded.to_dict(), result.to_dict())
            self.assertEqual(history.history_json(loaded), history.history_json(result))
            self.assertIn("registry_id", history.history_csv(result))
            self.assertIn("Registry History", history.render_markdown(result))
            self.assert_public(history.snapshot_schema())
            self.assert_public(history.transition_schema())
            self.assert_public(history.history_schema())
            self.assert_public(history.capabilities())


class RegistryHistoryPersistenceTests(RegistryHistoryFixture):
    def test_exact_four_file_write_load_and_manifest_are_deterministic(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = history.build_history(self.snapshots(root, "persist-a", "persist-b"))
            destination = root / "history"
            self.assertEqual(history.write_history(result, destination), destination)
            self.assertEqual({item.name for item in destination.iterdir()}, set(history.FILES))
            loaded = history.load_history(destination)
            self.assertEqual(loaded.to_dict(), result.to_dict())
            self.assertEqual(history.history_bytes(result), {name: (destination / name).read_bytes() for name in history.FILES})
            self.assertEqual(history.history_manifest_json(result), (destination / history.MANIFEST_NAME).read_text(encoding="utf-8"))
            with self.assertRaises(ValidationError):
                history.write_history(result, destination)
            history.write_history(result, destination, overwrite=True)

    def test_persistence_rejects_extra_members_and_tampered_canonical_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = history.build_history(self.snapshots(root, "tamper-a", "tamper-b"))
            destination = root / "history"
            history.write_history(result, destination)
            (destination / "extra.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                history.load_history(destination)
            (destination / "extra.json").unlink()
            raw = (destination / history.HISTORY_NAME).read_bytes()
            (destination / history.HISTORY_NAME).write_bytes(raw + b"\n")
            with self.assertRaises(ValidationError):
                history.load_history(destination)

    def test_mapping_rejects_forged_fields_and_history_constructor_rejects_nonadjacent_transition(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = history.build_history(self.snapshots(Path(temporary), "forged-a", "forged-b"))
            with self.assertRaises(ValidationError):
                history.history_from_mapping(result.to_dict() | {"source_path": "C:\\hidden"})
            transition = result.transitions[0]
            with self.assertRaises(ValidationError):
                history.RegistryHistoryTransition(transition.ordinal, 2, 4, transition.baseline_registry_address, transition.candidate_registry_address, transition.diff_address, transition.state, transition.item_count, transition.added_count, transition.removed_count, transition.changed_count, transition.unchanged_count, transition.registry_changed_fields, "pending:transition")

    def test_history_builder_rejects_empty_string_and_untyped_inputs(self):
        with self.assertRaises(ValidationError):
            history.build_history(())
        with self.assertRaises(ValidationError):
            history.build_history("not-a-sequence")
        with self.assertRaises(ValidationError):
            history.build_history(({},))
        with self.assertRaises(ValidationError):
            history.build_history_from_directories("not-a-sequence")


class RegistryHistoryCliApiTests(RegistryHistoryFixture):
    def directories(self, root: Path) -> tuple[Path, Path]:
        first, second = self.snapshots(root, "cli-first", "cli-second")
        first_dir = root / "first"
        second_dir = root / "second"
        registry.write_registry(first, first_dir)
        registry.write_registry(second, second_dir)
        return first_dir, second_dir

    def server(self):
        from glio_noncode.api import create_server

        server = create_server("127.0.0.1", 0)
        import threading

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def test_cli_history_write_and_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = self.directories(root)
            destination = root / "history"
            output = root / "history.json"
            self.assertEqual(main([self.HISTORY_COMMAND, "--registry", str(first), "--registry", str(second), "--destination", str(destination), "--format", "json", "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["snapshot_count"], 2)
            self.assertEqual(main([self.HISTORY_COMMAND + "-schema"]), 0)
            self.assertEqual(main([self.HISTORY_COMMAND + "-snapshot-schema"]), 0)
            self.assertEqual(main([self.HISTORY_COMMAND + "-transition-schema"]), 0)
            self.assertEqual(main([self.HISTORY_COMMAND + "-capabilities"]), 0)

    def test_http_history_schema_capabilities_and_report_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            first, second = self.directories(Path(temporary))
            server, thread = self.server()
            try:
                prefix = f"http://127.0.0.1:{server.server_port}/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history"
                params = [("registry", str(first)), ("registry", str(second)), ("format", "json")]
                with urlopen(prefix + "?" + urlencode(params)) as response:
                    payload = json.loads(response.read())
                self.assertEqual(payload["snapshot_count"], 2)
                with urlopen(prefix + "/schema") as response:
                    self.assertFalse(json.loads(response.read())["additionalProperties"])
                with urlopen(prefix + "/snapshot-schema") as response:
                    self.assertFalse(json.loads(response.read())["additionalProperties"])
                with urlopen(prefix + "/transition-schema") as response:
                    self.assertFalse(json.loads(response.read())["additionalProperties"])
                with urlopen(prefix + "/capabilities") as response:
                    self.assertEqual(tuple(json.loads(response.read())["files"]), history.FILES)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
