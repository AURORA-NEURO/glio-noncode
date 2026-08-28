"""Deep contract coverage for federation review decision ledgers."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import json
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from glio_noncode import (
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review as review_model,
)
from glio_noncode import (
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_decision_ledger as ledger,
)
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_bytes, canonical_json
from tests.test_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review import (
    ReviewFixture,
)


class DecisionFixture(ReviewFixture):
    def build_ready_ledger(self, ledger_id: str = "ledger:ready"):
        return ledger.build_decision_ledger(self.build_ready_queue(), ledger_id=ledger_id)

    def build_held_ledger(self, ledger_id: str = "ledger:held"):
        return ledger.build_decision_ledger(self.build_held_queue(), ledger_id=ledger_id)

    def build_blocked_ledger(self, ledger_id: str = "ledger:blocked"):
        return ledger.build_decision_ledger(self.build_blocked_queue(), ledger_id=ledger_id)

    def write_ledger(self, value, destination, **kwargs):
        return ledger.write_decision_ledger(value, destination, **kwargs)

    @staticmethod
    def first_item(value, state=None):
        return next(item for item in value.items if state is None or item.state == state)

    @staticmethod
    def close_all_open(value, action="waive"):
        current = value
        for item in value.items:
            if item.state == "review" and action == "waive":
                current = ledger.append_decision_by_address(current, item.content_address, action, "optional warning adjudicated")
            elif item.state == "blocked" and action == "remediate":
                current = ledger.append_decision_by_address(current, item.content_address, action, "blocking condition remediated", evidence_address="evidence:remediation")
        return current


class DecisionCoreTests(DecisionFixture):
    def test_ready_queue_starts_closed_and_release_ready(self):
        value = self.build_ready_ledger()
        self.assertEqual(value.state, "closed")
        self.assertTrue(value.accepted)
        self.assertTrue(value.release_ready)
        self.assertEqual(value.item_count, 36)
        self.assertEqual(value.entry_count, 0)
        self.assertEqual(value.covered_count, 0)
        self.assertEqual(value.open_count, 0)
        self.assertEqual(value.closed_count, 36)
        self.assertEqual(value.unreviewed_count, 0)

    def test_held_queue_starts_open_but_source_gate_is_authoritative(self):
        value = self.build_held_ledger()
        self.assertEqual(value.state, "open")
        self.assertTrue(value.accepted)
        self.assertFalse(value.release_ready)
        self.assertEqual(value.open_count, 5)
        self.assertEqual(value.unreviewed_count, 5)
        self.assertEqual(value.escalated_count, 0)

    def test_blocked_queue_starts_blocked_and_not_accepted(self):
        value = self.build_blocked_ledger()
        self.assertEqual(value.state, "blocked")
        self.assertFalse(value.accepted)
        self.assertFalse(value.release_ready)
        self.assertEqual(value.blocked_count, 3)
        self.assertEqual(value.open_count, 8)

    def test_ledger_addresses_are_deterministic_for_same_snapshot(self):
        first = self.build_ready_ledger()
        second = self.build_ready_ledger()
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(ledger.address_decision_ledger(first), first.content_address)
        self.assertIsNone(first.head_address)

    def test_ledger_id_changes_ledger_address_without_changing_source_queue(self):
        first = self.build_ready_ledger("ledger:first")
        second = self.build_ready_ledger("ledger:second")
        self.assertEqual(first.queue_address, second.queue_address)
        self.assertNotEqual(first.content_address, second.content_address)
        self.assertNotEqual(first.ledger_id, second.ledger_id)

    def test_ledger_is_path_free_and_has_no_runtime_attribution(self):
        value = self.build_ready_ledger()
        payload = canonical_json(value.to_dict()).casefold()
        self.assertNotIn("source_path", payload)
        self.assertNotIn(str(self.real_packet()).casefold(), payload)
        for forbidden in ("agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"):
            self.assertNotIn(f'"{forbidden}"', payload)

    def test_clear_item_can_be_acknowledged(self):
        value = self.build_ready_ledger()
        item = self.first_item(value)
        updated = ledger.append_decision_by_address(value, item.content_address, "acknowledge", "clear item confirmed")
        self.assertEqual(updated.entry_count, 1)
        self.assertEqual(updated.covered_count, 1)
        self.assertEqual(updated.open_count, 0)
        self.assertEqual(updated.state, "closed")
        self.assertTrue(updated.release_ready)
        self.assertEqual(updated.entries[0].result_state, "closed")
        self.assertIsNone(updated.entries[0].evidence_address)

    def test_warning_can_be_waived_but_does_not_promote_source_gate(self):
        value = self.build_held_ledger()
        item = self.first_item(value, "review")
        updated = ledger.append_decision_by_address(value, item.content_address, "waive", "optional warning accepted with rationale")
        self.assertEqual(updated.entry_count, 1)
        self.assertEqual(updated.open_count, 4)
        self.assertEqual(updated.closed_count, 32)
        self.assertEqual(updated.unreviewed_count, 4)
        self.assertFalse(updated.release_ready)
        self.assertEqual(updated.entries[0].result_state, "closed")

    def test_blocker_requires_evidence_for_remediation(self):
        value = self.build_blocked_ledger()
        item = self.first_item(value, "blocked")
        with self.assertRaises(ValidationError):
            ledger.append_decision_by_address(value, item.content_address, "remediate", "attempted without evidence")
        updated = ledger.append_decision_by_address(value, item.content_address, "remediate", "blocking condition remediated", evidence_address="evidence:one")
        self.assertEqual(updated.open_count, value.open_count - 1)
        self.assertEqual(updated.blocked_count, value.blocked_count - 1)
        self.assertFalse(updated.accepted)
        self.assertFalse(updated.release_ready)

    def test_escalation_preserves_open_state_and_tracks_escalated_count(self):
        value = self.build_held_ledger()
        item = self.first_item(value, "review")
        updated = ledger.append_decision_by_address(value, item.content_address, "escalate", "requires additional review")
        self.assertEqual(updated.open_count, value.open_count)
        self.assertEqual(updated.escalated_count, 1)
        self.assertEqual(updated.state, "open")
        self.assertFalse(updated.release_ready)

    def test_reopen_requires_prior_closed_decision_and_head_is_guarded(self):
        value = self.build_held_ledger()
        item = self.first_item(value, "review")
        with self.assertRaises(ValidationError):
            ledger.append_decision_by_address(value, item.content_address, "reopen", "not previously decided")
        closed = ledger.append_decision_by_address(value, item.content_address, "waive", "warning reviewed")
        with self.assertRaises(ValidationError):
            ledger.append_decision_by_address(closed, item.content_address, "reopen", "stale writer", expected_head_address="decision:stale")
        reopened = ledger.append_decision_by_address(closed, item.content_address, "reopen", "new evidence requires another review", expected_head_address=closed.head_address)
        self.assertEqual(reopened.entry_count, 2)
        self.assertEqual(reopened.open_count, value.open_count)
        self.assertEqual(reopened.unreviewed_count, value.unreviewed_count - 1)
        self.assertEqual(reopened.entries[1].supersedes_address, closed.head_address)
        self.assertEqual(reopened.head_address, reopened.entries[-1].content_address)

    def test_decision_ids_are_unique_and_action_rules_are_fail_closed(self):
        value = self.build_held_ledger()
        item = self.first_item(value, "review")
        closed = ledger.append_decision_by_address(value, item.content_address, "waive", "warning reviewed", decision_id="decision:one")
        with self.assertRaises(ValidationError):
            ledger.append_decision_by_address(closed, item.content_address, "reopen", "same decision ID", decision_id="decision:one")
        with self.assertRaises(ValidationError):
            ledger.append_decision_by_address(value, item.content_address, "acknowledge", "warning cannot be acknowledged")
        blocked = self.build_blocked_ledger()
        blocker = self.first_item(blocked, "blocked")
        with self.assertRaises(ValidationError):
            ledger.append_decision_by_address(blocked, blocker.content_address, "waive", "critical blocker cannot be waived")

    def test_all_warning_items_can_be_closed_without_claiming_release(self):
        value = self.close_all_open(self.build_held_ledger())
        self.assertEqual(value.open_count, 0)
        self.assertEqual(value.closed_count, 36)
        self.assertEqual(value.entry_count, 5)
        self.assertEqual(value.covered_count, 5)
        self.assertEqual(value.state, "closed")
        self.assertTrue(value.accepted)
        self.assertFalse(value.release_ready)

    def test_mapping_round_trip_replays_the_same_ledger(self):
        value = self.build_held_ledger()
        item = self.first_item(value, "review")
        value = ledger.append_decision_by_address(value, item.content_address, "waive", "warning reviewed")
        restored = ledger.decision_ledger_from_mapping(value.to_dict())
        self.assertEqual(restored.to_dict(), value.to_dict())
        self.assertEqual(restored.content_address, value.content_address)
        self.assertEqual(ledger.decision_entry_from_mapping(value.entries[0].to_dict()).to_dict(), value.entries[0].to_dict())

    def test_mapping_rejects_unknown_or_tampered_fields(self):
        body = self.build_ready_ledger().to_dict()
        body["private"] = True
        with self.assertRaises(ValidationError):
            ledger.decision_ledger_from_mapping(body)
        body = self.build_ready_ledger().to_dict()
        body["content_address"] = "ledger:tampered"
        with self.assertRaises(ValidationError):
            ledger.decision_ledger_from_mapping(body)

    def test_direct_entry_contract_rejects_invalid_action_shapes(self):
        value = self.build_held_ledger()
        item = self.first_item(value, "review")
        body = {
            "ordinal": 0,
            "decision_id": "decision:invalid",
            "previous_head_address": None,
            "item_address": item.content_address,
            "record_type": item.record_type,
            "record_id": item.record_id,
            "plane": item.plane,
            "kind": item.kind,
            "source_state": item.state,
            "source_priority": item.priority,
            "action": "remediate",
            "result_state": "closed",
            "rationale": "missing evidence",
            "evidence_address": None,
            "supersedes_address": None,
            "content_address": "entry:invalid",
        }
        with self.assertRaises(ValidationError):
            ledger.decision_entry_from_mapping(body)


class DecisionQueryAndExportTests(DecisionFixture):
    def test_summary_and_resource_queries_are_bounded(self):
        value = self.build_held_ledger()
        summary = ledger.query_decision_ledger(value)
        self.assertEqual(summary.total_count, 1)
        self.assertEqual(summary.items[0]["state"], "open")
        open_items = ledger.query_decision_ledger(value, resource="open", limit=256)
        self.assertEqual(open_items.total_count, 5)
        warnings = ledger.query_decision_ledger(value, resource="items", record_type="finding", limit=256)
        self.assertEqual(warnings.total_count, 21)
        self.assertEqual(ledger.query_decision_ledger(value, resource="blockers", limit=256).total_count, 0)

    def test_action_and_text_filters_select_latest_decisions(self):
        value = self.build_held_ledger()
        item = self.first_item(value, "review")
        value = ledger.append_decision_by_address(value, item.content_address, "escalate", "requires specialist review")
        escalated = ledger.query_decision_ledger(value, resource="escalated", action="escalate", text="SPECIALIST", limit=10)
        self.assertEqual(escalated.total_count, 1)
        self.assertEqual(escalated.items[0]["item_address"], item.content_address)
        self.assertTrue(escalated.items[0]["covered"])

    def test_query_pagination_and_invalid_windows_are_fail_closed(self):
        value = self.build_held_ledger()
        page = ledger.query_decision_ledger(value, resource="items", offset=2, limit=3)
        self.assertEqual(page.total_count, 36)
        self.assertEqual(page.returned_count, 3)
        self.assertEqual(page.items[0]["ordinal"], 2)
        with self.assertRaises(ValidationError):
            ledger.DecisionQuery(resource="items", offset=4090, limit=10)
        with self.assertRaises(ValidationError):
            ledger.query_decision_ledger(value, ledger.DecisionQuery(resource="items"), limit=2)

    def test_json_exports_are_canonical(self):
        value = self.build_held_ledger()
        payload = ledger.decision_ledger_json(value)
        self.assertEqual(payload, canonical_json(value.to_dict()))
        self.assertEqual(canonical_bytes(json.loads(payload)), payload.encode())
        result = ledger.query_decision_ledger(value, resource="open", limit=256)
        query_payload = ledger.decision_query_json(result)
        self.assertEqual(query_payload, canonical_json(result.to_dict()))

    def test_csv_exports_have_stable_headers(self):
        value = self.build_held_ledger()
        item = self.first_item(value, "review")
        value = ledger.append_decision_by_address(value, item.content_address, "escalate", "requires review")
        rows = list(csv.DictReader(StringIO(ledger.decision_ledger_csv(value))))
        self.assertEqual(len(rows), 1)
        self.assertEqual(list(rows[0]), ["ordinal", "decision_id", "item_address", "record_type", "record_id", "plane", "kind", "source_state", "source_priority", "action", "result_state", "rationale", "evidence_address", "supersedes_address", "previous_head_address", "content_address"])
        query_rows = list(csv.DictReader(StringIO(ledger.decision_query_csv(ledger.query_decision_ledger(value, resource="open", limit=256)))))
        self.assertEqual(len(query_rows), 5)

    def test_markdown_exports_are_explicit_and_empty_queries_are_safe(self):
        value = self.build_ready_ledger()
        self.assertIn("# Observatory Packet Registry Federation Review Decision Ledger", ledger.render_decision_ledger_markdown(value))
        result = ledger.query_decision_ledger(value, resource="open", limit=256)
        self.assertIn("No records.", ledger.render_decision_query_markdown(result))

    def test_schema_and_capabilities_declare_decision_rules(self):
        schema = ledger.decision_ledger_schema()
        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema["additionalProperties"])
        self.assertIn(ledger.VERSION, json.dumps(schema))
        query_schema = ledger.decision_query_schema()
        self.assertIn("escalated", json.dumps(query_schema))
        capabilities = ledger.decision_capabilities()
        self.assertEqual(capabilities["version"], ledger.VERSION)
        self.assertFalse(capabilities["rules"]["critical_waiver"])
        self.assertTrue(capabilities["persistence"]["head_guard"])
        self.assertIn("resolved_transition", json.dumps(capabilities))


class DecisionPersistenceTests(DecisionFixture):
    def test_persistence_has_exact_three_files(self):
        with tempfile.TemporaryDirectory() as root_text:
            destination = self.write_ledger(self.build_ready_ledger(), Path(root_text) / "ledger")
            self.assertEqual({item.name for item in destination.iterdir()}, {"manifest.json", "ledger.json", "entries.json"})

    def test_persistence_round_trip_preserves_entries_and_address(self):
        value = self.build_held_ledger()
        item = self.first_item(value, "review")
        value = ledger.append_decision_by_address(value, item.content_address, "waive", "warning reviewed")
        with tempfile.TemporaryDirectory() as root_text:
            loaded = ledger.load_decision_ledger(self.write_ledger(value, Path(root_text) / "ledger"))
            self.assertEqual(loaded.to_dict(), value.to_dict())
            self.assertEqual(loaded.head_address, value.head_address)
            self.assertEqual(loaded.content_address, value.content_address)

    def test_persistence_bytes_are_repeatable(self):
        value = self.build_held_ledger()
        with tempfile.TemporaryDirectory() as root_text:
            first = self.write_ledger(value, Path(root_text) / "first")
            second = self.write_ledger(value, Path(root_text) / "second")
            self.assertEqual({path.name: path.read_bytes() for path in first.iterdir()}, {path.name: path.read_bytes() for path in second.iterdir()})

    def test_manifest_contains_two_artifact_receipts_and_addresses(self):
        value = self.build_held_ledger()
        with tempfile.TemporaryDirectory() as root_text:
            destination = self.write_ledger(value, Path(root_text) / "ledger")
            manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["artifact_count"], 2)
            self.assertEqual(manifest["files"], ["manifest.json", "ledger.json", "entries.json"])
            self.assertEqual({item["name"] for item in manifest["artifacts"]}, {"ledger.json", "entries.json"})
            self.assertEqual(manifest["ledger_address"], value.content_address)
            self.assertEqual(manifest["entry_address"], ledger.address_decision_entries(value))
            self.assertEqual(manifest["manifest_address"], ledger._manifest_address({**manifest, "manifest_address": None}))

    def test_persistence_rejects_missing_or_extra_files(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            destination = self.write_ledger(self.build_ready_ledger(), root / "ledger")
            (destination / "entries.json").unlink()
            with self.assertRaises(ValidationError):
                ledger.load_decision_ledger(destination)
            destination = self.write_ledger(self.build_ready_ledger(), root / "ledger-two")
            (destination / "extra.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                ledger.load_decision_ledger(destination)

    def test_persistence_rejects_noncanonical_and_tampered_documents(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            destination = self.write_ledger(self.build_ready_ledger(), root / "ledger")
            manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
            (destination / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            with self.assertRaises(ValidationError):
                ledger.load_decision_ledger(destination)
            destination = self.write_ledger(self.build_ready_ledger(), root / "ledger-two")
            manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
            manifest["manifest_address"] = "manifest:tampered"
            (destination / "manifest.json").write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                ledger.load_decision_ledger(destination)
            destination = self.write_ledger(self.build_ready_ledger(), root / "ledger-three")
            (destination / "ledger.json").write_bytes((destination / "ledger.json").read_bytes() + b" ")
            with self.assertRaises(ValidationError):
                ledger.load_decision_ledger(destination)

    def test_persistence_rejects_tampered_entry_payload_or_linkage(self):
        value = self.build_held_ledger()
        item = self.first_item(value, "review")
        value = ledger.append_decision_by_address(value, item.content_address, "escalate", "requires review")
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            destination = self.write_ledger(value, root / "ledger")
            entries = json.loads((destination / "entries.json").read_text(encoding="utf-8"))
            entries["entries"][0]["rationale"] = "tampered"
            (destination / "entries.json").write_bytes(canonical_bytes(entries))
            with self.assertRaises(ValidationError):
                ledger.load_decision_ledger(destination)
            destination = self.write_ledger(value, root / "ledger-two")
            entries = json.loads((destination / "entries.json").read_text(encoding="utf-8"))
            entries["ledger_address"] = "ledger:other"
            (destination / "entries.json").write_bytes(canonical_bytes(entries))
            with self.assertRaises(ValidationError):
                ledger.load_decision_ledger(destination)

    def test_persistence_rejects_symlinked_files_and_directories(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            destination = self.write_ledger(self.build_ready_ledger(), root / "ledger")
            source = root / "entries-source.json"
            source.write_bytes((destination / "entries.json").read_bytes())
            (destination / "entries.json").unlink()
            try:
                (destination / "entries.json").symlink_to(source)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable in this environment")
            with self.assertRaises(ValidationError):
                ledger.load_decision_ledger(destination)
            alias = root / "alias"
            try:
                alias.symlink_to(destination, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks unavailable in this environment")
            with self.assertRaises(ValidationError):
                ledger.load_decision_ledger(alias)

    def test_persistence_overwrite_guard_and_replacement(self):
        with tempfile.TemporaryDirectory() as root_text:
            destination = self.write_ledger(self.build_ready_ledger(), Path(root_text) / "ledger")
            with self.assertRaises(ValidationError):
                self.write_ledger(self.build_held_ledger(), destination)
            replacement = self.build_held_ledger("ledger:replacement")
            self.write_ledger(replacement, destination, overwrite=True)
            self.assertEqual(ledger.load_decision_ledger(destination).to_dict(), replacement.to_dict())

    def test_load_rejects_non_directory_input(self):
        with tempfile.TemporaryDirectory() as root_text:
            source = Path(root_text) / "file"
            source.write_text("not a directory", encoding="utf-8")
            with self.assertRaises(ValidationError):
                ledger.load_decision_ledger(source)


class DecisionDiffTests(DecisionFixture):
    def test_same_decision_snapshot_is_unchanged(self):
        value = self.build_ready_ledger()
        diff = ledger.build_decision_diff(value, value, diff_id="diff:same")
        self.assertEqual(diff.state, "unchanged")
        self.assertEqual(diff.item_count, 36)
        self.assertEqual(diff.unchanged_count, 36)
        self.assertEqual(diff.changed_count, 0)
        self.assertEqual(diff.resolved_count, 0)
        self.assertTrue(all(item.action == "unchanged" for item in diff.items))

    def test_warning_waiver_is_a_semantic_changed_item(self):
        baseline = self.build_held_ledger()
        item = self.first_item(baseline, "review")
        candidate = ledger.append_decision_by_address(baseline, item.content_address, "waive", "warning reviewed")
        diff = ledger.build_decision_diff(baseline, candidate, diff_id="diff:waiver")
        self.assertEqual(diff.state, "changed")
        self.assertEqual(diff.changed_count, 1)
        self.assertEqual(diff.resolved_count, 1)
        resolved = ledger.query_decision_diff(diff, resource="resolved", limit=256)
        self.assertEqual(resolved.total_count, 1)
        self.assertEqual(resolved.items[0]["candidate_state"], "closed")

    def test_all_warning_resolutions_are_an_improved_diff_but_not_promotion(self):
        baseline = self.build_held_ledger()
        candidate = self.close_all_open(baseline)
        diff = ledger.build_decision_diff(baseline, candidate)
        self.assertEqual(diff.state, "improved")
        self.assertEqual(diff.resolved_count, 5)
        self.assertEqual(diff.candidate_state, "closed")
        self.assertFalse(diff.release_ready)

    def test_diff_exposes_added_and_removed_items(self):
        full = self.build_ready_ledger()
        reduced_queue = self.reduced_queue(self.build_ready_queue(), 35, "queue:reduced")
        reduced = ledger.build_decision_ledger(reduced_queue, ledger_id="ledger:reduced")
        added = ledger.build_decision_diff(reduced, full, diff_id="diff:added")
        removed = ledger.build_decision_diff(full, reduced, diff_id="diff:removed")
        self.assertEqual(added.added_count, 1)
        self.assertEqual(added.removed_count, 0)
        self.assertEqual(removed.removed_count, 1)
        self.assertEqual(removed.added_count, 0)
        self.assertEqual(ledger.query_decision_diff(added, resource="added", limit=256).total_count, 1)
        self.assertEqual(ledger.query_decision_diff(removed, resource="removed", limit=256).total_count, 1)

    def test_diff_addresses_and_mapping_are_deterministic(self):
        baseline = self.build_held_ledger()
        item = self.first_item(baseline, "review")
        candidate = ledger.append_decision_by_address(baseline, item.content_address, "escalate", "requires review")
        first = ledger.build_decision_diff(baseline, candidate, diff_id="diff:deterministic")
        second = ledger.build_decision_diff(baseline, candidate, diff_id="diff:deterministic")
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(ledger.address_decision_diff(first), first.content_address)
        restored = ledger.decision_diff_from_mapping(first.to_dict())
        self.assertEqual(restored.to_dict(), first.to_dict())

    def test_diff_rejects_tampered_address_or_unknown_fields(self):
        baseline = self.build_ready_ledger()
        value = ledger.build_decision_diff(baseline, baseline).to_dict()
        value["private"] = True
        with self.assertRaises(ValidationError):
            ledger.decision_diff_from_mapping(value)
        value = ledger.build_decision_diff(baseline, baseline).to_dict()
        value["content_address"] = "diff:tampered"
        with self.assertRaises(ValidationError):
            ledger.decision_diff_from_mapping(value)

    def test_diff_exports_and_schema_are_stable(self):
        baseline = self.build_held_ledger()
        item = self.first_item(baseline, "review")
        candidate = ledger.append_decision_by_address(baseline, item.content_address, "waive", "warning reviewed")
        diff = ledger.build_decision_diff(baseline, candidate)
        self.assertEqual(ledger.decision_diff_json(diff), canonical_json(diff.to_dict()))
        rows = list(csv.DictReader(StringIO(ledger.decision_diff_csv(diff))))
        self.assertEqual(len(rows), diff.item_count)
        self.assertIn("action", rows[0])
        self.assertIn("# Observatory Packet Registry Federation Review Decision Diff", ledger.render_decision_diff_markdown(diff))
        self.assertEqual(ledger.decision_diff_schema()["type"], "object")

    def test_diff_queries_support_action_and_pagination(self):
        baseline = self.build_held_ledger()
        item = self.first_item(baseline, "review")
        candidate = ledger.append_decision_by_address(baseline, item.content_address, "escalate", "requires review")
        diff = ledger.build_decision_diff(baseline, candidate)
        changed = ledger.query_decision_diff(diff, resource="changed", action="changed", offset=0, limit=1)
        self.assertEqual(changed.total_count, 1)
        self.assertEqual(changed.returned_count, 1)
        unchanged = ledger.query_decision_diff(diff, resource="unchanged", limit=256)
        self.assertEqual(unchanged.total_count, 35)


class DecisionCliTests(DecisionFixture):
    base = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decisions"

    @staticmethod
    def run_cli_json(arguments):
        output = StringIO()
        with redirect_stdout(output):
            status = main(arguments)
        text = output.getvalue()
        return status, json.loads(text) if text.strip() else None, text

    def test_cli_build_append_query_and_verify(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            queue = self.write_queue(self.build_held_queue(), root / "queue")
            first = root / "first"
            status, payload, _ = self.run_cli_json([self.base, "--input", str(queue), "--destination", str(first), "--ledger-id", "ledger:cli", "--format", "summary"])
            self.assertEqual(status, 0)
            self.assertEqual(payload["state"], "open")
            self.assertEqual(payload["open_count"], 5)
            item = self.first_item(ledger.load_decision_ledger(first), "review")
            second = root / "second"
            status, payload, _ = self.run_cli_json([self.base + "-append", "--input", str(first), "--item-address", item.content_address, "--action", "waive", "--rationale", "warning reviewed", "--destination", str(second), "--format", "summary"])
            self.assertEqual(status, 0)
            self.assertEqual(payload["entry_count"], 1)
            self.assertEqual(payload["open_count"], 4)
            status, payload, _ = self.run_cli_json([self.base + "-query", "--input", str(second), "--resource", "open", "--limit", "256"])
            self.assertEqual(status, 0)
            self.assertEqual(payload["total_count"], 4)
            status, payload, _ = self.run_cli_json([self.base + "-verify", "--input", str(second)])
            self.assertEqual(status, 0)
            self.assertTrue(payload["accepted"])

    def test_cli_diff_exports_and_contract_files(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            baseline = self.write_ledger(self.build_held_ledger(), root / "baseline")
            item = self.first_item(self.build_held_ledger(), "review")
            candidate_value = ledger.append_decision_by_address(self.build_held_ledger(), item.content_address, "waive", "warning reviewed")
            candidate = self.write_ledger(candidate_value, root / "candidate")
            status, payload, _ = self.run_cli_json([self.base + "-diff", "--baseline", str(baseline), "--candidate", str(candidate), "--format", "summary"])
            self.assertEqual(status, 0)
            self.assertEqual(payload["changed_count"], 1)
            status, payload, _ = self.run_cli_json([self.base + "-diff-query", "--baseline", str(baseline), "--candidate", str(candidate), "--resource", "resolved", "--limit", "256"])
            self.assertEqual(status, 0)
            self.assertEqual(payload["total_count"], 1)
            for suffix in ("-schema", "-capabilities", "-diff-schema", "-query-schema"):
                destination = root / (suffix[1:] + ".json")
                self.assertEqual(main([self.base + suffix, "--output", str(destination)]), 0)
                self.assertIsInstance(json.loads(destination.read_text(encoding="utf-8")), dict)
            for output_format, marker in (("csv", "action"), ("markdown", "# Observatory Packet Registry Federation Review Decision Query")):
                output = StringIO()
                with redirect_stdout(output):
                    status = main([self.base + "-diff-query", "--baseline", str(baseline), "--candidate", str(candidate), "--resource", "changed", "--limit", "256", "--format", output_format])
                self.assertEqual(status, 0)
                self.assertIn(marker, output.getvalue())


class DecisionApiTests(DecisionFixture):
    base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review"

    def start_server(self, root: Path):
        server = create_server("127.0.0.1", 0, root / "api-data")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def test_api_contract_routes_build_and_query_ledger(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            queue_directory = self.write_queue(self.build_held_queue(), root / "queue")
            decision_directory = self.write_ledger(ledger.build_decision_ledger(self.build_held_queue()), root / "decision")
            server, thread = self.start_server(root)
            try:
                for suffix in ("/decisions/schema", "/decisions/capabilities", "/decisions/diff/schema", "/decisions/query/schema"):
                    status, _, payload = self.http_json(server, self.base + suffix)
                    self.assertEqual(status, 200, suffix)
                    self.assertIsInstance(payload, dict)
                status, _, payload = self.http_json(server, self.base + "/decisions", {"input": str(queue_directory), "format": "summary"})
                self.assertEqual(status, 200)
                self.assertEqual(payload["state"], "open")
                self.assertEqual(payload["open_count"], 5)
                status, _, payload = self.http_json(server, self.base + "/decisions/query", {"input": str(decision_directory), "resource": "open", "limit": "256"})
                self.assertEqual(status, 200)
                self.assertEqual(payload["total_count"], 5)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_api_append_and_verify_are_explicit(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            queue_directory = self.write_queue(self.build_held_queue(), root / "queue")
            decision_directory = self.write_ledger(ledger.build_decision_ledger(self.build_held_queue()), root / "decision")
            item = self.first_item(ledger.load_decision_ledger(decision_directory), "review")
            server, thread = self.start_server(root)
            try:
                status, _, payload = self.http_json(server, self.base + "/decisions/append", {"input": str(decision_directory), "item_address": item.content_address, "action": "waive", "rationale": "warning reviewed"})
                self.assertEqual(status, 200)
                self.assertEqual(payload["entry_count"], 1)
                self.assertEqual(payload["open_count"], 4)
                status, _, payload = self.http_json(server, self.base + "/decisions/verify", {"input": str(decision_directory)})
                self.assertEqual(status, 200)
                self.assertTrue(payload["accepted"])
                self.assertTrue(payload["release_ready"] is False)
                self.assertTrue(queue_directory.is_dir())
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_api_diff_and_text_exports(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            baseline = self.write_ledger(self.build_held_ledger(), root / "baseline")
            item = self.first_item(self.build_held_ledger(), "review")
            candidate_value = ledger.append_decision_by_address(self.build_held_ledger(), item.content_address, "waive", "warning reviewed")
            candidate = self.write_ledger(candidate_value, root / "candidate")
            server, thread = self.start_server(root)
            try:
                status, _, payload = self.http_json(server, self.base + "/decisions/diff", {"baseline": str(baseline), "candidate": str(candidate), "format": "summary"})
                self.assertEqual(status, 200)
                self.assertEqual(payload["changed_count"], 1)
                status, _, payload = self.http_json(server, self.base + "/decisions/diff/query", {"baseline": str(baseline), "candidate": str(candidate), "resource": "resolved", "limit": "256"})
                self.assertEqual(status, 200)
                self.assertEqual(payload["total_count"], 1)
                for output_format, marker in (("csv", "action"), ("markdown", "# Observatory Packet Registry Federation Review Decision Query")):
                    status, content_type, body = self.http_text(server, self.base + "/decisions/diff/query", {"baseline": str(baseline), "candidate": str(candidate), "resource": "changed", "format": output_format, "limit": "256"})
                    self.assertEqual(status, 200)
                    self.assertIn(marker, body)
                    self.assertTrue(content_type)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


class DecisionRealDataTests(DecisionFixture):
    def test_downloaded_data_can_be_adjudicated_without_source_paths(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            gate = self.build_real_gate(root / "real")
            queue = review_model.build_review_queue(gate, queue_id="queue:real-decision")
            value = ledger.build_decision_ledger(queue, ledger_id="ledger:real")
            destination = self.write_ledger(value, root / "ledger")
            loaded = ledger.load_decision_ledger(destination)
            self.assertEqual(loaded.item_count, 36)
            self.assertEqual(loaded.state, "closed")
            self.assertTrue(loaded.release_ready)
            self.assertEqual(loaded.federation_id, gate.federation_id)
            payload = canonical_json(loaded.to_dict()).casefold()
            self.assertNotIn(str(self.real_packet()).casefold(), payload)
            self.assertNotIn("source_path", payload)


if __name__ == "__main__":
    unittest.main()
