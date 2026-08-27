"""Deep regression tests for the release-window review control plane."""

# ruff: noqa: E501

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
from urllib.parse import urlencode

from glio_noncode.api import create_server
from glio_noncode.errors import ValidationError
from glio_noncode.module_workbench_execution_packet import build_module_workbench_execution_packet
from glio_noncode.module_workbench_execution_packet_archive import (
    build_module_workbench_execution_packet_archive,
)
from glio_noncode.module_workbench_execution_packet_archive_store import (
    append_module_workbench_execution_packet_archive_store,
    build_module_workbench_execution_packet_archive_store,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication import (
    build_module_workbench_execution_packet_archive_store_replication,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet import (
    build_module_workbench_execution_packet_archive_store_replication_packet,
    write_module_workbench_execution_packet_archive_store_replication_packet,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_batch import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_batch,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review import (
    append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_decision,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_entry,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_from_directories,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_schema,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_markdown,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_query_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_query_schema,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_schema,
    query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_markdown,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_contracts import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDecision,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewState,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_query_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_query_schema,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_schema,
    query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_markdown,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query import (
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query_schema,
    query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query_markdown,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime import (
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_query_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_query_schema,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_schema,
    query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_markdown,
    run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime,
)
from glio_noncode.serialization import canonical_json
from tests.test_module_workbench_execution import ModuleWorkbenchExecutionFixture


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewTests(
    unittest.TestCase
):
    """Exercise review decisions, runtime closure, assurance, and diffs."""

    def setUp(self) -> None:
        self.fixture = ModuleWorkbenchExecutionFixture()
        self.fixture.setUp()

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def _archive(self, archive_id: str):
        packet = build_module_workbench_execution_packet(
            self.fixture.report(), packet_id=archive_id
        )
        return build_module_workbench_execution_packet_archive(packet, archive_id=archive_id)

    def _packet(self, packet_id: str = "review-packet"):
        base = self._archive("base")
        next_archive = self._archive("next")
        target = build_module_workbench_execution_packet_archive_store(
            (base,), store_id="review-target"
        )
        source = append_module_workbench_execution_packet_archive_store(
            target, next_archive, operation_id="review-next"
        )
        plan = build_module_workbench_execution_packet_archive_store_replication(source, target)
        packet, _ = build_module_workbench_execution_packet_archive_store_replication_packet(
            plan, packet_id=packet_id
        )
        return packet

    def _evidence(self, divergent: bool = False):
        left = self._packet("review-left")
        right = self._packet("review-right") if divergent else left
        diff = build_module_workbench_execution_packet_archive_store_replication_packet_diff(
            left, right
        )
        release = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release(
                diff
            )
        )
        batch = build_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(
            (("review", diff, release),), batch_id="review-batch"
        )
        window = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
            batch, window_id="review-window"
        )
        from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime import (
            run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime,
        )

        packet_runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime(
            batch, window_id=window.window_id
        )
        packet_assurance = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance(
            window, packet_runtime
        )
        return window, packet_assurance

    def _promoted(self):
        window, packet_assurance = self._evidence()
        ledger = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
            window,
            packet_assurance,
            decisions=(
                {
                    "entry_id": "promote",
                    "decision": "promote",
                    "rationale": "matched evidence is ready for handoff",
                    "required_actions": (),
                },
            ),
            ledger_id="review-ledger",
        )
        return window, packet_assurance, ledger

    def test_promote_entry_requires_and_retains_ready_evidence(self) -> None:
        window, packet_assurance, ledger = self._promoted()
        self.assertEqual(
            ledger.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewState.PROMOTED.value,
        )
        self.assertTrue(ledger.release_ready)
        self.assertTrue(ledger.accepted)
        self.assertTrue(ledger.append_only)
        self.assertEqual(ledger.entry_count, 1)
        self.assertEqual(ledger.head_address, ledger.entries[0].content_address)
        self.assertEqual(ledger.entries[0].window_address, window.content_address)
        self.assertEqual(ledger.entries[0].assurance_address, packet_assurance.content_address)
        self.assertIs(
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
                ledger, window=window, assurance=packet_assurance
            ),
            ledger,
        )

    def test_promote_decision_fails_closed_for_divergent_evidence(self) -> None:
        window, packet_assurance = self._evidence(divergent=True)
        with self.assertRaises(ValidationError):
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
                window,
                packet_assurance,
                decisions=(
                    {
                        "entry_id": "unsafe-promote",
                        "decision": ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDecision.PROMOTE,
                        "rationale": "must not bypass blockers",
                    },
                ),
            )

    def test_hold_block_and_supersede_decisions_are_explicit(self) -> None:
        window, packet_assurance = self._evidence(divergent=True)
        hold = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
            window,
            packet_assurance,
            decisions=(
                {
                    "entry_id": "hold",
                    "decision": "hold",
                    "rationale": "divergence requires review",
                    "required_actions": ("rerun packet comparison",),
                },
            ),
        )
        self.assertEqual(hold.state, "hold")
        self.assertFalse(hold.release_ready)
        superseded = append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_decision(
            hold,
            window,
            packet_assurance,
            entry_id="supersede",
            decision="supersede",
            rationale="replace the held review after a new evidence set",
            required_actions=("build a new verified window",),
        )
        self.assertEqual(superseded.state, "superseded")
        self.assertEqual(superseded.entry_count, 2)
        self.assertEqual(
            superseded.entries[1].supersedes_entry_address,
            superseded.entries[0].content_address,
        )

    def test_append_preserves_prior_revision_and_updates_head(self) -> None:
        window, packet_assurance, ledger = self._promoted()
        next_ledger = append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_decision(
            ledger,
            window,
            packet_assurance,
            entry_id="hold-after-promote",
            decision="hold",
            rationale="pause while the next packet is assembled",
            required_actions=("compare the next packet",),
        )
        self.assertEqual(ledger.entry_count, 1)
        self.assertEqual(ledger.state, "promoted")
        self.assertEqual(next_ledger.entry_count, 2)
        self.assertEqual(next_ledger.entries[0].content_address, ledger.head_address)
        self.assertEqual(next_ledger.entries[1].previous_entry_address, ledger.head_address)
        self.assertEqual(next_ledger.state, "hold")
        self.assertFalse(next_ledger.release_ready)
        self.assertNotEqual(next_ledger.content_address, ledger.content_address)

    def test_empty_ledger_is_unreviewed_and_runtime_blocks(self) -> None:
        window, packet_assurance = self._evidence()
        ledger = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
            window, packet_assurance, decisions=()
        )
        self.assertEqual(ledger.state, "unreviewed")
        self.assertFalse(ledger.accepted)
        self.assertFalse(ledger.release_ready)
        runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime(
            ledger, window, packet_assurance
        )
        self.assertEqual(runtime.state, "blocked")
        self.assertEqual(runtime.blocked_count, 2)
        self.assertEqual(runtime.skipped_count, 2)
        self.assertFalse(runtime.accepted)
        self.assertFalse(runtime.release_ready)

    def test_entry_builder_rejects_invalid_semantics(self) -> None:
        window, packet_assurance = self._evidence()
        with self.assertRaises(ValidationError):
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_entry(
                window,
                packet_assurance,
                entry_id="bad",
                decision="promote",
                rationale="not ready to promote without actions",
                required_actions=("should fail",),
            )
        with self.assertRaises(ValidationError):
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_entry(
                window,
                packet_assurance,
                entry_id="bad-hold",
                decision="hold",
                rationale="missing action",
                required_actions=(),
            )
        with self.assertRaises(ValidationError):
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_entry(
                window,
                packet_assurance,
                entry_id="bad-supersede",
                decision="supersede",
                rationale="needs prior entry",
                required_actions=("replace",),
            )

    def test_ledger_rejects_duplicate_decisions_and_tampering(self) -> None:
        window, packet_assurance = self._evidence()
        with self.assertRaises(ValidationError):
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
                window,
                packet_assurance,
                decisions=(
                    {"entry_id": "duplicate", "decision": "promote", "rationale": "ready"},
                    {"entry_id": "duplicate", "decision": "promote", "rationale": "ready"},
                ),
            )
        _, _, ledger = self._promoted()
        ledger.entries[0].rationale = "tampered"
        with self.assertRaises(ValidationError):
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
                ledger
            )

    def test_review_exports_are_canonical_and_reviewable(self) -> None:
        _, _, ledger = self._promoted()
        encoded = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_json(
            ledger
        )
        self.assertEqual(json.loads(encoded)["state"], "promoted")
        csv_text = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_csv(
            ledger
        )
        self.assertIn("entry_id", csv_text)
        self.assertEqual(len(csv_text.splitlines()), 2)
        markdown = render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_markdown(
            ledger
        )
        self.assertIn("append-only", markdown)
        self.assertIn("promote", markdown)

    def test_review_query_filters_exports_and_tamper_checks(self) -> None:
        window, packet_assurance, ledger = self._promoted()
        ledger = append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_decision(
            ledger,
            window,
            packet_assurance,
            entry_id="hold",
            decision="hold",
            rationale="wait for another packet",
            required_actions=("rerun",),
        )
        result = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
            ledger, resource="entries", decision="hold", has_required_actions=True
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["entry_id"], "hold")
        self.assertEqual(
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query(
                result
            ),
            result,
        )
        self.assertIn(
            "entry_id",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query_json(
                result
            ),
        )
        self.assertIn(
            "entry_id",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query_csv(
                result
            ),
        )
        self.assertIn(
            "Entry",
            render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query_markdown(
                result
            ),
        )
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
                ledger, resource="nope"
            )
        tampered = dict(result)
        tampered["append_only"] = False
        with self.assertRaises(ValidationError):
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query(
                tampered
            )

    def test_review_runtime_closes_promote_and_holds_non_release_decisions(self) -> None:
        window, packet_assurance, ledger = self._promoted()
        runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime(
            ledger, window, packet_assurance, runtime_id="promoted-runtime"
        )
        self.assertEqual(runtime.state, "completed")
        self.assertEqual(runtime.completed_count, 7)
        self.assertEqual(runtime.blocked_count, 0)
        self.assertEqual(runtime.skipped_count, 0)
        self.assertTrue(runtime.accepted)
        self.assertTrue(runtime.release_ready)
        self.assertIs(
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime(
                runtime
            ),
            runtime,
        )
        held = append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_decision(
            ledger,
            window,
            packet_assurance,
            entry_id="held",
            decision="hold",
            rationale="retain review before release",
            required_actions=("review next packet",),
        )
        held_runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime(
            held, window, packet_assurance
        )
        self.assertTrue(held_runtime.accepted)
        self.assertFalse(held_runtime.release_ready)
        self.assertEqual(held_runtime.state, "completed")
        self.assertIn("handoff", held_runtime.stages[5].detail)
        self.assertIn(
            "stage_id",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_json(
                held_runtime
            ),
        )
        self.assertIn(
            "Kind",
            render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_markdown(
                held_runtime
            ),
        )
        self.assertIn(
            "stage_id",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_csv(
                held_runtime
            ),
        )

    def test_runtime_query_filters_stages_and_detects_address_tamper(self) -> None:
        window, packet_assurance, ledger = self._promoted()
        runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime(
            ledger, window, packet_assurance
        )
        result = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime(
            runtime, resource="stages", kind="resolve_head", accepted=True
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["kind"], "resolve_head")
        tampered = dict(result)
        tampered["content_address"] = "runtime-query:tampered"
        from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime import (
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_query,
        )

        with self.assertRaises(ValidationError):
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_query(
                tampered
            )

    def test_review_assurance_covers_promote_chain_and_runtime(self) -> None:
        window, packet_assurance, ledger = self._promoted()
        runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime(
            ledger, window, packet_assurance
        )
        assurance = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance(
            ledger, window, packet_assurance, runtime
        )
        self.assertEqual(assurance.finding_count, 10)
        self.assertEqual(assurance.blocker_count, 0)
        self.assertEqual(assurance.warning_count, 0)
        self.assertTrue(assurance.accepted)
        self.assertTrue(assurance.release_ready)
        self.assertEqual(assurance.state, "accepted")
        self.assertIs(
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance(
                assurance
            ),
            assurance,
        )
        self.assertIn(
            "finding_id",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_json(
                assurance
            ),
        )
        self.assertIn(
            "finding_id",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_csv(
                assurance
            ),
        )
        self.assertIn(
            "Findings",
            render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_markdown(
                assurance
            ),
        )

    def test_review_assurance_blocks_unreviewed_and_query_filters_findings(self) -> None:
        window, packet_assurance = self._evidence()
        ledger = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
            window, packet_assurance
        )
        assurance = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance(
            ledger, window, packet_assurance
        )
        self.assertEqual(assurance.warning_count, 1)
        self.assertEqual(assurance.state, "hold")
        self.assertTrue(assurance.accepted)
        self.assertFalse(assurance.release_ready)
        result = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance(
            assurance, resource="findings", passed=False
        )
        self.assertGreaterEqual(result["total"], 1)
        self.assertTrue(any(row["kind"] == "head-decision" for row in result["items"]))
        tampered = dict(result)
        tampered["content_address"] = "assurance-query:tampered"
        with self.assertRaises(ValidationError):
            from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance import (
                verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_query,
            )

            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_query(
                tampered
            )

    def test_review_diff_exact_append_changed_and_removed_states(self) -> None:
        window, packet_assurance, promoted = self._promoted()
        exact = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff(
            promoted, promoted, diff_id="exact"
        )
        self.assertEqual(exact.state, "exact")
        self.assertTrue(exact.accepted)
        appended = append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_decision(
            promoted,
            window,
            packet_assurance,
            entry_id="hold",
            decision="hold",
            rationale="pause for review",
            required_actions=("review",),
        )
        append_diff = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff(
            promoted, appended, diff_id="append"
        )
        self.assertEqual(append_diff.state, "append_only")
        self.assertTrue(append_diff.append_only)
        self.assertEqual(append_diff.added_count, 1)
        changed = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
            window,
            packet_assurance,
            decisions=(
                {
                    "entry_id": "promote",
                    "decision": "promote",
                    "rationale": "different rationale but still ready",
                },
            ),
        )
        changed_diff = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff(
            promoted, changed, diff_id="changed"
        )
        self.assertEqual(changed_diff.state, "divergent")
        self.assertEqual(changed_diff.changed_count, 1)
        self.assertFalse(changed_diff.accepted)
        removed_diff = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff(
            appended, promoted, diff_id="removed"
        )
        self.assertEqual(removed_diff.removed_count, 1)
        self.assertEqual(removed_diff.state, "divergent")
        self.assertFalse(removed_diff.accepted)

    def test_review_diff_query_exports_and_tamper_detection(self) -> None:
        _, _, promoted = self._promoted()
        _, _, appended = self._append_promoted()
        value = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff(
            promoted, appended
        )
        result = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff(
            value, resource="actions", action="added"
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["action"], "added")
        self.assertIn(
            "entry_id",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_json(
                value
            ),
        )
        self.assertIn(
            "entry_id",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_csv(
                value
            ),
        )
        self.assertIn(
            "Action",
            render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_markdown(
                value
            ),
        )
        tampered = dict(result)
        tampered["content_address"] = "diff-query:tampered"
        from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff import (
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_query,
        )

        with self.assertRaises(ValidationError):
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_query(
                tampered
            )

    def _append_promoted(self):
        window, packet_assurance, promoted = self._promoted()
        appended = append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_decision(
            promoted,
            window,
            packet_assurance,
            entry_id="hold",
            decision="hold",
            rationale="pause for review",
            required_actions=("review",),
        )
        return window, packet_assurance, appended

    def test_review_diff_rejects_different_evidence_scopes(self) -> None:
        first = self._promoted()[2]
        window, assurance = self._evidence(divergent=True)
        second = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
            window,
            assurance,
            decisions=(
                {
                    "entry_id": "hold",
                    "decision": "hold",
                    "rationale": "different scope",
                    "required_actions": ("review",),
                },
            ),
        )
        with self.assertRaises(ValidationError):
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff(
                first, second
            )

    def test_directory_builder_and_http_routes_use_persisted_packets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            left = Path(temp) / "left"
            right = Path(temp) / "right"
            source = self._archive("base")
            target = build_module_workbench_execution_packet_archive_store(
                (source,), store_id="directory-target"
            )
            plan = build_module_workbench_execution_packet_archive_store_replication(target, target)
            stored, payloads = (
                build_module_workbench_execution_packet_archive_store_replication_packet(
                    plan, packet_id="directory-review-packet"
                )
            )
            write_module_workbench_execution_packet_archive_store_replication_packet(
                stored, payloads, left
            )
            write_module_workbench_execution_packet_archive_store_replication_packet(
                stored, payloads, right
            )
            ledger = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_from_directories(
                (("persisted", left, right),),
                decisions=(
                    {
                        "entry_id": "promote",
                        "decision": "promote",
                        "rationale": "persisted matched evidence is ready",
                    },
                ),
                batch_id="directory-review-batch",
                window_id="directory-review-window",
                ledger_id="directory-review-ledger",
            )
            self.assertTrue(ledger.release_ready)
            server = create_server("127.0.0.1", 0, temp)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = None
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                query = urlencode(
                    [
                        ("pair", f"persisted={left}={right}"),
                        ("decision", "promote"),
                        ("rationale", "persisted matched evidence is ready"),
                        ("required_action", ""),
                    ]
                )
                path = (
                    "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review?"
                    + query
                )
                connection.request("GET", path)
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                payload = json.loads(response.read())
                self.assertEqual(payload["state"], "promoted")
                connection.request(
                    "GET",
                    "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review/schema",
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertTrue(json.loads(response.read())["identity_free"])
            finally:
                if connection is not None:
                    connection.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_schema_and_capabilities_remain_identity_free(self) -> None:
        values = (
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_capabilities(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query_capabilities(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_capabilities(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_query_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_query_capabilities(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_capabilities(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_query_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_query_capabilities(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_capabilities(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_query_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_query_capabilities(),
        )
        for value in values:
            encoded = canonical_json(value).casefold()
            self.assertNotIn("agent", encoded)
            self.assertNotIn("model", encoded)
            self.assertNotIn("private", encoded)
            self.assertNotIn("language", encoded)
            self.assertTrue(value["identity_free"])


if __name__ == "__main__":
    unittest.main()
