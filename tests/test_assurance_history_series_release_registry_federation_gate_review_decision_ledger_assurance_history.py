"""Deep contracts for longitudinal review decision-ledger assurance history."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import threading
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance as assurance
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history as history
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_bytes, canonical_json
from examples import release_registry_federation_gate_review_decision_ledger_assurance_history_demo as demo
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance import AssuranceFixture


class HistoryFixture(AssuranceFixture):
    """Build persisted-download-shaped assurance gates in three outcomes."""

    def setUp(self):
        super().setUp()
        self.ready_gate = assurance.build_assurance_gate(self.ready_ledger, gate_id="gate:history-ready")
        self.held_gate = assurance.build_assurance_gate(self.held_ledger, gate_id="gate:history-held")
        self.blocked_gate = assurance.build_assurance_gate(self.blocked_ledger, gate_id="gate:history-blocked")

    def build_history(self, gates=None, snapshot_ids=None):
        gates = tuple(gates or (self.ready_gate, self.ready_gate, self.held_gate, self.blocked_gate, self.ready_gate))
        snapshot_ids = tuple(snapshot_ids or ("snapshot:0", "snapshot:1", "snapshot:2", "snapshot:3", "snapshot:4"))
        return history.build_history(gates, history_id="history:test", snapshot_ids=snapshot_ids)

    @staticmethod
    def capture_cli(argv):
        output = StringIO()
        with redirect_stdout(output):
            status = main(argv)
        return status, output.getvalue()

    @staticmethod
    def write_history(value, root: Path, name: str = "history") -> Path:
        target = root / name
        history.write_history(value, target)
        return target

    @staticmethod
    def write_gate(value, root: Path, name: str) -> Path:
        target = root / name
        assurance.write_assurance_gate(value, target)
        return target

    def assert_public(self, value):
        payload = value.to_dict() if hasattr(value, "to_dict") else value
        text = canonical_json(payload)
        self.assertNotIn("C:\\", text)
        self.assertNotIn("/Users/", text)
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


class HistoryBuildTests(HistoryFixture):
    def test_empty_history_is_explicit_and_addressed(self):
        value = history.build_history((), history_id="history:empty")
        self.assertEqual(value.state, history.HistoryState.EMPTY.value)
        self.assertEqual(value.head_address, history.INITIAL_HEAD)
        self.assertFalse(value.accepted)
        self.assertFalse(value.release_ready)
        self.assert_public(value)
        self.assertEqual(history.address_history(value), value.content_address)

    def test_history_preserves_outcome_transitions(self):
        value = self.build_history()
        self.assertEqual(tuple(item.transition for item in value.entries), ("initial", "stable", "regressed", "regressed", "improved"))
        self.assertEqual(value.initial_count, 1)
        self.assertEqual(value.stable_count, 1)
        self.assertEqual(value.regressed_count, 2)
        self.assertEqual(value.improved_count, 1)
        self.assertEqual(value.promote_count, 3)
        self.assertEqual(value.hold_count, 1)
        self.assertEqual(value.block_count, 1)
        self.assertEqual(value.state, "promote")
        self.assertTrue(value.release_ready)

    def test_repeated_build_is_deterministic(self):
        first = self.build_history()
        second = self.build_history()
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(history.history_json(first), history.history_json(second))
        self.assertEqual(history.address_history(first), history.address_history(second))

    def test_default_snapshot_ids_are_content_stable(self):
        first = history.build_history((self.ready_gate, self.held_gate))
        second = history.build_history((self.ready_gate, self.held_gate))
        self.assertEqual(tuple(item.snapshot_id for item in first.entries), tuple(item.snapshot_id for item in second.entries))
        self.assertEqual(first.content_address, second.content_address)

    def test_custom_history_id_changes_only_history_identity_graph(self):
        first = self.build_history()
        second = history.build_history((self.ready_gate,), history_id="history:other", snapshot_ids=("snapshot:0",))
        self.assertNotEqual(first.history_id, second.history_id)
        self.assertNotEqual(first.content_address, second.content_address)
        self.assertEqual(first.entries[0].bundle_address, second.entries[0].bundle_address)

    def test_entry_addresses_form_a_contiguous_head_chain(self):
        value = self.build_history()
        self.assertEqual(value.entries[0].previous_address, history.INITIAL_HEAD)
        for previous, current in zip(value.entries, value.entries[1:], strict=False):
            self.assertEqual(current.previous_address, previous.content_address)
        self.assertEqual(value.head_address, value.entries[-1].content_address)
        self.assertTrue(all(history.address_entry(entry) == entry.content_address for entry in value.entries))

    def test_append_requires_expected_head(self):
        value = history.build_history((self.ready_gate,), history_id="history:append", snapshot_ids=("s0",))
        appended = history.append_history(value, self.held_gate, snapshot_id="s1", expected_address=value.content_address)
        self.assertEqual(appended.entry_count, 2)
        self.assertEqual(appended.entries[-1].previous_address, value.head_address)
        with self.assertRaises(ValidationError):
            history.append_history(value, self.held_gate, snapshot_id="s1", expected_address="wrong:head")

    def test_append_rejects_duplicate_snapshot(self):
        value = history.build_history((self.ready_gate,), history_id="history:append", snapshot_ids=("s0",))
        with self.assertRaises(ValidationError):
            history.append_history(value, self.held_gate, snapshot_id="s0")

    def test_append_classifies_new_snapshot_against_terminal_entry(self):
        value = history.build_history((self.held_gate,), history_id="history:append", snapshot_ids=("s0",))
        appended = history.append_history(value, self.ready_gate, snapshot_id="s1")
        self.assertEqual(appended.entries[-1].transition, "improved")
        self.assertEqual(appended.latest_snapshot_id, "s1")

    def test_history_verifier_replays_summary(self):
        value = self.build_history()
        self.assertIs(history.verify_history(value), value)
        self.assertIs(history.verify_history_against_gates(value, (self.ready_gate, self.ready_gate, self.held_gate, self.blocked_gate, self.ready_gate)), value)

    def test_verifier_rejects_cross_snapshot_gate_sequence(self):
        value = self.build_history()
        with self.assertRaises(ValidationError):
            history.verify_history_against_gates(value, (self.ready_gate, self.ready_gate, self.held_gate, self.blocked_gate, self.held_gate))

    def test_history_mapping_round_trip(self):
        value = self.build_history()
        mapped = history.history_from_mapping(value.to_dict())
        self.assertEqual(mapped.to_dict(), value.to_dict())
        self.assertEqual(history.entry_from_mapping(value.entries[0].to_dict()).to_dict(), value.entries[0].to_dict())

    def test_mapping_rejects_unknown_fields(self):
        payload = self.build_history().to_dict() | {"unexpected": True}
        with self.assertRaises(ValidationError):
            history.history_from_mapping(payload)
        with self.assertRaises(ValidationError):
            history.entry_from_mapping(self.build_history().entries[0].to_dict() | {"unexpected": True})

    def test_public_projection_is_recursive(self):
        self.assert_public(self.build_history())
        self.assert_public(self.build_history().entries[0])

    def test_capabilities_are_closed_and_descriptive(self):
        value = history.capabilities()
        self.assertEqual(tuple(value["package_files"]), history.FILES)
        self.assertEqual(tuple(value["diff_package_files"]), history.DIFF_FILES)
        self.assertEqual(tuple(value["resources"]["history"]), history.HistoryQuery.RESOURCES)
        self.assertIn("independent replay", value["features"])
        self.assert_public(value)

    def test_schema_contracts_have_bounded_arrays_and_closed_objects(self):
        self.assertFalse(history.history_schema()["additionalProperties"])
        self.assertEqual(history.history_schema()["properties"]["entries"]["maxItems"], history.MAX_ENTRIES)
        self.assertFalse(history.entry_schema()["additionalProperties"])
        self.assertEqual(history.diff_schema()["properties"]["items"]["maxItems"], history.MAX_DIFF_ITEMS)
        self.assertFalse(history.query_schema()["additionalProperties"])
        self.assertFalse(history.diff_query_schema()["additionalProperties"])


class HistoryDiffTests(HistoryFixture):
    def test_identical_history_diff_is_unchanged(self):
        value = self.build_history()
        diff = history.build_diff(value, value)
        self.assertEqual(diff.state, "unchanged")
        self.assertEqual(diff.unchanged_count, value.entry_count)
        self.assertEqual(diff.changed_count, 0)
        self.assertEqual(diff.improved_count, 0)
        self.assertEqual(diff.regressed_count, 0)
        self.assertEqual(history.address_diff(diff), diff.content_address)

    def test_diff_detects_added_snapshot(self):
        baseline = history.build_history((self.ready_gate,), snapshot_ids=("s0",))
        candidate = history.build_history((self.ready_gate, self.held_gate), snapshot_ids=("s0", "s1"))
        diff = history.build_diff(baseline, candidate)
        added = [item for item in diff.items if item.action == "added"]
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0].key, "s1")
        self.assertEqual(added[0].direction, "improved")

    def test_diff_detects_removed_snapshot(self):
        baseline = history.build_history((self.ready_gate, self.held_gate), snapshot_ids=("s0", "s1"))
        candidate = history.build_history((self.ready_gate,), snapshot_ids=("s0",))
        diff = history.build_diff(baseline, candidate)
        removed = [item for item in diff.items if item.action == "removed"]
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0].key, "s1")
        self.assertEqual(removed[0].direction, "regressed")

    def test_diff_detects_changed_snapshot_and_direction(self):
        baseline = history.build_history((self.held_gate,), snapshot_ids=("s0",))
        candidate = history.build_history((self.ready_gate,), snapshot_ids=("s0",))
        diff = history.build_diff(baseline, candidate)
        self.assertEqual(diff.changed_count, 1)
        self.assertEqual(diff.improved_count, 1)
        self.assertEqual(diff.state, "improved")
        self.assertEqual(diff.items[0].action, "changed")

    def test_diff_detects_regression_and_mixed_direction(self):
        baseline = history.build_history((self.held_gate, self.ready_gate), snapshot_ids=("s0", "s1"))
        candidate = history.build_history((self.ready_gate, self.blocked_gate), snapshot_ids=("s0", "s1"))
        diff = history.build_diff(baseline, candidate)
        self.assertEqual(diff.improved_count, 1)
        self.assertEqual(diff.regressed_count, 1)
        self.assertEqual(diff.state, "mixed")
        regression = history.build_diff(
            history.build_history((self.ready_gate, self.ready_gate), snapshot_ids=("s0", "s1")),
            history.build_history((self.blocked_gate, self.blocked_gate), snapshot_ids=("s0", "s1")),
        )
        self.assertEqual(regression.regressed_count, 2)
        self.assertEqual(regression.state, "regressed")

    def test_diff_mapping_round_trip_and_public_boundary(self):
        value = history.build_diff(self.build_history(), history.build_history((self.ready_gate, self.held_gate), snapshot_ids=("snapshot:0", "snapshot:1")))
        self.assertEqual(history.diff_from_mapping(value.to_dict()).to_dict(), value.to_dict())
        self.assert_public(value)
        self.assert_public(value.items[0])

    def test_diff_verifier_against_histories(self):
        baseline = self.build_history()
        candidate = history.build_history((self.ready_gate, self.held_gate), snapshot_ids=("snapshot:0", "snapshot:1"))
        value = history.build_diff(baseline, candidate)
        self.assertIs(history.verify_diff(value), value)
        self.assertIs(history.verify_diff_against_histories(value, baseline, candidate), value)
        with self.assertRaises(ValidationError):
            history.verify_diff_against_histories(value, baseline, baseline)

    def test_diff_rejects_unknown_mapping_fields(self):
        value = history.build_diff(self.build_history(), self.build_history())
        with self.assertRaises(ValidationError):
            history.diff_from_mapping(value.to_dict() | {"unexpected": True})
        with self.assertRaises(ValidationError):
            history.diff_item_from_mapping(value.items[0].to_dict() | {"unexpected": True})

    def test_diff_item_addresses_are_unique_and_recomputable(self):
        value = history.build_diff(self.build_history(), history.build_history((self.ready_gate, self.held_gate), snapshot_ids=("snapshot:0", "snapshot:1")))
        self.assertEqual(len({item.content_address for item in value.items}), value.item_count)
        self.assertTrue(all(history.address_diff_item(item) == item.content_address for item in value.items))


class HistoryQueryTests(HistoryFixture):
    def test_query_summary_is_addressed(self):
        value = self.build_history()
        result = history.query_history(value)
        self.assertEqual(result.total_count, 1)
        self.assertEqual(result.returned_count, 1)
        self.assertEqual(result.items[0]["history_id"], value.history_id)
        self.assertEqual(history.address_query(result), result.content_address)

    def test_query_filters_by_transition_and_state(self):
        value = self.build_history()
        result = history.query_history(value, resource="entries", transition="regressed")
        self.assertEqual(result.returned_count, 2)
        self.assertTrue(all(item["transition"] == "regressed" for item in result.items))
        result = history.query_history(value, resource="states", gate_state="promote", release_ready=True)
        self.assertEqual(result.returned_count, 3)
        self.assertTrue(all(item["gate_state"] == "promote" and item["release_ready"] for item in result.items))

    def test_query_filters_by_text_and_pagination(self):
        value = self.build_history()
        result = history.query_history(value, resource="entries", text="snapshot:2", offset=0, limit=1)
        self.assertEqual(result.returned_count, 1)
        self.assertEqual(result.items[0]["snapshot_id"], "snapshot:2")
        empty = history.query_history(value, resource="entries", offset=100)
        self.assertEqual(empty.returned_count, 0)
        self.assertEqual(empty.items, ())

    def test_query_object_and_kwargs_are_mutually_exclusive(self):
        value = self.build_history()
        with self.assertRaises(ValidationError):
            history.query_history(value, history.HistoryQuery(resource="entries"), limit=1)

    def test_query_rejects_bad_filters_and_windows(self):
        value = self.build_history()
        with self.assertRaises(ValidationError):
            history.HistoryQuery(transition="unknown")
        with self.assertRaises(ValidationError):
            history.HistoryQuery(offset=-1)
        with self.assertRaises(ValidationError):
            history.HistoryQuery(resource="unknown")
        with self.assertRaises(ValidationError):
            history.query_history(value, resource="entries", limit=0)

    def test_diff_query_filters_actions_directions_and_states(self):
        value = history.build_diff(self.build_history(), history.build_history((self.ready_gate, self.held_gate), snapshot_ids=("snapshot:0", "snapshot:1")))
        result = history.query_diff(value, resource="items", action="added")
        self.assertTrue(all(item["action"] == "added" for item in result.items))
        result = history.query_diff(value, resource="directions", direction="regressed")
        self.assertTrue(all(item["direction"] == "regressed" for item in result.items))
        result = history.query_diff(value, resource="items", gate_state="hold")
        self.assertTrue(all(item["candidate_gate_state"] == "hold" or item["baseline_gate_state"] == "hold" for item in result.items))

    def test_diff_query_object_and_kwargs_are_mutually_exclusive(self):
        value = history.build_diff(self.build_history(), self.build_history())
        with self.assertRaises(ValidationError):
            history.query_diff(value, history.HistoryDiffQuery(resource="items"), limit=1)

    def test_query_serializers_are_stable(self):
        value = self.build_history()
        result = history.query_history(value, resource="entries")
        self.assertEqual(history.query_json(result), history.query_json(result))
        self.assertIn("snapshot:0", history.query_csv(result))
        self.assertIn("Assurance History Query", history.render_query_markdown(result))
        diff = history.build_diff(value, value)
        diff_result = history.query_diff(diff, resource="items")
        self.assertIn("Diff Query", history.render_diff_query_markdown(diff_result))


class HistoryPersistenceTests(HistoryFixture):
    def test_history_writes_exact_three_files_and_reloads(self):
        value = self.build_history()
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.write_history(value, Path(temporary))
            self.assertEqual({item.name for item in destination.iterdir()}, set(history.FILES))
            loaded = history.load_history(destination)
            self.assertEqual(loaded.to_dict(), value.to_dict())
            self.assertEqual(history.verify_history_directory(destination).to_dict(), loaded.to_dict())

    def test_history_manifest_and_artifacts_are_canonical(self):
        value = self.build_history()
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.write_history(value, Path(temporary))
            manifest = json.loads((destination / history.MANIFEST_NAME).read_text(encoding="utf-8"))
            self.assertEqual(canonical_bytes(manifest), (destination / history.MANIFEST_NAME).read_bytes())
            self.assertEqual(manifest["history_address"], value.content_address)
            self.assertEqual(manifest["artifact_count"], 2)
            for artifact in manifest["artifacts"]:
                raw = (destination / artifact["name"]).read_bytes()
                self.assertEqual(artifact["bytes"], len(raw))
                self.assertEqual(artifact["byte_address"], history.hash_bytes(raw) if hasattr(history, "hash_bytes") else artifact["byte_address"])

    def test_history_rejects_extra_file(self):
        value = self.build_history()
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.write_history(value, Path(temporary))
            (destination / "extra.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                history.load_history(destination)

    def test_history_rejects_manifest_tampering(self):
        value = self.build_history()
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.write_history(value, Path(temporary))
            manifest = json.loads((destination / history.MANIFEST_NAME).read_text(encoding="utf-8"))
            manifest["history_id"] = "history:tampered"
            (destination / history.MANIFEST_NAME).write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                history.load_history(destination)

    def test_history_rejects_noncanonical_artifact(self):
        value = self.build_history()
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.write_history(value, Path(temporary))
            raw = (destination / history.ENTRIES_NAME).read_bytes()
            (destination / history.ENTRIES_NAME).write_bytes(b"{ \"version\": " + raw.split(b":", 1)[1])
            with self.assertRaises(ValidationError):
                history.load_history(destination)

    def test_history_overwrite_requires_explicit_flag(self):
        value = self.build_history()
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.write_history(value, Path(temporary))
            with self.assertRaises(ValidationError):
                history.write_history(value, destination)
            history.write_history(value, destination, overwrite=True)
            self.assertEqual(history.load_history(destination).content_address, value.content_address)

    def test_diff_writes_exact_two_files_and_reloads(self):
        baseline = self.build_history()
        candidate = history.build_history((self.ready_gate, self.held_gate), snapshot_ids=("snapshot:0", "snapshot:1"))
        value = history.build_diff(baseline, candidate)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "diff"
            history.write_diff(value, destination)
            self.assertEqual({item.name for item in destination.iterdir()}, set(history.DIFF_FILES))
            self.assertEqual(history.load_diff(destination).to_dict(), value.to_dict())

    def test_diff_rejects_extra_file(self):
        value = history.build_diff(self.build_history(), self.build_history())
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "diff"
            history.write_diff(value, destination)
            (destination / "extra.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                history.load_diff(destination)


class HistoryCliTests(HistoryFixture):
    def test_cli_schema_commands_are_available(self):
        command = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history"
        for suffix in ("schema", "entry-schema", "diff-schema", "diff-item-schema", "query-schema", "diff-query-schema", "capabilities"):
            status, output = self.capture_cli([command + "-" + suffix])
            self.assertEqual(status, 0)
            self.assertTrue(json.loads(output))

    def test_cli_builds_verifies_and_queries_history(self):
        command = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            gate_one = self.write_gate(self.ready_gate, root, "gate-one")
            gate_two = self.write_gate(self.held_gate, root, "gate-two")
            destination = root / "history"
            status, output = self.capture_cli([command, "--gate", str(gate_one), "--gate", str(gate_two), "--snapshot-id", "s0", "--snapshot-id", "s1", "--destination", str(destination), "--format", "summary"])
            self.assertEqual(status, 2)
            self.assertEqual(json.loads(output)["state"], "hold")
            status, output = self.capture_cli([command + "-verify", "--input", str(destination)])
            self.assertEqual(status, 2)
            self.assertEqual(json.loads(output)["state"], "hold")
            status, output = self.capture_cli([command + "-query", "--input", str(destination), "--resource", "entries", "--format", "json"])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output)["returned_count"], 2)

    def test_cli_builds_and_queries_diff(self):
        base_command = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.write_history(history.build_history((self.ready_gate,), snapshot_ids=("s0",)), root, "first")
            second = self.write_history(history.build_history((self.ready_gate, self.held_gate), snapshot_ids=("s0", "s1")), root, "second")
            destination = root / "diff"
            status, output = self.capture_cli([base_command + "-diff", "--baseline", str(first), "--candidate", str(second), "--destination", str(destination), "--format", "summary"])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output)["added_count"], 1)
            status, output = self.capture_cli([base_command + "-diff-query", "--input", str(destination), "--resource", "items", "--action", "added"])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output)["returned_count"], 1)


class HistoryDemoTests(AssuranceFixture):
    def test_demo_reassures_persisted_decision_ledger(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.write_ledger(self.ready_ledger, root, "first-ledger")
            second = self.write_ledger(self.held_ledger, root, "second-ledger")
            result, value, diff = demo.run_demo(
                ledgers=(first, second),
                snapshot_ids=("download-one", "download-two"),
                destination=root / "history",
            )
            self.assertEqual(result.source_kind, "decision-ledger")
            self.assertEqual(result.source_count, 2)
            self.assertEqual(value.entry_count, 2)
            self.assertEqual(value.state, "hold")
            self.assertFalse(value.release_ready)
            self.assertIsNone(diff)
            self.assertNotIn(str(root), demo._render(value, result, diff, "summary"))

    def test_demo_accepts_current_assurance_gate_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.write_assurance(self.build(self.ready_ledger), root, "first-gate")
            result, value, _ = demo.run_demo(
                assurance_gates=(first,),
                destination=root / "history",
            )
            self.assertEqual(result.source_kind, "assurance-gate")
            self.assertEqual(value.entry_count, 1)
            self.assertTrue(value.release_ready)

    def test_demo_builds_a_path_free_history_diff(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = root / "baseline"
            demo.run_demo(
                ledgers=(self.write_ledger(self.ready_ledger, root, "baseline-ledger"),),
                destination=baseline,
            )
            result, candidate, diff = demo.run_demo(
                ledgers=(self.write_ledger(self.ready_ledger, root, "candidate-ledger"), self.write_ledger(self.held_ledger, root, "candidate-held-ledger")),
                snapshot_ids=("download-one", "download-two"),
                destination=root / "candidate",
                baseline=baseline,
                diff_destination=root / "history-diff",
            )
            self.assertIsNotNone(diff)
            self.assertEqual(result.diff_address, diff.content_address)
            self.assertNotIn(str(root), demo._render(candidate, result, diff, "summary"))


class HistoryApiTests(HistoryFixture):
    PREFIX = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review"

    def _server(self):
        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def test_history_api_schema_capabilities_and_build(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.write_assurance(self.ready_gate, root, "first-gate")
            second = self.write_assurance(self.ready_gate, root, "second-gate")
            server, thread = self._server()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                prefix = self.PREFIX + "/decision-ledger/assurance-history"
                for suffix in ("/schema", "/entry-schema", "/diff-schema", "/diff-item-schema", "/query-schema", "/diff-query-schema", "/capabilities"):
                    with urlopen(base + prefix + suffix) as response:
                        self.assertEqual(response.status, 200)
                        self.assertIsInstance(json.loads(response.read()), dict)
                query = urlencode([("gate_directory", str(first)), ("gate_directory", str(second)), ("snapshot_id", "api-one"), ("snapshot_id", "api-two"), ("format", "summary")])
                with urlopen(base + prefix + "?" + query) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read())["entry_count"], 2)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_history_api_verify_query_and_diff(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.write_history(history.build_history((self.ready_gate,), snapshot_ids=("api-one",)), root, "baseline")
            candidate = self.write_history(history.build_history((self.ready_gate, self.held_gate), snapshot_ids=("api-one", "api-two")), root, "candidate")
            diff = root / "diff"
            server, thread = self._server()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                prefix = self.PREFIX + "/decision-ledger/assurance-history"
                with urlopen(base + prefix + "/verify?input=" + str(baseline)) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read())["state"], "promote")
                with urlopen(base + prefix + "/query?input=" + str(candidate) + "&resource=entries") as response:
                    self.assertEqual(json.loads(response.read())["total_count"], 2)
                query = urlencode({"baseline": str(baseline), "candidate": str(candidate), "destination": str(diff), "format": "summary"})
                with urlopen(base + prefix + "/diff?" + query) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read())["added_count"], 1)
                with urlopen(base + prefix + "/diff/verify?input=" + str(diff)) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read())["added_count"], 1)
                with urlopen(base + prefix + "/diff/query?input=" + str(diff) + "&resource=items&action=added") as response:
                    self.assertEqual(json.loads(response.read())["total_count"], 1)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


class HistoryAdditionalCoverageTests(HistoryFixture):
    def test_entry_renderers_and_fixed_csv_columns(self):
        value = self.build_history()
        self.assertIn("Assurance History Entry", history.render_entry_markdown(value.entries[0]))
        self.assertEqual(history.history_csv(value).splitlines()[0].split(",")[0], "ordinal")
        self.assertIn("content_address", history.history_csv(value).splitlines()[0])
        diff = history.build_diff(value, value)
        self.assertEqual(history.diff_csv(diff).splitlines()[0].split(",")[0], "ordinal")

    def test_diff_query_serializers_are_stable(self):
        value = history.build_diff(self.build_history(), self.build_history())
        result = history.query_diff(value, resource="items")
        self.assertEqual(history.diff_query_json(result), history.diff_query_json(result))
        self.assertIn("action", history.diff_query_csv(result).splitlines()[0])

    def test_history_and_diff_reject_wrong_typed_verifier_inputs(self):
        with self.assertRaises(ValidationError):
            history.verify_history({})
        with self.assertRaises(ValidationError):
            history.verify_diff({})
        with self.assertRaises(ValidationError):
            history.address_history({})
        with self.assertRaises(ValidationError):
            history.address_diff({})

    def test_diff_state_enumeration_is_fixed(self):
        self.assertEqual(tuple(item.value for item in history.HistoryDiffDirection), ("unchanged", "improved", "regressed", "mixed"))
        self.assertEqual(tuple(item.value for item in history.HistoryTransition), ("initial", "stable", "improved", "regressed", "changed"))

    def test_public_projection_does_not_publish_input_paths(self):
        value = self.build_history()
        self.assertNotIn("C:\\", history.render_history_markdown(value))
        self.assertNotIn("/Users/", history.render_history_markdown(value))
        self.assertNotIn("C:\\", history.history_json(value))

    def test_history_diff_summary_contains_both_addresses(self):
        value = history.build_diff(self.build_history(), self.build_history())
        summary = value.summary()
        self.assertEqual(summary["baseline_address"], summary["candidate_address"])
        self.assertIn("content_address", summary)

    def test_storage_summary_separates_entry_document(self):
        value = self.build_history()
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.write_history(value, Path(temporary))
            summary = json.loads((destination / history.HISTORY_NAME).read_text(encoding="utf-8"))
            entries = json.loads((destination / history.ENTRIES_NAME).read_text(encoding="utf-8"))
            self.assertNotIn("entries", summary)
            self.assertEqual(len(entries["entries"]), value.entry_count)
            self.assertEqual(summary["entry_count"], entries["entry_count"])

    def test_history_loader_rejects_legacy_download_shape(self):
        old_shape = Path(r"C:\Users\murar\AppData\Local\Temp\glio-noncode-real-downloaded-replay-768c568d74044655acf09834ad693ea0")
        if old_shape.exists():
            with self.assertRaises(ValidationError):
                history.load_history(old_shape)
