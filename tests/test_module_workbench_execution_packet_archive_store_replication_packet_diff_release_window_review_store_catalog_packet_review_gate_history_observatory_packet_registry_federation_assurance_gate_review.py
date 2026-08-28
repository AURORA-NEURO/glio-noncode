"""Deep contract coverage for federation review routing and snapshot diffs."""

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

import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history as history
import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet as packet
import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry as registry
import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation as federation
import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate as assurance_gate
import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review as review
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_bytes, canonical_json
from tests.test_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate import (
    AssuranceGateFixture,
)


class ReviewFixture(AssuranceGateFixture):
    def build_ready_queue(self, queue_id: str = "queue:ready"):
        return review.build_review_queue(self.build_ready_gate(), queue_id=queue_id)

    def build_held_queue(self, queue_id: str = "queue:held"):
        return review.build_review_queue(self.build_held_gate(), queue_id=queue_id)

    def build_blocked_queue(self, queue_id: str = "queue:blocked"):
        return review.build_review_queue(self.build_blocked_gate(), queue_id=queue_id)

    def build_empty_queue(self, queue_id: str = "queue:empty"):
        return review.build_review_queue(self.build_empty_gate(), queue_id=queue_id)

    @staticmethod
    def write_queue(value, destination, **kwargs):
        return review.write_review_queue(value, destination, **kwargs)

    def build_real_gate(self, root: Path):
        source = self.real_packet()
        if not source.is_dir():
            self.skipTest("retained downloaded packet fixture is not installed")
        history_value = history.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_from_directories(
            source,
            source,
            history_id="history:review-real",
        )
        history_directory = history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            history_value,
            root / "history",
        )
        packet_one = packet.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_from_history_directories(
            (history_directory, history_directory),
            observation_ids=("review-real-a", "review-real-b"),
            packet_id="packet:review-real-a",
        )
        packet_two = packet.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_from_history_directories(
            (history_directory, history_directory),
            observation_ids=("review-real-c", "review-real-d"),
            packet_id="packet:review-real-b",
        )
        registry_one = registry.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
            (packet_one,),
            registry_id="registry:review-real-a",
        )
        registry_two = registry.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
            (packet_two,),
            registry_id="registry:review-real-b",
        )
        registry_one_directory = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
            registry_one,
            root / "registry-a",
        )
        registry_two_directory = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
            registry_two,
            root / "registry-b",
        )
        federation_value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_from_directories(
            (registry_two_directory, registry_one_directory),
            federation_id="federation:review-real",
        )
        return assurance_gate.build_federation_assurance_gate(
            federation_value,
            assurance_id="assurance:review-real",
            gate_id="gate:review-real",
        )

    @staticmethod
    def reduced_queue(value, count: int, queue_id: str):
        items = tuple(value.items[:count])
        body = value.summary()
        body.update(
            {
                "queue_id": queue_id,
                "item_count": len(items),
                "clear_count": sum(item.state == "clear" for item in items),
                "warning_count": sum(item.state == "review" for item in items),
                "blocker_count": sum(item.state == "blocked" for item in items),
                "open_count": sum(item.state != "clear" for item in items),
                "critical_count": sum(item.priority == "critical" for item in items),
                "items": items,
                "content_address": "pending:queue",
            }
        )
        provisional = review.FederationReviewQueue(**body)
        body["content_address"] = review.address_review_queue(provisional)
        return review.FederationReviewQueue(**body)


class ReviewQueueCoreTests(ReviewFixture):
    def test_ready_queue_routes_every_finding_and_check(self):
        value = self.build_ready_queue()
        self.assertEqual(value.state, "clear")
        self.assertTrue(value.accepted)
        self.assertTrue(value.release_ready)
        self.assertEqual(value.item_count, 36)
        self.assertEqual(value.clear_count, 36)
        self.assertEqual(value.warning_count, 0)
        self.assertEqual(value.blocker_count, 0)
        self.assertEqual(value.open_count, 0)
        self.assertEqual(value.critical_count, 0)

    def test_queue_preserves_the_assurance_then_gate_order(self):
        value = self.build_ready_queue()
        self.assertEqual(
            [item.record_type for item in value.items],
            ["finding"] * 21 + ["check"] * 15,
        )
        self.assertEqual([item.ordinal for item in value.items], list(range(36)))
        self.assertEqual(len({item.record_id for item in value.items}), 36)
        self.assertEqual(
            [item.kind for item in value.items[:5]],
            [
                "federation-address",
                "version-boundary",
                "registry-conservation",
                "hydrated-members",
                "registry-addresses",
            ],
        )

    def test_queue_items_have_deterministic_addresses(self):
        first = self.build_ready_queue()
        second = self.build_ready_queue()
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(
            [item.content_address for item in first.items],
            [item.content_address for item in second.items],
        )
        self.assertEqual(
            review.address_review_queue(first),
            first.content_address,
        )
        self.assertTrue(
            all(review.address_review_item(item) == item.content_address for item in first.items)
        )

    def test_queue_can_use_an_explicit_public_identifier(self):
        value = self.build_ready_queue("queue:explicit")
        self.assertEqual(value.queue_id, "queue:explicit")
        self.assertTrue(value.content_address.startswith(review.REVIEW_PREFIX + ":"))
        self.assertNotEqual(value.content_address, self.build_ready_queue().content_address)

    def test_queue_is_path_free_and_public(self):
        value = self.build_ready_queue()
        payload = canonical_json(value.to_dict()).casefold()
        self.assertNotIn("source_path", payload)
        self.assertNotIn(str(self.real_packet()).casefold(), payload)
        for forbidden in ("agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"):
            self.assertNotIn(f'"{forbidden}"', payload)

    def test_held_queue_is_accepted_but_routes_open_review(self):
        value = self.build_held_queue()
        self.assertEqual(value.gate_state, "hold")
        self.assertEqual(value.state, "review")
        self.assertTrue(value.accepted)
        self.assertFalse(value.release_ready)
        self.assertGreater(value.warning_count, 0)
        self.assertEqual(value.blocker_count, 0)
        self.assertEqual(value.open_count, value.warning_count)
        self.assertEqual(value.critical_count, 0)
        self.assertTrue(all(item.state != "blocked" for item in value.items))

    def test_blocked_queue_routes_critical_blockers(self):
        value = self.build_blocked_queue()
        self.assertEqual(value.gate_state, "block")
        self.assertEqual(value.state, "blocked")
        self.assertFalse(value.accepted)
        self.assertFalse(value.release_ready)
        self.assertGreater(value.blocker_count, 0)
        self.assertEqual(value.open_count, value.warning_count + value.blocker_count)
        self.assertEqual(value.critical_count, value.blocker_count)
        self.assertTrue(all(item.priority == "critical" for item in value.items if not item.passed and item.state == "blocked"))

    def test_empty_federation_remains_visible_as_review(self):
        value = self.build_empty_queue()
        self.assertEqual(value.gate_state, "hold")
        self.assertEqual(value.state, "review")
        self.assertTrue(value.accepted)
        self.assertFalse(value.release_ready)
        self.assertGreaterEqual(value.warning_count, 1)

    def test_item_state_and_priority_conserve_source_evidence(self):
        value = self.build_blocked_queue()
        for item in value.items:
            if item.passed:
                self.assertEqual((item.state, item.priority, item.severity), ("clear", "none", "pass"))
            elif item.severity == "blocker" or item.required is True:
                self.assertEqual((item.state, item.priority), ("blocked", "critical"))
            else:
                self.assertEqual((item.state, item.priority), ("review", "high"))

    def test_invalid_gate_type_is_rejected(self):
        with self.assertRaises(ValidationError):
            review.build_review_queue({})

    def test_invalid_queue_identifiers_are_rejected(self):
        with self.assertRaises(ValidationError):
            self.build_ready_queue(" ")
        with self.assertRaises(ValidationError):
            self.build_ready_queue("q" * 257)

    def test_mapping_round_trip_preserves_queue(self):
        value = self.build_ready_queue()
        restored = review.review_queue_from_mapping(value.to_dict())
        self.assertEqual(restored.to_dict(), value.to_dict())
        self.assertEqual(restored.content_address, value.content_address)
        self.assertEqual(
            [item.to_dict() for item in restored.items],
            [item.to_dict() for item in value.items],
        )

    def test_mapping_round_trip_preserves_each_item(self):
        value = self.build_ready_queue()
        for item in value.items:
            restored = review.federation_review_item_from_mapping(item.to_dict())
            self.assertEqual(restored.to_dict(), item.to_dict())

    def test_mapping_rejects_unknown_queue_fields(self):
        body = self.build_ready_queue().to_dict()
        body["source_path"] = "not-public"
        with self.assertRaises(ValidationError):
            review.review_queue_from_mapping(body)

    def test_mapping_rejects_unknown_item_fields(self):
        body = self.build_ready_queue().items[0].to_dict()
        body["agent"] = "forbidden"
        with self.assertRaises(ValidationError):
            review.federation_review_item_from_mapping(body)

    def test_queue_verification_rejects_tampered_item_address(self):
        value = self.build_ready_queue()
        body = value.to_dict()
        body["items"][0]["remediation"] = "changed"
        with self.assertRaises(ValidationError):
            review.review_queue_from_mapping(body)

    def test_queue_verification_rejects_tampered_queue_address(self):
        value = self.build_ready_queue()
        body = value.to_dict()
        body["content_address"] = "review:tampered"
        with self.assertRaises(ValidationError):
            review.review_queue_from_mapping(body)


class ReviewDiffCoreTests(ReviewFixture):
    def test_same_snapshot_is_unchanged(self):
        value = self.build_ready_queue()
        diff = review.build_review_diff(value, value, diff_id="diff:same")
        self.assertEqual(diff.state, "unchanged")
        self.assertEqual(diff.item_count, 36)
        self.assertEqual(diff.unchanged_count, 36)
        self.assertEqual(diff.changed_count, 0)
        self.assertEqual(diff.added_count, 0)
        self.assertEqual(diff.removed_count, 0)
        self.assertEqual(diff.resolved_count, 0)
        self.assertTrue(all(item.action == "unchanged" for item in diff.items))

    def test_held_to_ready_is_improved_and_resolves_items(self):
        baseline = self.build_held_queue()
        candidate = self.build_ready_queue()
        diff = review.build_review_diff(baseline, candidate, diff_id="diff:recovered")
        self.assertEqual(diff.state, "improved")
        self.assertEqual(diff.baseline_state, "review")
        self.assertEqual(diff.candidate_state, "clear")
        self.assertGreater(diff.changed_count, 0)
        self.assertGreater(diff.resolved_count, 0)
        self.assertEqual(diff.item_count, 36)
        self.assertEqual(diff.changed_count + diff.unchanged_count, diff.item_count)

    def test_ready_to_blocked_is_regressed(self):
        baseline = self.build_ready_queue()
        candidate = self.build_blocked_queue()
        diff = review.build_review_diff(baseline, candidate, diff_id="diff:regressed")
        self.assertEqual(diff.state, "regressed")
        self.assertEqual(diff.baseline_state, "clear")
        self.assertEqual(diff.candidate_state, "blocked")
        self.assertGreater(diff.changed_count, 0)
        self.assertEqual(diff.resolved_count, 0)

    def test_removed_and_added_records_are_explicit(self):
        full = self.build_ready_queue()
        reduced = self.reduced_queue(full, 35, "queue:reduced")
        added = review.build_review_diff(reduced, full, diff_id="diff:added")
        removed = review.build_review_diff(full, reduced, diff_id="diff:removed")
        self.assertEqual(added.added_count, 1)
        self.assertEqual(added.removed_count, 0)
        self.assertTrue(any(item.action == "added" for item in added.items))
        self.assertEqual(removed.removed_count, 1)
        self.assertEqual(removed.added_count, 0)
        self.assertTrue(any(item.action == "removed" for item in removed.items))

    def test_diff_item_keys_are_stable_and_unique(self):
        diff = review.build_review_diff(self.build_held_queue(), self.build_ready_queue())
        self.assertEqual(len({item.key for item in diff.items}), diff.item_count)
        self.assertEqual(
            [item.ordinal for item in diff.items],
            list(range(diff.item_count)),
        )
        self.assertTrue(all(item.record_type in {"finding", "check"} for item in diff.items))
        self.assertTrue(all(item.plane and item.kind for item in diff.items))

    def test_diff_addresses_are_deterministic(self):
        baseline = self.build_held_queue()
        candidate = self.build_ready_queue()
        first = review.build_review_diff(baseline, candidate)
        second = review.build_review_diff(baseline, candidate)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(review.address_review_diff(first), first.content_address)
        self.assertTrue(all(review.address_review_diff_item(item) == item.content_address for item in first.items))

    def test_diff_mapping_round_trip(self):
        value = review.build_review_diff(self.build_held_queue(), self.build_ready_queue())
        restored = review.review_diff_from_mapping(value.to_dict())
        self.assertEqual(restored.to_dict(), value.to_dict())
        self.assertEqual(restored.content_address, value.content_address)

    def test_diff_item_mapping_round_trip(self):
        value = review.build_review_diff(self.build_held_queue(), self.build_ready_queue())
        for item in value.items:
            restored = review.federation_review_diff_item_from_mapping(item.to_dict())
            self.assertEqual(restored.to_dict(), item.to_dict())

    def test_diff_mapping_rejects_unknown_fields(self):
        body = review.build_review_diff(self.build_ready_queue(), self.build_ready_queue()).to_dict()
        body["private"] = True
        with self.assertRaises(ValidationError):
            review.review_diff_from_mapping(body)

    def test_diff_verification_rejects_tampered_item(self):
        value = review.build_review_diff(self.build_held_queue(), self.build_ready_queue())
        body = value.to_dict()
        body["items"][0]["remediation"] = "tampered"
        with self.assertRaises(ValidationError):
            review.review_diff_from_mapping(body)

    def test_diff_verification_rejects_tampered_address(self):
        value = review.build_review_diff(self.build_held_queue(), self.build_ready_queue())
        body = value.to_dict()
        body["content_address"] = "diff:tampered"
        with self.assertRaises(ValidationError):
            review.review_diff_from_mapping(body)

    def test_diff_requires_typed_snapshots(self):
        with self.assertRaises(ValidationError):
            review.build_review_diff({}, self.build_ready_queue())
        with self.assertRaises(ValidationError):
            review.build_review_diff(self.build_ready_queue(), {})


class ReviewQueryTests(ReviewFixture):
    def test_summary_query_returns_one_summary(self):
        value = self.build_ready_queue()
        result = review.query_review_queue(value, resource="summary")
        self.assertEqual(result.total_count, 1)
        self.assertEqual(result.returned_count, 1)
        self.assertEqual(result.items[0], value.summary())
        self.assertEqual(result.source_address, value.content_address)

    def test_items_query_returns_all_items(self):
        result = review.query_review_queue(self.build_ready_queue(), resource="items", limit=128)
        self.assertEqual(result.total_count, 36)
        self.assertEqual(result.returned_count, 36)

    def test_queue_resource_filters_are_disjoint(self):
        value = self.build_blocked_queue()
        open_result = review.query_review_queue(value, resource="open", limit=128)
        blockers = review.query_review_queue(value, resource="blockers", limit=128)
        warnings = review.query_review_queue(value, resource="warnings", limit=128)
        clear = review.query_review_queue(value, resource="clear", limit=128)
        self.assertEqual(open_result.total_count, value.open_count)
        self.assertEqual(blockers.total_count, value.blocker_count)
        self.assertEqual(warnings.total_count, value.warning_count)
        self.assertEqual(clear.total_count, value.clear_count)
        self.assertEqual(
            open_result.total_count,
            blockers.total_count + warnings.total_count,
        )
        self.assertEqual(
            {item["content_address"] for item in blockers.items}.intersection(
                item["content_address"] for item in warnings.items
            ),
            set(),
        )

    def test_queue_filter_by_record_type(self):
        value = self.build_ready_queue()
        findings = review.query_review_queue(value, resource="items", record_type="finding", limit=128)
        checks = review.query_review_queue(value, resource="items", record_type="check", limit=128)
        self.assertEqual(findings.total_count, 21)
        self.assertEqual(checks.total_count, 15)
        self.assertTrue(all(item["record_type"] == "finding" for item in findings.items))
        self.assertTrue(all(item["record_type"] == "check" for item in checks.items))

    def test_queue_filter_by_state_priority_and_passed(self):
        value = self.build_blocked_queue()
        blockers = review.query_review_queue(value, resource="items", state="blocked", priority="critical", passed=False, limit=128)
        self.assertEqual(blockers.total_count, value.blocker_count)
        self.assertTrue(all(item["state"] == "blocked" for item in blockers.items))
        self.assertTrue(all(item["priority"] == "critical" for item in blockers.items))
        self.assertTrue(all(item["passed"] is False for item in blockers.items))

    def test_queue_filter_by_plane(self):
        value = self.build_ready_queue()
        federation_items = review.query_review_queue(value, resource="items", plane="federation", limit=128)
        self.assertGreater(federation_items.total_count, 0)
        self.assertTrue(all(item["plane"] == "federation" for item in federation_items.items))

    def test_queue_text_filter_is_case_insensitive(self):
        value = self.build_ready_queue()
        result = review.query_review_queue(value, resource="items", text="PUBLIC", limit=128)
        self.assertGreater(result.total_count, 0)
        self.assertTrue(all("public" in canonical_json(item).casefold() for item in result.items))

    def test_queue_pagination_is_bounded_and_ordered(self):
        value = self.build_ready_queue()
        first = review.query_review_queue(value, resource="items", offset=0, limit=7)
        second = review.query_review_queue(value, resource="items", offset=7, limit=7)
        self.assertEqual(first.returned_count, 7)
        self.assertEqual(second.returned_count, 7)
        self.assertEqual(first.items[-1]["ordinal"] + 1, second.items[0]["ordinal"])
        at_end = review.query_review_queue(value, resource="items", offset=36, limit=1)
        self.assertEqual(at_end.total_count, 36)
        self.assertEqual(at_end.returned_count, 0)

    def test_query_object_and_kwargs_cannot_be_combined(self):
        value = self.build_ready_queue()
        query = review.ReviewQuery(resource="items")
        with self.assertRaises(ValidationError):
            review.query_review_queue(value, query, limit=2)
        diff = review.build_review_diff(value, value)
        with self.assertRaises(ValidationError):
            review.query_review_diff(diff, query, limit=2)

    def test_invalid_query_values_are_rejected(self):
        value = self.build_ready_queue()
        for kwargs in (
            {"resource": "not-a-resource"},
            {"resource": "items", "state": "bad"},
            {"resource": "items", "priority": "bad"},
            {"resource": "items", "record_type": "bad"},
            {"resource": "items", "action": "bad"},
            {"resource": "items", "offset": -1},
            {"resource": "items", "limit": 0},
            {"resource": "items", "offset": 4090, "limit": 20},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                review.query_review_queue(value, **kwargs)

    def test_query_result_is_addressed_and_public(self):
        value = self.build_ready_queue()
        result = review.query_review_queue(value, resource="items", limit=4)
        self.assertIn(":", result.content_address)
        self.assertEqual(result.to_dict()["source_address"], value.content_address)
        payload = canonical_json(result.to_dict()).casefold()
        self.assertNotIn("source_path", payload)
        self.assertNotIn("private", payload)

    def test_diff_queries_expose_actions_and_resolutions(self):
        diff = review.build_review_diff(self.build_held_queue(), self.build_ready_queue())
        changed = review.query_review_diff(diff, resource="changed", limit=256)
        resolved = review.query_review_diff(diff, resource="resolved", limit=256)
        self.assertEqual(changed.total_count, diff.changed_count)
        self.assertEqual(resolved.total_count, diff.resolved_count)
        self.assertTrue(all(item["action"] == "changed" for item in changed.items))
        self.assertTrue(all(item["candidate_state"] == "clear" for item in resolved.items))

    def test_diff_queries_expose_added_removed_and_unchanged(self):
        full = self.build_ready_queue()
        reduced = self.reduced_queue(full, 35, "queue:reduced")
        diff = review.build_review_diff(reduced, full)
        self.assertEqual(review.query_review_diff(diff, resource="added", limit=256).total_count, 1)
        self.assertEqual(review.query_review_diff(diff, resource="removed", limit=256).total_count, 0)
        self.assertEqual(review.query_review_diff(diff, resource="unchanged", limit=256).total_count, 35)

    def test_query_mapping_round_trip(self):
        query = review.ReviewQuery(resource="items", state="review", priority="high", record_type="finding", plane="runtime", text="runtime", offset=2, limit=9)
        restored = review.ReviewQuery(**query.to_dict())
        self.assertEqual(restored.to_dict(), query.to_dict())
        self.assertEqual(review.address_review_query(restored), review.address_review_query(query))


class ReviewExportTests(ReviewFixture):
    def test_queue_json_is_canonical(self):
        value = self.build_ready_queue()
        payload = review.review_queue_json(value)
        self.assertEqual(payload, canonical_json(value.to_dict()))
        self.assertEqual(canonical_bytes(json.loads(payload)), payload.encode())

    def test_diff_json_is_canonical(self):
        value = review.build_review_diff(self.build_held_queue(), self.build_ready_queue())
        payload = review.review_diff_json(value)
        self.assertEqual(payload, canonical_json(value.to_dict()))
        self.assertEqual(canonical_bytes(json.loads(payload)), payload.encode())

    def test_queue_csv_has_stable_headers_and_all_rows(self):
        value = self.build_ready_queue()
        rows = list(csv.DictReader(StringIO(review.review_queue_csv(value))))
        self.assertEqual(len(rows), 36)
        self.assertEqual(
            list(rows[0]),
            ["ordinal", "record_type", "record_id", "plane", "kind", "severity", "required", "passed", "state", "priority", "remediation", "evidence_address", "content_address"],
        )

    def test_diff_csv_has_stable_headers_and_all_rows(self):
        value = review.build_review_diff(self.build_held_queue(), self.build_ready_queue())
        rows = list(csv.DictReader(StringIO(review.review_diff_csv(value))))
        self.assertEqual(len(rows), value.item_count)
        self.assertEqual(
            list(rows[0]),
            ["ordinal", "action", "key", "record_type", "plane", "kind", "baseline_state", "candidate_state", "baseline_priority", "candidate_priority", "remediation", "content_address"],
        )

    def test_query_csv_is_empty_for_an_empty_page(self):
        value = self.build_ready_queue()
        result = review.query_review_queue(value, resource="items", offset=36, limit=1)
        self.assertEqual(review.review_query_csv(result), "")

    def test_query_csv_contains_filtered_rows(self):
        value = self.build_ready_queue()
        result = review.query_review_queue(value, resource="items", record_type="check", limit=4)
        rows = list(csv.DictReader(StringIO(review.review_query_csv(result))))
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row["record_type"] == "check" for row in rows))

    def test_markdown_exports_have_human_titles(self):
        queue = self.build_ready_queue()
        diff = review.build_review_diff(self.build_held_queue(), queue)
        self.assertIn("# Observatory Packet Registry Federation Review Queue", review.render_review_queue_markdown(queue))
        self.assertIn("# Observatory Packet Registry Federation Review Diff", review.render_review_diff_markdown(diff))
        query = review.query_review_queue(queue, resource="items", limit=2)
        self.assertIn("# Observatory Packet Registry Federation Review Query", review.render_review_query_markdown(query))

    def test_empty_markdown_export_is_explicit(self):
        value = self.build_ready_queue()
        result = review.query_review_queue(value, resource="items", offset=36, limit=1)
        self.assertIn("No records.", review.render_review_query_markdown(result))

    def test_schemas_are_strict_and_versioned(self):
        for schema in (review.review_queue_schema(), review.review_diff_schema()):
            self.assertEqual(schema["type"], "object")
            self.assertTrue(schema["additionalProperties"] is False or "additionalProperties" not in schema)
            self.assertIn("$schema", schema)
            self.assertIn("title", schema)
            self.assertIn(review.VERSION, json.dumps(schema))
        query_schema = review.review_query_schema()
        self.assertEqual(query_schema["type"], "object")
        self.assertFalse(query_schema.get("additionalProperties", True))
        self.assertIn("resolved", json.dumps(query_schema))

    def test_capabilities_advertise_the_full_review_surface(self):
        capabilities = review.review_capabilities()
        self.assertEqual(capabilities["version"], review.VERSION)
        self.assertEqual(capabilities["boundary"], review.BOUNDARY)
        self.assertEqual(capabilities["queue"]["item_count"], 36)
        self.assertEqual(capabilities["queue"]["states"], ["clear", "review", "blocked"])
        self.assertEqual(capabilities["queue"]["priorities"], ["none", "high", "critical"])
        self.assertEqual(capabilities["diff"]["actions"], ["added", "removed", "unchanged", "changed"])
        self.assertTrue(capabilities["persistence"]["atomic_write"])
        self.assertTrue(capabilities["queries"]["pagination"])


class ReviewPersistenceTests(ReviewFixture):
    def test_persistence_has_exact_two_files(self):
        with tempfile.TemporaryDirectory() as root_text:
            destination = self.write_queue(self.build_ready_queue(), Path(root_text) / "queue")
            self.assertEqual({item.name for item in destination.iterdir()}, {"manifest.json", "review.json"})

    def test_persistence_round_trip_is_exact(self):
        value = self.build_ready_queue()
        with tempfile.TemporaryDirectory() as root_text:
            first = self.write_queue(value, Path(root_text) / "first")
            loaded = review.load_review_queue(first)
            self.assertEqual(loaded.to_dict(), value.to_dict())
            self.assertEqual(loaded.content_address, value.content_address)

    def test_persistence_bytes_are_repeatable(self):
        value = self.build_ready_queue()
        with tempfile.TemporaryDirectory() as root_text:
            first = self.write_queue(value, Path(root_text) / "first")
            second = self.write_queue(value, Path(root_text) / "second")
            self.assertEqual(
                {path.name: path.read_bytes() for path in first.iterdir()},
                {path.name: path.read_bytes() for path in second.iterdir()},
            )

    def test_manifest_contains_one_artifact_receipt(self):
        with tempfile.TemporaryDirectory() as root_text:
            destination = self.write_queue(self.build_ready_queue(), Path(root_text) / "queue")
            manifest = json.loads((destination / "manifest.json").read_text())
            self.assertEqual(manifest["artifact_count"], 1)
            self.assertEqual(manifest["files"], ["manifest.json", "review.json"])
            self.assertEqual(manifest["artifact"]["name"], "review.json")
            self.assertEqual(manifest["artifact"]["bytes"], (destination / "review.json").stat().st_size)
            self.assertEqual(manifest["manifest_address"], review._manifest_address({**manifest, "manifest_address": None}))

    def test_persistence_rejects_missing_file(self):
        with tempfile.TemporaryDirectory() as root_text:
            destination = self.write_queue(self.build_ready_queue(), Path(root_text) / "queue")
            (destination / "review.json").unlink()
            with self.assertRaises(ValidationError):
                review.load_review_queue(destination)

    def test_persistence_rejects_extra_file(self):
        with tempfile.TemporaryDirectory() as root_text:
            destination = self.write_queue(self.build_ready_queue(), Path(root_text) / "queue")
            (destination / "extra.json").write_text("{}")
            with self.assertRaises(ValidationError):
                review.load_review_queue(destination)

    def test_persistence_rejects_noncanonical_manifest(self):
        with tempfile.TemporaryDirectory() as root_text:
            destination = self.write_queue(self.build_ready_queue(), Path(root_text) / "queue")
            manifest = json.loads((destination / "manifest.json").read_text())
            (destination / "manifest.json").write_text(json.dumps(manifest, indent=2))
            with self.assertRaises(ValidationError):
                review.load_review_queue(destination)

    def test_persistence_rejects_tampered_manifest_address(self):
        with tempfile.TemporaryDirectory() as root_text:
            destination = self.write_queue(self.build_ready_queue(), Path(root_text) / "queue")
            manifest = json.loads((destination / "manifest.json").read_text())
            manifest["manifest_address"] = "manifest:tampered"
            (destination / "manifest.json").write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                review.load_review_queue(destination)

    def test_persistence_rejects_tampered_review_bytes(self):
        with tempfile.TemporaryDirectory() as root_text:
            destination = self.write_queue(self.build_ready_queue(), Path(root_text) / "queue")
            raw = (destination / "review.json").read_bytes()
            (destination / "review.json").write_bytes(raw + b" ")
            with self.assertRaises(ValidationError):
                review.load_review_queue(destination)

    def test_persistence_rejects_tampered_review_payload(self):
        with tempfile.TemporaryDirectory() as root_text:
            destination = self.write_queue(self.build_ready_queue(), Path(root_text) / "queue")
            body = json.loads((destination / "review.json").read_text())
            body["state"] = "blocked"
            (destination / "review.json").write_bytes(canonical_bytes(body))
            with self.assertRaises(ValidationError):
                review.load_review_queue(destination)

    def test_persistence_rejects_symlinked_review_document(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            destination = self.write_queue(self.build_ready_queue(), root / "queue")
            source = root / "review-source.json"
            source.write_bytes((destination / "review.json").read_bytes())
            (destination / "review.json").unlink()
            try:
                (destination / "review.json").symlink_to(source)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable in this environment")
            with self.assertRaises(ValidationError):
                review.load_review_queue(destination)

    def test_persistence_rejects_symlinked_directory(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            destination = self.write_queue(self.build_ready_queue(), root / "queue")
            alias = root / "alias"
            try:
                alias.symlink_to(destination, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable in this environment")
            with self.assertRaises(ValidationError):
                review.load_review_queue(alias)

    def test_persistence_refuses_nonempty_destination_without_overwrite(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            destination = self.write_queue(self.build_ready_queue(), root / "queue")
            with self.assertRaises(ValidationError):
                self.write_queue(self.build_ready_queue("queue:other"), destination)

    def test_persistence_overwrite_replaces_existing_queue(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            destination = self.write_queue(self.build_ready_queue(), root / "queue")
            replacement = self.build_ready_queue("queue:replacement")
            self.write_queue(replacement, destination, overwrite=True)
            self.assertEqual(review.load_review_queue(destination).to_dict(), replacement.to_dict())

    def test_load_rejects_non_directory_input(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            source = root / "file"
            source.write_text("not a directory")
            with self.assertRaises(ValidationError):
                review.load_review_queue(source)


class ReviewCliTests(ReviewFixture):
    base = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review"

    @staticmethod
    def run_cli_json(arguments):
        output = StringIO()
        with redirect_stdout(output):
            status = main(arguments)
        text = output.getvalue()
        return status, json.loads(text) if text.strip() else None, text

    def test_cli_builds_queue_from_persisted_gate_and_writes_exact_package(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            gate_directory = self.write_gate(self.build_ready_gate(), root / "gate")
            queue_directory = root / "queue"
            status, summary, _ = self.run_cli_json([
                self.base,
                "--input",
                str(gate_directory),
                "--queue-id",
                "queue:cli",
                "--destination",
                str(queue_directory),
                "--format",
                "summary",
            ])
            self.assertEqual(status, 0)
            self.assertEqual(summary["queue_id"], "queue:cli")
            self.assertEqual(summary["item_count"], 36)
            self.assertEqual(summary["state"], "clear")
            self.assertEqual({item.name for item in queue_directory.iterdir()}, {"manifest.json", "review.json"})

    def test_cli_query_verify_and_export_formats(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            queue_directory = self.write_queue(self.build_held_queue(), root / "queue")
            status, payload, _ = self.run_cli_json([
                self.base + "-query",
                "--input",
                str(queue_directory),
                "--resource",
                "open",
                "--limit",
                "256",
            ])
            self.assertEqual(status, 0)
            self.assertEqual(payload["total_count"], 5)
            self.assertEqual(payload["returned_count"], 5)
            status, payload, _ = self.run_cli_json([self.base + "-verify", "--input", str(queue_directory)])
            self.assertEqual(status, 0)
            self.assertTrue(payload["accepted"])
            for output_format, marker in (("csv", "record_id"), ("markdown", "# Observatory Packet Registry Federation Review Query")):
                output = StringIO()
                with redirect_stdout(output):
                    status = main([
                        self.base + "-query",
                        "--input",
                        str(queue_directory),
                        "--resource",
                        "items",
                        "--limit",
                        "2",
                        "--format",
                        output_format,
                    ])
                self.assertEqual(status, 0)
                self.assertIn(marker, output.getvalue())

    def test_cli_diff_and_diff_query_cover_recovery_and_resolution(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            baseline = self.write_queue(self.build_held_queue(), root / "baseline")
            candidate = self.write_queue(self.build_ready_queue(), root / "candidate")
            status, payload, _ = self.run_cli_json([
                self.base + "-diff",
                "--baseline",
                str(baseline),
                "--candidate",
                str(candidate),
                "--diff-id",
                "diff:cli",
                "--format",
                "summary",
            ])
            self.assertEqual(status, 0)
            self.assertEqual(payload["diff_id"], "diff:cli")
            self.assertEqual(payload["state"], "improved")
            self.assertGreater(payload["resolved_count"], 0)
            status, payload, _ = self.run_cli_json([
                self.base + "-diff-query",
                "--baseline",
                str(baseline),
                "--candidate",
                str(candidate),
                "--resource",
                "resolved",
                "--limit",
                "256",
            ])
            self.assertEqual(status, 0)
            self.assertEqual(payload["total_count"], payload["returned_count"])
            self.assertGreater(payload["total_count"], 0)
            for output_format, marker in (("csv", "action"), ("markdown", "# Observatory Packet Registry Federation Review Query")):
                output = StringIO()
                with redirect_stdout(output):
                    status = main([
                        self.base + "-diff-query",
                        "--baseline",
                        str(baseline),
                        "--candidate",
                        str(candidate),
                        "--resource",
                        "changed",
                        "--limit",
                        "256",
                        "--format",
                        output_format,
                    ])
                self.assertEqual(status, 0)
                self.assertIn(marker, output.getvalue())

    def test_cli_contract_commands_are_versioned_and_writable(self):
        commands = ("-schema", "-capabilities", "-diff-schema", "-query-schema")
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            for suffix in commands:
                destination = root / (suffix[1:] + ".json")
                status = main([self.base + suffix, "--output", str(destination)])
                self.assertEqual(status, 0)
                payload = json.loads(destination.read_text(encoding="utf-8"))
                self.assertIsInstance(payload, dict)
                if suffix != "-query-schema":
                    self.assertIn(review.VERSION, json.dumps(payload))


class ReviewApiTests(ReviewFixture):
    base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review"

    def start_server(self, root: Path):
        server = create_server("127.0.0.1", 0, root / "api-data")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def test_api_contract_routes_and_queue_summary(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            queue_directory = self.write_queue(self.build_ready_queue(), root / "queue")
            server, thread = self.start_server(root)
            try:
                for suffix in ("/schema", "/capabilities", "/diff/schema", "/query/schema"):
                    status, _, payload = self.http_json(server, self.base + suffix)
                    self.assertEqual(status, 200, suffix)
                    self.assertIsInstance(payload, dict)
                status, _, payload = self.http_json(server, self.base, {"input": str(queue_directory), "format": "summary"})
                self.assertEqual(status, 200)
                self.assertEqual(payload["item_count"], 36)
                self.assertEqual(payload["state"], "clear")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_api_query_verify_and_text_formats(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            queue_directory = self.write_queue(self.build_held_queue(), root / "queue")
            server, thread = self.start_server(root)
            try:
                status, _, payload = self.http_json(server, self.base + "/query", {"input": str(queue_directory), "resource": "warnings", "limit": "256"})
                self.assertEqual(status, 200)
                self.assertEqual(payload["total_count"], 5)
                status, _, payload = self.http_json(server, self.base + "/verify", {"input": str(queue_directory)})
                self.assertEqual(status, 200)
                self.assertTrue(payload["accepted"])
                for output_format, marker in (("csv", "record_id"), ("markdown", "# Observatory Packet Registry Federation Review Query")):
                    status, content_type, body = self.http_text(server, self.base + "/query", {"input": str(queue_directory), "resource": "items", "limit": "2", "format": output_format})
                    self.assertEqual(status, 200)
                    self.assertIn(marker, body)
                    self.assertTrue(content_type)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_api_diff_routes_recovery_and_filtering(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            baseline = self.write_queue(self.build_held_queue(), root / "baseline")
            candidate = self.write_queue(self.build_ready_queue(), root / "candidate")
            server, thread = self.start_server(root)
            try:
                status, _, payload = self.http_json(server, self.base + "/diff", {"baseline": str(baseline), "candidate": str(candidate), "format": "summary"})
                self.assertEqual(status, 200)
                self.assertEqual(payload["state"], "improved")
                status, _, payload = self.http_json(server, self.base + "/diff/query", {"baseline": str(baseline), "candidate": str(candidate), "resource": "resolved", "limit": "256"})
                self.assertEqual(status, 200)
                self.assertGreater(payload["total_count"], 0)
                for output_format, marker in (("csv", "action"), ("markdown", "# Observatory Packet Registry Federation Review Query")):
                    status, content_type, body = self.http_text(server, self.base + "/diff/query", {"baseline": str(baseline), "candidate": str(candidate), "resource": "changed", "limit": "256", "format": output_format})
                    self.assertEqual(status, 200)
                    self.assertIn(marker, body)
                    self.assertTrue(content_type)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


class ReviewRealDataTests(ReviewFixture):
    def test_real_downloaded_data_routes_into_review_queue(self):
        with tempfile.TemporaryDirectory() as root_text:
            queue = review.build_review_queue(self.build_real_gate(Path(root_text)))
            self.assertEqual(queue.item_count, 36)
            self.assertEqual(queue.state, "clear")
            self.assertTrue(queue.accepted)
            self.assertTrue(queue.release_ready)
            self.assertEqual(queue.warning_count, 0)
            self.assertEqual(queue.blocker_count, 0)

    def test_real_downloaded_review_queue_round_trips_without_source_paths(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            queue = review.build_review_queue(self.build_real_gate(root))
            destination = review.write_review_queue(queue, root / "queue")
            loaded = review.load_review_queue(destination)
            payload = canonical_json(loaded.to_dict()).casefold()
            self.assertEqual(loaded.content_address, queue.content_address)
            self.assertNotIn(str(self.real_packet()).casefold(), payload)
            self.assertNotIn("source_path", payload)

    def test_real_downloaded_review_diff_is_deterministic(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            first = review.build_review_queue(self.build_real_gate(root / "first"), queue_id="queue:real-a")
            second = review.build_review_queue(self.build_real_gate(root / "second"), queue_id="queue:real-b")
            diff_one = review.build_review_diff(first, second, diff_id="diff:real")
            diff_two = review.build_review_diff(first, second, diff_id="diff:real")
            self.assertEqual(diff_one.to_dict(), diff_two.to_dict())
            self.assertEqual(diff_one.state, "unchanged")
            self.assertEqual(diff_one.item_count, 36)


if __name__ == "__main__":
    unittest.main()
