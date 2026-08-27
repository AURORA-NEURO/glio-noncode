"""Deep regression coverage for catalog packet transitions and reviews."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import json
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from http.client import HTTPConnection
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff as packet_diff
import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review as packet_review
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
    write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet,
    load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet,
    write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime import (
    run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime,
)
from glio_noncode.serialization import canonical_bytes, content_hash


class CatalogPacketDiffReviewTests(unittest.TestCase):
    """Exercise comparison, decision, persistence, and public transport contracts."""

    @staticmethod
    def _store(
        store_id: str,
        *,
        state: str = "ready",
        release_ready: bool = True,
        accepted: bool = True,
        window_address: str = "window:one",
        ledger_address: str | None = None,
    ) -> SimpleNamespace:
        ledger = SimpleNamespace(
            window_address=window_address,
            content_address=ledger_address or f"ledger:{store_id}",
            head_address=f"entry:{store_id}",
            entry_count=1,
        )
        return SimpleNamespace(
            store_id=store_id,
            content_address=f"store:{store_id}",
            ledger_address=ledger.content_address,
            head_address=ledger.head_address,
            entry_count=1,
            state=state,
            release_ready=release_ready,
            accepted=accepted,
            append_only=True,
            operation_count=1,
            ledger=ledger,
        )

    def _catalog(self, *stores: SimpleNamespace, catalog_id: str = "catalog"):
        return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
            stores,
            catalog_id=catalog_id,
        )

    def _components(self, catalog=None, **kwargs):
        catalog = catalog or self._catalog(self._store("alpha"), self._store("beta"))
        runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime(
            catalog
        )
        federation = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation(
            catalog,
            federation_id=kwargs.get("federation_id", "federation"),
            selected_window_address=kwargs.get("selected_window_address"),
            store_ids=kwargs.get("store_ids"),
            require_same_window=kwargs.get("require_same_window", True),
            require_unique_ledger=kwargs.get("require_unique_ledger", True),
            minimum_members=kwargs.get("minimum_members", 1),
            minimum_ready=kwargs.get("minimum_ready", 1),
        )
        assurance = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance(
            catalog,
            stores=getattr(catalog, "stores", ()),
            assurance_id=kwargs.get("assurance_id", "assurance"),
        )
        gate = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate(
            catalog,
            runtime,
            federation,
            assurance,
            gate_id=kwargs.get("gate_id", "gate"),
        )
        return catalog, runtime, federation, assurance, gate

    def _packet(self, catalog=None, **kwargs):
        catalog, runtime, federation, assurance, gate = self._components(catalog, **kwargs)
        return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
            catalog,
            runtime,
            federation,
            assurance,
            gate,
            packet_id=kwargs.get("packet_id", "packet"),
        )

    def _diff(self, left=None, right=None, **kwargs):
        return packet_diff.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
            left or self._packet(packet_id="left"),
            right or self._packet(packet_id="right"),
            diff_id=kwargs.get("diff_id", "diff"),
        )

    def _review(self, diff=None, **kwargs):
        return packet_review.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
            diff or self._diff(),
            review_id=kwargs.get("review_id", "review"),
            decision=kwargs.get("decision"),
            decision_id=kwargs.get("decision_id", "decision-0"),
            detail=kwargs.get("detail"),
        )

    @staticmethod
    def _write_packet(root: str | Path, packet, name: str) -> Path:
        destination = Path(root) / name
        write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
            packet, destination
        )
        return destination

    @staticmethod
    def _write_catalog(root: str | Path, catalog) -> Path:
        destination = Path(root) / "catalog"
        write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
            catalog, destination
        )
        return destination

    def _pair_directories(self, root: str | Path):
        left = self._write_packet(root, self._packet(packet_id="left"), "left")
        right = self._write_packet(root, self._packet(packet_id="right"), "right")
        return left, right

    def test_exact_packets_produce_five_unchanged_actions(self) -> None:
        packet = self._packet(packet_id="same")
        diff = self._diff(packet, packet)
        self.assertEqual(diff.state, "exact")
        self.assertEqual(diff.release_transition, "unchanged")
        self.assertEqual(diff.action_count, 5)
        self.assertEqual(diff.unchanged_count, 5)
        self.assertEqual(diff.changed_count, 0)
        self.assertEqual(diff.added_count, 0)
        self.assertEqual(diff.removed_count, 0)
        self.assertTrue(diff.accepted)
        self.assertTrue(diff.release_ready)
        self.assertEqual([item.action for item in diff.actions], ["unchanged"] * 5)

    def test_different_packet_ids_change_only_the_aggregate_boundary(self) -> None:
        left = self._packet(packet_id="left")
        right = self._packet(packet_id="right")
        diff = self._diff(left, right)
        self.assertEqual(diff.state, "changed")
        self.assertEqual(diff.release_transition, "unchanged")
        self.assertEqual(diff.unchanged_count, 5)
        self.assertEqual(diff.changed_count, 0)
        self.assertNotEqual(diff.left_packet_address, diff.right_packet_address)
        self.assertTrue(all(item.left_address == item.right_address for item in diff.actions))
        self.assertTrue(all(item.changed_fields == () for item in diff.actions))

    def test_changed_catalog_produces_changed_component_actions(self) -> None:
        left = self._packet(packet_id="left")
        right = self._packet(
            self._catalog(self._store("gamma"), catalog_id="new-catalog"), packet_id="right"
        )
        diff = self._diff(left, right)
        self.assertEqual(diff.state, "changed")
        self.assertGreater(diff.changed_count, 0)
        self.assertEqual(diff.action_count, 5)
        changed = [item for item in diff.actions if item.action == "changed"]
        self.assertTrue(changed)
        self.assertTrue(all(item.changed_fields for item in changed))
        self.assertTrue(all(item.left_byte_count > 0 for item in changed))
        self.assertTrue(all(item.right_byte_count > 0 for item in changed))

    def test_action_addresses_and_byte_measurements_are_conserved(self) -> None:
        diff = self._diff()
        self.assertEqual([item.ordinal for item in diff.actions], list(range(5)))
        for item in diff.actions:
            self.assertEqual(
                packet_diff.address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_action(
                    item
                ),
                item.content_address,
            )
            self.assertTrue(item.detail)
            self.assertTrue(item.accepted)
            for address in (
                item.left_address,
                item.right_address,
                item.left_byte_address,
                item.right_byte_address,
            ):
                self.assertTrue(address is None or ":" in address)

    def test_diff_summary_is_public_and_excludes_hydrated_packets(self) -> None:
        diff = self._diff()
        document = diff.to_dict()
        summary = diff.summary()
        for value in (document, summary):
            encoded = json.dumps(value).casefold()
            self.assertNotIn('"left_packet"', encoded)
            self.assertNotIn('"right_packet"', encoded)
            self.assertNotIn('"agent"', encoded)
            self.assertNotIn('"language"', encoded)
            self.assertNotIn('"model"', encoded)
            self.assertNotIn('"user"', encoded)
        self.assertNotIn("actions", summary)
        self.assertEqual(document["action_count"], 5)
        self.assertEqual(document["check_count"], 6)

    def test_diff_verification_has_addressed_ordered_checks(self) -> None:
        diff = self._diff()
        receipt = packet_diff.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
            diff
        )
        self.assertTrue(receipt.accepted)
        self.assertEqual(receipt.diff_address, diff.content_address)
        self.assertEqual(receipt.check_count, 7)
        self.assertEqual(receipt.passed_count, receipt.check_count)
        self.assertEqual(receipt.failed_count, 0)
        self.assertEqual([item.ordinal for item in receipt.checks], list(range(7)))
        self.assertTrue(all(item.passed for item in receipt.checks))
        self.assertTrue(all(":" in item.content_address for item in receipt.checks))

    def test_diff_verification_rejects_an_aggregate_mutation(self) -> None:
        diff = self._diff()
        diff.release_ready = False
        receipt = packet_diff.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
            diff
        )
        self.assertFalse(receipt.accepted)
        self.assertGreater(receipt.failed_count, 0)
        self.assertTrue(any(item.kind == "diff-address" for item in receipt.checks))

    def test_diff_verification_rejects_a_changed_action_measurement(self) -> None:
        diff = self._diff()
        diff.actions[0].right_byte_count = 0
        receipt = packet_diff.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
            diff
        )
        self.assertFalse(receipt.accepted)
        self.assertTrue(any(item.kind == "action-addresses" for item in receipt.checks))

    def test_diff_json_csv_and_markdown_are_deterministic(self) -> None:
        diff = self._diff()
        first = packet_diff.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_json(
            diff
        )
        second = packet_diff.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_json(
            diff
        )
        self.assertEqual(first, second)
        document = json.loads(first)
        self.assertEqual(document["content_address"], diff.content_address)
        self.assertEqual(len(document["actions"]), 5)
        rows = list(
            csv.DictReader(
                packet_diff.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_csv(
                    diff
                ).splitlines()
            )
        )
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]["artifact_kind"], "catalog")
        markdown = packet_diff.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_markdown(
            diff
        )
        self.assertIn("Catalog Packet Diff", markdown)
        self.assertIn(diff.content_address, markdown)
        self.assertIn("catalog", markdown)

    def test_diff_query_supports_summary_actions_checks_filters_and_paging(self) -> None:
        diff = self._diff()
        summary = packet_diff.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
            diff, resource="summary", offset=0, limit=1
        )
        actions = packet_diff.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
            diff, resource="actions", artifact_kind="gate", offset=0, limit=1
        )
        checks = packet_diff.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
            diff, resource="checks", text="public", offset=0, limit=1
        )
        self.assertEqual(summary["total"], 1)
        self.assertEqual(actions["total"], 1)
        self.assertEqual(actions["items"][0]["artifact_kind"], "gate")
        self.assertEqual(checks["total"], 1)
        self.assertEqual(checks["items"][0]["kind"], "public-boundary")
        for result in (summary, actions, checks):
            self.assertTrue(
                packet_diff.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_query(
                    result
                )
            )

    def test_diff_query_action_filter_and_offset_are_honored(self) -> None:
        diff = self._diff()
        result = packet_diff.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
            diff, action="unchanged", offset=2, limit=2
        )
        self.assertEqual(result["total"], 5)
        self.assertEqual(result["offset"], 2)
        self.assertEqual(result["limit"], 2)
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual([item["ordinal"] for item in result["items"]], [2, 3])

    def test_diff_query_receipt_rejects_mutation(self) -> None:
        result = packet_diff.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
            self._diff()
        )
        result["total"] = 99
        with self.assertRaises(ValidationError):
            packet_diff.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_query(
                result
            )

    def test_diff_query_rejects_unknown_filters_and_invalid_bounds(self) -> None:
        diff = self._diff()
        invalid = (
            {"resource": "unknown"},
            {"action": "unknown"},
            {"artifact_kind": "unknown"},
            {"offset": -1},
            {"limit": 0},
            {"limit": 513},
            {"offset": True},
            {"limit": True},
        )
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                packet_diff.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
                    diff, **kwargs
                )

    def test_diff_query_exports_are_deterministic(self) -> None:
        result = packet_diff.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
            self._diff(), resource="actions", limit=2
        )
        encoded = packet_diff.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_query_json(
            result
        )
        rows = list(
            csv.DictReader(
                packet_diff.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_query_csv(
                    result
                ).splitlines()
            )
        )
        markdown = packet_diff.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_query_markdown(
            result
        )
        self.assertEqual(len(json.loads(encoded)["items"]), 2)
        self.assertEqual(len(rows), 2)
        self.assertIn("Catalog Packet Diff Query", markdown)

    def test_diff_schema_and_capabilities_are_identity_free(self) -> None:
        values = (
            packet_diff.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_schema(),
            packet_diff.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_capabilities(),
            packet_diff.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_query_schema(),
            packet_diff.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_query_capabilities(),
        )
        for value in values:
            encoded = json.dumps(value).casefold()
            self.assertNotIn('"agent"', encoded)
            self.assertNotIn('"language"', encoded)
            self.assertNotIn('"model"', encoded)
            self.assertNotIn('"user"', encoded)
        self.assertEqual(values[0]["actions"], ["unchanged", "changed", "added", "removed"])
        self.assertEqual(values[0]["resources"], ["summary", "actions", "checks"])
        self.assertTrue(values[1]["addressed_checks"])
        self.assertTrue(values[1]["fail_closed"])
        self.assertTrue(values[2]["addressed_receipts"])

    def test_diff_from_directories_rehydrates_both_packets(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            diff = packet_diff.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_from_directories(
                left, right, diff_id="directory-diff"
            )
            self.assertEqual(diff.diff_id, "directory-diff")
            self.assertEqual(diff.left_packet_id, "left")
            self.assertEqual(diff.right_packet_id, "right")
            self.assertTrue(
                packet_diff.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
                    diff
                ).accepted
            )

    def test_release_transitions_cover_hold_and_block(self) -> None:
        ready = self._packet(packet_id="ready")
        held = self._packet(
            self._catalog(
                self._store("held", state="held", release_ready=False), catalog_id="held"
            ),
            packet_id="held",
        )
        blocked = self._packet(
            self._catalog(
                self._store("blocked", state="blocked", release_ready=False, accepted=False),
                catalog_id="blocked",
            ),
            packet_id="blocked",
        )
        self.assertEqual(self._diff(ready, held).release_transition, "held")
        self.assertEqual(self._diff(ready, blocked).release_transition, "blocked")

    def test_release_transitions_cover_recovery_and_regression(self) -> None:
        blocked = self._packet(
            self._catalog(
                self._store("blocked", state="blocked", release_ready=False, accepted=False),
                catalog_id="blocked",
            ),
            packet_id="blocked",
        )
        held = self._packet(
            self._catalog(
                self._store("held", state="held", release_ready=False), catalog_id="held"
            ),
            packet_id="held",
        )
        ready = self._packet(packet_id="ready")
        self.assertEqual(self._diff(blocked, held).release_transition, "recovered")
        self.assertEqual(self._diff(blocked, ready).release_transition, "recovered")
        self.assertEqual(self._diff(held, blocked).release_transition, "blocked")

    def test_diff_loader_rejects_missing_packet_directory(self) -> None:
        with self.assertRaises(ValidationError):
            packet_diff.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_from_directories(
                "missing-left", "missing-right"
            )

    def test_default_ready_review_promotes(self) -> None:
        diff = self._diff(self._packet(packet_id="left"), self._packet(packet_id="right"))
        review = self._review(diff)
        self.assertEqual(review.entry_count, 1)
        self.assertEqual(review.state, "ready")
        self.assertTrue(review.release_ready)
        self.assertTrue(review.accepted)
        self.assertEqual(review.entries[0].decision, "promote")
        self.assertFalse(review.entries[0].action_required)
        self.assertEqual(review.head_address, review.entries[0].content_address)

    def test_default_held_review_holds_accepted_nonready_evidence(self) -> None:
        left = self._packet(packet_id="left")
        right = self._packet(
            self._catalog(
                self._store("held", state="held", release_ready=False), catalog_id="held"
            ),
            packet_id="right",
        )
        review = self._review(self._diff(left, right))
        self.assertEqual(review.entries[0].decision, "hold")
        self.assertEqual(review.state, "held")
        self.assertTrue(review.accepted)
        self.assertFalse(review.release_ready)
        self.assertTrue(review.entries[0].action_required)

    def test_default_blocked_review_blocks_rejected_evidence(self) -> None:
        left = self._packet(packet_id="left")
        right = self._packet(
            self._catalog(
                self._store("blocked", state="blocked", release_ready=False, accepted=False),
                catalog_id="blocked",
            ),
            packet_id="right",
        )
        review = self._review(self._diff(left, right))
        self.assertEqual(review.entries[0].decision, "block")
        self.assertEqual(review.state, "blocked")
        self.assertFalse(review.release_ready)
        self.assertTrue(review.entries[0].action_required)

    def test_explicit_review_decisions_obey_typed_constraints(self) -> None:
        ready_diff = self._diff()
        held_diff = self._diff(
            self._packet(packet_id="left"),
            self._packet(
                self._catalog(
                    self._store("held", state="held", release_ready=False), catalog_id="held"
                ),
                packet_id="right",
            ),
        )
        self.assertEqual(self._review(ready_diff, decision="supersede").state, "held")
        self.assertEqual(self._review(held_diff, decision="hold").state, "held")
        self.assertEqual(self._review(held_diff, decision="block").state, "blocked")
        with self.assertRaises(ValidationError):
            self._review(ready_diff, decision="hold")
        with self.assertRaises(ValidationError):
            self._review(ready_diff, decision="block")

    def test_review_summary_and_entries_retain_diff_evidence(self) -> None:
        diff = self._diff()
        review = self._review(
            diff, review_id="review-id", decision_id="decision-id", detail="explicit rationale"
        )
        entry = review.entries[0]
        self.assertEqual(entry.diff_address, diff.content_address)
        self.assertEqual(entry.left_packet_address, diff.left_packet_address)
        self.assertEqual(entry.right_packet_address, diff.right_packet_address)
        self.assertEqual(entry.detail, "explicit rationale")
        self.assertIsNone(entry.previous_entry_address)
        self.assertEqual(review.summary()["review_id"], "review-id")
        self.assertNotIn("entries", review.summary())
        self.assertEqual(review.to_dict()["entry_count"], 1)
        encoded = json.dumps(review.to_dict()).casefold()
        for forbidden in ('"agent"', '"language"', '"model"', '"user"'):
            self.assertNotIn(forbidden, encoded)

    def test_review_verification_has_addressed_ordered_checks(self) -> None:
        diff = self._diff()
        review = self._review(diff)
        receipt = packet_review.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
            review, diff=diff
        )
        self.assertTrue(receipt.accepted)
        self.assertEqual(receipt.review_address, review.content_address)
        self.assertEqual(receipt.check_count, 9)
        self.assertEqual(receipt.failed_count, 0)
        self.assertEqual([item.ordinal for item in receipt.checks], list(range(9)))

    def test_review_verification_rejects_head_and_state_mutation(self) -> None:
        review = self._review()
        review.head_address = "entry:wrong"
        receipt = packet_review.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
            review
        )
        self.assertFalse(receipt.accepted)
        self.assertTrue(any(item.kind == "aggregate-address" for item in receipt.checks))
        self.assertTrue(any(item.kind == "head-conservation" for item in receipt.checks))

    def test_review_verification_rejects_noncontiguous_entry_chain(self) -> None:
        first = self._review()
        second_diff = self._diff(self._packet(packet_id="right"), self._packet(packet_id="third"))
        continued = packet_review.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_decision(
            first, second_diff
        )
        continued.entries[1].previous_entry_address = "entry:wrong"
        receipt = packet_review.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
            continued
        )
        self.assertFalse(receipt.accepted)
        self.assertTrue(any(item.kind == "aggregate-address" for item in receipt.checks))
        self.assertTrue(any(item.kind == "chain-continuity" for item in receipt.checks))

    def test_review_append_continues_from_the_current_head(self) -> None:
        first_diff = self._diff(self._packet(packet_id="left"), self._packet(packet_id="right"))
        first_review = self._review(first_diff, review_id="chain")
        second_diff = self._diff(self._packet(packet_id="right"), self._packet(packet_id="third"))
        second_review = packet_review.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_decision(
            first_review,
            second_diff,
            decision="supersede",
            decision_id="decision-1",
            expected_head_address=first_review.head_address,
        )
        self.assertEqual(second_review.entry_count, 2)
        self.assertEqual(second_review.entries[1].previous_entry_address, first_review.head_address)
        self.assertEqual(second_review.entries[1].diff_address, second_diff.content_address)
        self.assertEqual(second_review.head_address, second_review.entries[1].content_address)
        self.assertEqual(second_review.state, "held")
        self.assertTrue(
            packet_review.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                second_review
            ).accepted
        )

    def test_review_append_rejects_stale_head_and_skipped_packet(self) -> None:
        first_review = self._review(
            self._diff(self._packet(packet_id="left"), self._packet(packet_id="right"))
        )
        next_diff = self._diff(self._packet(packet_id="right"), self._packet(packet_id="third"))
        with self.assertRaises(ValidationError):
            packet_review.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_decision(
                first_review, next_diff, expected_head_address="review:stale"
            )
        skipped = self._diff(self._packet(packet_id="not-current"), self._packet(packet_id="third"))
        with self.assertRaises(ValidationError):
            packet_review.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_decision(
                first_review, skipped
            )

    def test_review_append_rejects_invalid_decision_and_empty_detail(self) -> None:
        review = self._review()
        next_diff = self._diff(self._packet(packet_id="right"), self._packet(packet_id="third"))
        with self.assertRaises(ValidationError):
            packet_review.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_decision(
                review, next_diff, decision="unknown"
            )
        appended = packet_review.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_decision(
            review, next_diff, decision="supersede", detail=""
        )
        self.assertTrue(appended.entries[-1].detail)

    def test_review_json_csv_and_markdown_are_deterministic(self) -> None:
        review = self._review()
        first = packet_review.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_json(
            review
        )
        second = packet_review.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_json(
            review
        )
        self.assertEqual(first, second)
        document = json.loads(first)
        self.assertEqual(document["content_address"], review.content_address)
        self.assertEqual(len(document["entries"]), 1)
        rows = list(
            csv.DictReader(
                packet_review.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_csv(
                    review
                ).splitlines()
            )
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["decision"], "promote")
        markdown = packet_review.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_markdown(
            review
        )
        self.assertIn("Catalog Packet Review", markdown)
        self.assertIn(review.content_address, markdown)
        self.assertIn("promote", markdown)

    def test_review_query_supports_resources_filters_paging_and_receipts(self) -> None:
        review = self._review()
        summary = packet_review.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
            review, resource="summary", limit=1
        )
        entries = packet_review.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
            review,
            resource="entries",
            decision="promote",
            action_required=False,
            text="promote",
            offset=0,
            limit=1,
        )
        self.assertEqual(summary["total"], 1)
        self.assertEqual(entries["total"], 1)
        self.assertEqual(entries["items"][0]["decision"], "promote")
        self.assertTrue(
            packet_review.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_query(
                summary
            )
        )
        self.assertTrue(
            packet_review.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_query(
                entries
            )
        )

    def test_review_query_filters_action_required_decisions(self) -> None:
        held_review = self._review(
            self._diff(
                self._packet(packet_id="left"),
                self._packet(
                    self._catalog(
                        self._store("held", state="held", release_ready=False), catalog_id="held"
                    ),
                    packet_id="right",
                ),
            )
        )
        required = packet_review.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
            held_review, action_required=True
        )
        promote = packet_review.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
            held_review, decision="promote"
        )
        self.assertEqual(required["total"], 1)
        self.assertEqual(required["items"][0]["decision"], "hold")
        self.assertEqual(promote["total"], 0)

    def test_review_query_receipt_rejects_mutation(self) -> None:
        result = packet_review.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
            self._review()
        )
        result["total"] = 99
        with self.assertRaises(ValidationError):
            packet_review.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_query(
                result
            )

    def test_review_query_rejects_invalid_resources_filters_and_bounds(self) -> None:
        review = self._review()
        invalid = (
            {"resource": "unknown"},
            {"decision": "unknown"},
            {"action_required": "yes"},
            {"offset": -1},
            {"limit": 0},
            {"limit": 513},
            {"offset": True},
            {"limit": True},
        )
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                packet_review.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                    review, **kwargs
                )

    def test_review_query_exports_are_deterministic(self) -> None:
        result = packet_review.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
            self._review(), limit=1
        )
        encoded = packet_review.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_query_json(
            result
        )
        rows = list(
            csv.DictReader(
                packet_review.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_query_csv(
                    result
                ).splitlines()
            )
        )
        markdown = packet_review.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_query_markdown(
            result
        )
        self.assertEqual(len(json.loads(encoded)["items"]), 1)
        self.assertEqual(len(rows), 1)
        self.assertIn("Catalog Packet Review Query", markdown)

    def test_review_schema_and_capabilities_are_identity_free(self) -> None:
        values = (
            packet_review.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_schema(),
            packet_review.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_capabilities(),
            packet_review.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_query_schema(),
            packet_review.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_query_capabilities(),
        )
        for value in values:
            encoded = json.dumps(value).casefold()
            self.assertNotIn('"agent"', encoded)
            self.assertNotIn('"language"', encoded)
            self.assertNotIn('"model"', encoded)
            self.assertNotIn('"user"', encoded)
        self.assertEqual(values[0]["decisions"], ["promote", "hold", "block", "supersede"])
        self.assertEqual(values[0]["exact_files"], ["manifest.json", "review.json"])
        self.assertTrue(values[1]["atomic_write"])
        self.assertTrue(values[1]["append_only"])
        self.assertTrue(values[2]["addressed_receipts"])

    def test_review_write_and_load_is_an_exact_two_file_round_trip(self) -> None:
        review = self._review()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "review"
            written = packet_review.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                review, destination
            )
            self.assertEqual(written, destination)
            self.assertEqual(
                sorted(item.name for item in destination.iterdir()),
                ["manifest.json", "review.json"],
            )
            loaded = packet_review.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                destination
            )
            self.assertEqual(loaded.to_dict(), review.to_dict())
            self.assertEqual(loaded.content_address, review.content_address)
            self.assertTrue(
                packet_review.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                    loaded
                ).accepted
            )

    def test_review_write_bytes_are_stable_across_destinations(self) -> None:
        review = self._review()
        with tempfile.TemporaryDirectory() as root:
            left = Path(root) / "left"
            right = Path(root) / "right"
            packet_review.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                review, left
            )
            packet_review.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                review, right
            )
            for name in ("manifest.json", "review.json"):
                self.assertEqual((left / name).read_bytes(), (right / name).read_bytes())

    def test_review_write_rejects_existing_destination_without_overwrite(self) -> None:
        review = self._review()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "review"
            packet_review.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                review, destination
            )
            with self.assertRaises(ValidationError):
                packet_review.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                    review, destination
                )
            replacement = self._review(review_id="replacement")
            packet_review.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                replacement, destination, overwrite=True
            )
            loaded = packet_review.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                destination
            )
            self.assertEqual(loaded.review_id, "replacement")

    def test_review_loader_rejects_mutated_document_bytes(self) -> None:
        review = self._review()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "review"
            packet_review.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                review, destination
            )
            path = destination / "review.json"
            path.write_bytes(path.read_bytes() + b" ")
            with self.assertRaises(ValidationError):
                packet_review.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                    destination
                )

    def test_review_loader_rejects_noncanonical_document_json(self) -> None:
        review = self._review()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "review"
            packet_review.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                review, destination
            )
            path = destination / "review.json"
            path.write_text(json.dumps(json.loads(path.read_text()), indent=2), encoding="utf-8")
            with self.assertRaises(ValidationError):
                packet_review.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                    destination
                )

    def test_review_loader_rejects_missing_and_extra_files(self) -> None:
        review = self._review()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "review"
            packet_review.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                review, destination
            )
            (destination / "review.json").unlink()
            with self.assertRaises(ValidationError):
                packet_review.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                    destination
                )
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "review"
            packet_review.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                review, destination
            )
            (destination / "extra.json").write_bytes(b"{}")
            with self.assertRaises(ValidationError):
                packet_review.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                    destination
                )

    def test_review_loader_rejects_manifest_address_and_structure_mutation(self) -> None:
        review = self._review()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "review"
            packet_review.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                review, destination
            )
            manifest_path = destination / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["byte_count"] = 0
            manifest_path.write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                packet_review.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                    destination
                )
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "review"
            packet_review.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                review, destination
            )
            manifest_path = destination / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["review"] = dict(manifest["review"])
            manifest["review"]["state"] = "blocked"
            manifest_body = {
                key: value for key, value in manifest.items() if key != "manifest_address"
            }
            manifest["manifest_address"] = content_hash(
                manifest_body,
                prefix=packet_review.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_PREFIX
                + "-manifest",
            )
            manifest_path.write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                packet_review.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                    destination
                )

    def test_review_loader_rejects_symlink_when_platform_allows_one(self) -> None:
        review = self._review()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "review"
            packet_review.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                review, destination
            )
            target = Path(root) / "review-copy.json"
            target.write_bytes((destination / "review.json").read_bytes())
            path = destination / "review.json"
            try:
                path.unlink()
                path.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are unavailable in this environment")
            with self.assertRaises(ValidationError):
                packet_review.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                    destination
                )

    def test_review_from_directories_builds_a_verified_review(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            review = packet_review.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_from_directories(
                left, right, review_id="directory-review"
            )
            self.assertEqual(review.review_id, "directory-review")
            self.assertEqual(review.entries[0].decision, "promote")
            self.assertTrue(
                packet_review.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                    review
                ).accepted
            )

    def test_cli_diff_and_review_commands_build_real_packet_output(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            diff_path = Path(root) / "diff.json"
            review_path = Path(root) / "review.json"
            diff_result = main(
                [
                    "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-diff",
                    "--left-packet-directory",
                    str(left),
                    "--right-packet-directory",
                    str(right),
                    "--format",
                    "summary",
                    "--output",
                    str(diff_path),
                ]
            )
            review_result = main(
                [
                    "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review",
                    "--left-packet-directory",
                    str(left),
                    "--right-packet-directory",
                    str(right),
                    "--format",
                    "summary",
                    "--output",
                    str(review_path),
                ]
            )
            self.assertEqual(diff_result, 0)
            self.assertEqual(review_result, 0)
            self.assertEqual(json.loads(diff_path.read_text())["action_count"], 5)
            self.assertEqual(json.loads(review_path.read_text())["state"], "ready")

    def test_cli_diff_and_review_query_commands_page_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            diff_path = Path(root) / "diff-query.json"
            review_path = Path(root) / "review-query.json"
            diff_result = main(
                [
                    "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-diff-query",
                    "--left-packet-directory",
                    str(left),
                    "--right-packet-directory",
                    str(right),
                    "--artifact-kind",
                    "gate",
                    "--output",
                    str(diff_path),
                ]
            )
            review_result = main(
                [
                    "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-query",
                    "--left-packet-directory",
                    str(left),
                    "--right-packet-directory",
                    str(right),
                    "--decision-filter",
                    "promote",
                    "--output",
                    str(review_path),
                ]
            )
            self.assertEqual(diff_result, 0)
            self.assertEqual(review_result, 0)
            self.assertEqual(json.loads(diff_path.read_text())["total"], 1)
            self.assertEqual(json.loads(review_path.read_text())["items"][0]["decision"], "promote")

    def test_cli_schema_and_capability_commands_are_discoverable(self) -> None:
        commands = (
            "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-diff-schema",
            "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-diff-capabilities",
            "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-diff-query-schema",
            "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-diff-query-capabilities",
            "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-schema",
            "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-capabilities",
            "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-query-schema",
            "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-query-capabilities",
        )
        for command in commands:
            output = StringIO()
            with redirect_stdout(output):
                result = main([command])
            self.assertEqual(result, 0)
            self.assertTrue(json.loads(output.getvalue()))

    def _http_json(self, server, path: str, params: dict[str, str]):
        connection = HTTPConnection("127.0.0.1", server.server_address[1], timeout=15)
        connection.request("GET", path + "?" + urlencode(params))
        response = connection.getresponse()
        body = response.read().decode("utf-8")
        content_type = response.getheader("Content-Type", "")
        connection.close()
        return response.status, content_type, body

    def test_http_diff_and_review_routes_build_queries_and_schemas(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            server = create_server("127.0.0.1", 0, str(Path(root) / "data"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            diff_base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/diff"
            review_base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review"
            try:
                cases = (
                    (
                        diff_base,
                        {"left_packet_directory": str(left), "right_packet_directory": str(right)},
                        "changed",
                    ),
                    (
                        diff_base + "/query",
                        {
                            "left_packet_directory": str(left),
                            "right_packet_directory": str(right),
                            "artifact_kind": "gate",
                        },
                        "query",
                    ),
                    (diff_base + "/schema", {}, "schema"),
                    (diff_base + "/capabilities", {}, "schema"),
                    (diff_base + "/query/schema", {}, "schema"),
                    (diff_base + "/query/capabilities", {}, "schema"),
                    (
                        review_base,
                        {"left_packet_directory": str(left), "right_packet_directory": str(right)},
                        "ready",
                    ),
                    (
                        review_base + "/query",
                        {
                            "left_packet_directory": str(left),
                            "right_packet_directory": str(right),
                            "decision_filter": "promote",
                        },
                        "query",
                    ),
                    (review_base + "/schema", {}, "schema"),
                    (review_base + "/capabilities", {}, "schema"),
                    (review_base + "/query/schema", {}, "schema"),
                    (review_base + "/query/capabilities", {}, "schema"),
                )
                for path, params, expected in cases:
                    status, content_type, body = self._http_json(server, path, params)
                    self.assertEqual(status, 200)
                    if expected == "changed":
                        self.assertEqual(json.loads(body)["state"], "changed")
                    elif expected == "ready":
                        self.assertEqual(json.loads(body)["state"], "ready")
                    elif expected == "query":
                        self.assertEqual(json.loads(body)["total"], 1)
                    else:
                        self.assertTrue(json.loads(body))
                    self.assertIn("application/json", content_type)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_http_diff_and_review_routes_negotiate_csv_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            server = create_server("127.0.0.1", 0, str(Path(root) / "data"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            diff_base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/diff"
            review_base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review"
            try:
                for base, marker in (
                    (diff_base, "artifact_kind,action"),
                    (review_base, "ordinal,decision_id,decision"),
                ):
                    for fmt, content_type in (("csv", "text/csv"), ("markdown", "text/markdown")):
                        status, actual_type, body = self._http_json(
                            server,
                            base,
                            {
                                "left_packet_directory": str(left),
                                "right_packet_directory": str(right),
                                "format": fmt,
                            },
                        )
                        self.assertEqual(status, 200)
                        self.assertIn(content_type, actual_type)
                        self.assertIn(
                            marker
                            if fmt == "csv"
                            else ("Artifact" if base == diff_base else "Decision"),
                            body,
                        )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_real_downloaded_packet_diff_and_review_round_trip(self) -> None:
        packet_directory = Path(
            r"C:\Users\murar\AppData\Local\Temp\glio-noncode-real-demo-9b0hnhh2\packet"
        )
        if not packet_directory.is_dir():
            self.skipTest("real downloaded packet fixture is not present")
        loaded = load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
            packet_directory
        )
        diff = self._diff(loaded, loaded, diff_id="real-diff")
        review = self._review(diff, review_id="real-review")
        self.assertEqual(diff.state, "exact")
        self.assertTrue(diff.accepted)
        self.assertTrue(diff.release_ready)
        self.assertEqual(review.entries[0].decision, "promote")
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "real-review"
            packet_review.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                review, destination
            )
            reloaded = packet_review.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                destination
            )
            self.assertEqual(reloaded.content_address, review.content_address)
            self.assertTrue(
                packet_review.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                    reloaded
                ).accepted
            )

    def test_diff_projection_flags_allow_independent_transport_views(self) -> None:
        diff = self._diff()
        summary = diff.to_dict(include_actions=False, include_checks=False)
        actions_only = diff.to_dict(include_actions=True, include_checks=False)
        checks_only = diff.to_dict(include_actions=False, include_checks=True)
        self.assertNotIn("actions", summary)
        self.assertNotIn("checks", summary)
        self.assertIn("actions", actions_only)
        self.assertNotIn("checks", actions_only)
        self.assertNotIn("actions", checks_only)
        self.assertIn("checks", checks_only)
        self.assertEqual(actions_only["action_count"], len(actions_only["actions"]))
        self.assertEqual(checks_only["check_count"], len(checks_only["checks"]))

    def test_review_projection_flag_allows_head_only_transport(self) -> None:
        review = self._review()
        summary = review.to_dict(include_entries=False)
        full = review.to_dict(include_entries=True)
        self.assertNotIn("entries", summary)
        self.assertIn("entries", full)
        self.assertEqual(summary["head_address"], full["entries"][-1]["content_address"])
        self.assertEqual(full["entry_count"], len(full["entries"]))

    def test_diff_json_and_review_json_use_canonical_bytes(self) -> None:
        diff = self._diff()
        review = self._review(diff)
        diff_text = packet_diff.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_json(
            diff
        )
        review_text = packet_review.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_json(
            review
        )
        self.assertTrue(diff_text.endswith("\n"))
        self.assertTrue(review_text.endswith("\n"))
        self.assertEqual(canonical_bytes(json.loads(diff_text)), diff_text[:-1].encode("utf-8"))
        self.assertEqual(canonical_bytes(json.loads(review_text)), review_text[:-1].encode("utf-8"))

    def test_changed_action_fields_identify_all_changed_measurements(self) -> None:
        left = self._packet(packet_id="left")
        right = self._packet(
            self._catalog(self._store("different"), catalog_id="different"), packet_id="right"
        )
        diff = self._diff(left, right)
        catalog_action = next(item for item in diff.actions if item.artifact_kind == "catalog")
        self.assertEqual(
            catalog_action.changed_fields, ("content_address", "byte_address", "byte_count")
        )
        self.assertNotEqual(catalog_action.left_address, catalog_action.right_address)
        self.assertNotEqual(catalog_action.left_byte_address, catalog_action.right_byte_address)
        self.assertNotEqual(catalog_action.left_byte_count, catalog_action.right_byte_count)

    def test_diff_transition_table_is_stable_for_all_release_states(self) -> None:
        ready = self._packet(packet_id="ready")
        held = self._packet(
            self._catalog(
                self._store("held", state="held", release_ready=False), catalog_id="held"
            ),
            packet_id="held",
        )
        blocked = self._packet(
            self._catalog(
                self._store("blocked", state="blocked", release_ready=False, accepted=False),
                catalog_id="blocked",
            ),
            packet_id="blocked",
        )
        cases = (
            (ready, ready, "unchanged"),
            (ready, held, "held"),
            (ready, blocked, "blocked"),
            (held, ready, "promoted"),
            (held, held, "unchanged"),
            (held, blocked, "blocked"),
            (blocked, ready, "recovered"),
            (blocked, held, "recovered"),
            (blocked, blocked, "unchanged"),
        )
        for left, right, expected in cases:
            with self.subTest(left=left.state, right=right.state):
                self.assertEqual(self._diff(left, right).release_transition, expected)

    def test_diff_acceptance_and_readiness_follow_right_packet_state(self) -> None:
        left = self._packet(packet_id="left")
        for state, release_ready, accepted in (
            ("ready", True, True),
            ("held", False, True),
            ("blocked", False, False),
        ):
            right = self._packet(
                self._catalog(
                    self._store(state, state=state, release_ready=release_ready, accepted=accepted),
                    catalog_id=state,
                ),
                packet_id=state,
            )
            diff = self._diff(left, right)
            self.assertTrue(diff.accepted)
            self.assertEqual(diff.release_ready, release_ready)
            self.assertEqual(diff.right_state, state)

    def test_diff_schema_declares_all_transition_values(self) -> None:
        schema = packet_diff.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_schema()
        self.assertEqual(schema["actions"], ["unchanged", "changed", "added", "removed"])
        self.assertEqual(schema["states"], ["exact", "changed"])
        self.assertEqual(
            schema["transitions"],
            ["unchanged", "promoted", "held", "blocked", "recovered", "regressed"],
        )
        self.assertEqual(schema["max_artifacts"], 5)
        self.assertTrue(schema["path_free"])
        self.assertTrue(schema["timestamp_free"])

    def test_review_decision_table_maps_each_decision_to_a_state(self) -> None:
        ready_diff = self._diff()
        held_diff = self._diff(
            self._packet(packet_id="left"),
            self._packet(
                self._catalog(
                    self._store("held", state="held", release_ready=False), catalog_id="held"
                ),
                packet_id="right",
            ),
        )
        self.assertEqual(self._review(ready_diff).state, "ready")
        self.assertEqual(self._review(held_diff).state, "held")
        self.assertEqual(self._review(held_diff, decision="block").state, "blocked")
        self.assertEqual(self._review(ready_diff, decision="supersede").state, "held")

    def test_review_promote_is_rejected_for_held_and_blocked_diffs(self) -> None:
        for state, accepted in (("held", True), ("blocked", False)):
            right = self._packet(
                self._catalog(
                    self._store(state, state=state, release_ready=False, accepted=accepted),
                    catalog_id=state,
                ),
                packet_id="right",
            )
            with self.subTest(state=state), self.assertRaises(ValidationError):
                self._review(self._diff(self._packet(packet_id="left"), right), decision="promote")

    def test_review_block_is_rejected_for_fully_ready_evidence(self) -> None:
        with self.assertRaises(ValidationError):
            self._review(self._diff(), decision="block")

    def test_review_supersede_always_requires_follow_up_action(self) -> None:
        for diff in (
            self._diff(),
            self._diff(
                self._packet(packet_id="left"),
                self._packet(
                    self._catalog(
                        self._store("held", state="held", release_ready=False), catalog_id="held"
                    ),
                    packet_id="right",
                ),
            ),
        ):
            review = self._review(diff, decision="supersede")
            self.assertEqual(review.entries[0].decision, "supersede")
            self.assertTrue(review.entries[0].action_required)
            self.assertFalse(review.release_ready)

    def test_review_default_decision_is_deterministic_for_each_right_state(self) -> None:
        left = self._packet(packet_id="left")
        cases = (
            ("ready", True, True, "promote"),
            ("held", False, True, "hold"),
            ("blocked", False, False, "block"),
        )
        for state, release_ready, accepted, decision in cases:
            right = self._packet(
                self._catalog(
                    self._store(state, state=state, release_ready=release_ready, accepted=accepted),
                    catalog_id=state,
                ),
                packet_id=state,
            )
            review = self._review(self._diff(left, right))
            self.assertEqual(review.entries[0].decision, decision)

    def test_appending_without_an_explicit_decision_uses_the_new_diff_state(self) -> None:
        first = self._review(
            self._diff(self._packet(packet_id="left"), self._packet(packet_id="right"))
        )
        held_diff = self._diff(
            self._packet(packet_id="right"),
            self._packet(
                self._catalog(
                    self._store("held", state="held", release_ready=False), catalog_id="held"
                ),
                packet_id="held",
            ),
        )
        appended = packet_review.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_decision(
            first, held_diff
        )
        self.assertEqual(appended.entries[-1].decision, "hold")
        self.assertEqual(appended.state, "held")
        self.assertEqual(appended.entry_count, 2)

    def test_appended_review_keeps_previous_entry_address_and_changes_aggregate_address(
        self,
    ) -> None:
        first = self._review(
            self._diff(self._packet(packet_id="left"), self._packet(packet_id="right"))
        )
        second_diff = self._diff(self._packet(packet_id="right"), self._packet(packet_id="third"))
        second = packet_review.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_decision(
            first, second_diff
        )
        self.assertEqual(second.entries[1].previous_entry_address, first.entries[0].content_address)
        self.assertNotEqual(second.content_address, first.content_address)
        self.assertNotEqual(second.head_address, first.head_address)
        self.assertEqual(second.entries[1].ordinal, 1)

    def test_review_verification_without_a_supplied_diff_remains_structurally_complete(
        self,
    ) -> None:
        review = self._review()
        receipt = packet_review.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
            review
        )
        self.assertTrue(receipt.accepted)
        self.assertEqual(receipt.check_count, 8)
        self.assertEqual(receipt.failed_count, 0)

    def test_review_verification_with_a_diff_adds_linkage_assurance(self) -> None:
        diff = self._diff()
        review = self._review(diff)
        receipt = packet_review.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
            review, diff=diff
        )
        self.assertEqual(receipt.check_count, 9)
        self.assertTrue(any(item.kind == "diff-link" for item in receipt.checks))

    def test_review_check_addresses_are_recomputed_after_append(self) -> None:
        review = self._review()
        next_diff = self._diff(self._packet(packet_id="right"), self._packet(packet_id="third"))
        appended = packet_review.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_decision(
            review, next_diff
        )
        receipt = packet_review.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
            appended
        )
        for index, check in enumerate(receipt.checks):
            self.assertEqual(check.ordinal, index)
            self.assertTrue(check.content_address.startswith("module-workbench"))

    def test_diff_and_review_reject_untyped_inputs_before_accessing_attributes(self) -> None:
        with self.assertRaises(ValidationError):
            packet_diff.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
                object(), self._packet()
            )
        with self.assertRaises(ValidationError):
            packet_review.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                object()
            )
        with self.assertRaises(ValidationError):
            packet_review.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                object()
            )

    def test_review_persistence_rejects_unverified_mutated_reviews(self) -> None:
        review = self._review()
        review.release_ready = False
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValidationError):
                packet_review.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                    review, Path(root) / "review"
                )

    def test_review_loader_rejects_manifest_version_and_unknown_key(self) -> None:
        review = self._review()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "review"
            packet_review.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                review, destination
            )
            manifest_path = destination / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["manifest_version"] = "unknown"
            manifest_path.write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                packet_review.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                    destination
                )
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "review"
            packet_review.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                review, destination
            )
            manifest_path = destination / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["unexpected"] = True
            manifest_path.write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                packet_review.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                    destination
                )

    def test_review_loader_rejects_manifest_byte_address_mutation(self) -> None:
        review = self._review()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "review"
            packet_review.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                review, destination
            )
            manifest_path = destination / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["byte_address"] = "packet-review-bytes:tampered"
            manifest_path.write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                packet_review.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                    destination
                )

    def test_review_loader_rejects_child_directory_and_destination_file(self) -> None:
        review = self._review()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "review"
            packet_review.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                review, destination
            )
            (destination / "child").mkdir()
            with self.assertRaises(ValidationError):
                packet_review.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                    destination
                )
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "review"
            destination.write_text("not a directory", encoding="utf-8")
            with self.assertRaises(ValidationError):
                packet_review.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                    review, destination, overwrite=True
                )

    def test_diff_query_beyond_end_returns_empty_but_keeps_total(self) -> None:
        result = packet_diff.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
            self._diff(), offset=50, limit=2
        )
        self.assertEqual(result["total"], 5)
        self.assertEqual(result["items"], [])
        self.assertEqual(result["offset"], 50)
        self.assertTrue(
            packet_diff.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_query(
                result
            )
        )

    def test_review_query_beyond_end_returns_empty_but_keeps_total(self) -> None:
        result = packet_review.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
            self._review(), offset=50, limit=2
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"], [])
        self.assertEqual(result["offset"], 50)
        self.assertTrue(
            packet_review.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_query(
                result
            )
        )

    def test_query_text_matching_is_case_insensitive(self) -> None:
        diff_result = packet_diff.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
            self._diff(), resource="checks", text="PuBlIc"
        )
        review_result = packet_review.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
            self._review(), text="PROMOTE"
        )
        self.assertEqual(diff_result["total"], 1)
        self.assertEqual(diff_result["items"][0]["kind"], "public-boundary")
        self.assertEqual(review_result["total"], 1)

    def test_query_export_receipts_preserve_filter_metadata(self) -> None:
        diff_result = packet_diff.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
            self._diff(), action="unchanged", artifact_kind="gate", offset=0, limit=1
        )
        review_result = packet_review.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
            self._review(), decision="promote", action_required=False, offset=0, limit=1
        )
        self.assertEqual(diff_result["query"]["action"], "unchanged")
        self.assertEqual(diff_result["query"]["artifact_kind"], "gate")
        self.assertEqual(review_result["query"]["decision"], "promote")
        self.assertFalse(review_result["query"]["action_required"])
        self.assertEqual(
            json.loads(
                packet_diff.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_query_json(
                    diff_result
                )
            )["query"],
            diff_result["query"],
        )
        self.assertEqual(
            json.loads(
                packet_review.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_query_json(
                    review_result
                )
            )["query"],
            review_result["query"],
        )

    def test_cli_can_render_diff_and_review_as_csv_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            for command, marker in (
                (
                    "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-diff",
                    "Catalog Packet Diff",
                ),
                (
                    "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review",
                    "Catalog Packet Review",
                ),
            ):
                for output_format in ("csv", "markdown"):
                    output = StringIO()
                    with redirect_stdout(output):
                        result = main(
                            [
                                command,
                                "--left-packet-directory",
                                str(left),
                                "--right-packet-directory",
                                str(right),
                                "--format",
                                output_format,
                            ]
                        )
                    self.assertEqual(result, 0)
                    if output_format == "markdown":
                        self.assertIn(marker, output.getvalue())
                    else:
                        self.assertIn("ordinal", output.getvalue())

    def test_cli_can_render_diff_and_review_queries_as_csv_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            for command in (
                "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-diff-query",
                "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-query",
            ):
                for output_format in ("csv", "markdown"):
                    output = StringIO()
                    with redirect_stdout(output):
                        result = main(
                            [
                                command,
                                "--left-packet-directory",
                                str(left),
                                "--right-packet-directory",
                                str(right),
                                "--format",
                                output_format,
                            ]
                        )
                    self.assertEqual(result, 0)
                    self.assertTrue(output.getvalue().strip())

    def test_http_routes_accept_directory_aliases_and_query_filters(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            server = create_server("127.0.0.1", 0, str(Path(root) / "data"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/diff"
            try:
                status, _, body = self._http_json(
                    server,
                    base + "/query",
                    {
                        "left_directory": str(left),
                        "right_directory": str(right),
                        "resource": "actions",
                        "artifact_kind": "gate",
                        "offset": "0",
                        "limit": "1",
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)["items"][0]["artifact_kind"], "gate")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_http_routes_fail_closed_when_packet_directories_are_missing(self) -> None:
        server = create_server("127.0.0.1", 0, tempfile.gettempdir())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review"
        try:
            status, _, body = self._http_json(server, base, {})
            self.assertEqual(status, 400)
            self.assertIn("left_packet_directory", body)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_repeated_diff_builds_have_identical_addresses_and_documents(self) -> None:
        left = self._packet(packet_id="left")
        right = self._packet(packet_id="right")
        first = self._diff(left, right, diff_id="stable")
        second = self._diff(left, right, diff_id="stable")
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(
            packet_diff.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_json(
                first
            ),
            packet_diff.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_json(
                second
            ),
        )

    def test_repeated_review_builds_have_identical_addresses_and_documents(self) -> None:
        diff = self._diff()
        first = self._review(diff, review_id="stable")
        second = self._review(diff, review_id="stable")
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(
            packet_review.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_json(
                first
            ),
            packet_review.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_json(
                second
            ),
        )

    def test_diff_id_changes_only_the_addressed_diff_identity(self) -> None:
        first = self._diff(diff_id="first")
        second = self._diff(diff_id="second")
        self.assertNotEqual(first.content_address, second.content_address)
        self.assertEqual(first.left_packet_address, second.left_packet_address)
        self.assertEqual(first.right_packet_address, second.right_packet_address)
        self.assertEqual(
            [item.to_dict() for item in first.actions],
            [item.to_dict() for item in second.actions],
        )
        self.assertEqual(
            [item.to_dict() for item in first.checks],
            [item.to_dict() for item in second.checks],
        )

    def test_review_id_and_decision_id_are_addressed_review_inputs(self) -> None:
        diff = self._diff()
        first = self._review(diff, review_id="first", decision_id="one")
        second = self._review(diff, review_id="second", decision_id="two")
        self.assertNotEqual(first.content_address, second.content_address)
        self.assertNotEqual(first.entries[0].content_address, second.entries[0].content_address)
        self.assertEqual(first.entries[0].diff_address, second.entries[0].diff_address)
        self.assertEqual(first.state, second.state)

    def test_diff_content_address_excludes_hydrated_component_objects(self) -> None:
        diff = self._diff()
        document = diff.to_dict()
        self.assertEqual(
            set(document),
            {
                "diff_id",
                "version",
                "boundary",
                "left_packet_id",
                "right_packet_id",
                "left_packet_address",
                "right_packet_address",
                "left_state",
                "right_state",
                "state",
                "release_transition",
                "action_count",
                "unchanged_count",
                "changed_count",
                "added_count",
                "removed_count",
                "accepted",
                "release_ready",
                "check_count",
                "passed_count",
                "failed_count",
                "content_address",
                "actions",
                "checks",
            },
        )
        for action in document["actions"]:
            self.assertNotIn("packet", action)
            self.assertNotIn("artifact", action)
        self.assertTrue(diff.content_address.startswith("module-workbench"))

    def test_review_content_address_excludes_hydrated_diff_objects(self) -> None:
        review = self._review()
        document = review.to_dict()
        self.assertEqual(
            set(document),
            {
                "review_id",
                "version",
                "boundary",
                "entry_count",
                "state",
                "release_ready",
                "accepted",
                "head_address",
                "content_address",
                "entries",
            },
        )
        for entry in document["entries"]:
            self.assertNotIn("diff", entry)
            self.assertNotIn("packet", entry)
        self.assertTrue(review.content_address.startswith("module-workbench"))

    def test_diff_query_summary_contains_the_same_address_as_the_diff(self) -> None:
        diff = self._diff()
        result = packet_diff.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
            diff, resource="summary"
        )
        self.assertEqual(result["diff"]["content_address"], diff.content_address)
        self.assertEqual(result["items"], [diff.summary()])
        self.assertEqual(result["query"]["resource"], "summary")

    def test_review_query_summary_contains_the_same_address_as_the_review(self) -> None:
        review = self._review()
        result = packet_review.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
            review, resource="summary"
        )
        self.assertEqual(result["review"]["content_address"], review.content_address)
        self.assertEqual(result["items"], [review.summary()])
        self.assertEqual(result["query"]["resource"], "summary")

    def test_query_empty_text_is_rejected_in_both_boundaries(self) -> None:
        with self.assertRaises(ValidationError):
            packet_diff.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
                self._diff(), text=""
            )
        with self.assertRaises(ValidationError):
            packet_review.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                self._review(), text=""
            )

    def test_query_text_is_bounded_in_both_boundaries(self) -> None:
        too_long = "x" * 4097
        with self.assertRaises(ValidationError):
            packet_diff.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
                self._diff(), text=too_long
            )
        with self.assertRaises(ValidationError):
            packet_review.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                self._review(), text=too_long
            )

    def test_diff_and_review_ids_are_bounded(self) -> None:
        too_long = "x" * 257
        with self.assertRaises(ValidationError):
            self._diff(diff_id=too_long)
        with self.assertRaises(ValidationError):
            self._review(review_id=too_long)
        with self.assertRaises(ValidationError):
            self._review(decision_id=too_long)

    def test_append_does_not_mutate_the_prior_review(self) -> None:
        first = self._review(
            self._diff(self._packet(packet_id="left"), self._packet(packet_id="right"))
        )
        original = first.to_dict()
        next_diff = self._diff(self._packet(packet_id="right"), self._packet(packet_id="third"))
        appended = packet_review.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_decision(
            first, next_diff
        )
        self.assertEqual(first.to_dict(), original)
        self.assertEqual(first.entry_count, 1)
        self.assertEqual(len(first.entries), 1)
        self.assertEqual(appended.entry_count, 2)
        self.assertNotEqual(appended.to_dict(), original)

    def test_append_can_promote_a_ready_follow_up_transition(self) -> None:
        first = self._review(
            self._diff(self._packet(packet_id="left"), self._packet(packet_id="right"))
        )
        next_diff = self._diff(self._packet(packet_id="right"), self._packet(packet_id="third"))
        appended = packet_review.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_decision(
            first, next_diff, decision="promote"
        )
        self.assertEqual(appended.entries[-1].decision, "promote")
        self.assertEqual(appended.state, "ready")
        self.assertTrue(appended.release_ready)
        self.assertFalse(appended.entries[-1].action_required)

    def test_append_can_block_an_accepted_nonready_follow_up_transition(self) -> None:
        first = self._review(
            self._diff(self._packet(packet_id="left"), self._packet(packet_id="right"))
        )
        next_diff = self._diff(
            self._packet(packet_id="right"),
            self._packet(
                self._catalog(
                    self._store("held", state="held", release_ready=False), catalog_id="held"
                ),
                packet_id="held",
            ),
        )
        appended = packet_review.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_decision(
            first, next_diff, decision="block"
        )
        self.assertEqual(appended.state, "blocked")
        self.assertFalse(appended.release_ready)
        self.assertTrue(appended.accepted)

    def test_review_manifest_conserves_document_address_and_byte_count(self) -> None:
        review = self._review()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "review"
            packet_review.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                review, destination
            )
            manifest = json.loads((destination / "manifest.json").read_text())
            document = (destination / "review.json").read_bytes()
            self.assertEqual(manifest["byte_count"], len(document))
            self.assertEqual(manifest["review"], json.loads(document))
            self.assertEqual(
                manifest["manifest_version"],
                packet_review.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_VERSION,
            )
            self.assertTrue(manifest["byte_address"].startswith("module-workbench"))
            self.assertTrue(manifest["manifest_address"].startswith("module-workbench"))

    def test_review_persistence_creates_missing_parent_directories(self) -> None:
        review = self._review()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "nested" / "review"
            self.assertFalse(destination.parent.exists())
            packet_review.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                review, destination
            )
            self.assertTrue(destination.is_dir())
            self.assertTrue((destination / "manifest.json").is_file())
            self.assertTrue((destination / "review.json").is_file())

    def test_review_overwrite_keeps_the_published_file_set_exact(self) -> None:
        first = self._review(review_id="first")
        second = self._review(review_id="second")
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "review"
            packet_review.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                first, destination
            )
            packet_review.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                second, destination, overwrite=True
            )
            self.assertEqual(
                sorted(item.name for item in destination.iterdir()),
                ["manifest.json", "review.json"],
            )
            self.assertEqual(
                packet_review.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                    destination
                ).review_id,
                "second",
            )

    def test_diff_query_and_review_query_limits_are_inclusive_at_the_maximum(self) -> None:
        diff_result = packet_diff.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
            self._diff(), limit=512
        )
        review_result = packet_review.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
            self._review(), limit=512
        )
        self.assertEqual(diff_result["limit"], 512)
        self.assertEqual(review_result["limit"], 512)
        self.assertTrue(
            packet_diff.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_query(
                diff_result
            )
        )
        self.assertTrue(
            packet_review.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_query(
                review_result
            )
        )

    def test_http_review_query_filters_required_actions(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            server = create_server("127.0.0.1", 0, str(Path(root) / "data"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/query"
            try:
                status, _, body = self._http_json(
                    server,
                    base,
                    {
                        "left_packet_directory": str(left),
                        "right_packet_directory": str(right),
                        "action_required": "false",
                        "decision_filter": "promote",
                    },
                )
                self.assertEqual(status, 200)
                payload = json.loads(body)
                self.assertEqual(payload["total"], 1)
                self.assertFalse(payload["items"][0]["action_required"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_public_review_and_diff_projections_have_no_source_paths(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            diff = packet_diff.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_from_directories(
                left, right
            )
            review = packet_review.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_from_directories(
                left, right
            )
            for value in (diff.to_dict(), review.to_dict()):
                encoded = json.dumps(value)
                self.assertNotIn(str(left), encoded)
                self.assertNotIn(str(right), encoded)
                self.assertNotIn("tempfile", encoded.casefold())

    def test_real_packet_directory_can_be_compared_and_reviewed_twice(self) -> None:
        packet_directory = Path(
            r"C:\Users\murar\AppData\Local\Temp\glio-noncode-real-demo-9b0hnhh2\packet"
        )
        if not packet_directory.is_dir():
            self.skipTest("real downloaded packet fixture is not present")
        first = packet_diff.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_from_directories(
            packet_directory, packet_directory, diff_id="real"
        )
        second = packet_review.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_from_directories(
            packet_directory, packet_directory, diff_id="real", review_id="real"
        )
        self.assertEqual(first.state, "exact")
        self.assertEqual(first.release_transition, "unchanged")
        self.assertEqual(second.entries[0].decision, "promote")
        self.assertEqual(second.entries[0].diff_address, first.content_address)

    def test_diff_markdown_reports_all_action_counts(self) -> None:
        diff = self._diff(self._packet(packet_id="left"), self._packet(packet_id="right"))
        markdown = packet_diff.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_markdown(
            diff
        )
        self.assertIn(f"- changed: `{diff.changed_count}`", markdown)
        self.assertIn(f"- unchanged: `{diff.unchanged_count}`", markdown)
        self.assertIn(f"- accepted: `{str(diff.accepted).lower()}`", markdown)
        self.assertIn(f"- release-ready: `{str(diff.release_ready).lower()}`", markdown)
        for ordinal in range(5):
            self.assertIn(f"| {ordinal} |", markdown)

    def test_review_markdown_reports_every_decision_entry(self) -> None:
        first = self._review(
            self._diff(self._packet(packet_id="left"), self._packet(packet_id="right")),
            review_id="markdown",
        )
        next_diff = self._diff(self._packet(packet_id="right"), self._packet(packet_id="third"))
        review = packet_review.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_decision(
            first, next_diff, decision="supersede"
        )
        markdown = packet_review.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_markdown(
            review
        )
        self.assertIn("| 0 | `promote`", markdown)
        self.assertIn("| 1 | `supersede`", markdown)
        self.assertIn(review.head_address, markdown)
        self.assertIn("true", markdown)

    def test_review_manifest_and_document_are_each_canonical_objects(self) -> None:
        review = self._review()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "review"
            packet_review.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                review, destination
            )
            for name in ("manifest.json", "review.json"):
                raw = (destination / name).read_bytes()
                self.assertEqual(raw, canonical_bytes(json.loads(raw)))
                self.assertTrue(raw.endswith(b"}"))
                self.assertNotIn(b"\n", raw)

    def test_query_receipt_address_changes_when_paging_changes(self) -> None:
        diff = self._diff()
        first = packet_diff.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
            diff, offset=0, limit=1
        )
        second = packet_diff.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
            diff, offset=1, limit=1
        )
        self.assertNotEqual(first["content_address"], second["content_address"])
        self.assertEqual(first["items"][0]["ordinal"], 0)
        self.assertEqual(second["items"][0]["ordinal"], 1)
        review = self._review()
        first_review = packet_review.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
            review, offset=0, limit=1
        )
        second_review = packet_review.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
            review, offset=1, limit=1
        )
        self.assertNotEqual(first_review["content_address"], second_review["content_address"])
        self.assertEqual(first_review["items"][0]["ordinal"], 0)
        self.assertEqual(second_review["items"], [])

    def test_query_filters_can_return_a_verified_empty_result(self) -> None:
        diff_result = packet_diff.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
            self._diff(), action="added"
        )
        review_result = packet_review.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
            self._review(), decision="block"
        )
        self.assertEqual(diff_result["total"], 0)
        self.assertEqual(diff_result["items"], [])
        self.assertEqual(review_result["total"], 0)
        self.assertEqual(review_result["items"], [])
        self.assertTrue(
            packet_diff.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_query(
                diff_result
            )
        )
        self.assertTrue(
            packet_review.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_query(
                review_result
            )
        )


if __name__ == "__main__":
    unittest.main()
