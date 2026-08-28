"""Deep contracts for federation-gate review routing and decisions."""

# ruff: noqa: E501

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate as gate
from glio_noncode import assurance_history_series_release_registry_federation_gate_review as review
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_bytes, canonical_json
from tests.test_assurance_history_series_release_registry_federation_gate import (
    FederationGateFixture,
)


class ReviewFixture(unittest.TestCase):
    """Use the current federation gate fixture as downloaded-style input."""

    def setUp(self):
        self.gates = FederationGateFixture("runTest")
        self.gates.setUp()
        self.ready_gate = gate.build_federation_assurance_gate(self.gates.ready_source, gate_id="gate:ready")
        self.held_gate = gate.build_federation_assurance_gate(self.gates.held_source, gate_id="gate:held")
        self.blocked_gate = gate.build_federation_assurance_gate(self.gates.blocked_source, gate_id="gate:blocked")
        self.ready_review = review.build_review(self.ready_gate, queue_id="queue:ready")
        self.held_review = review.build_review(self.held_gate, queue_id="queue:held")
        self.blocked_review = review.build_review(self.blocked_gate, queue_id="queue:blocked")

    @staticmethod
    def public_keys(value):
        if isinstance(value, dict):
            output = set(value)
            for nested in value.values():
                output.update(ReviewFixture.public_keys(nested))
            return output
        if isinstance(value, (list, tuple)):
            output = set()
            for nested in value:
                output.update(ReviewFixture.public_keys(nested))
            return output
        return set()

    def assert_public(self, value):
        payload = value.to_dict() if hasattr(value, "to_dict") else value
        self.assertFalse(self.public_keys(payload) & review._FORBIDDEN_KEYS)
        self.assertNotIn("C:\\", canonical_json(payload))
        self.assertNotIn("/Users/", canonical_json(payload))

    @staticmethod
    def capture_cli(argv):
        stream = StringIO()
        with redirect_stdout(stream):
            status = main(argv)
        return status, stream.getvalue()

    @staticmethod
    def failed_item(value):
        return next(item for item in value.items if not item.passed)

    @staticmethod
    def evidence(index=1):
        return f"evidence:review-{index}"


class ReviewQueueCoreTests(ReviewFixture):
    def test_ready_queue_routes_findings_and_checks_once(self):
        queue = self.ready_review.queue
        self.assertEqual(queue.item_count, self.ready_gate.assurance.finding_count + self.ready_gate.gate.check_count)
        self.assertEqual(queue.failed_count, 0)
        self.assertEqual(queue.state, "clear")
        self.assertTrue(queue.release_ready)
        self.assertEqual(sum(item.record_type == "finding" for item in queue.items), self.ready_gate.assurance.finding_count)
        self.assertEqual(sum(item.record_type == "check" for item in queue.items), self.ready_gate.gate.check_count)

    def test_held_queue_preserves_warning_items_without_promoting(self):
        queue = self.held_review.queue
        self.assertEqual(queue.state, "review")
        self.assertFalse(queue.release_ready)
        self.assertGreater(queue.warning_count, 0)
        self.assertEqual(queue.blocker_count, 0)
        self.assertTrue(all(item.priority == "high" for item in queue.items if not item.passed))

    def test_blocked_queue_preserves_blocker_items_and_fails_closed(self):
        queue = self.blocked_review.queue
        self.assertEqual(queue.state, "blocked")
        self.assertFalse(queue.accepted)
        self.assertFalse(queue.release_ready)
        self.assertGreater(queue.blocker_count, 0)
        self.assertTrue(all(item.priority == "critical" for item in queue.items if item.required and not item.passed))

    def test_queue_item_ids_are_source_scoped(self):
        self.assertTrue(all(item.item_id.startswith(("finding:", "check:")) for item in self.ready_review.queue.items))
        self.assertEqual(len({item.item_id for item in self.ready_review.queue.items}), self.ready_review.queue.item_count)
        self.assertEqual(len({item.source_address for item in self.ready_review.queue.items}), self.ready_review.queue.item_count)

    def test_check_items_use_transport_plane(self):
        checks = [item for item in self.ready_review.queue.items if item.record_type == "check"]
        self.assertTrue(checks)
        self.assertTrue(all(item.plane == "transport" for item in checks))

    def test_review_bundle_has_independent_verification(self):
        self.assertEqual(self.ready_review.verification.finding_count, 10)
        self.assertEqual(self.ready_review.verification.failed_count, 0)
        self.assertEqual(self.held_review.verification.failed_count, 0)
        self.assertTrue(self.ready_review.verification.release_ready)
        self.assertTrue(self.held_review.verification.release_ready)
        self.assertFalse(self.held_review.queue.release_ready)

    def test_review_against_source_gate_is_exact(self):
        self.assertIs(review.verify_review_against_gate(self.ready_review, self.ready_gate), self.ready_review)
        with self.assertRaises(ValidationError):
            review.verify_review_against_gate(self.ready_review, self.held_gate)

    def test_queue_address_excludes_item_ordinals(self):
        first = review.build_review_queue(self.ready_gate, queue_id="queue:one")
        second = review.build_review_queue(self.ready_gate, queue_id="queue:one")
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual([item.content_address for item in first.items], [item.content_address for item in second.items])

    def test_different_queue_identity_changes_queue_address(self):
        first = review.build_review_queue(self.ready_gate, queue_id="queue:one")
        second = review.build_review_queue(self.ready_gate, queue_id="queue:two")
        self.assertNotEqual(first.content_address, second.content_address)

    def test_all_public_projections_are_path_free(self):
        self.assert_public(self.ready_review)
        self.assert_public(self.held_review)
        self.assert_public(self.blocked_review)
        self.assert_public(review.review_capabilities())

    def test_constructor_rejects_unknown_item_state(self):
        item = self.ready_review.queue.items[0].to_dict()
        item["state"] = "mystery"
        with self.assertRaises(ValidationError):
            review.item_from_mapping(item)

    def test_constructor_rejects_unknown_item_fields(self):
        item = self.ready_review.queue.items[0].to_dict() | {"private": "no"}
        with self.assertRaises(ValidationError):
            review.item_from_mapping(item)

    def test_constructor_rejects_severity_priority_mismatch(self):
        item = self.ready_review.queue.items[0].to_dict()
        item["passed"] = False
        item["state"] = "open"
        item["priority"] = "high"
        with self.assertRaises(ValidationError):
            review.item_from_mapping(item)

    def test_constructor_rejects_noncontiguous_queue_items(self):
        payload = self.ready_review.queue.to_dict()
        payload["items"][0]["ordinal"] = 4
        with self.assertRaises(ValidationError):
            review.queue_from_mapping(payload)

    def test_verification_finding_addresses_are_stable(self):
        first = self.ready_review.verification.findings[0]
        second = review.build_review(self.ready_gate, queue_id="queue:ready").verification.findings[0]
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(review.address_verification_finding(first), first.content_address)

    def test_verification_rejects_stale_queue_address(self):
        payload = self.ready_review.to_dict()
        payload["verification"]["queue_address"] = "queue:stale"
        payload["verification"]["content_address"] = "pending:verification"
        with self.assertRaises(ValidationError):
            review.review_from_mapping(payload)


class ReviewPersistenceTests(ReviewFixture):
    def test_queue_persistence_is_exact_four_file_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "review"
            review.write_review(self.ready_review, destination)
            self.assertEqual({item.name for item in destination.iterdir()}, set(review.QUEUE_FILES))
            loaded = review.load_review(destination)
            self.assertEqual(loaded.to_dict(), self.ready_review.to_dict())
            self.assertEqual(review.verify_review_directory(destination).to_dict(), self.ready_review.to_dict())

    def test_queue_manifest_has_byte_receipts(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "review"
            review.write_review(self.ready_review, destination)
            manifest = json.loads((destination / review.MANIFEST_NAME).read_text(encoding="utf-8"))
            self.assertEqual(manifest["files"], list(review.QUEUE_FILES))
            self.assertEqual(manifest["artifact_count"], 3)
            for artifact in manifest["artifacts"]:
                raw = (destination / artifact["name"]).read_bytes()
                self.assertEqual(artifact["bytes"], len(raw))
                self.assertEqual(artifact["byte_address"], review._file_address(artifact["name"], raw))

    def test_queue_persistence_is_canonical_utf8(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "review"
            review.write_review(self.ready_review, destination)
            for path in destination.iterdir():
                parsed = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(path.read_bytes(), canonical_bytes(parsed))

    def test_queue_loader_rejects_missing_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "review"
            review.write_review(self.ready_review, destination)
            (destination / review.ITEMS_NAME).unlink()
            with self.assertRaises(ValidationError):
                review.load_review(destination)

    def test_queue_loader_rejects_extra_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "review"
            review.write_review(self.ready_review, destination)
            (destination / "extra.json").write_bytes(b"{}")
            with self.assertRaises(ValidationError):
                review.load_review(destination)

    def test_queue_loader_rejects_noncanonical_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "review"
            review.write_review(self.ready_review, destination)
            path = destination / review.QUEUE_NAME
            path.write_text(json.dumps(json.loads(path.read_text(encoding="utf-8")), indent=2), encoding="utf-8")
            with self.assertRaises(ValidationError):
                review.load_review(destination)

    def test_queue_loader_rejects_tampered_item_document(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "review"
            review.write_review(self.ready_review, destination)
            payload = json.loads((destination / review.ITEMS_NAME).read_text(encoding="utf-8"))
            payload["items"][0]["detail"] = "tampered"
            (destination / review.ITEMS_NAME).write_bytes(canonical_bytes(payload))
            with self.assertRaises(ValidationError):
                review.load_review(destination)

    def test_queue_loader_rejects_tampered_manifest_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "review"
            review.write_review(self.ready_review, destination)
            manifest_path = destination / review.MANIFEST_NAME
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"][0]["bytes"] += 1
            manifest["content_address"] = "pending:tampered"
            manifest_path.write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                review.load_review(destination)

    def test_queue_writer_requires_overwrite_for_nonempty_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "review"
            review.write_review(self.ready_review, destination)
            with self.assertRaises(ValidationError):
                review.write_review(self.ready_review, destination)
            review.write_review(self.ready_review, destination, overwrite=True)
            self.assertEqual(review.load_review(destination).queue.queue_id, "queue:ready")

    def test_queue_writer_rejects_symlink_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            destination = root / "link"
            try:
                destination.symlink_to(source, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks unavailable")
            with self.assertRaises(ValidationError):
                review.write_review(self.ready_review, destination)

    def test_review_mapping_round_trip_is_exact(self):
        self.assertEqual(review.review_from_mapping(self.ready_review.to_dict()).to_dict(), self.ready_review.to_dict())

    def test_review_mapping_rejects_private_key(self):
        payload = self.ready_review.to_dict()
        payload["queue"]["private"] = True
        with self.assertRaises(ValidationError):
            review.review_from_mapping(payload)

    def test_gate_directory_builder_rehydrates_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "gate"
            gate.write_federation_assurance_gate(self.ready_gate, source)
            loaded = review.build_review_from_gate_directory(source, queue_id="queue:from-directory")
            self.assertEqual(loaded.queue.queue_id, "queue:from-directory")
            self.assertEqual(loaded.queue.gate_address, self.ready_gate.gate.content_address)


class ReviewQueryTests(ReviewFixture):
    def test_query_summary_is_addressed(self):
        result = review.query_review(self.ready_review, resource="summary")
        self.assertEqual(result.total_count, 1)
        self.assertEqual(result.returned[0]["queue_id"], "queue:ready")
        self.assertEqual(result.content_address, review.address_query_result(result))

    def test_query_items_and_record_type_filters(self):
        result = review.query_review(self.ready_review, resource="items", record_type="finding")
        self.assertEqual(result.total_count, self.ready_gate.assurance.finding_count)
        self.assertTrue(all(row["record_type"] == "finding" for row in result.returned))
        result = review.query_review(self.ready_review, resource="checks")
        self.assertEqual(result.total_count, self.ready_gate.gate.check_count)

    def test_query_blockers_and_warnings_only_returns_failed_items(self):
        blockers = review.query_review(self.blocked_review, resource="blockers")
        warnings = review.query_review(self.held_review, resource="warnings")
        self.assertTrue(blockers.returned)
        self.assertTrue(warnings.returned)
        self.assertTrue(all(not row["passed"] and row["required"] for row in blockers.returned))
        self.assertTrue(all(not row["passed"] and not row["required"] for row in warnings.returned))

    def test_query_open_clear_passed_and_failed_partitions(self):
        queue = self.held_review.queue
        open_rows = review.query_review(self.held_review, resource="open")
        clear_rows = review.query_review(self.held_review, resource="clear")
        passed_rows = review.query_review(self.held_review, resource="passed")
        failed_rows = review.query_review(self.held_review, resource="failed")
        self.assertEqual(open_rows.total_count + clear_rows.total_count, queue.item_count)
        self.assertEqual(passed_rows.total_count, clear_rows.total_count)
        self.assertEqual(failed_rows.total_count, open_rows.total_count)

    def test_query_plane_severity_priority_state_and_required_filters(self):
        result = review.query_review(self.blocked_review, resource="items", plane="runtime", severity="blocker", required=True, state="blocked", priority="critical", passed=False)
        self.assertTrue(result.returned)
        self.assertTrue(all(row["plane"] == "runtime" and row["required"] for row in result.returned))

    def test_query_text_is_case_insensitive(self):
        result = review.query_review(self.ready_review, resource="items", text="SOURCE-BUNDLE")
        self.assertTrue(result.returned)
        self.assertTrue(all("source-bundle" in row["source_id"] or "source-bundle" in row["detail"] for row in result.returned))

    def test_query_pagination_is_bounded_and_deterministic(self):
        first = review.query_review(self.ready_review, resource="items", offset=0, limit=3)
        second = review.query_review(self.ready_review, resource="items", offset=3, limit=3)
        self.assertEqual(first.total_count, second.total_count)
        self.assertEqual(first.returned[0]["item_id"], self.ready_review.queue.items[0].item_id)
        self.assertEqual(first.returned[0]["ordinal"], 0)
        self.assertEqual(second.returned[0]["ordinal"], 3)

    def test_query_rejects_invalid_resource(self):
        with self.assertRaises(ValidationError):
            review.query_review(self.ready_review, resource="unknown")

    def test_query_rejects_zero_limit(self):
        with self.assertRaises(ValidationError):
            review.query_review(self.ready_review, limit=0)

    def test_query_rejects_negative_offset(self):
        with self.assertRaises(ValidationError):
            review.query_review(self.ready_review, offset=-1)

    def test_query_result_mapping_and_exports(self):
        result = review.query_review(self.held_review, resource="warnings")
        self.assertEqual(review.query_json(result), canonical_json(result.to_dict()))
        self.assertIn("item_id", review.query_csv(result))
        self.assertIn("Federation gate review query", review.render_query_markdown(result))

    def test_review_exports_are_deterministic(self):
        self.assertEqual(review.review_json(self.ready_review), review.review_json(review.build_review(self.ready_gate, queue_id="queue:ready")))
        self.assertIn("record_type", review.review_csv(self.ready_review))
        self.assertIn("Federation gate review", review.render_review_markdown(self.ready_review))

    def test_query_mapping_rejects_unknown_fields(self):
        payload = review.query_review(self.ready_review).to_dict()["query"] | {"private": True}
        with self.assertRaises(TypeError):
            review.ReviewQuery(**payload)


class DecisionLedgerCoreTests(ReviewFixture):
    def setUp(self):
        super().setUp()
        self.ready_ledger = review.build_decision_ledger(self.ready_review, ledger_id="ledger:ready")
        self.held_ledger = review.build_decision_ledger(self.held_review, ledger_id="ledger:held")
        self.blocked_ledger = review.build_decision_ledger(self.blocked_review, ledger_id="ledger:blocked")

    def test_empty_ready_ledger_has_initial_head_and_clear_replay(self):
        self.assertEqual(self.ready_ledger.entry_count, 0)
        self.assertEqual(self.ready_ledger.head_address, review.INITIAL_HEAD)
        self.assertEqual(self.ready_ledger.replay.clear_count, len(self.ready_ledger.items))
        self.assertEqual(self.ready_ledger.state, "clear")
        self.assertTrue(self.ready_ledger.release_ready)

    def test_held_ledger_preserves_source_gate_authority(self):
        self.assertEqual(self.held_ledger.state, "review")
        self.assertTrue(self.held_ledger.accepted)
        self.assertFalse(self.held_ledger.release_ready)
        self.assertEqual(self.held_ledger.replay.source_release_ready, self.held_review.queue.release_ready)

    def test_blocked_ledger_is_not_made_accepted_by_empty_decision_log(self):
        self.assertFalse(self.blocked_ledger.accepted)
        self.assertFalse(self.blocked_ledger.release_ready)
        self.assertEqual(self.blocked_ledger.state, "blocked")

    def test_acknowledge_reopen_and_remediate_replay_chain(self):
        item = self.failed_item(self.held_ledger)
        first = review.append_decision(self.held_ledger, item_id=item.item_id, action="acknowledge", rationale="review accepted", expected_head_address=self.held_ledger.head_address)
        second = review.append_decision(first, item_id=item.item_id, action="reopen", rationale="new evidence requested", expected_head_address=first.head_address)
        third = review.append_decision(second, item_id=item.item_id, action="remediate", rationale="evidence attached", evidence_address=self.evidence(), expected_head_address=second.head_address)
        replay_item = third.replay.items[item.ordinal]
        self.assertEqual(third.entry_count, 3)
        self.assertEqual(replay_item.state, "resolved")
        self.assertEqual(third.replay.resolved_count, 1)
        self.assertFalse(third.release_ready)
        self.assertEqual(third.head_address, third.entries[-1].content_address)

    def test_escalation_is_replayable_and_keeps_review_open(self):
        item = self.failed_item(self.held_ledger)
        value = review.append_decision(self.held_ledger, item_id=item.item_id, action="escalate", rationale="specialist review", expected_head_address=self.held_ledger.head_address)
        self.assertEqual(value.replay.items[item.ordinal].state, "escalated")
        self.assertEqual(value.replay.escalated_count, 1)
        self.assertEqual(value.state, "review")

    def test_warning_can_be_waived_only_with_evidence(self):
        item = self.failed_item(self.held_ledger)
        with self.assertRaises(ValidationError):
            review.append_decision(self.held_ledger, item_id=item.item_id, action="waive", rationale="not enough", expected_head_address=self.held_ledger.head_address)
        value = review.append_decision(self.held_ledger, item_id=item.item_id, action="waive", rationale="documented exception", evidence_address=self.evidence(2), expected_head_address=self.held_ledger.head_address)
        self.assertEqual(value.replay.items[item.ordinal].state, "waived")
        self.assertEqual(value.replay.waived_count, 1)
        self.assertFalse(value.release_ready)

    def test_blocker_cannot_be_waived(self):
        item = self.failed_item(self.blocked_ledger)
        self.assertTrue(item.required)
        with self.assertRaises(ValidationError):
            review.append_decision(self.blocked_ledger, item_id=item.item_id, action="waive", rationale="exception", evidence_address=self.evidence(), expected_head_address=self.blocked_ledger.head_address)

    def test_blocker_remediation_does_not_override_source_gate(self):
        item = self.failed_item(self.blocked_ledger)
        value = review.append_decision(self.blocked_ledger, item_id=item.item_id, action="remediate", rationale="corrected source", evidence_address=self.evidence(), expected_head_address=self.blocked_ledger.head_address)
        self.assertEqual(value.replay.items[item.ordinal].state, "resolved")
        self.assertFalse(value.accepted)
        self.assertFalse(value.release_ready)
        self.assertEqual(value.state, "blocked")

    def test_head_guard_rejects_stale_expected_head(self):
        item = self.failed_item(self.held_ledger)
        with self.assertRaises(ValidationError):
            review.append_decision(self.held_ledger, item_id=item.item_id, action="acknowledge", rationale="stale", expected_head_address="none:wrong")

    def test_action_requires_one_item_identifier(self):
        with self.assertRaises(ValidationError):
            review.append_decision(self.held_ledger, action="acknowledge", rationale="missing", expected_head_address=self.held_ledger.head_address)
        item = self.failed_item(self.held_ledger)
        with self.assertRaises(ValidationError):
            review.append_decision(self.held_ledger, item_id=item.item_id, item_address="item:wrong", action="acknowledge", rationale="ambiguous", expected_head_address=self.held_ledger.head_address)

    def test_action_rejects_already_clear_item(self):
        item = self.ready_ledger.items[0]
        with self.assertRaises(ValidationError):
            review.append_decision(self.ready_ledger, item_id=item.item_id, action="acknowledge", rationale="not needed", expected_head_address=self.ready_ledger.head_address)

    def test_action_requires_evidence_address_for_remediation(self):
        item = self.failed_item(self.held_ledger)
        with self.assertRaises(ValidationError):
            review.append_decision(self.held_ledger, item_id=item.item_id, action="remediate", rationale="no evidence", evidence_address=review.NO_EVIDENCE, expected_head_address=self.held_ledger.head_address)

    def test_decision_addresses_and_ancestry_are_deterministic(self):
        item = self.failed_item(self.held_ledger)
        first = review.append_decision(self.held_ledger, item_id=item.item_id, action="acknowledge", rationale="review accepted", expected_head_address=self.held_ledger.head_address, decision_id="decision:one")
        second = review.append_decision(self.held_ledger, item_id=item.item_id, action="acknowledge", rationale="review accepted", expected_head_address=self.held_ledger.head_address, decision_id="decision:one")
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.entries[0].previous_address, review.INITIAL_HEAD)

    def test_ledger_public_projection_contains_no_private_fields(self):
        self.assert_public(self.ready_ledger)
        self.assert_public(self.held_ledger)
        self.assert_public(self.blocked_ledger)


class DecisionLedgerPersistenceTests(DecisionLedgerCoreTests):
    def test_ledger_persistence_is_exact_four_file_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "ledger"
            review.write_decision_ledger(self.ready_ledger, destination)
            self.assertEqual({item.name for item in destination.iterdir()}, set(review.LEDGER_FILES))
            loaded = review.load_decision_ledger(destination)
            self.assertEqual(loaded.to_dict(), self.ready_ledger.to_dict())

    def test_nonempty_ledger_persists_decisions_and_replay(self):
        item = self.failed_item(self.held_ledger)
        value = review.append_decision(self.held_ledger, item_id=item.item_id, action="remediate", rationale="evidence attached", evidence_address=self.evidence(), expected_head_address=self.held_ledger.head_address)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "ledger"
            review.write_decision_ledger(value, destination)
            loaded = review.load_decision_ledger(destination)
            self.assertEqual(loaded.entry_count, 1)
            self.assertEqual(loaded.entries[0].evidence_address, self.evidence())
            self.assertEqual(loaded.replay.to_dict(), value.replay.to_dict())

    def test_ledger_manifest_receipts_are_exact(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "ledger"
            review.write_decision_ledger(self.ready_ledger, destination)
            manifest = json.loads((destination / review.MANIFEST_NAME).read_text(encoding="utf-8"))
            self.assertEqual(manifest["files"], list(review.LEDGER_FILES))
            self.assertEqual(manifest["artifact_count"], 3)
            for artifact in manifest["artifacts"]:
                raw = (destination / artifact["name"]).read_bytes()
                self.assertEqual(artifact["byte_address"], review._file_address(artifact["name"], raw))

    def test_ledger_loader_rejects_missing_entries(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "ledger"
            review.write_decision_ledger(self.ready_ledger, destination)
            (destination / review.ENTRIES_NAME).unlink()
            with self.assertRaises(ValidationError):
                review.load_decision_ledger(destination)

    def test_ledger_loader_rejects_tampered_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "ledger"
            review.write_decision_ledger(self.ready_ledger, destination)
            payload = json.loads((destination / review.REPLAY_NAME).read_text(encoding="utf-8"))
            payload["clear_count"] = 0
            (destination / review.REPLAY_NAME).write_bytes(canonical_bytes(payload))
            with self.assertRaises(ValidationError):
                review.load_decision_ledger(destination)

    def test_ledger_loader_rejects_tampered_decision(self):
        item = self.failed_item(self.held_ledger)
        value = review.append_decision(self.held_ledger, item_id=item.item_id, action="acknowledge", rationale="review accepted", expected_head_address=self.held_ledger.head_address)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "ledger"
            review.write_decision_ledger(value, destination)
            payload = json.loads((destination / review.ENTRIES_NAME).read_text(encoding="utf-8"))
            payload["entries"][0]["rationale"] = "tampered"
            (destination / review.ENTRIES_NAME).write_bytes(canonical_bytes(payload))
            with self.assertRaises(ValidationError):
                review.load_decision_ledger(destination)

    def test_ledger_loader_rejects_noncanonical_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "ledger"
            review.write_decision_ledger(self.ready_ledger, destination)
            manifest = json.loads((destination / review.MANIFEST_NAME).read_text(encoding="utf-8"))
            (destination / review.MANIFEST_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            with self.assertRaises(ValidationError):
                review.load_decision_ledger(destination)

    def test_ledger_from_review_directory_preserves_source_links(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            queue_directory = root / "review"
            ledger_directory = root / "ledger"
            review.write_review(self.held_review, queue_directory)
            value = review.build_decision_ledger_from_directory(queue_directory, ledger_id="ledger:directory")
            review.write_decision_ledger(value, ledger_directory)
            self.assertEqual(review.load_decision_ledger(ledger_directory).queue_address, self.held_review.queue.content_address)

    def test_ledger_writer_rejects_nonempty_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "ledger"
            review.write_decision_ledger(self.ready_ledger, destination)
            with self.assertRaises(ValidationError):
                review.write_decision_ledger(self.ready_ledger, destination)
            review.write_decision_ledger(self.ready_ledger, destination, overwrite=True)


class DecisionQueryTests(DecisionLedgerCoreTests):
    def test_decision_query_summary_items_and_entries(self):
        item = self.failed_item(self.held_ledger)
        value = review.append_decision(self.held_ledger, item_id=item.item_id, action="acknowledge", rationale="review accepted", expected_head_address=self.held_ledger.head_address)
        self.assertEqual(review.query_decision_ledger(value, resource="summary").total_count, 1)
        self.assertEqual(review.query_decision_ledger(value, resource="items").total_count, len(value.items))
        entries = review.query_decision_ledger(value, resource="entries")
        self.assertEqual(entries.total_count, 1)
        self.assertEqual(entries.returned[0]["action"], "acknowledge")

    def test_decision_query_state_partitions(self):
        item = self.failed_item(self.held_ledger)
        value = review.append_decision(self.held_ledger, item_id=item.item_id, action="escalate", rationale="specialist review", expected_head_address=self.held_ledger.head_address)
        self.assertEqual(review.query_decision_ledger(value, resource="escalated").total_count, 1)
        open_rows = review.query_decision_ledger(value, resource="open").returned
        self.assertNotIn(item.item_id, {row["item_id"] for row in open_rows})
        self.assertEqual(review.query_decision_ledger(value, resource="resolved").total_count, 0)

    def test_decision_query_action_item_and_text_filters(self):
        item = self.failed_item(self.held_ledger)
        value = review.append_decision(self.held_ledger, item_id=item.item_id, action="remediate", rationale="Evidence Attached", evidence_address=self.evidence(), expected_head_address=self.held_ledger.head_address)
        result = review.query_decision_ledger(value, resource="entries", item_id=item.item_id, action="remediate", text="evidence")
        self.assertEqual(result.total_count, 1)

    def test_decision_query_rejects_invalid_resource_and_action(self):
        with self.assertRaises(ValidationError):
            review.query_decision_ledger(self.ready_ledger, resource="unknown")
        with self.assertRaises(ValidationError):
            review.query_decision_ledger(self.ready_ledger, action="invalid")

    def test_decision_exports_are_deterministic(self):
        item = self.failed_item(self.held_ledger)
        value = review.append_decision(self.held_ledger, item_id=item.item_id, action="acknowledge", rationale="review accepted", expected_head_address=self.held_ledger.head_address)
        result = review.query_decision_ledger(value, resource="entries")
        self.assertEqual(review.decision_query_json(result), canonical_json(result.to_dict()))
        self.assertIn("decision_id", review.decision_ledger_csv(value))
        self.assertIn("decision ledger", review.render_decision_ledger_markdown(value))
        self.assertIn("Federation decision query", review.render_decision_query_markdown(result))

    def test_decision_query_result_is_public(self):
        result = review.query_decision_ledger(self.ready_ledger, resource="items")
        self.assert_public(result)


class DecisionDiffTests(DecisionLedgerCoreTests):
    def test_empty_ledgers_have_no_diff_changes(self):
        value = review.build_decision_diff(self.ready_ledger, self.ready_ledger, diff_id="diff:empty")
        self.assertEqual(value.item_count, len(self.ready_ledger.items))
        self.assertEqual(value.unchanged_count, value.item_count)
        self.assertEqual(value.changed_count, 0)
        self.assertEqual(value.state, "none")

    def test_decision_diff_detects_improvement_from_escalated_to_resolved(self):
        item = self.failed_item(self.held_ledger)
        baseline = review.append_decision(self.held_ledger, item_id=item.item_id, action="escalate", rationale="specialist review", expected_head_address=self.held_ledger.head_address)
        candidate = review.append_decision(baseline, item_id=item.item_id, action="remediate", rationale="evidence attached", evidence_address=self.evidence(), expected_head_address=baseline.head_address)
        value = review.build_decision_diff(baseline, candidate, diff_id="diff:improved")
        changed = next(row for row in value.items if row.item_id == item.item_id)
        self.assertEqual(changed.action, "changed")
        self.assertEqual(changed.direction, "improved")
        self.assertEqual(value.improved_count, 1)
        self.assertEqual(value.state, "improved")

    def test_decision_diff_detects_regression_after_reopen(self):
        item = self.failed_item(self.held_ledger)
        resolved = review.append_decision(self.held_ledger, item_id=item.item_id, action="remediate", rationale="evidence attached", evidence_address=self.evidence(), expected_head_address=self.held_ledger.head_address)
        reopened = review.append_decision(resolved, item_id=item.item_id, action="reopen", rationale="evidence invalid", expected_head_address=resolved.head_address)
        value = review.build_decision_diff(resolved, reopened, diff_id="diff:regressed")
        changed = next(row for row in value.items if row.item_id == item.item_id)
        self.assertEqual(changed.direction, "regressed")
        self.assertEqual(value.regressed_count, 1)
        self.assertEqual(value.state, "regressed")

    def test_decision_diff_handles_added_and_removed_item_sets(self):
        item = self.failed_item(self.held_ledger)
        baseline = review.append_decision(self.held_ledger, item_id=item.item_id, action="acknowledge", rationale="review accepted", expected_head_address=self.held_ledger.head_address)
        candidate = review.build_decision_ledger(self.ready_review, ledger_id="ledger:ready-candidate")
        value = review.build_decision_diff(baseline, candidate, diff_id="diff:sets")
        self.assertEqual(value.item_count, len(set(item.item_id for item in baseline.items) | set(item.item_id for item in candidate.items)))
        self.assertGreaterEqual(value.changed_count + value.added_count + value.removed_count, 1)

    def test_diff_persistence_has_exact_two_files(self):
        item = self.failed_item(self.held_ledger)
        baseline = review.append_decision(self.held_ledger, item_id=item.item_id, action="escalate", rationale="specialist review", expected_head_address=self.held_ledger.head_address)
        candidate = review.append_decision(baseline, item_id=item.item_id, action="remediate", rationale="evidence attached", evidence_address=self.evidence(), expected_head_address=baseline.head_address)
        value = review.build_decision_diff(baseline, candidate, diff_id="diff:persist")
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "diff"
            review.write_decision_diff(value, destination)
            self.assertEqual({item.name for item in destination.iterdir()}, set(review.DIFF_FILES))
            self.assertEqual(review.load_decision_diff(destination).to_dict(), value.to_dict())

    def test_diff_loader_rejects_tampered_document(self):
        value = review.build_decision_diff(self.ready_ledger, self.ready_ledger)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "diff"
            review.write_decision_diff(value, destination)
            payload = json.loads((destination / review.DIFF_NAME).read_text(encoding="utf-8"))
            payload["state"] = "improved"
            (destination / review.DIFF_NAME).write_bytes(canonical_bytes(payload))
            with self.assertRaises(ValidationError):
                review.load_decision_diff(destination)

    def test_diff_export_is_public_and_deterministic(self):
        value = review.build_decision_diff(self.ready_ledger, self.ready_ledger, diff_id="diff:exports")
        self.assert_public(value)
        self.assertEqual(review.diff_json(value), canonical_json(value.to_dict()))
        self.assertIn("direction", review.diff_csv(value))
        self.assertIn("Federation review decision diff", review.render_diff_markdown(value))


class ReviewSchemaCapabilityTests(ReviewFixture):
    def test_schemas_are_json_objects_with_closed_top_level(self):
        schemas = [review.item_schema(), review.queue_schema(), review.verification_finding_schema(), review.verification_schema(), review.review_schema(), review.query_schema(), review.manifest_schema(), review.decision_schema(), review.replay_schema(), review.ledger_schema(), review.decision_query_schema(), review.decision_diff_schema()]
        for schema in schemas:
            self.assertIsInstance(schema, dict)
            self.assertEqual(schema["type"], "object")
            self.assertFalse(schema["additionalProperties"])
            self.assertNotIn("agent", self.public_keys(schema))

    def test_capabilities_describe_queue_ledger_and_diff(self):
        value = review.diff_capabilities()
        self.assertEqual(value["version"], review.VERSION)
        self.assertEqual(value["packages"]["queue_files"], list(review.QUEUE_FILES))
        self.assertEqual(value["packages"]["ledger_files"], list(review.LEDGER_FILES))
        self.assertFalse(value["ledger"]["blocker_waiver"])
        self.assertTrue(value["ledger"]["source_gate_authoritative"])
        self.assert_public(value)

    def test_enum_values_are_stable(self):
        self.assertEqual(tuple(review.ReviewAction), ("acknowledge", "remediate", "waive", "escalate", "reopen"))
        self.assertEqual(tuple(review.ReviewQueueState), ("clear", "review", "blocked"))
        self.assertIn("critical", tuple(review.ReviewPriority))
        self.assertIn("changed", tuple(review.DiffAction))


class ReviewCliTests(ReviewFixture):
    BASE = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-series-release-registry-federation-gate-review"
    LEDGER = BASE + "-decision-ledger"
    DIFF = LEDGER + "-diff"

    def _persist_gate(self, root):
        federation_directory = root / "federation"
        gate.write_federation_assurance_gate(self.ready_gate, federation_directory)
        return federation_directory

    def test_cli_review_build_verify_query_and_contracts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "gate"
            destination = root / "review"
            gate.write_federation_assurance_gate(self.ready_gate, source)
            status, output = self.capture_cli([self.BASE, "--input", str(source), "--queue-id", "queue:cli", "--destination", str(destination), "--format", "summary"])
            self.assertEqual(status, 0)
            summary = json.loads(output)
            self.assertEqual(summary["queue_id"], "queue:cli")
            status, output = self.capture_cli([self.BASE + "-verify", "--input", str(destination)])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output)["verification_state"], "clear")
            status, output = self.capture_cli([self.BASE + "-query", "--input", str(destination), "--resource", "checks", "--format", "json"])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output)["total_count"], self.ready_gate.gate.check_count)
            for suffix in ("schema", "queue-schema", "verification-schema", "item-schema", "query-schema", "manifest-schema", "capabilities"):
                status, output = self.capture_cli([self.BASE + "-" + suffix])
                self.assertEqual(status, 0)
                self.assertIsInstance(json.loads(output), dict)

    def test_cli_decision_ledger_and_append_round_trip(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "gate"
            queue_directory = root / "review"
            ledger_directory = root / "ledger"
            gate.write_federation_assurance_gate(self.held_gate, source)
            status, output = self.capture_cli([self.BASE, "--input", str(source), "--queue-id", "queue:cli-held", "--destination", str(queue_directory), "--format", "summary"])
            self.assertEqual(status, 2)
            queue = review.load_review(queue_directory)
            item = self.failed_item(queue.queue)
            status, output = self.capture_cli([self.LEDGER, "--input", str(queue_directory), "--ledger-id", "ledger:cli", "--destination", str(ledger_directory), "--format", "summary"])
            self.assertEqual(status, 2)
            self.assertEqual(json.loads(output)["state"], "review")
            status, output = self.capture_cli([self.LEDGER + "-append", "--input", str(ledger_directory), "--item-id", item.item_id, "--action", "remediate", "--rationale", "evidence attached", "--evidence-address", self.evidence(), "--expected-head", review.INITIAL_HEAD, "--destination", str(ledger_directory), "--allow-existing", "--format", "summary"])
            self.assertEqual(status, 2)
            self.assertEqual(json.loads(output)["entry_count"], 1)
            status, output = self.capture_cli([self.LEDGER + "-query", "--input", str(ledger_directory), "--resource", "entries"])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output)["total_count"], 1)
            status, output = self.capture_cli([self.LEDGER + "-verify", "--input", str(ledger_directory)])
            self.assertEqual(status, 2)

    def test_cli_diff_and_diff_contracts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "gate"
            queue_directory = root / "review"
            baseline_directory = root / "baseline"
            candidate_directory = root / "candidate"
            diff_directory = root / "diff"
            gate.write_federation_assurance_gate(self.held_gate, source)
            self.capture_cli([self.BASE, "--input", str(source), "--destination", str(queue_directory), "--format", "summary"])
            queue = review.load_review(queue_directory)
            item = self.failed_item(queue.queue)
            self.capture_cli([self.LEDGER, "--input", str(queue_directory), "--destination", str(baseline_directory), "--format", "summary"])
            status, _ = self.capture_cli([self.LEDGER + "-append", "--input", str(baseline_directory), "--item-id", item.item_id, "--action", "escalate", "--rationale", "route", "--expected-head", review.INITIAL_HEAD, "--destination", str(candidate_directory), "--format", "summary"])
            self.assertEqual(status, 2)
            status, output = self.capture_cli([self.DIFF, "--baseline", str(baseline_directory), "--candidate", str(candidate_directory), "--destination", str(diff_directory), "--format", "summary"])
            self.assertEqual(status, 0)
            self.assertIn("changed_count", json.loads(output))
            for suffix in ("schema", "item-schema", "capabilities"):
                status, output = self.capture_cli([self.DIFF + "-" + suffix])
                self.assertEqual(status, 0)
                self.assertIsInstance(json.loads(output), dict)


class ReviewApiTests(ReviewFixture):
    PREFIX = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review"

    def test_api_review_schema_capabilities_and_build(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "gate"
            gate.write_federation_assurance_gate(self.ready_gate, source)
            server = create_server("127.0.0.1", 0)
            server.glio_assurance_history_series_release_registry_federation_gate_directory = str(source)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                for suffix in ("/schema", "/queue-schema", "/verification-schema", "/item-schema", "/query-schema", "/manifest-schema", "/capabilities"):
                    with urlopen(base + self.PREFIX + suffix) as response:
                        self.assertEqual(response.status, 200)
                        self.assertIsInstance(json.loads(response.read()), dict)
                with urlopen(base + self.PREFIX + "?input=" + str(source) + "&format=summary") as response:
                    payload = json.loads(response.read())
                    self.assertEqual(response.status, 200)
                    self.assertEqual(payload["state"], "clear")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_api_query_and_ledger_route_round_trip(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "gate"
            queue_directory = Path(temporary) / "review"
            ledger_directory = Path(temporary) / "ledger"
            gate.write_federation_assurance_gate(self.held_gate, source)
            review.write_review(self.held_review, queue_directory)
            review.write_decision_ledger(review.build_decision_ledger(self.held_review), ledger_directory)
            server = create_server("127.0.0.1", 0)
            server.glio_assurance_history_series_release_registry_federation_gate_review_directory = str(queue_directory)
            server.glio_assurance_history_series_release_registry_federation_gate_review_decision_ledger_directory = str(ledger_directory)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                with urlopen(base + self.PREFIX + "/query?input=" + str(queue_directory) + "&resource=warnings") as response:
                    payload = json.loads(response.read())
                    self.assertGreater(payload["total_count"], 0)
                ledger_prefix = self.PREFIX + "/decision-ledger"
                with urlopen(base + ledger_prefix + "/query?input=" + str(ledger_directory) + "&resource=summary") as response:
                    payload = json.loads(response.read())
                    self.assertEqual(payload["total_count"], 1)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_api_append_route_requires_head_and_persists_next_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            queue_directory = root / "review"
            ledger_directory = root / "ledger"
            next_directory = root / "ledger-next"
            review.write_review(self.held_review, queue_directory)
            ledger = review.build_decision_ledger(self.held_review)
            review.write_decision_ledger(ledger, ledger_directory)
            item = self.failed_item(self.held_review.queue)
            server = create_server("127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                payload = {
                    "directory": str(ledger_directory),
                    "item_id": item.item_id,
                    "action": "remediate",
                    "rationale": "downloaded review evidence is attached",
                    "evidence_address": self.evidence(9),
                    "expected_head": review.INITIAL_HEAD,
                    "destination": str(next_directory),
                }
                request = Request(
                    f"http://127.0.0.1:{server.server_port}{self.PREFIX}/decision-ledger/append",
                    data=canonical_bytes(payload),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with self.assertRaises(HTTPError) as raised:
                    urlopen(request)
                self.assertEqual(raised.exception.code, 422)
                self.assertEqual(review.load_decision_ledger(next_directory).entry_count, 1)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


class ReviewFailureMatrixTests(ReviewFixture):
    def test_queue_verification_rejects_wrong_gate_link(self):
        payload = self.ready_review.verification.to_dict()
        payload["gate_address"] = "gate:wrong"
        with self.assertRaises(ValidationError):
            review.verification_from_mapping(payload)

    def test_queue_loader_rejects_directory_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target"
            target.mkdir()
            link = root / "link"
            try:
                link.symlink_to(target, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks unavailable")
            with self.assertRaises(ValidationError):
                review.load_review(link)

    def test_decision_from_mapping_rejects_unknown_action(self):
        item = self.failed_item(self.held_review.queue)
        payload = {"ordinal": 0, "decision_id": "decision:one", "item_id": item.item_id, "item_address": item.content_address, "action": "unknown", "rationale": "bad", "evidence_address": review.NO_EVIDENCE, "previous_address": review.INITIAL_HEAD, "content_address": "pending:decision"}
        with self.assertRaises(ValidationError):
            review.decision_from_mapping(payload)

    def test_decision_requires_no_unexpected_evidence_for_acknowledge(self):
        item = self.failed_item(self.held_review.queue)
        payload = {"ordinal": 0, "decision_id": "decision:one", "item_id": item.item_id, "item_address": item.content_address, "action": "acknowledge", "rationale": "bad", "evidence_address": "evidence:unexpected", "previous_address": review.INITIAL_HEAD, "content_address": "pending:decision"}
        with self.assertRaises(ValidationError):
            review.decision_from_mapping(payload)

    def test_reopen_requires_handled_state(self):
        item = self.failed_item(self.held_review.queue)
        ledger = review.build_decision_ledger(self.held_review)
        with self.assertRaises(ValidationError):
            review.append_decision(ledger, item_id=item.item_id, action="reopen", rationale="not handled", expected_head_address=ledger.head_address)

    def test_diff_loader_rejects_missing_manifest(self):
        value = review.build_decision_diff(review.build_decision_ledger(self.ready_review), review.build_decision_ledger(self.ready_review))
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "diff"
            review.write_decision_diff(value, destination)
            (destination / review.MANIFEST_NAME).unlink()
            with self.assertRaises(ValidationError):
                review.load_decision_diff(destination)

    def test_query_result_rejects_more_rows_than_limit(self):
        result = review.query_review(self.ready_review, resource="items", limit=2)
        result.returned = tuple(list(result.returned) + [result.returned[0], result.returned[1]])
        with self.assertRaises(ValidationError):
            review.verify_review_query(result)

    def test_public_projection_rejects_forbidden_mapping(self):
        with self.assertRaises(ValidationError):
            review.queue_from_mapping(self.ready_review.queue.to_dict() | {"agent": "forbidden"})


if __name__ == "__main__":
    unittest.main()
