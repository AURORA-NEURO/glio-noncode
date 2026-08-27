"""Deep contract coverage for longitudinal packet-review gate history."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import json
import os
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
import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance as packet_assurance
import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate as packet_gate
import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history as history
import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay as replay
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet,
    load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet,
    write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet,
)
from glio_noncode.serialization import canonical_bytes, canonical_json, content_hash


class GateHistoryTests(unittest.TestCase):
    """Exercise the full public history lifecycle against typed packets."""

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

    def _packet(self, catalog=None, **kwargs):
        catalog = catalog or self._catalog(self._store("alpha"), self._store("beta"))
        from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance import (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance,
        )
        from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation import (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation,
        )
        from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate import (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate,
        )
        from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime import (
            run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime,
        )

        runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime(
            catalog
        )
        federation = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation(
            catalog
        )
        assurance = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance(
            catalog
        )
        gate = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate(
            catalog, runtime, federation, assurance
        )
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
            decision_id=kwargs.get("decision_id", "decision:0"),
            detail=kwargs.get("detail"),
        )

    def _assurance(self, review=None, diff=None, **kwargs):
        review = review or self._review(diff)
        return packet_assurance.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
            review, diff=diff, assurance_id=kwargs.get("assurance_id", "assurance")
        )

    def _gate(self, diff=None, review=None, assurance=None, **kwargs):
        diff = diff or self._diff()
        review = review or self._review(diff)
        assurance = assurance or self._assurance(review, diff)
        return packet_gate.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
            diff, review, assurance, gate_id=kwargs.get("gate_id", "gate")
        )

    def _history(self, *, decision=None, right=None, history_id="history", detail=None):
        diff = self._diff(right=right, diff_id=f"diff:{history_id}")
        review = self._review(
            diff, decision=decision, decision_id=f"decision:{history_id}", detail=detail
        )
        assurance = self._assurance(review, diff, assurance_id=f"assurance:{history_id}")
        gate = self._gate(diff, review, assurance, gate_id=f"gate:{history_id}")
        return history.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            gate, history_id=history_id, detail=detail
        )

    def _decision_gate(self, decision: str, suffix: str):
        if decision == "block":
            left, right = self._blocked_pair()
        elif decision in {"hold", "supersede"}:
            left, right = self._held_pair()
        else:
            left, right = (
                self._packet(packet_id=f"left-{suffix}"),
                self._packet(packet_id=f"right-{suffix}"),
            )
        diff = self._diff(left, right, diff_id=f"diff:{suffix}")
        review = self._review(
            diff,
            review_id=f"review:{suffix}",
            decision=decision,
            decision_id=f"decision:{suffix}",
            detail=f"{decision} {suffix}",
        )
        assurance = self._assurance(review, diff, assurance_id=f"assurance:{suffix}")
        return self._gate(diff, review, assurance, gate_id=f"gate:{suffix}")

    def _held_pair(self):
        return self._packet(packet_id="left"), self._packet(
            self._catalog(self._store("held", state="held", release_ready=False)), packet_id="right"
        )

    def _blocked_pair(self):
        return self._packet(packet_id="left"), self._packet(
            self._catalog(
                self._store("blocked", state="blocked", release_ready=False, accepted=False)
            ),
            packet_id="right",
        )

    @staticmethod
    def _write_packet(root: str | Path, packet, name: str) -> Path:
        destination = Path(root) / name
        write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
            packet, destination
        )
        return destination

    def _pair_directories(self, root: str | Path):
        left = self._write_packet(root, self._packet(packet_id="left"), "left")
        right = self._write_packet(root, self._packet(packet_id="right"), "right")
        return left, right

    def _real_packet(self) -> Path:
        return Path(r"C:\Users\murar\AppData\Local\Temp\glio-noncode-real-demo-9b0hnhh2\packet")

    @staticmethod
    def _http_json(server, path: str, params: dict[str, str]):
        connection = HTTPConnection("127.0.0.1", server.server_address[1], timeout=15)
        connection.request("GET", path + "?" + urlencode(params))
        response = connection.getresponse()
        body = response.read().decode("utf-8")
        content_type = response.getheader("Content-Type", "")
        connection.close()
        return response.status, content_type, body

    def test_fixture_packet_is_usable(self):
        packet = self._packet()
        self.assertTrue(packet.accepted)
        self.assertTrue(packet.release_ready)

    def test_fixture_packets_have_different_addresses_when_ids_differ(self):
        self.assertNotEqual(
            self._packet(packet_id="left").content_address,
            self._packet(packet_id="right").content_address,
        )

    def test_ready_history_has_one_promote_entry(self):
        value = self._history()
        self.assertEqual(value.entry_count, 1)
        self.assertEqual(value.promote_count, 1)
        self.assertEqual(value.hold_count, 0)
        self.assertEqual(value.block_count, 0)
        self.assertEqual(value.supersede_count, 0)
        self.assertEqual(value.state, "ready")
        self.assertTrue(value.accepted)
        self.assertTrue(value.release_ready)

    def test_ready_history_head_is_entry_address(self):
        value = self._history()
        self.assertEqual(value.head_address, value.entries[-1].content_address)
        self.assertEqual(value.gate_address, value.entries[-1].gate_address)

    def test_history_boundary_is_public(self):
        value = self._history()
        self.assertEqual(
            value.boundary,
            history.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_BOUNDARY,
        )

    def test_history_id_is_preserved(self):
        value = self._history(history_id="run:123")
        self.assertEqual(value.history_id, "run:123")

    def test_history_entries_are_tuple_backed(self):
        self.assertIsInstance(self._history().entries, tuple)

    def test_history_entry_ordinal_starts_at_zero(self):
        self.assertEqual(self._history().entries[0].ordinal, 0)

    def test_first_entry_has_no_previous_head(self):
        self.assertIsNone(self._history().entries[0].previous_head_address)

    def test_entry_projects_gate_decision(self):
        value = self._history()
        self.assertEqual(value.entries[0].decision, "promote")

    def test_entry_projects_ready_state(self):
        entry = self._history().entries[0]
        self.assertEqual((entry.state, entry.accepted, entry.release_ready), ("ready", True, True))

    def test_entry_address_is_deterministic(self):
        entry = self._history().entries[0]
        self.assertEqual(
            history.address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_entry(
                entry
            ),
            entry.content_address,
        )

    def test_history_address_is_deterministic(self):
        value = self._history()
        self.assertEqual(
            history.address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                value
            ),
            value.content_address,
        )

    def test_build_rejects_untyped_gate(self):
        with self.assertRaises(ValidationError):
            history.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                SimpleNamespace()
            )

    def test_build_rejects_untyped_history_input_to_append(self):
        with self.assertRaises(ValidationError):
            history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                SimpleNamespace(), self._gate()
            )

    def test_build_from_directories_reads_persisted_packets(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            value = history.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_from_directories(
                left, right, history_id="directories"
            )
            self.assertEqual(value.history_id, "directories")
            self.assertTrue(value.release_ready)

    def test_build_from_directories_rejects_unknown_options(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            with self.assertRaises(ValidationError):
                history.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_from_directories(
                    left, right, unknown_option=True
                )

    def test_build_from_directories_accepts_explicit_ids(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            value = history.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_from_directories(
                left,
                right,
                diff_id="d:1",
                review_id="r:1",
                assurance_id="a:1",
                gate_id="g:1",
                history_id="h:1",
                decision_id="decision:1",
            )
            self.assertEqual(value.history_id, "h:1")
            self.assertTrue(value.accepted)

    def test_build_from_directories_accepts_hold_decision(self):
        with tempfile.TemporaryDirectory() as root:
            left = self._write_packet(root, self._held_pair()[0], "left")
            right = self._write_packet(root, self._held_pair()[1], "right")
            value = history.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_from_directories(
                left, right, decision="hold", history_id="held"
            )
            self.assertEqual((value.state, value.release_ready), ("held", False))

    def test_build_from_directories_accepts_block_decision(self):
        with tempfile.TemporaryDirectory() as root:
            left = self._write_packet(root, self._blocked_pair()[0], "left")
            right = self._write_packet(root, self._blocked_pair()[1], "right")
            value = history.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_from_directories(
                left, right, decision="block", history_id="blocked"
            )
            self.assertEqual((value.state, value.accepted), ("blocked", False))

    def test_build_from_directories_accepts_supersede_decision(self):
        with tempfile.TemporaryDirectory() as root:
            left = self._write_packet(root, self._held_pair()[0], "left")
            right = self._write_packet(root, self._held_pair()[1], "right")
            value = history.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_from_directories(
                left, right, decision="supersede", history_id="superseded"
            )
            self.assertEqual(value.state, "held")

    def test_supplied_detail_is_in_entry(self):
        value = self._history(detail="manual release review")
        self.assertEqual(value.entries[0].detail, "manual release review")

    def test_default_detail_is_nonempty(self):
        self.assertTrue(self._history().entries[0].detail)

    def test_public_projection_contains_no_private_attributes(self):
        value = self._history()
        self.assertNotIn("_validate", canonical_json(value.to_dict()))

    def test_public_projection_contains_no_agent_attribute(self):
        self.assertNotIn("agent", canonical_json(self._history().to_dict()).casefold())

    def test_public_projection_contains_no_language_attribute(self):
        self.assertNotIn("language", canonical_json(self._history().to_dict()).casefold())

    def test_public_projection_contains_no_model_attribute(self):
        self.assertNotIn("model", canonical_json(self._history().to_dict()).casefold())

    def test_public_projection_contains_no_user_attribute(self):
        self.assertNotIn("user", canonical_json(self._history().to_dict()).casefold())

    def test_public_projection_contains_no_path_attribute(self):
        self.assertNotIn("path", canonical_json(self._history().to_dict()).casefold())

    def test_public_projection_contains_no_timestamp_attribute(self):
        self.assertNotIn("timestamp", canonical_json(self._history().to_dict()).casefold())

    def test_append_promote_to_hold_updates_head(self):
        value = self._history()
        appended = history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value, self._decision_gate("hold", "hold-1"), expected_head_address=value.head_address
        )
        self.assertEqual(appended.entry_count, 2)
        self.assertEqual(appended.state, "held")
        self.assertFalse(appended.release_ready)
        self.assertEqual(appended.hold_count, 1)
        self.assertEqual(appended.entries[1].previous_head_address, value.head_address)

    def test_append_hold_to_block_updates_head(self):
        value = self._history()
        value = history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value, self._decision_gate("hold", "hold-2")
        )
        value = history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value, self._decision_gate("block", "block-1")
        )
        self.assertEqual(
            (value.state, value.accepted, value.release_ready), ("blocked", False, False)
        )
        self.assertEqual((value.promote_count, value.hold_count, value.block_count), (1, 1, 1))

    def test_append_block_to_promote_preserves_rejection_record(self):
        value = self._history()
        value = history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value, self._decision_gate("block", "block-2")
        )
        value = history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value, self._decision_gate("promote", "promote-2")
        )
        self.assertEqual(value.state, "ready")
        self.assertTrue(value.release_ready)
        self.assertEqual([item.decision for item in value.entries], ["promote", "block", "promote"])

    def test_append_supersede_is_held(self):
        value = self._history()
        appended = history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value, self._decision_gate("supersede", "supersede-1")
        )
        self.assertEqual(appended.entries[-1].state, "held")
        self.assertFalse(appended.entries[-1].release_ready)
        self.assertEqual(appended.supersede_count, 1)

    def test_append_is_content_addressed(self):
        value = history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history(), self._decision_gate("hold", "address-append")
        )
        self.assertEqual(
            history.address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                value
            ),
            value.content_address,
        )

    def test_append_is_deterministic_for_same_head(self):
        first = history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history(), self._decision_gate("hold", "same-append")
        )
        second = history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history(), self._decision_gate("hold", "same-append")
        )
        self.assertEqual(first.content_address, second.content_address)

    def test_append_requires_current_expected_head(self):
        value = self._history()
        with self.assertRaises(ValidationError):
            history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                value,
                self._decision_gate("hold", "stale"),
                expected_head_address="history-entry:stale",
            )

    def test_append_accepts_omitted_expected_head(self):
        value = history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history(), self._decision_gate("hold", "no-guard")
        )
        self.assertEqual(value.entry_count, 2)

    def test_append_rejects_duplicate_gate_address(self):
        gate = self._decision_gate("promote", "duplicate-gate")
        value = history.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            gate
        )
        with self.assertRaises(ValidationError):
            history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                value, gate
            )

    def test_append_rejects_unverified_gate_address_projection(self):
        gate = self._decision_gate("hold", "bad-gate")
        gate.content_address = "gate:tampered"
        with self.assertRaises(ValidationError):
            history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), gate
            )

    def test_append_rejects_unverified_history(self):
        value = self._history()
        value.head_address = "head:tampered"
        with self.assertRaises(ValidationError):
            history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                value, self._decision_gate("hold", "bad-history")
            )

    def test_append_rejects_wrong_gate_type(self):
        with self.assertRaises(ValidationError):
            history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), SimpleNamespace(content_address="gate:x")
            )

    def test_append_rejects_wrong_history_type(self):
        with self.assertRaises(ValidationError):
            history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                SimpleNamespace(), self._decision_gate("hold", "wrong-history")
            )

    def test_append_rejects_when_entry_limit_is_exhausted(self):
        value = self._history()
        value.entry_count = history.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_MAX_ENTRIES
        with self.assertRaises(ValidationError):
            history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                value, self._decision_gate("hold", "limit")
            )

    def test_append_does_not_mutate_input_entries(self):
        value = self._history()
        original = value.entries
        history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value, self._decision_gate("hold", "immutable")
        )
        self.assertEqual(value.entries, original)
        self.assertEqual(value.entry_count, 1)

    def test_append_does_not_mutate_input_address(self):
        value = self._history()
        original = value.content_address
        history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value, self._decision_gate("hold", "immutable-address")
        )
        self.assertEqual(value.content_address, original)

    def test_append_preserves_history_id(self):
        value = self._history(history_id="keep-me")
        appended = history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value, self._decision_gate("hold", "history-id")
        )
        self.assertEqual(appended.history_id, "keep-me")

    def test_append_preserves_history_boundary(self):
        value = self._history()
        appended = history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value, self._decision_gate("hold", "boundary")
        )
        self.assertEqual(appended.boundary, value.boundary)

    def test_append_assigns_next_contiguous_ordinal(self):
        value = self._history()
        value = history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value, self._decision_gate("hold", "ordinal-1")
        )
        value = history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value, self._decision_gate("supersede", "ordinal-2")
        )
        self.assertEqual([item.ordinal for item in value.entries], [0, 1, 2])

    def test_append_links_previous_head_to_immediate_parent(self):
        first = self._history()
        second = history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            first, self._decision_gate("hold", "link-1")
        )
        third = history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            second, self._decision_gate("block", "link-2")
        )
        self.assertEqual(third.entries[1].previous_head_address, first.head_address)
        self.assertEqual(third.entries[2].previous_head_address, second.head_address)

    def test_append_chain_is_replayable(self):
        value = self._history()
        decisions = ("hold", "supersede", "block", "promote")
        for ordinal, decision in enumerate(decisions):
            value = history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                value, self._decision_gate(decision, f"replay-{ordinal}")
            )
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertTrue(receipt.accepted)
        self.assertEqual(value.entry_count, 5)
        self.assertEqual(value.promote_count, 2)
        self.assertEqual(value.hold_count, 1)
        self.assertEqual(value.block_count, 1)
        self.assertEqual(value.supersede_count, 1)

    def test_all_decision_kinds_have_closed_projection(self):
        for decision, expected in (
            ("promote", ("ready", True, True)),
            ("hold", ("held", True, False)),
            ("supersede", ("held", True, False)),
            ("block", ("blocked", False, False)),
        ):
            right = None
            if decision == "block":
                right = self._blocked_pair()[1]
            elif decision in {"hold", "supersede"}:
                right = self._held_pair()[1]
            value = self._history(
                decision=decision, right=right, history_id=f"projection-{decision}"
            )
            self.assertEqual((value.state, value.accepted, value.release_ready), expected)

    def test_history_head_projection_matches_every_decision(self):
        for decision in (None, "hold", "supersede", "block"):
            right = (
                self._blocked_pair()[1]
                if decision == "block"
                else self._held_pair()[1]
                if decision in {"hold", "supersede"}
                else None
            )
            value = self._history(
                decision=decision, right=right, history_id=f"head-{decision or 'promote'}"
            )
            entry = value.entries[-1]
            self.assertEqual(value.gate_address, entry.gate_address)
            self.assertEqual(value.head_address, entry.content_address)
            self.assertEqual(value.state, entry.state)

    def test_history_counter_conservation_after_mixed_chain(self):
        value = self._history()
        for ordinal, decision in enumerate(("hold", "block", "supersede", "promote")):
            value = history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                value, self._decision_gate(decision, f"counts-{ordinal}")
            )
        self.assertEqual(
            value.entry_count,
            sum((value.promote_count, value.hold_count, value.block_count, value.supersede_count)),
        )

    def test_history_entry_details_survive_append(self):
        gate = self._decision_gate("hold", "detail-survival")
        value = history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history(), gate, detail="evidence is incomplete"
        )
        self.assertEqual(value.entries[-1].detail, "evidence is incomplete")

    def test_history_detail_is_separate_from_entry_detail(self):
        value = self._history(detail="history detail")
        self.assertEqual(value.entries[0].detail, "history detail")

    def test_history_summary_excludes_entries(self):
        value = self._history()
        self.assertNotIn("entries", value.summary())

    def test_history_full_projection_includes_entries(self):
        value = self._history()
        self.assertEqual(len(value.to_dict()["entries"]), 1)

    def test_history_projection_can_be_canonicalized(self):
        value = self._history()
        self.assertEqual(json.loads(canonical_json(value.to_dict())), value.to_dict())

    def test_history_version_is_stable(self):
        self.assertEqual(
            self._history().version,
            history.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_VERSION,
        )

    def test_history_constants_are_bounded(self):
        self.assertGreater(
            history.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_MAX_ENTRIES,
            1,
        )
        self.assertGreaterEqual(
            history.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_MAX_CHECKS,
            10,
        )

    def test_verifier_accepts_ready_history(self):
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        self.assertTrue(receipt.accepted)

    def test_verifier_reports_nine_structural_checks(self):
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        self.assertEqual(receipt.check_count, 9)

    def test_verifier_reports_ten_checks_with_supplied_head(self):
        gate = self._decision_gate("promote", "supplied-head")
        value = history.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            gate
        )
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value, supplied_gate=gate
        )
        self.assertEqual(receipt.check_count, 10)
        self.assertTrue(receipt.accepted)

    def test_verifier_rejects_untyped_value(self):
        with self.assertRaises(ValidationError):
            history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                SimpleNamespace()
            )

    def test_verifier_rejects_untyped_supplied_gate(self):
        with self.assertRaises(ValidationError):
            history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), supplied_gate=SimpleNamespace()
            )

    def test_verifier_detects_tampered_history_address(self):
        value = self._history()
        value.content_address = "history:tampered"
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertFalse(receipt.accepted)
        self.assertFalse(receipt.checks[0].passed)

    def test_verifier_detects_tampered_head_address(self):
        value = self._history()
        value.head_address = "entry:tampered"
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertFalse(receipt.accepted)
        self.assertFalse(
            next(item for item in receipt.checks if item.kind == "head-projection").passed
        )

    def test_verifier_detects_tampered_gate_projection(self):
        value = self._history()
        value.gate_address = "gate:tampered"
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertFalse(
            next(item for item in receipt.checks if item.kind == "head-projection").passed
        )

    def test_verifier_detects_tampered_state_projection(self):
        value = self._history()
        value.state = "held"
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertFalse(receipt.accepted)
        self.assertFalse(
            next(item for item in receipt.checks if item.kind == "head-projection").passed
        )

    def test_verifier_detects_tampered_accepted_projection(self):
        value = self._history()
        value.accepted = False
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertFalse(
            next(item for item in receipt.checks if item.kind == "head-projection").passed
        )

    def test_verifier_detects_tampered_ready_projection(self):
        value = self._history()
        value.release_ready = False
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertFalse(
            next(item for item in receipt.checks if item.kind == "head-projection").passed
        )

    def test_verifier_detects_tampered_entry_address(self):
        value = self._history()
        value.entries[0].content_address = "entry:tampered"
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertFalse(
            next(item for item in receipt.checks if item.kind == "entry-addresses").passed
        )

    def test_verifier_detects_tampered_entry_ordinal(self):
        value = self._history()
        value.entries[0].ordinal = 1
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertFalse(
            next(item for item in receipt.checks if item.kind == "head-continuity").passed
        )

    def test_verifier_detects_tampered_entry_decision_closure(self):
        value = self._history()
        value.entries[0].decision = "block"
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertFalse(
            next(item for item in receipt.checks if item.kind == "decision-closure").passed
        )

    def test_verifier_detects_tampered_entry_state(self):
        value = self._history()
        value.entries[0].state = "held"
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertFalse(
            next(item for item in receipt.checks if item.kind == "decision-closure").passed
        )

    def test_verifier_detects_tampered_entry_acceptance(self):
        value = self._history()
        value.entries[0].accepted = False
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertFalse(
            next(item for item in receipt.checks if item.kind == "decision-closure").passed
        )

    def test_verifier_detects_tampered_entry_readiness(self):
        value = self._history()
        value.entries[0].release_ready = False
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertFalse(
            next(item for item in receipt.checks if item.kind == "decision-closure").passed
        )

    def test_verifier_detects_tampered_entry_count(self):
        value = self._history()
        value.entry_count = 2
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertFalse(
            next(item for item in receipt.checks if item.kind == "entry-conservation").passed
        )

    def test_verifier_detects_tampered_promote_count(self):
        value = self._history()
        value.promote_count = 0
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertFalse(
            next(item for item in receipt.checks if item.kind == "decision-counts").passed
        )

    def test_verifier_detects_tampered_hold_count(self):
        value = self._history()
        value.hold_count = 1
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertFalse(
            next(item for item in receipt.checks if item.kind == "decision-counts").passed
        )

    def test_verifier_detects_tampered_block_count(self):
        value = self._history()
        value.block_count = 1
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertFalse(
            next(item for item in receipt.checks if item.kind == "decision-counts").passed
        )

    def test_verifier_detects_tampered_supersede_count(self):
        value = self._history()
        value.supersede_count = 1
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertFalse(
            next(item for item in receipt.checks if item.kind == "decision-counts").passed
        )

    def test_verifier_detects_tampered_second_previous_head(self):
        value = history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history(), self._decision_gate("hold", "chain-tamper")
        )
        value.entries[1].previous_head_address = "head:wrong"
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertFalse(
            next(item for item in receipt.checks if item.kind == "head-continuity").passed
        )

    def test_verifier_detects_duplicate_gate_addresses(self):
        value = history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history(), self._decision_gate("hold", "duplicate-check")
        )
        value.entries[1].gate_address = value.entries[0].gate_address
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertFalse(
            next(item for item in receipt.checks if item.kind == "unique-gates").passed
        )

    def test_verifier_detects_wrong_supplied_head_gate(self):
        value = self._history()
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value, supplied_gate=self._decision_gate("promote", "different-supplied")
        )
        self.assertFalse(receipt.accepted)
        self.assertFalse(receipt.checks[-1].passed)

    def test_verifier_detects_tampered_supplied_head_gate_address(self):
        gate = self._decision_gate("promote", "tampered-supplied")
        value = history.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            gate
        )
        gate.content_address = "gate:tampered"
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value, supplied_gate=gate
        )
        self.assertFalse(receipt.accepted)

    def test_verification_receipt_counts_passed_and_failed(self):
        value = self._history()
        value.head_address = "entry:bad"
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertEqual(receipt.passed_count + receipt.failed_count, receipt.check_count)
        self.assertEqual(receipt.failed_count, sum(not item.passed for item in receipt.checks))

    def test_verification_receipt_address_is_deterministic(self):
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        self.assertEqual(
            history.address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_verification(
                receipt
            ),
            receipt.content_address,
        )

    def test_verification_check_addresses_are_deterministic(self):
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        for check in receipt.checks:
            self.assertEqual(
                history.address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_check(
                    check
                ),
                check.content_address,
            )

    def test_verification_check_kinds_are_unique(self):
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        self.assertEqual(len({item.kind for item in receipt.checks}), receipt.check_count)

    def test_verification_check_ordinals_are_contiguous(self):
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        self.assertEqual(
            [item.ordinal for item in receipt.checks], list(range(receipt.check_count))
        )

    def test_verification_expected_observed_are_public_data(self):
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        for check in receipt.checks:
            self.assertIsNotNone(check.expected)
            self.assertIsNotNone(check.observed)

    def test_verification_receipt_has_history_address(self):
        value = self._history()
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertEqual(receipt.history_address, value.content_address)

    def test_verification_receipt_to_dict_is_jsonable(self):
        receipt = history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        self.assertEqual(json.loads(canonical_json(receipt.to_dict())), receipt.to_dict())

    def test_history_entry_from_dict_round_trips(self):
        entry = self._history().entries[0]
        restored = history._entry_from_dict(entry.to_dict())
        self.assertEqual(restored.to_dict(), entry.to_dict())

    def test_history_from_dict_round_trips(self):
        value = self._history()
        restored = history._history_from_dict(value.to_dict())
        self.assertEqual(restored.to_dict(), value.to_dict())

    def test_history_from_dict_rehydrates_entries_as_tuples(self):
        restored = history._history_from_dict(self._history().to_dict())
        self.assertIsInstance(restored.entries, tuple)

    def test_history_from_dict_rejects_missing_entries(self):
        body = self._history().to_dict()
        body.pop("entries")
        with self.assertRaises((KeyError, ValidationError, TypeError)):
            history._history_from_dict(body)

    def test_history_from_dict_rejects_extra_constructor_field(self):
        body = self._history().to_dict()
        body["extra"] = True
        with self.assertRaises(TypeError):
            history._history_from_dict(body)

    def test_decision_enum_values_are_public(self):
        self.assertEqual(
            [
                item.value
                for item in history.ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryDecision
            ],
            ["promote", "hold", "block", "supersede"],
        )

    def test_state_enum_values_are_public(self):
        self.assertEqual(
            [
                item.value
                for item in history.ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryState
            ],
            ["ready", "held", "blocked"],
        )

    def _mixed_history(self):
        value = self._history()
        for ordinal, decision in enumerate(("hold", "block", "supersede", "promote")):
            value = history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                value, self._decision_gate(decision, f"query-mixed-{ordinal}")
            )
        return value

    def test_history_json_export_has_trailing_newline(self):
        output = history.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_json(
            self._history()
        )
        self.assertTrue(output.endswith("\n"))

    def test_history_json_export_is_canonical(self):
        value = self._history()
        output = history.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_json(
            value
        )
        self.assertEqual(output, canonical_json(value.to_dict()) + "\n")

    def test_history_json_export_contains_entries(self):
        self.assertIn(
            '"entries"',
            history.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_json(
                self._history()
            ),
        )

    def test_history_json_export_rejects_tampered_value(self):
        value = self._history()
        value.head_address = "head:bad"
        with self.assertRaises(ValidationError):
            history.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_json(
                value
            )

    def test_history_csv_has_expected_header(self):
        output = history.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_csv(
            self._history()
        )
        self.assertEqual(
            next(csv.reader(StringIO(output))),
            [
                "ordinal",
                "gate_address",
                "decision",
                "state",
                "accepted",
                "release_ready",
                "previous_head_address",
                "detail",
                "content_address",
            ],
        )

    def test_history_csv_has_one_row_per_entry(self):
        value = self._mixed_history()
        rows = list(
            csv.DictReader(
                StringIO(
                    history.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_csv(
                        value
                    )
                )
            )
        )
        self.assertEqual(len(rows), value.entry_count)

    def test_history_csv_preserves_decisions(self):
        rows = list(
            csv.DictReader(
                StringIO(
                    history.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_csv(
                        self._mixed_history()
                    )
                )
            )
        )
        self.assertEqual(
            [row["decision"] for row in rows], ["promote", "hold", "block", "supersede", "promote"]
        )

    def test_history_csv_preserves_previous_heads(self):
        value = self._mixed_history()
        rows = list(
            csv.DictReader(
                StringIO(
                    history.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_csv(
                        value
                    )
                )
            )
        )
        self.assertEqual(rows[0]["previous_head_address"], "")
        self.assertEqual(rows[1]["previous_head_address"], value.entries[0].content_address)

    def test_history_csv_is_newline_terminated(self):
        self.assertTrue(
            history.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_csv(
                self._history()
            ).endswith("\n")
        )

    def test_history_csv_rejects_tampered_value(self):
        value = self._history()
        value.content_address = "history:bad"
        with self.assertRaises(ValidationError):
            history.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_csv(
                value
            )

    def test_history_markdown_has_title(self):
        self.assertTrue(
            history.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_markdown(
                self._history()
            ).startswith("# Catalog Packet Review Gate History")
        )

    def test_history_markdown_has_head(self):
        value = self._history()
        self.assertIn(
            value.head_address,
            history.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_markdown(
                value
            ),
        )

    def test_history_markdown_has_decision_table(self):
        output = history.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_markdown(
            self._history()
        )
        self.assertIn("| # | Decision | State | Accepted | Ready | Detail |", output)

    def test_history_markdown_lists_all_entries(self):
        output = history.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_markdown(
            self._mixed_history()
        )
        self.assertGreaterEqual(output.count("| `"), 5)

    def test_history_markdown_rejects_tampered_value(self):
        value = self._history()
        value.content_address = "history:bad"
        with self.assertRaises(ValidationError):
            history.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_markdown(
                value
            )

    def test_query_defaults_to_entries(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        self.assertEqual(result["query"]["resource"], "entries")
        self.assertEqual(result["total"], 1)
        self.assertEqual(len(result["items"]), 1)

    def test_query_summary_returns_one_row(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history(), resource="summary"
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["entry_count"], 5)

    def test_query_checks_returns_verification_checks(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history(), resource="checks"
        )
        self.assertEqual(result["total"], 9)
        self.assertEqual(result["items"][0]["kind"], "aggregate-address")

    def test_query_entries_returns_all_mixed_rows(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history()
        )
        self.assertEqual(result["total"], 5)
        self.assertEqual(
            [row["decision"] for row in result["items"]],
            ["promote", "hold", "block", "supersede", "promote"],
        )

    def test_query_filters_promote_decisions(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history(), decision="promote"
        )
        self.assertEqual(result["total"], 2)
        self.assertTrue(all(row["decision"] == "promote" for row in result["items"]))

    def test_query_filters_hold_decisions(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history(), decision="hold"
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["state"], "held")

    def test_query_filters_block_decisions(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history(), decision="block"
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["state"], "blocked")

    def test_query_filters_supersede_decisions(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history(), decision="supersede"
        )
        self.assertEqual(result["total"], 1)

    def test_query_filters_ready_state(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history(), state="ready"
        )
        self.assertEqual(result["total"], 2)
        self.assertTrue(all(row["state"] == "ready" for row in result["items"]))

    def test_query_filters_held_state(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history(), state="held"
        )
        self.assertEqual(result["total"], 2)
        self.assertTrue(all(row["state"] == "held" for row in result["items"]))

    def test_query_filters_blocked_state(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history(), state="blocked"
        )
        self.assertEqual(result["total"], 1)

    def test_query_filters_accepted_rows(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history(), accepted=True
        )
        self.assertEqual(result["total"], 4)
        self.assertTrue(all(row["accepted"] for row in result["items"]))

    def test_query_filters_rejected_rows(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history(), accepted=False
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["decision"], "block")

    def test_query_filters_release_ready_rows(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history(), release_ready=True
        )
        self.assertEqual(result["total"], 2)

    def test_query_filters_not_release_ready_rows(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history(), release_ready=False
        )
        self.assertEqual(result["total"], 3)

    def test_query_combines_decision_and_state_filters(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history(), decision="hold", state="held"
        )
        self.assertEqual(result["total"], 1)

    def test_query_text_matches_detail(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history(), text="supersede"
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["decision"], "supersede")

    def test_query_text_is_case_insensitive(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history(), text="SUPERSEDE"
        )
        self.assertEqual(result["total"], 1)

    def test_query_offset_pages_rows(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history(), offset=2, limit=2
        )
        self.assertEqual(result["total"], 5)
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["items"][0]["ordinal"], 2)

    def test_query_limit_truncates_rows(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history(), limit=1
        )
        self.assertEqual(len(result["items"]), 1)

    def test_query_offset_beyond_end_is_empty(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history(), offset=99
        )
        self.assertEqual(result["items"], [])

    def test_query_result_contains_history_summary(self):
        value = self._mixed_history()
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertEqual(result["history"], value.summary())

    def test_query_result_is_addressed(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        self.assertTrue(
            result["content_address"].startswith(
                history.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_QUERY_PREFIX
                + ":"
            )
        )

    def test_query_receipt_verifies(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        self.assertEqual(
            history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_query(
                result
            ),
            result,
        )

    def test_query_receipt_rejects_address_tampering(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        result["content_address"] = "query:bad"
        with self.assertRaises(ValidationError):
            history.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_query(
                result
            )

    def test_query_rejects_invalid_resource(self):
        with self.assertRaises(ValidationError):
            history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), resource="invalid"
            )

    def test_query_rejects_invalid_decision(self):
        with self.assertRaises(ValidationError):
            history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), decision="invalid"
            )

    def test_query_rejects_invalid_state(self):
        with self.assertRaises(ValidationError):
            history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), state="invalid"
            )

    def test_query_rejects_nonboolean_accepted(self):
        with self.assertRaises(ValidationError):
            history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), accepted=1
            )

    def test_query_rejects_nonboolean_release_ready(self):
        with self.assertRaises(ValidationError):
            history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), release_ready=1
            )

    def test_query_rejects_negative_offset(self):
        with self.assertRaises(ValidationError):
            history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), offset=-1
            )

    def test_query_rejects_boolean_offset(self):
        with self.assertRaises(ValidationError):
            history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), offset=True
            )

    def test_query_rejects_zero_limit(self):
        with self.assertRaises(ValidationError):
            history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), limit=0
            )

    def test_query_rejects_boolean_limit(self):
        with self.assertRaises(ValidationError):
            history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), limit=True
            )

    def test_query_rejects_limit_above_bound(self):
        with self.assertRaises(ValidationError):
            history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), limit=513
            )

    def test_query_rejects_empty_text(self):
        with self.assertRaises(ValidationError):
            history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), text=""
            )

    def test_query_json_export_is_addressed(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        self.assertEqual(
            history.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_query_json(
                result
            ),
            canonical_json(result) + "\n",
        )

    def test_query_csv_entries_has_entry_header(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        self.assertIn(
            "gate_address",
            history.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_query_csv(
                result
            ).splitlines()[0],
        )

    def test_query_csv_checks_has_check_header(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history(), resource="checks"
        )
        self.assertIn(
            "kind",
            history.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_query_csv(
                result
            ).splitlines()[0],
        )

    def test_query_csv_summary_has_summary_header(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history(), resource="summary"
        )
        self.assertIn(
            "history_id",
            history.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_query_csv(
                result
            ).splitlines()[0],
        )

    def test_query_markdown_entries_has_title(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        self.assertTrue(
            history.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_query_markdown(
                result
            ).startswith("# Catalog Packet Review Gate History Query")
        )

    def test_query_markdown_checks_has_kind(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history(), resource="checks"
        )
        self.assertIn(
            "Kind",
            history.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_query_markdown(
                result
            ),
        )

    def test_query_markdown_summary_has_field_table(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history(), resource="summary"
        )
        self.assertIn(
            "| Field | Value |",
            history.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_query_markdown(
                result
            ),
        )

    def test_query_exports_reject_tampered_receipt(self):
        result = history.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        result["content_address"] = "query:bad"
        with self.assertRaises(ValidationError):
            history.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_query_json(
                result
            )

    def test_cli_history_schema_command_is_json(self):
        output = StringIO()
        with redirect_stdout(output):
            result = main(
                [
                    "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-schema"
                ]
            )
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue())["max_entries"], 256)

    def test_cli_history_capabilities_command_is_json(self):
        output = StringIO()
        with redirect_stdout(output):
            result = main(
                [
                    "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-capabilities"
                ]
            )
        self.assertEqual(result, 0)
        self.assertIn("append", json.loads(output.getvalue())["operations"])

    def test_cli_history_query_schema_command_is_json(self):
        output = StringIO()
        with redirect_stdout(output):
            result = main(
                [
                    "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-query-schema"
                ]
            )
        self.assertEqual(result, 0)
        self.assertIn("decision", json.loads(output.getvalue())["filters"])

    def test_cli_history_query_capabilities_command_is_json(self):
        output = StringIO()
        with redirect_stdout(output):
            result = main(
                [
                    "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-query-capabilities"
                ]
            )
        self.assertEqual(result, 0)
        self.assertTrue(json.loads(output.getvalue())["addressed_receipts"])

    def test_cli_history_builds_summary_from_directories(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history",
                        "--left-packet-directory",
                        str(left),
                        "--right-packet-directory",
                        str(right),
                        "--format",
                        "summary",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.getvalue())["state"], "ready")

    def test_cli_history_builds_json_from_directories(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history",
                        "--left-packet-directory",
                        str(left),
                        "--right-packet-directory",
                        str(right),
                    ]
                )
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.getvalue())["entry_count"], 1)

    def test_cli_history_builds_csv_from_directories(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history",
                        "--left-packet-directory",
                        str(left),
                        "--right-packet-directory",
                        str(right),
                        "--format",
                        "csv",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertIn("gate_address", output.getvalue().splitlines()[0])

    def test_cli_history_builds_markdown_from_directories(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history",
                        "--left-packet-directory",
                        str(left),
                        "--right-packet-directory",
                        str(right),
                        "--format",
                        "markdown",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertTrue(output.getvalue().startswith("# Catalog Packet Review Gate History"))

    def test_cli_history_accepts_explicit_history_id(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history",
                        "--left-packet-directory",
                        str(left),
                        "--right-packet-directory",
                        str(right),
                        "--history-id",
                        "cli-history",
                        "--format",
                        "summary",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.getvalue())["history_id"], "cli-history")

    def test_cli_history_accepts_hold_decision(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._held_pair()
            left = self._write_packet(root, left, "left")
            right = self._write_packet(root, right, "right")
            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history",
                        "--left-packet-directory",
                        str(left),
                        "--right-packet-directory",
                        str(right),
                        "--decision",
                        "hold",
                        "--format",
                        "summary",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.getvalue())["state"], "held")

    def test_cli_history_accepts_block_decision(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._blocked_pair()
            left = self._write_packet(root, left, "left")
            right = self._write_packet(root, right, "right")
            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history",
                        "--left-packet-directory",
                        str(left),
                        "--right-packet-directory",
                        str(right),
                        "--decision",
                        "block",
                        "--format",
                        "summary",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.getvalue())["state"], "blocked")

    def test_cli_history_query_returns_entries(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-query",
                        "--left-packet-directory",
                        str(left),
                        "--right-packet-directory",
                        str(right),
                    ]
                )
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.getvalue())["total"], 1)

    def test_cli_history_query_accepts_resource_checks(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-query",
                        "--left-packet-directory",
                        str(left),
                        "--right-packet-directory",
                        str(right),
                        "--resource",
                        "checks",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.getvalue())["items"][0]["kind"], "aggregate-address")

    def test_cli_history_query_filters_decision(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._held_pair()
            left = self._write_packet(root, left, "left")
            right = self._write_packet(root, right, "right")
            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-query",
                        "--left-packet-directory",
                        str(left),
                        "--right-packet-directory",
                        str(right),
                        "--decision",
                        "hold",
                        "--decision-filter",
                        "hold",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.getvalue())["items"][0]["decision"], "hold")

    def test_cli_history_query_accepts_state_filter(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._held_pair()
            left = self._write_packet(root, left, "left")
            right = self._write_packet(root, right, "right")
            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-query",
                        "--left-packet-directory",
                        str(left),
                        "--right-packet-directory",
                        str(right),
                        "--decision",
                        "hold",
                        "--state",
                        "held",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.getvalue())["total"], 1)

    def test_cli_history_query_accepts_accepted_flag(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._held_pair()
            left = self._write_packet(root, left, "left")
            right = self._write_packet(root, right, "right")
            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-query",
                        "--left-packet-directory",
                        str(left),
                        "--right-packet-directory",
                        str(right),
                        "--decision",
                        "hold",
                        "--accepted",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.getvalue())["total"], 1)

    def test_cli_history_query_accepts_release_ready_flag(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-query",
                        "--left-packet-directory",
                        str(left),
                        "--right-packet-directory",
                        str(right),
                        "--release-ready",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.getvalue())["total"], 1)

    def test_cli_history_query_can_render_csv(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-query",
                        "--left-packet-directory",
                        str(left),
                        "--right-packet-directory",
                        str(right),
                        "--format",
                        "csv",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertIn("gate_address", output.getvalue().splitlines()[0])

    def test_cli_history_query_can_render_markdown(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-query",
                        "--left-packet-directory",
                        str(left),
                        "--right-packet-directory",
                        str(right),
                        "--format",
                        "markdown",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertIn("# Catalog Packet Review Gate History Query", output.getvalue())

    def test_cli_history_query_paginates(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-query",
                        "--left-packet-directory",
                        str(left),
                        "--right-packet-directory",
                        str(right),
                        "--offset",
                        "1",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.getvalue())["items"], [])

    def test_cli_history_query_rejects_missing_directories(self):
        output = StringIO()
        with redirect_stdout(output):
            result = main(
                [
                    "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-query",
                    "--left-packet-directory",
                    "missing",
                    "--right-packet-directory",
                    "missing",
                ]
            )
        self.assertEqual(result, 2)

    def test_http_history_schema_route(self):
        server = create_server("127.0.0.1", 0, tempfile.mkdtemp())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history"
        try:
            status, content_type, body = self._http_json(server, base + "/schema", {})
            self.assertEqual(status, 200)
            self.assertIn("application/json", content_type)
            self.assertEqual(json.loads(body)["resources"], ["summary", "entries", "checks"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_http_history_capabilities_route(self):
        server = create_server("127.0.0.1", 0, tempfile.mkdtemp())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history"
        try:
            status, _, body = self._http_json(server, base + "/capabilities", {})
            self.assertEqual(status, 200)
            self.assertIn("append", json.loads(body)["operations"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_http_history_query_schema_route(self):
        server = create_server("127.0.0.1", 0, tempfile.mkdtemp())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history"
        try:
            status, _, body = self._http_json(server, base + "/query/schema", {})
            self.assertEqual(status, 200)
            self.assertIn("decision", json.loads(body)["filters"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_http_history_query_capabilities_route(self):
        server = create_server("127.0.0.1", 0, tempfile.mkdtemp())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history"
        try:
            status, _, body = self._http_json(server, base + "/query/capabilities", {})
            self.assertEqual(status, 200)
            self.assertTrue(json.loads(body)["addressed_receipts"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_http_history_base_builds_summary(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            server = create_server("127.0.0.1", 0, str(Path(root) / "data"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history"
            try:
                status, content_type, body = self._http_json(
                    server,
                    base,
                    {"left_packet_directory": str(left), "right_packet_directory": str(right)},
                )
                self.assertEqual(status, 200)
                self.assertIn("application/json", content_type)
                self.assertEqual(json.loads(body)["state"], "ready")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_http_history_query_builds_entries(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            server = create_server("127.0.0.1", 0, str(Path(root) / "data"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/query"
            try:
                status, _, body = self._http_json(
                    server,
                    base,
                    {"left_packet_directory": str(left), "right_packet_directory": str(right)},
                )
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)["total"], 1)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_http_history_query_supports_checks(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            server = create_server("127.0.0.1", 0, str(Path(root) / "data"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/query"
            try:
                status, _, body = self._http_json(
                    server,
                    base,
                    {
                        "left_packet_directory": str(left),
                        "right_packet_directory": str(right),
                        "resource": "checks",
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)["items"][0]["kind"], "aggregate-address")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_http_history_query_supports_summary(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            server = create_server("127.0.0.1", 0, str(Path(root) / "data"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/query"
            try:
                status, _, body = self._http_json(
                    server,
                    base,
                    {
                        "left_packet_directory": str(left),
                        "right_packet_directory": str(right),
                        "resource": "summary",
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)["items"][0]["entry_count"], 1)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_http_history_supports_directory_aliases(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            server = create_server("127.0.0.1", 0, str(Path(root) / "data"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history"
            try:
                status, _, body = self._http_json(
                    server, base, {"left_directory": str(left), "right_directory": str(right)}
                )
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)["state"], "ready")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_http_history_csv_negotiation(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            server = create_server("127.0.0.1", 0, str(Path(root) / "data"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history"
            try:
                status, content_type, body = self._http_json(
                    server,
                    base,
                    {
                        "left_packet_directory": str(left),
                        "right_packet_directory": str(right),
                        "format": "csv",
                    },
                )
                self.assertEqual(status, 200)
                self.assertIn("text/csv", content_type)
                self.assertIn("gate_address", body.splitlines()[0])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_http_history_markdown_negotiation(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            server = create_server("127.0.0.1", 0, str(Path(root) / "data"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history"
            try:
                status, content_type, body = self._http_json(
                    server,
                    base,
                    {
                        "left_packet_directory": str(left),
                        "right_packet_directory": str(right),
                        "format": "markdown",
                    },
                )
                self.assertEqual(status, 200)
                self.assertIn("text/markdown", content_type)
                self.assertIn("# Catalog Packet Review Gate History", body)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_http_history_query_csv_negotiation(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            server = create_server("127.0.0.1", 0, str(Path(root) / "data"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/query"
            try:
                status, content_type, body = self._http_json(
                    server,
                    base,
                    {
                        "left_packet_directory": str(left),
                        "right_packet_directory": str(right),
                        "format": "csv",
                    },
                )
                self.assertEqual(status, 200)
                self.assertIn("text/csv", content_type)
                self.assertIn("gate_address", body.splitlines()[0])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_http_history_query_markdown_negotiation(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            server = create_server("127.0.0.1", 0, str(Path(root) / "data"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/query"
            try:
                status, content_type, body = self._http_json(
                    server,
                    base,
                    {
                        "left_packet_directory": str(left),
                        "right_packet_directory": str(right),
                        "format": "markdown",
                    },
                )
                self.assertEqual(status, 200)
                self.assertIn("text/markdown", content_type)
                self.assertIn("# Catalog Packet Review Gate History Query", body)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_http_blocked_history_is_valid_transport(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._blocked_pair()
            left = self._write_packet(root, left, "left")
            right = self._write_packet(root, right, "right")
            server = create_server("127.0.0.1", 0, str(Path(root) / "data"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history"
            try:
                status, _, body = self._http_json(
                    server,
                    base,
                    {
                        "left_packet_directory": str(left),
                        "right_packet_directory": str(right),
                        "decision": "block",
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)["state"], "blocked")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_http_history_missing_directories_fails_closed(self):
        server = create_server("127.0.0.1", 0, tempfile.mkdtemp())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history"
        try:
            status, _, body = self._http_json(server, base, {})
            self.assertGreaterEqual(status, 400)
            self.assertTrue(body)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_http_history_duplicate_query_parameter_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            server = create_server("127.0.0.1", 0, str(Path(root) / "data"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history"
            try:
                connection = HTTPConnection("127.0.0.1", server.server_address[1], timeout=15)
                query = urlencode(
                    [
                        ("left_packet_directory", str(left)),
                        ("left_packet_directory", str(left)),
                        ("right_packet_directory", str(right)),
                    ]
                )
                connection.request("GET", base + "?" + query)
                response = connection.getresponse()
                body = response.read().decode("utf-8")
                connection.close()
                self.assertGreaterEqual(response.status, 400)
                self.assertTrue(body)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_replay_returns_report(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        self.assertIsInstance(
            report,
            replay.ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayReport,
        )

    def test_replay_accepts_ready_history(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        self.assertTrue(report.accepted)
        self.assertEqual(report.final_state, "ready")

    def test_replay_has_one_event_per_entry(self):
        value = self._mixed_history()
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertEqual(report.event_count, value.entry_count)

    def test_replay_has_eight_checks(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        self.assertEqual(report.check_count, 8)
        self.assertEqual(report.passed_count, 8)

    def test_replay_event_ordinals_are_contiguous(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history()
        )
        self.assertEqual([item.ordinal for item in report.events], list(range(report.event_count)))

    def test_replay_event_addresses_are_deterministic(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        for event in report.events:
            self.assertEqual(
                replay.address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_event(
                    event
                ),
                event.content_address,
            )

    def test_replay_check_addresses_are_deterministic(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        for check in report.checks:
            self.assertEqual(
                replay.address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_check(
                    check
                ),
                check.content_address,
            )

    def test_replay_report_address_is_deterministic(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        self.assertEqual(
            replay.address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_report(
                report
            ),
            report.content_address,
        )

    def test_replay_starts_at_start_state(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        self.assertEqual(report.events[0].before_state, "start")

    def test_replay_ready_transition(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        self.assertEqual(
            (report.events[0].before_state, report.events[0].after_state), ("start", "ready")
        )

    def test_replay_mixed_state_sequence(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history()
        )
        self.assertEqual(
            [item.before_state for item in report.events],
            ["start", "ready", "held", "blocked", "held"],
        )
        self.assertEqual(
            [item.after_state for item in report.events],
            ["ready", "held", "blocked", "held", "ready"],
        )

    def test_replay_preserves_gate_addresses(self):
        value = self._mixed_history()
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertEqual(
            [item.gate_address for item in report.events],
            [item.gate_address for item in value.entries],
        )

    def test_replay_preserves_head_addresses(self):
        value = self._mixed_history()
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertEqual(
            [item.head_address for item in report.events],
            [item.content_address for item in value.entries],
        )

    def test_replay_preserves_decisions(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history()
        )
        self.assertEqual(
            [item.decision for item in report.events],
            ["promote", "hold", "block", "supersede", "promote"],
        )

    def test_replay_preserves_acceptance_flags(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history()
        )
        self.assertEqual([item.accepted for item in report.events], [True, True, False, True, True])

    def test_replay_preserves_release_ready_flags(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history()
        )
        self.assertEqual(
            [item.release_ready for item in report.events], [True, False, False, False, True]
        )

    def test_replay_report_preserves_history_address(self):
        value = self._history()
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertEqual(report.history_address, value.content_address)

    def test_replay_report_preserves_terminal_acceptance(self):
        value = self._history(decision="block", right=self._blocked_pair()[1])
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertFalse(report.final_accepted)

    def test_replay_report_preserves_terminal_readiness(self):
        value = self._history(decision="hold", right=self._held_pair()[1])
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertFalse(report.final_release_ready)

    def test_replay_rejects_untyped_history(self):
        with self.assertRaises(ValidationError):
            replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                SimpleNamespace()
            )

    def test_replay_detects_tampered_source_history(self):
        value = self._history()
        value.head_address = "head:bad"
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertFalse(report.accepted)
        self.assertFalse(report.checks[0].passed)

    def test_replay_verifier_accepts_report(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        self.assertIs(
            replay.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay(
                report
            ),
            report,
        )

    def test_replay_verifier_rejects_untyped_report(self):
        with self.assertRaises(ValidationError):
            replay.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay(
                SimpleNamespace()
            )

    def test_replay_verifier_rejects_tampered_report_address(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        report.content_address = "report:bad"
        with self.assertRaises(ValidationError):
            replay.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay(
                report
            )

    def test_replay_verifier_rejects_tampered_event_address(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        report.events[0].content_address = "event:bad"
        with self.assertRaises(ValidationError):
            replay.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay(
                report
            )

    def test_replay_verifier_rejects_tampered_check_address(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        report.checks[0].content_address = "check:bad"
        with self.assertRaises(ValidationError):
            replay.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay(
                report
            )

    def test_replay_verifier_rejects_rejected_report(self):
        value = self._history()
        value.head_address = "head:bad"
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        with self.assertRaises(ValidationError):
            replay.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay(
                report
            )

    def test_replay_json_has_newline(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        self.assertTrue(
            replay.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_json(
                report
            ).endswith("\n")
        )

    def test_replay_json_is_canonical(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        self.assertEqual(
            replay.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_json(
                report
            ),
            canonical_json(report.to_dict()) + "\n",
        )

    def test_replay_csv_has_event_header(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        self.assertIn(
            "before_state",
            replay.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_csv(
                report
            ).splitlines()[0],
        )

    def test_replay_csv_has_one_row_per_event(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history()
        )
        rows = list(
            csv.DictReader(
                StringIO(
                    replay.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_csv(
                        report
                    )
                )
            )
        )
        self.assertEqual(len(rows), report.event_count)

    def test_replay_csv_preserves_transition_order(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history()
        )
        rows = list(
            csv.DictReader(
                StringIO(
                    replay.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_csv(
                        report
                    )
                )
            )
        )
        self.assertEqual(
            [row["before_state"] for row in rows], ["start", "ready", "held", "blocked", "held"]
        )

    def test_replay_markdown_has_title(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        self.assertTrue(
            replay.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_markdown(
                report
            ).startswith("# Catalog Packet Review Gate History Replay")
        )

    def test_replay_markdown_has_final_state(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        self.assertIn(
            "final-state: `ready`",
            replay.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_markdown(
                report
            ),
        )

    def test_replay_markdown_lists_transitions(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history()
        )
        output = replay.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_markdown(
            report
        )
        self.assertGreaterEqual(output.count("| `"), 5)

    def test_replay_exports_reject_unaccepted_report(self):
        value = self._history()
        value.head_address = "head:bad"
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        with self.assertRaises(ValidationError):
            replay.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_json(
                report
            )

    def test_replay_schema_exposes_states(self):
        schema = replay.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_schema()
        self.assertEqual(schema["states"], ["start", "ready", "held", "blocked"])

    def test_replay_schema_exposes_limits(self):
        schema = replay.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_schema()
        self.assertEqual(schema["max_events"], 256)
        self.assertEqual(schema["max_checks"], 16)

    def test_replay_schema_is_identity_free(self):
        schema = replay.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_schema()
        self.assertTrue(schema["identity_free"])
        self.assertTrue(schema["path_free"])
        self.assertTrue(schema["timestamp_free"])

    def test_replay_capabilities_expose_replay(self):
        self.assertIn(
            "replay",
            replay.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_capabilities()[
                "operations"
            ],
        )

    def test_replay_capabilities_expose_terminal_projection(self):
        self.assertTrue(
            replay.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_capabilities()[
                "terminal_projection"
            ]
        )

    def test_replay_query_defaults_to_events(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        result = replay.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay(
            report
        )
        self.assertEqual(result["query"]["resource"], "events")
        self.assertEqual(result["total"], 1)

    def test_replay_query_summary(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history()
        )
        result = replay.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay(
            report, resource="summary"
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["event_count"], 5)

    def test_replay_query_checks(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        result = replay.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay(
            report, resource="checks"
        )
        self.assertEqual(result["total"], 8)

    def test_replay_query_filters_decision(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history()
        )
        result = replay.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay(
            report, decision="block"
        )
        self.assertEqual(result["total"], 1)

    def test_replay_query_filters_before_state(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history()
        )
        result = replay.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay(
            report, before_state="held"
        )
        self.assertEqual(result["total"], 2)

    def test_replay_query_filters_after_state(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history()
        )
        result = replay.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay(
            report, after_state="blocked"
        )
        self.assertEqual(result["total"], 1)

    def test_replay_query_filters_accepted(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history()
        )
        result = replay.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay(
            report, accepted=False
        )
        self.assertEqual(result["total"], 1)

    def test_replay_query_filters_ready(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history()
        )
        result = replay.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay(
            report, release_ready=True
        )
        self.assertEqual(result["total"], 2)

    def test_replay_query_paginates(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._mixed_history()
        )
        result = replay.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay(
            report, offset=1, limit=2
        )
        self.assertEqual(len(result["items"]), 2)

    def test_replay_query_result_verifies(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        result = replay.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay(
            report
        )
        self.assertEqual(
            replay.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_query(
                result
            ),
            result,
        )

    def test_replay_query_result_is_addressed(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        result = replay.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay(
            report
        )
        self.assertTrue(
            result["content_address"].startswith(
                replay.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_REPLAY_PREFIX
                + "-query:"
            )
        )

    def test_replay_query_json_export(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        result = replay.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay(
            report
        )
        self.assertEqual(
            replay.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_query_json(
                result
            ),
            canonical_json(result) + "\n",
        )

    def test_replay_query_csv_events_header(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        result = replay.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay(
            report
        )
        self.assertIn(
            "before_state",
            replay.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_query_csv(
                result
            ).splitlines()[0],
        )

    def test_replay_query_markdown_has_title(self):
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            self._history()
        )
        result = replay.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay(
            report
        )
        self.assertTrue(
            replay.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_query_markdown(
                result
            ).startswith("# Catalog Packet Review Gate History Replay Query")
        )

    def test_cli_replay_schema_command(self):
        output = StringIO()
        with redirect_stdout(output):
            result = main(
                [
                    "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-replay-schema"
                ]
            )
        self.assertEqual(result, 0)
        self.assertIn("start", json.loads(output.getvalue())["states"])

    def test_cli_replay_capabilities_command(self):
        output = StringIO()
        with redirect_stdout(output):
            result = main(
                [
                    "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-replay-capabilities"
                ]
            )
        self.assertEqual(result, 0)
        self.assertTrue(json.loads(output.getvalue())["state_reconstruction"])

    def test_cli_replay_query_schema_command(self):
        output = StringIO()
        with redirect_stdout(output):
            result = main(
                [
                    "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-replay-query-schema"
                ]
            )
        self.assertEqual(result, 0)
        self.assertIn("before_state", json.loads(output.getvalue())["filters"])

    def test_cli_replay_query_capabilities_command(self):
        output = StringIO()
        with redirect_stdout(output):
            result = main(
                [
                    "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-replay-query-capabilities"
                ]
            )
        self.assertEqual(result, 0)
        self.assertTrue(json.loads(output.getvalue())["addressed_receipts"])

    def test_cli_replay_builds_summary(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-replay",
                        "--left-packet-directory",
                        str(left),
                        "--right-packet-directory",
                        str(right),
                        "--format",
                        "summary",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.getvalue())["final_state"], "ready")

    def test_cli_replay_builds_json(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-replay",
                        "--left-packet-directory",
                        str(left),
                        "--right-packet-directory",
                        str(right),
                    ]
                )
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.getvalue())["event_count"], 1)

    def test_cli_replay_builds_csv(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-replay",
                        "--left-packet-directory",
                        str(left),
                        "--right-packet-directory",
                        str(right),
                        "--format",
                        "csv",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertIn("before_state", output.getvalue().splitlines()[0])

    def test_cli_replay_builds_markdown(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-replay",
                        "--left-packet-directory",
                        str(left),
                        "--right-packet-directory",
                        str(right),
                        "--format",
                        "markdown",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertTrue(
                output.getvalue().startswith("# Catalog Packet Review Gate History Replay")
            )

    def test_cli_replay_supports_block_decision(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._blocked_pair()
            left = self._write_packet(root, left, "left")
            right = self._write_packet(root, right, "right")
            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-replay",
                        "--left-packet-directory",
                        str(left),
                        "--right-packet-directory",
                        str(right),
                        "--decision",
                        "block",
                        "--format",
                        "summary",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.getvalue())["final_state"], "blocked")

    def test_cli_replay_query_returns_events(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-replay-query",
                        "--left-packet-directory",
                        str(left),
                        "--right-packet-directory",
                        str(right),
                    ]
                )
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.getvalue())["total"], 1)

    def test_cli_replay_query_supports_checks(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-replay-query",
                        "--left-packet-directory",
                        str(left),
                        "--right-packet-directory",
                        str(right),
                        "--resource",
                        "checks",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.getvalue())["total"], 8)

    def test_cli_replay_query_supports_after_state(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-replay-query",
                        "--left-packet-directory",
                        str(left),
                        "--right-packet-directory",
                        str(right),
                        "--after-state",
                        "ready",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.getvalue())["total"], 1)

    def test_http_replay_schema_route(self):
        server = create_server("127.0.0.1", 0, tempfile.mkdtemp())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/replay"
        try:
            status, _, body = self._http_json(server, base + "/schema", {})
            self.assertEqual(status, 200)
            self.assertIn("start", json.loads(body)["states"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_http_replay_capabilities_route(self):
        server = create_server("127.0.0.1", 0, tempfile.mkdtemp())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/replay"
        try:
            status, _, body = self._http_json(server, base + "/capabilities", {})
            self.assertEqual(status, 200)
            self.assertTrue(json.loads(body)["state_reconstruction"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_http_replay_query_schema_route(self):
        server = create_server("127.0.0.1", 0, tempfile.mkdtemp())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/replay"
        try:
            status, _, body = self._http_json(server, base + "/query/schema", {})
            self.assertEqual(status, 200)
            self.assertIn("after_state", json.loads(body)["filters"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_http_replay_query_capabilities_route(self):
        server = create_server("127.0.0.1", 0, tempfile.mkdtemp())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/replay"
        try:
            status, _, body = self._http_json(server, base + "/query/capabilities", {})
            self.assertEqual(status, 200)
            self.assertTrue(json.loads(body)["addressed_receipts"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_http_replay_base_builds_summary(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            server = create_server("127.0.0.1", 0, str(Path(root) / "data"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/replay"
            try:
                status, _, body = self._http_json(
                    server,
                    base,
                    {"left_packet_directory": str(left), "right_packet_directory": str(right)},
                )
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)["final_state"], "ready")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_http_replay_query_builds_events(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            server = create_server("127.0.0.1", 0, str(Path(root) / "data"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/replay/query"
            try:
                status, _, body = self._http_json(
                    server,
                    base,
                    {"left_packet_directory": str(left), "right_packet_directory": str(right)},
                )
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)["total"], 1)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_http_replay_query_supports_csv(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            server = create_server("127.0.0.1", 0, str(Path(root) / "data"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/replay/query"
            try:
                status, content_type, body = self._http_json(
                    server,
                    base,
                    {
                        "left_packet_directory": str(left),
                        "right_packet_directory": str(right),
                        "format": "csv",
                    },
                )
                self.assertEqual(status, 200)
                self.assertIn("text/csv", content_type)
                self.assertIn("before_state", body.splitlines()[0])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_http_replay_query_supports_markdown(self):
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            server = create_server("127.0.0.1", 0, str(Path(root) / "data"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/replay/query"
            try:
                status, content_type, body = self._http_json(
                    server,
                    base,
                    {
                        "left_packet_directory": str(left),
                        "right_packet_directory": str(right),
                        "format": "markdown",
                    },
                )
                self.assertEqual(status, 200)
                self.assertIn("text/markdown", content_type)
                self.assertIn("# Catalog Packet Review Gate History Replay Query", body)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_real_downloaded_packet_is_present_for_demo(self):
        if not self._real_packet().is_dir():
            self.skipTest("real downloaded packet fixture is not present")
        self.assertTrue((self._real_packet() / "manifest.json").is_file())

    def test_real_downloaded_packet_builds_history(self):
        packet_directory = self._real_packet()
        if not packet_directory.is_dir():
            self.skipTest("real downloaded packet fixture is not present")
        value = history.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_from_directories(
            packet_directory, packet_directory, history_id="real-history"
        )
        self.assertEqual(value.history_id, "real-history")
        self.assertTrue(value.accepted)
        self.assertTrue(value.release_ready)

    def test_real_downloaded_packet_replays(self):
        packet_directory = self._real_packet()
        if not packet_directory.is_dir():
            self.skipTest("real downloaded packet fixture is not present")
        value = history.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_from_directories(
            packet_directory, packet_directory, history_id="real-replay"
        )
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        self.assertTrue(report.accepted)
        self.assertEqual(report.final_state, "ready")

    def test_real_downloaded_packet_history_round_trips(self):
        packet_directory = self._real_packet()
        if not packet_directory.is_dir():
            self.skipTest("real downloaded packet fixture is not present")
        value = history.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_from_directories(
            packet_directory, packet_directory, history_id="real-roundtrip"
        )
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "real-history"
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                value, destination
            )
            loaded = history.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                destination
            )
            self.assertEqual(loaded.content_address, value.content_address)

    def test_real_downloaded_packet_history_csv_has_data(self):
        packet_directory = self._real_packet()
        if not packet_directory.is_dir():
            self.skipTest("real downloaded packet fixture is not present")
        value = history.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_from_directories(
            packet_directory, packet_directory
        )
        rows = list(
            csv.DictReader(
                StringIO(
                    history.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_csv(
                        value
                    )
                )
            )
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["decision"], "promote")

    def test_real_downloaded_packet_history_summary_is_path_free(self):
        packet_directory = self._real_packet()
        if not packet_directory.is_dir():
            self.skipTest("real downloaded packet fixture is not present")
        value = history.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_from_directories(
            packet_directory, packet_directory
        )
        output = canonical_json(value.summary()).casefold()
        self.assertNotIn("packet_directory", output)
        self.assertNotIn("\\", output)

    def test_real_downloaded_packet_replay_query_is_addressed(self):
        packet_directory = self._real_packet()
        if not packet_directory.is_dir():
            self.skipTest("real downloaded packet fixture is not present")
        value = history.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_from_directories(
            packet_directory, packet_directory
        )
        report = replay.replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        result = replay.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay(
            report
        )
        self.assertTrue(result["content_address"])

    def test_real_downloaded_packet_cli_demo(self):
        packet_directory = self._real_packet()
        if not packet_directory.is_dir():
            self.skipTest("real downloaded packet fixture is not present")
        output = StringIO()
        with redirect_stdout(output):
            result = main(
                [
                    "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-replay",
                    "--left-packet-directory",
                    str(packet_directory),
                    "--right-packet-directory",
                    str(packet_directory),
                    "--format",
                    "summary",
                ]
            )
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue())["final_state"], "ready")

    def test_real_downloaded_packet_contains_only_published_packet_files(self):
        packet_directory = self._real_packet()
        if not packet_directory.is_dir():
            self.skipTest("real downloaded packet fixture is not present")
        self.assertEqual(
            {item.name for item in packet_directory.iterdir()},
            {
                "manifest.json",
                "catalog.json",
                "federation.json",
                "runtime.json",
                "assurance.json",
                "gate.json",
            },
        )

    def test_real_downloaded_packet_loaded_content_is_canonical(self):
        packet_directory = self._real_packet()
        if not packet_directory.is_dir():
            self.skipTest("real downloaded packet fixture is not present")
        loaded = load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
            packet_directory
        )
        self.assertEqual(
            (packet_directory / "manifest.json").read_bytes(),
            canonical_bytes(json.loads((packet_directory / "manifest.json").read_text())),
        )
        self.assertTrue(loaded.accepted)

    def test_write_creates_parent_directory(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "nested" / "history"
            written = history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), destination
            )
            self.assertEqual(written, destination)
            self.assertTrue(destination.is_dir())

    def test_write_creates_exact_two_files(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "history"
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), destination
            )
            self.assertEqual(
                {item.name for item in destination.iterdir()}, {"manifest.json", "history.json"}
            )

    def test_write_history_document_is_canonical(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "history"
            value = self._history()
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                value, destination
            )
            raw = (destination / "history.json").read_bytes()
            self.assertEqual(raw, canonical_bytes(value.to_dict()))

    def test_write_history_manifest_is_canonical(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "history"
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), destination
            )
            raw = (destination / "manifest.json").read_bytes()
            self.assertEqual(raw, canonical_bytes(json.loads(raw)))

    def test_write_history_manifest_references_document(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "history"
            value = self._history()
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                value, destination
            )
            manifest = json.loads((destination / "manifest.json").read_text())
            self.assertEqual(manifest["history"], value.to_dict())

    def test_write_history_manifest_counts_document_bytes(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "history"
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), destination
            )
            manifest = json.loads((destination / "manifest.json").read_text())
            self.assertEqual(manifest["byte_count"], (destination / "history.json").stat().st_size)

    def test_write_history_manifest_hashes_document_bytes(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "history"
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), destination
            )
            manifest = json.loads((destination / "manifest.json").read_text())
            expected = (
                history.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_PREFIX
                + "-bytes"
            )
            self.assertTrue(manifest["byte_address"].startswith(expected + ":"))

    def test_write_history_manifest_address_is_content_hash(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "history"
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), destination
            )
            manifest = json.loads((destination / "manifest.json").read_text())
            body = {key: item for key, item in manifest.items() if key != "manifest_address"}
            self.assertEqual(
                manifest["manifest_address"],
                content_hash(
                    body,
                    prefix=history.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_PREFIX
                    + "-manifest",
                ),
            )

    def test_write_rejects_existing_destination_by_default(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "history"
            destination.mkdir()
            with self.assertRaises(ValidationError):
                history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                    self._history(), destination
                )

    def test_write_overwrite_replaces_existing_directory(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "history"
            destination.mkdir()
            (destination / "old.txt").write_text("old")
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), destination, overwrite=True
            )
            self.assertFalse((destination / "old.txt").exists())
            self.assertTrue((destination / "history.json").exists())

    def test_write_overwrite_is_stable(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "history"
            value = self._history()
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                value, destination
            )
            first = {item.name: item.read_bytes() for item in destination.iterdir()}
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                value, destination, overwrite=True
            )
            second = {item.name: item.read_bytes() for item in destination.iterdir()}
            self.assertEqual(first, second)

    def test_write_rejects_tampered_history(self):
        value = self._history()
        value.content_address = "history:tampered"
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValidationError):
                history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                    value, Path(root) / "history"
                )

    def test_load_round_trips_ready_history(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "history"
            value = self._history()
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                value, destination
            )
            loaded = history.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                destination
            )
            self.assertEqual(loaded.to_dict(), value.to_dict())

    def test_load_round_trips_held_history(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "history"
            value = self._history(decision="hold", right=self._held_pair()[1])
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                value, destination
            )
            loaded = history.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                destination
            )
            self.assertEqual(
                (loaded.state, loaded.accepted, loaded.release_ready), ("held", True, False)
            )

    def test_load_round_trips_blocked_history(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "history"
            value = self._history(decision="block", right=self._blocked_pair()[1])
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                value, destination
            )
            loaded = history.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                destination
            )
            self.assertEqual(
                (loaded.state, loaded.accepted, loaded.release_ready), ("blocked", False, False)
            )

    def test_load_round_trips_mixed_history(self):
        value = self._history()
        for ordinal, decision in enumerate(("hold", "block", "supersede", "promote")):
            value = history.append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                value, self._decision_gate(decision, f"persist-mixed-{ordinal}")
            )
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "history"
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                value, destination
            )
            loaded = history.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                destination
            )
            self.assertEqual(loaded.content_address, value.content_address)
            self.assertEqual(
                [item.decision for item in loaded.entries],
                ["promote", "hold", "block", "supersede", "promote"],
            )

    def test_load_rejects_missing_directory(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValidationError):
                history.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                    Path(root) / "missing"
                )

    def test_load_rejects_file_path(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "file"
            path.write_text("not a directory")
            with self.assertRaises(ValidationError):
                history.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                    path
                )

    def test_load_rejects_extra_file(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "history"
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), destination
            )
            (destination / "extra.json").write_text("{}")
            with self.assertRaises(ValidationError):
                history.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                    destination
                )

    def test_load_rejects_nested_directory(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "history"
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), destination
            )
            (destination / "nested").mkdir()
            with self.assertRaises(ValidationError):
                history.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                    destination
                )

    def test_load_rejects_noncanonical_history_json(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "history"
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), destination
            )
            document = json.loads((destination / "history.json").read_text())
            (destination / "history.json").write_text(json.dumps(document, indent=2))
            with self.assertRaises(ValidationError):
                history.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                    destination
                )

    def test_load_rejects_noncanonical_manifest(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "history"
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), destination
            )
            manifest = json.loads((destination / "manifest.json").read_text())
            (destination / "manifest.json").write_text(json.dumps(manifest, indent=2))
            with self.assertRaises(ValidationError):
                history.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                    destination
                )

    def test_load_rejects_invalid_history_json(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "history"
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), destination
            )
            (destination / "history.json").write_text("{")
            with self.assertRaises(ValidationError):
                history.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                    destination
                )

    def test_load_rejects_invalid_manifest_json(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "history"
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), destination
            )
            (destination / "manifest.json").write_text("{")
            with self.assertRaises(ValidationError):
                history.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                    destination
                )

    def test_load_rejects_manifest_version_mutation(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "history"
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), destination
            )
            manifest = json.loads((destination / "manifest.json").read_text())
            manifest["manifest_version"] = "wrong"
            (destination / "manifest.json").write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                history.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                    destination
                )

    def test_load_rejects_manifest_address_mutation(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "history"
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), destination
            )
            manifest = json.loads((destination / "manifest.json").read_text())
            manifest["manifest_address"] = "manifest:wrong"
            (destination / "manifest.json").write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                history.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                    destination
                )

    def test_load_rejects_manifest_history_mutation(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "history"
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), destination
            )
            manifest = json.loads((destination / "manifest.json").read_text())
            manifest["history"]["history_id"] = "wrong"
            body = {key: item for key, item in manifest.items() if key != "manifest_address"}
            manifest["manifest_address"] = content_hash(
                body,
                prefix=history.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_PREFIX
                + "-manifest",
            )
            (destination / "manifest.json").write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                history.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                    destination
                )

    def test_load_rejects_document_manifest_mismatch(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "history"
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), destination
            )
            document = json.loads((destination / "history.json").read_text())
            document["history_id"] = "changed"
            (destination / "history.json").write_bytes(canonical_bytes(document))
            with self.assertRaises(ValidationError):
                history.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                    destination
                )

    def test_load_rejects_document_byte_count_mismatch(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "history"
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), destination
            )
            manifest = json.loads((destination / "manifest.json").read_text())
            manifest["byte_count"] += 1
            body = {key: item for key, item in manifest.items() if key != "manifest_address"}
            manifest["manifest_address"] = content_hash(
                body,
                prefix=history.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_PREFIX
                + "-manifest",
            )
            (destination / "manifest.json").write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                history.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                    destination
                )

    def test_load_rejects_document_byte_address_mismatch(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "history"
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), destination
            )
            manifest = json.loads((destination / "manifest.json").read_text())
            manifest["byte_address"] = "bytes:wrong"
            body = {key: item for key, item in manifest.items() if key != "manifest_address"}
            manifest["manifest_address"] = content_hash(
                body,
                prefix=history.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_PREFIX
                + "-manifest",
            )
            (destination / "manifest.json").write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                history.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                    destination
                )

    def test_load_rejects_document_content_address_mutation(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "history"
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), destination
            )
            document = json.loads((destination / "history.json").read_text())
            document["content_address"] = "history:wrong"
            (destination / "history.json").write_bytes(canonical_bytes(document))
            with self.assertRaises(ValidationError):
                history.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                    destination
                )

    @unittest.skipUnless(
        os.name != "nt", "directory symlinks may require elevated Windows privileges"
    )
    def test_load_rejects_symlinked_directory(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "target"
            link = Path(root) / "link"
            target.mkdir()
            link.symlink_to(target, target_is_directory=True)
            with self.assertRaises(ValidationError):
                history.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                    link
                )

    @unittest.skipUnless(os.name != "nt", "file symlinks may require elevated Windows privileges")
    def test_load_rejects_symlinked_child(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "history"
            history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                self._history(), destination
            )
            target = Path(root) / "target"
            target.write_bytes((destination / "history.json").read_bytes())
            (destination / "history.json").unlink()
            (destination / "history.json").symlink_to(target)
            with self.assertRaises(ValidationError):
                history.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                    destination
                )
