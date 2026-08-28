"""Deep contracts for longitudinal decision-assurance histories."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import json
import threading
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from glio_noncode import (
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_decision_ledger_assurance as assurance,
)
from glio_noncode import (
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_decision_ledger_assurance_history as history,
)
from glio_noncode.errors import ValidationError
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.serialization import canonical_bytes, canonical_json
from tests.test_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_decision_ledger_assurance import AssuranceFixture


class HistoryFixture(AssuranceFixture):
    def build_ready_history(self, history_id="history:ready"):
        return history.build_decision_assurance_history(self.build_ready_assurance_gate(), history_id=history_id)

    def build_held_history(self, history_id="history:held"):
        return history.build_decision_assurance_history(self.build_held_assurance_gate(), history_id=history_id)

    def write_history(self, value, destination, **kwargs):
        return history.write_decision_assurance_history(value, destination, **kwargs)


class HistoryCoreTests(HistoryFixture):
    def test_initial_history_observation_is_ready_and_addressed(self):
        value = self.build_ready_history()
        self.assertEqual(value.entry_count, 1)
        self.assertEqual(value.initial_count, 1)
        self.assertEqual(value.current_state, "ready")
        self.assertEqual(value.current_gate_state, "promote")
        self.assertTrue(value.current_accepted)
        self.assertTrue(value.current_release_ready)
        self.assertEqual(value.head_address, value.entries[0].content_address)
        self.assertEqual(value.entries[0].transition, "initial")
        self.assertEqual(history.address_decision_assurance_history(value), value.content_address)
        self.assertEqual(history.address_decision_assurance_history_entry(value.entries[0]), value.entries[0].content_address)

    def test_repeated_same_gate_is_stable_and_replay_passes(self):
        gate = self.build_ready_assurance_gate()
        value = history.build_decision_assurance_history(gate, history_id="history:stable")
        value = history.append_decision_assurance_history(value, gate, snapshot_id="snapshot:stable-2")
        self.assertEqual(value.entry_count, 2)
        self.assertEqual(value.stable_count, 1)
        self.assertEqual(value.current_state, "ready")
        self.assertEqual(value.entries[1].transition, "stable")
        self.assertEqual(value.entries[1].previous_entry_address, value.entries[0].content_address)
        self.assertEqual(value.entries[1].previous_gate_address, value.entries[0].gate_address)
        replay = history.replay_decision_assurance_history(value)
        self.assertEqual(replay.check_count, 7)
        self.assertEqual(replay.passed_count, 7)
        self.assertEqual(replay.failure_count, 0)
        self.assertTrue(replay.accepted)
        self.assertTrue(replay.release_ready)

    def test_held_to_ready_and_ready_to_held_are_directional(self):
        held = self.build_held_assurance_gate()
        ready = self.build_ready_assurance_gate()
        improving = history.build_decision_assurance_history(held, history_id="history:improving")
        improving = history.append_decision_assurance_history(improving, ready, snapshot_id="snapshot:ready")
        self.assertEqual(improving.entries[1].transition, "improved")
        self.assertEqual(improving.improved_count, 1)
        self.assertEqual(improving.current_state, "ready")
        regressing = history.build_decision_assurance_history(ready, history_id="history:regressing")
        regressing = history.append_decision_assurance_history(regressing, held, snapshot_id="snapshot:held")
        self.assertEqual(regressing.entries[1].transition, "regressed")
        self.assertEqual(regressing.regressed_count, 1)
        self.assertEqual(regressing.current_state, "held")

    def test_same_gate_state_can_record_a_semantic_change(self):
        held = self.build_held_assurance_gate()
        closed_held_ledger = self.close_all_open(self.build_held_ledger())
        closed_held = assurance.build_decision_assurance_gate(closed_held_ledger)
        self.assertEqual(held.gate.state, closed_held.gate.state)
        self.assertNotEqual(held.gate.to_dict(), closed_held.gate.to_dict())
        value = history.build_decision_assurance_history(held, history_id="history:changed")
        value = history.append_decision_assurance_history(value, closed_held, snapshot_id="snapshot:closed-held")
        self.assertEqual(value.entries[1].transition, "changed")
        self.assertEqual(value.changed_count, 1)

    def test_blocked_snapshot_is_retained_as_blocked(self):
        value = self.build_held_history("history:blocked-transition")
        value = history.append_decision_assurance_history(value, self.build_blocked_assurance_gate(), snapshot_id="snapshot:blocked")
        self.assertEqual(value.entries[1].transition, "regressed")
        self.assertEqual(value.current_state, "blocked")
        self.assertEqual(value.current_gate_state, "block")
        self.assertFalse(value.current_accepted)
        self.assertFalse(value.current_release_ready)

    def test_expected_head_and_unique_ids_guard_append_only_writes(self):
        value = self.build_ready_history("history:guards")
        with self.assertRaises(ValidationError):
            history.append_decision_assurance_history(value, self.build_ready_assurance_gate(), expected_head_address="history:stale")
        with self.assertRaises(ValidationError):
            history.append_decision_assurance_history(value, self.build_ready_assurance_gate(), snapshot_id=value.entries[0].snapshot_id)
        with self.assertRaises(ValidationError):
            history.append_decision_assurance_history(value, self.build_ready_assurance_gate(), entry_id=value.entries[0].entry_id)
        extended = history.append_decision_assurance_history(value, self.build_ready_assurance_gate(), expected_head_address=value.head_address, snapshot_id="snapshot:second", entry_id="entry:second")
        self.assertEqual(extended.entries[1].entry_id, "entry:second")

    def test_history_is_public_and_does_not_retain_downloaded_paths(self):
        value = self.build_ready_history()
        payload = canonical_json(value.to_dict()).casefold()
        self.assertNotIn(str(self.real_packet()).casefold(), payload)
        self.assertNotIn("source_path", payload)
        for forbidden in ("agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"):
            self.assertNotIn(f'"{forbidden}"', payload)

    def test_history_mapping_round_trip_and_tamper_rejection(self):
        value = self.build_held_history()
        restored = history.decision_assurance_history_from_mapping(value.to_dict())
        self.assertEqual(restored.to_dict(), value.to_dict())
        self.assertEqual(restored.content_address, value.content_address)
        body = value.to_dict()
        body["private"] = True
        with self.assertRaises(ValidationError):
            history.decision_assurance_history_from_mapping(body)
        body = value.to_dict()
        body["entries"][0]["transition"] = "regressed"
        with self.assertRaises(ValidationError):
            history.decision_assurance_history_from_mapping(body)
        entry = value.entries[0].to_dict()
        entry["content_address"] = "entry:tampered"
        with self.assertRaises(ValidationError):
            history.decision_assurance_history_entry_from_mapping(entry)

    def test_entry_and_history_conservation_rejects_invalid_direct_shapes(self):
        value = self.build_ready_history()
        entry = value.entries[0].to_dict()
        entry["snapshot_state"] = "held"
        with self.assertRaises(ValidationError):
            history.DecisionAssuranceHistoryEntry(**entry)
        body = value.to_dict()
        body["entry_count"] = 2
        with self.assertRaises(ValidationError):
            history.decision_assurance_history_from_mapping(body)
        body = value.to_dict()
        body["current_state"] = "held"
        with self.assertRaises(ValidationError):
            history.decision_assurance_history_from_mapping(body)


class HistoryReplayTests(HistoryFixture):
    def test_replay_checks_are_addressed_and_deterministic(self):
        value = history.build_decision_assurance_history(self.build_held_assurance_gate(), history_id="history:replay")
        value = history.append_decision_assurance_history(value, self.build_ready_assurance_gate(), snapshot_id="snapshot:ready")
        first = history.replay_decision_assurance_history(value)
        second = history.replay_decision_assurance_history(value)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.state, "passed")
        self.assertTrue(all(history.address_decision_assurance_history_replay_check(check) == check.content_address for check in first.checks))
        self.assertEqual(history.address_decision_assurance_history_replay(first), first.content_address)
        self.assertEqual(history.verify_decision_assurance_history_replay(first).content_address, first.content_address)

    def test_replay_mapping_rejects_unknown_fields_and_tampered_checks(self):
        replay = history.replay_decision_assurance_history(self.build_ready_history())
        body = replay.to_dict()
        body["private"] = True
        with self.assertRaises(ValidationError):
            history.decision_assurance_history_replay_from_mapping(body)
        body = replay.to_dict()
        body["checks"][0]["detail"] = "tampered"
        with self.assertRaises(ValidationError):
            history.decision_assurance_history_replay_from_mapping(body)
        check = replay.checks[0].to_dict()
        check["content_address"] = "check:tampered"
        with self.assertRaises(ValidationError):
            history.decision_assurance_history_replay_check_from_mapping(check)

    def test_replay_of_held_history_is_structurally_accepted_but_not_release_ready(self):
        replay = history.replay_decision_assurance_history(self.build_held_history("history:held-replay"))
        self.assertTrue(replay.accepted)
        self.assertFalse(replay.release_ready)
        self.assertEqual(replay.current_state, "held")
        self.assertEqual(replay.current_gate_state, "hold")

    def test_replay_exports_are_canonical_and_marked(self):
        replay = history.replay_decision_assurance_history(self.build_ready_history("history:exports"))
        self.assertEqual(history.decision_assurance_history_replay_json(replay), canonical_json(replay.to_dict()))
        rows = list(csv.DictReader(StringIO(history.decision_assurance_history_replay_csv(replay))))
        self.assertEqual(len(rows), 7)
        self.assertIn("# Federation Review Decision Assurance History Replay", history.render_decision_assurance_history_replay_markdown(replay))
        schema = history.decision_assurance_history_replay_schema()
        self.assertFalse(schema["additionalProperties"])
        self.assertIn(history.VERSION, json.dumps(schema))


class HistoryQueryExportTests(HistoryFixture):
    def build_long_history(self):
        value = history.build_decision_assurance_history(self.build_held_assurance_gate(), history_id="history:query")
        value = history.append_decision_assurance_history(value, self.build_ready_assurance_gate(), snapshot_id="snapshot:ready")
        value = history.append_decision_assurance_history(value, self.build_ready_assurance_gate(), snapshot_id="snapshot:stable")
        value = history.append_decision_assurance_history(value, self.build_blocked_assurance_gate(), snapshot_id="snapshot:blocked")
        return value

    def test_summary_transition_and_state_queries_are_bounded(self):
        value = self.build_long_history()
        summary = history.query_decision_assurance_history(value)
        self.assertEqual(summary.total_count, 1)
        self.assertEqual(summary.items[0]["current_state"], "blocked")
        improved = history.query_decision_assurance_history(value, resource="improved", limit=32)
        self.assertEqual(improved.total_count, 1)
        self.assertEqual(improved.items[0]["transition"], "improved")
        blocked = history.query_decision_assurance_history(value, resource="blocked", limit=32)
        self.assertEqual(blocked.total_count, 1)
        self.assertEqual(blocked.items[0]["snapshot_state"], "blocked")
        accepted = history.query_decision_assurance_history(value, resource="accepted", limit=32)
        self.assertEqual(accepted.total_count, 3)
        release_ready = history.query_decision_assurance_history(value, resource="release-ready", limit=32)
        self.assertEqual(release_ready.total_count, 2)

    def test_query_filters_text_gate_state_and_pagination(self):
        value = self.build_long_history()
        result = history.query_decision_assurance_history(value, resource="entries", transition="stable", gate_state="promote", text="stable", offset=0, limit=1)
        self.assertEqual(result.total_count, 1)
        self.assertEqual(result.returned_count, 1)
        self.assertEqual(result.items[0]["snapshot_id"], "snapshot:stable")
        self.assertEqual(result.query.to_dict()["text"], "stable")
        with self.assertRaises(ValidationError):
            history.AssuranceHistoryQuery(resource="unknown")
        with self.assertRaises(ValidationError):
            history.AssuranceHistoryQuery(resource="entries", offset=4090, limit=10)
        with self.assertRaises(ValidationError):
            history.query_decision_assurance_history(value, history.AssuranceHistoryQuery(resource="entries"), limit=1)

    def test_json_csv_markdown_schema_and_capability_exports(self):
        value = self.build_long_history()
        self.assertEqual(history.decision_assurance_history_json(value), canonical_json(value.to_dict()))
        rows = list(csv.DictReader(StringIO(history.decision_assurance_history_csv(value))))
        self.assertEqual(len(rows), value.entry_count)
        result = history.query_decision_assurance_history(value, resource="transitions", limit=32)
        self.assertEqual(history.decision_assurance_history_query_json(result), canonical_json(result.to_dict()))
        self.assertEqual(len(list(csv.DictReader(StringIO(history.decision_assurance_history_query_csv(result))))), result.returned_count)
        self.assertIn("# Federation Review Decision Assurance History", history.render_decision_assurance_history_markdown(value))
        self.assertIn("# Federation Review Decision Assurance History Query", history.render_decision_assurance_history_query_markdown(result))
        self.assertFalse(history.decision_assurance_history_schema()["additionalProperties"])
        self.assertFalse(history.decision_assurance_history_entry_schema()["additionalProperties"])
        self.assertIn("release-ready", json.dumps(history.decision_assurance_history_query_schema()))
        capabilities = history.capabilities()
        self.assertEqual(capabilities["history"]["maximum_entries"], history.MAX_ENTRIES)
        self.assertEqual(capabilities["replay"]["checks"], 7)

    def test_empty_history_query_is_explicit(self):
        empty = history._empty_history("history:empty")
        result = history.query_decision_assurance_history(empty, resource="entries", limit=32)
        self.assertEqual(result.total_count, 0)
        self.assertEqual(result.returned_count, 0)
        self.assertEqual(history.decision_assurance_history_query_csv(result), "")
        self.assertIn("No records.", history.render_decision_assurance_history_query_markdown(result))
        replay = history.replay_decision_assurance_history(empty)
        self.assertTrue(replay.accepted)
        self.assertFalse(replay.release_ready)


class HistoryPersistenceTests(HistoryFixture):
    def test_exact_three_file_persistence_round_trip_and_manifest_receipts(self):
        value = history.build_decision_assurance_history(self.build_held_assurance_gate(), history_id="history:persist")
        value = history.append_decision_assurance_history(value, self.build_ready_assurance_gate(), snapshot_id="snapshot:ready")
        with tempfile.TemporaryDirectory() as root_text:
            destination = self.write_history(value, Path(root_text) / "history")
            self.assertEqual({item.name for item in destination.iterdir()}, {"manifest.json", "history.json", "entries.json"})
            loaded = history.load_decision_assurance_history(destination)
            self.assertEqual(loaded.to_dict(), value.to_dict())
            manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["files"], ["manifest.json", "history.json", "entries.json"])
            self.assertEqual(manifest["artifact_count"], 2)
            self.assertEqual(manifest["entry_count"], value.entry_count)
            self.assertEqual(manifest["history_address"], value.content_address)
            self.assertEqual(manifest["head_address"], value.head_address)
            self.assertEqual(manifest["manifest_address"], history._manifest_address({**manifest, "manifest_address": None}))

    def test_persistence_bytes_are_repeatable(self):
        value = self.build_ready_history("history:bytes")
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            first = self.write_history(value, root / "first")
            second = self.write_history(value, root / "second")
            self.assertEqual({path.name: path.read_bytes() for path in first.iterdir()}, {path.name: path.read_bytes() for path in second.iterdir()})

    def test_persistence_rejects_missing_extra_noncanonical_and_tampered_documents(self):
        value = self.build_ready_history("history:tamper")
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            missing = self.write_history(value, root / "missing")
            (missing / "entries.json").unlink()
            with self.assertRaises(ValidationError):
                history.load_decision_assurance_history(missing)
            extra = self.write_history(value, root / "extra")
            (extra / "extra.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                history.load_decision_assurance_history(extra)
            noncanonical = self.write_history(value, root / "noncanonical")
            manifest = json.loads((noncanonical / "manifest.json").read_text(encoding="utf-8"))
            (noncanonical / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            with self.assertRaises(ValidationError):
                history.load_decision_assurance_history(noncanonical)
            tampered = self.write_history(value, root / "tampered")
            body = json.loads((tampered / "history.json").read_text(encoding="utf-8"))
            body["current_state"] = "blocked"
            (tampered / "history.json").write_bytes(canonical_bytes(body))
            with self.assertRaises(ValidationError):
                history.load_decision_assurance_history(tampered)

    def test_persistence_rejects_entry_bytes_manifest_linkage_and_symlinks(self):
        value = self.build_ready_history("history:tamper-links")
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            entry_tamper = self.write_history(value, root / "entry-tamper")
            body = json.loads((entry_tamper / "entries.json").read_text(encoding="utf-8"))
            body["entries"][0]["detail"] = "not-present"
            (entry_tamper / "entries.json").write_bytes(canonical_bytes(body))
            with self.assertRaises(ValidationError):
                history.load_decision_assurance_history(entry_tamper)
            manifest_tamper = self.write_history(value, root / "manifest-tamper")
            manifest = json.loads((manifest_tamper / "manifest.json").read_text(encoding="utf-8"))
            manifest["manifest_address"] = "manifest:tampered"
            (manifest_tamper / "manifest.json").write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                history.load_decision_assurance_history(manifest_tamper)
            symlink = self.write_history(value, root / "symlink")
            source = root / "entries-source.json"
            source.write_bytes((symlink / "entries.json").read_bytes())
            (symlink / "entries.json").unlink()
            try:
                (symlink / "entries.json").symlink_to(source)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable in this environment")
            with self.assertRaises(ValidationError):
                history.load_decision_assurance_history(symlink)
            alias = root / "alias"
            try:
                alias.symlink_to(symlink, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks unavailable in this environment")
            with self.assertRaises(ValidationError):
                history.load_decision_assurance_history(alias)

    def test_overwrite_guard_replacement_and_non_directory_input(self):
        value = self.build_ready_history("history:overwrite")
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            destination = self.write_history(value, root / "history")
            with self.assertRaises(ValidationError):
                self.write_history(value, destination)
            replacement = self.build_held_history("history:replacement")
            self.write_history(replacement, destination, overwrite=True)
            self.assertEqual(history.load_decision_assurance_history(destination).to_dict(), replacement.to_dict())
            source = root / "file"
            source.write_text("not a directory", encoding="utf-8")
            with self.assertRaises(ValidationError):
                history.load_decision_assurance_history(source)


class HistoryRealDataTests(HistoryFixture):
    def test_real_downloaded_assurance_gate_history_round_trip(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            source_gate = self.build_real_gate(root / "real")
            queue = self.build_ready_queue("queue:history-real")
            ledger = self.build_ready_ledger("ledger:history-real")
            value = history.build_decision_assurance_history(assurance.build_decision_assurance_gate(ledger), history_id="history:real-download")
            value = history.append_decision_assurance_history(value, assurance.build_decision_assurance_gate(ledger), snapshot_id="snapshot:real-repeat")
            self.assertTrue(source_gate.release_ready)
            self.assertEqual(value.stable_count, 1)
            destination = self.write_history(value, root / "history")
            loaded = history.load_decision_assurance_history(destination)
            self.assertEqual(loaded.entry_count, 2)
            self.assertTrue(loaded.current_release_ready)
            payload = canonical_json(loaded.to_dict()).casefold()
            self.assertNotIn(str(self.real_packet()).casefold(), payload)
            self.assertNotIn(str(queue.content_address).casefold(), payload)
            self.assertNotIn("source_path", payload)


class HistoryCliTests(HistoryFixture):
    base = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decisions-assurance-history"

    @staticmethod
    def run_cli_json(arguments):
        output = StringIO()
        with redirect_stdout(output):
            status = main(arguments)
        text = output.getvalue()
        return status, json.loads(text) if text.strip() else None, text

    def test_cli_build_query_replay_verify_and_contract_commands(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            baseline = self.write_assurance_gate(self.build_held_assurance_gate(), root / "baseline")
            candidate = self.write_assurance_gate(self.build_ready_assurance_gate(), root / "candidate")
            destination = root / "history"
            status, payload, _ = self.run_cli_json([self.base, "--gate", str(baseline), "--gate", str(candidate), "--history-id", "history:cli", "--destination", str(destination), "--format", "summary"])
            self.assertEqual(status, 0)
            self.assertEqual(payload["entry_count"], 2)
            self.assertEqual(payload["current_state"], "ready")
            self.assertEqual(payload["improved_count"], 1)
            status, payload, _ = self.run_cli_json([self.base + "-query", "--input", str(destination), "--resource", "improved", "--limit", "32"])
            self.assertEqual(status, 0)
            self.assertEqual(payload["total_count"], 1)
            status, payload, _ = self.run_cli_json([self.base + "-replay", "--input", str(destination), "--format", "summary"])
            self.assertEqual(status, 0)
            self.assertEqual(payload["passed_count"], 7)
            status, payload, _ = self.run_cli_json([self.base + "-verify", "--input", str(destination)])
            self.assertEqual(status, 0)
            self.assertEqual(payload["head_address"], history.load_decision_assurance_history(destination).head_address)
            status, payload, _ = self.run_cli_json([self.base + "-capabilities"])
            self.assertEqual(status, 0)
            self.assertIn("history", payload)
            for suffix in ("-schema", "-entry-schema", "-replay-schema", "-query-schema", "-replay-capabilities", "-query-capabilities"):
                output_path = root / (suffix[1:] + ".json")
                self.assertEqual(main([self.base + suffix, "--output", str(output_path)]), 0)
                self.assertIsInstance(json.loads(output_path.read_text(encoding="utf-8")), dict)
            output = StringIO()
            with redirect_stdout(output):
                status = main([self.base + "-query", "--input", str(destination), "--resource", "entries", "--limit", "2", "--format", "csv"])
            self.assertEqual(status, 0)
            self.assertIn("snapshot_id", output.getvalue())


class HistoryApiTests(HistoryFixture):
    base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decisions/assurance-history"

    @staticmethod
    def start_server(root: Path):
        server = create_server("127.0.0.1", 0, root / "api-data")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    @staticmethod
    def http_json(server, path: str, params=None):
        query = "?" + urlencode(params or {}, doseq=True) if params else ""
        request = Request(f"http://127.0.0.1:{server.server_port}{path}{query}", headers={"Accept": "application/json"})
        with urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    @staticmethod
    def http_text(server, path: str, params=None):
        query = "?" + urlencode(params or {}, doseq=True) if params else ""
        request = Request(f"http://127.0.0.1:{server.server_port}{path}{query}")
        with urlopen(request, timeout=10) as response:
            return response.status, response.headers.get_content_type(), response.read().decode("utf-8")

    def test_api_history_query_replay_and_contract_routes(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            value = history.build_decision_assurance_history(self.build_held_assurance_gate(), history_id="history:api")
            value = history.append_decision_assurance_history(value, self.build_ready_assurance_gate(), snapshot_id="snapshot:api-ready")
            destination = self.write_history(value, root / "history")
            server, thread = self.start_server(root)
            try:
                status, payload = self.http_json(server, self.base, {"input": str(destination), "format": "summary"})
                self.assertEqual(status, 200)
                self.assertEqual(payload["current_state"], "ready")
                status, payload = self.http_json(server, self.base + "/query", {"input": str(destination), "resource": "improved", "limit": "32"})
                self.assertEqual(status, 200)
                self.assertEqual(payload["total_count"], 1)
                status, payload = self.http_json(server, self.base + "/replay", {"input": str(destination), "format": "summary"})
                self.assertEqual(status, 200)
                self.assertTrue(payload["accepted"])
                status, payload = self.http_json(server, self.base + "/verify", {"input": str(destination)})
                self.assertEqual(status, 200)
                self.assertEqual(payload["content_address"], value.content_address)
                for suffix in ("/schema", "/entry-schema", "/replay/schema", "/query/schema", "/capabilities"):
                    status, payload = self.http_json(server, self.base + suffix)
                    self.assertEqual(status, 200, suffix)
                    self.assertIsInstance(payload, dict)
                status, content_type, body = self.http_text(server, self.base + "/query", {"input": str(destination), "resource": "entries", "limit": "2", "format": "markdown"})
                self.assertEqual(status, 200)
                self.assertIn("# Federation Review Decision Assurance History Query", body)
                self.assertTrue(content_type)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
