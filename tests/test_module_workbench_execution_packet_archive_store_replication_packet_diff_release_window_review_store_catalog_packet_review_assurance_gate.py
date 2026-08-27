"""Deep regression coverage for packet-review assurance and release gates."""

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
import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance as packet_assurance
import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate as packet_gate
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
from glio_noncode.serialization import canonical_bytes, canonical_json

module_assurance_verify = packet_assurance.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance
module_gate_verify = packet_gate.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate


class PacketReviewAssuranceGateTests(unittest.TestCase):
    """Exercise the independent assurance and combined gate boundary."""

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
            review,
            diff=diff,
            assurance_id=kwargs.get("assurance_id", "assurance"),
        )

    def _gate(self, diff=None, review=None, assurance=None, **kwargs):
        diff = diff or self._diff()
        review = review or self._review(diff)
        assurance = assurance or self._assurance(review, diff)
        return packet_gate.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
            diff,
            review,
            assurance,
            gate_id=kwargs.get("gate_id", "gate"),
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

    def _nonready_pair_directories(self, root: str | Path):
        left = self._write_packet(root, self._packet(packet_id="left"), "left")
        held_catalog = self._catalog(self._store("held", state="held", release_ready=False))
        right = self._write_packet(root, self._packet(held_catalog, packet_id="right"), "right")
        return left, right

    def test_ready_assurance_recomputes_eight_findings(self) -> None:
        diff = self._diff()
        review = self._review(diff)
        assurance = self._assurance(review, diff)
        self.assertEqual(assurance.review_state, "ready")
        self.assertEqual(assurance.finding_count, 8)
        self.assertEqual(assurance.passed_count, 8)
        self.assertEqual(assurance.failed_count, 0)
        self.assertEqual(assurance.blocker_count, 0)
        self.assertEqual(assurance.warning_count, 0)
        self.assertTrue(assurance.accepted)
        self.assertTrue(assurance.release_ready)

    def test_ready_gate_recomputes_eight_policy_checks(self) -> None:
        gate = self._gate()
        self.assertEqual(gate.decision, "promote")
        self.assertEqual(gate.state, "ready")
        self.assertEqual(gate.check_count, 8)
        self.assertEqual(gate.passed_count, 8)
        self.assertEqual(gate.failed_count, 0)
        self.assertTrue(gate.accepted)
        self.assertTrue(gate.release_ready)
        self.assertEqual([item.ordinal for item in gate.checks], list(range(8)))

    def test_assurance_without_diff_has_only_review_findings(self) -> None:
        review = self._review()
        assurance = self._assurance(review)
        self.assertIsNone(assurance.diff_address)
        self.assertEqual(assurance.finding_count, 5)
        self.assertTrue(assurance.accepted)
        self.assertTrue(assurance.release_ready)
        self.assertTrue(
            packet_assurance.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance
            ).accepted
        )

    def test_assurance_and_gate_addresses_are_stable(self) -> None:
        first_assurance = self._assurance()
        second_assurance = self._assurance()
        first_gate = self._gate()
        second_gate = self._gate()
        self.assertEqual(first_assurance.content_address, second_assurance.content_address)
        self.assertEqual(first_gate.content_address, second_gate.content_address)
        self.assertEqual(
            packet_assurance.address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                first_assurance
            ),
            first_assurance.content_address,
        )
        self.assertEqual(
            packet_gate.address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                first_gate
            ),
            first_gate.content_address,
        )

    def test_assurance_findings_are_ordered_and_addressed(self) -> None:
        assurance = self._assurance(diff=self._diff())
        self.assertEqual([item.ordinal for item in assurance.findings], list(range(8)))
        for finding in assurance.findings:
            self.assertEqual(
                packet_assurance.address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_finding(
                    finding
                ),
                finding.content_address,
            )
            self.assertIn(finding.severity, {"warning", "blocker"})
            self.assertIn(finding.state, {"passed", "failed"})
            self.assertTrue(finding.detail)

    def test_gate_checks_are_ordered_and_addressed(self) -> None:
        gate = self._gate()
        self.assertEqual([item.ordinal for item in gate.checks], list(range(8)))
        for check in gate.checks:
            self.assertEqual(
                packet_gate.address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_check(
                    check
                ),
                check.content_address,
            )
            self.assertIn("passed" if check.passed else "failed", {"passed", "failed"})
            self.assertTrue(check.detail)

    def test_assurance_verification_has_independent_checks(self) -> None:
        diff = self._diff()
        review = self._review(diff)
        assurance = self._assurance(review, diff)
        verification = packet_assurance.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
            assurance, review=review, diff=diff
        )
        self.assertTrue(verification.accepted)
        self.assertEqual(verification.check_count, 9)
        self.assertEqual(verification.passed_count, 9)
        self.assertEqual(verification.failed_count, 0)
        self.assertEqual([item.ordinal for item in verification.checks], list(range(9)))

    def test_gate_verification_has_component_link_checks(self) -> None:
        diff = self._diff()
        review = self._review(diff)
        assurance = self._assurance(review, diff)
        gate = self._gate(diff, review, assurance)
        verification = packet_gate.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
            gate, diff=diff, review=review, assurance=assurance
        )
        self.assertTrue(verification.accepted)
        self.assertEqual(verification.check_count, 9)
        self.assertEqual(verification.passed_count, 9)
        self.assertEqual(verification.failed_count, 0)

    def test_assurance_verification_without_components_is_structurally_complete(self) -> None:
        assurance = self._assurance(diff=self._diff())
        verification = packet_assurance.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
            assurance
        )
        self.assertTrue(verification.accepted)
        self.assertEqual(verification.check_count, 8)
        self.assertTrue(verification.content_address.startswith("module-workbench-execution"))

    def test_gate_verification_without_components_is_structurally_complete(self) -> None:
        gate = self._gate()
        verification = packet_gate.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
            gate
        )
        self.assertTrue(verification.accepted)
        self.assertEqual(verification.check_count, 9)
        self.assertTrue(verification.content_address.startswith("module-workbench-execution"))

    def test_held_review_is_accepted_but_not_release_ready(self) -> None:
        diff = self._diff(
            right=self._packet(
                self._catalog(self._store("held", state="held", release_ready=False)),
                packet_id="held-right",
            )
        )
        review = self._review(diff, decision="hold", detail="investigate changed evidence")
        assurance = self._assurance(review, diff)
        gate = self._gate(diff, review, assurance)
        self.assertEqual(review.state, "held")
        self.assertTrue(review.accepted)
        self.assertFalse(review.release_ready)
        self.assertTrue(assurance.accepted)
        self.assertFalse(assurance.release_ready)
        self.assertEqual(gate.decision, "hold")
        self.assertEqual(gate.state, "held")
        self.assertTrue(gate.accepted)
        self.assertFalse(gate.release_ready)

    def test_superseded_review_is_accepted_but_not_release_ready(self) -> None:
        diff = self._diff()
        review = self._review(diff, decision="supersede", detail="use a later packet")
        assurance = self._assurance(review, diff)
        gate = self._gate(diff, review, assurance)
        self.assertEqual(review.state, "held")
        self.assertEqual(gate.decision, "supersede")
        self.assertEqual(gate.state, "held")
        self.assertTrue(gate.accepted)
        self.assertFalse(gate.release_ready)

    def test_blocked_review_produces_blocked_gate(self) -> None:
        diff = self._diff(
            right=self._packet(
                self._catalog(
                    self._store("blocked", state="blocked", release_ready=False, accepted=False)
                ),
                packet_id="blocked-right",
            )
        )
        review = self._review(diff, decision="block", detail="reject this candidate")
        assurance = self._assurance(review, diff)
        gate = self._gate(diff, review, assurance)
        self.assertEqual(review.state, "blocked")
        self.assertTrue(review.accepted)
        self.assertFalse(review.release_ready)
        self.assertTrue(assurance.accepted)
        self.assertFalse(assurance.release_ready)
        self.assertEqual(gate.state, "blocked")
        self.assertFalse(gate.accepted)
        self.assertFalse(gate.release_ready)
        self.assertGreater(gate.failed_count, 0)

    def test_assurance_retains_review_and_diff_addresses(self) -> None:
        diff = self._diff(diff_id="diff-retained")
        review = self._review(diff, review_id="review-retained")
        assurance = self._assurance(review, diff, assurance_id="assurance-retained")
        self.assertEqual(assurance.review_address, review.content_address)
        self.assertEqual(assurance.diff_address, diff.content_address)
        self.assertEqual(assurance.assurance_id, "assurance-retained")
        self.assertNotIn("left_packet", canonical_json(assurance.to_dict()))
        self.assertNotIn("right_packet", canonical_json(assurance.to_dict()))

    def test_gate_retains_all_component_addresses(self) -> None:
        diff = self._diff(diff_id="diff-retained")
        review = self._review(diff, review_id="review-retained")
        assurance = self._assurance(review, diff, assurance_id="assurance-retained")
        gate = self._gate(diff, review, assurance, gate_id="gate-retained")
        self.assertEqual(gate.diff_address, diff.content_address)
        self.assertEqual(gate.review_address, review.content_address)
        self.assertEqual(gate.assurance_address, assurance.content_address)
        self.assertNotIn("left_packet", canonical_json(gate.to_dict()))
        self.assertNotIn("right_packet", canonical_json(gate.to_dict()))

    def test_assurance_detects_mutated_review_when_recomputed(self) -> None:
        diff = self._diff()
        review = self._review(diff)
        assurance = self._assurance(review, diff)
        review.head_address = "tampered:head"
        verification = packet_assurance.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
            assurance, review=review, diff=diff
        )
        self.assertFalse(verification.accepted)
        self.assertTrue(
            any(not item.passed and item.kind == "finding-content" for item in verification.checks)
        )

    def test_assurance_detects_mutated_assurance_finding(self) -> None:
        assurance = self._assurance(diff=self._diff())
        assurance.findings[0].detail = "tampered finding detail"
        verification = packet_assurance.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
            assurance
        )
        self.assertFalse(verification.accepted)
        self.assertFalse(verification.checks[2].passed)

    def test_gate_detects_mutated_gate_check(self) -> None:
        gate = self._gate()
        gate.checks[0].detail = "tampered gate detail"
        verification = packet_gate.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
            gate
        )
        self.assertFalse(verification.accepted)
        self.assertFalse(verification.checks[2].passed)

    def test_gate_detects_wrong_supplied_component_link(self) -> None:
        diff = self._diff()
        review = self._review(diff)
        assurance = self._assurance(review, diff)
        other_diff = self._diff(diff_id="other-diff")
        gate = self._gate(diff, review, assurance)
        verification = packet_gate.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
            gate, diff=other_diff, review=review, assurance=assurance
        )
        self.assertFalse(verification.accepted)
        self.assertFalse(verification.checks[3].passed)

    def test_assurance_rejects_untyped_review_before_attribute_access(self) -> None:
        with self.assertRaises(ValidationError):
            packet_assurance.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                SimpleNamespace()
            )

    def test_gate_rejects_untyped_components_before_attribute_access(self) -> None:
        with self.assertRaises(ValidationError):
            packet_gate.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                SimpleNamespace(), SimpleNamespace(), SimpleNamespace()
            )

    def test_assurance_json_is_canonical_and_public(self) -> None:
        assurance = self._assurance(diff=self._diff())
        rendered = packet_assurance.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_json(
            assurance
        )
        self.assertEqual(rendered, canonical_json(json.loads(rendered)) + "\n")
        self.assertNotIn("agent", rendered.casefold())
        self.assertNotIn("language", rendered.casefold())
        self.assertNotIn("model", rendered.casefold())
        self.assertNotIn("user", rendered.casefold())

    def test_gate_json_is_canonical_and_public(self) -> None:
        gate = self._gate()
        rendered = packet_gate.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_json(
            gate
        )
        self.assertEqual(rendered, canonical_json(json.loads(rendered)) + "\n")
        self.assertNotIn("agent", rendered.casefold())
        self.assertNotIn("language", rendered.casefold())
        self.assertNotIn("model", rendered.casefold())
        self.assertNotIn("user", rendered.casefold())

    def test_assurance_csv_contains_one_row_per_finding(self) -> None:
        assurance = self._assurance(diff=self._diff())
        rendered = packet_assurance.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_csv(
            assurance
        )
        rows = list(csv.DictReader(rendered.splitlines()))
        self.assertEqual(len(rows), assurance.finding_count)
        self.assertEqual(rows[0]["ordinal"], "0")
        self.assertEqual(rows[-1]["ordinal"], str(assurance.finding_count - 1))
        self.assertIn("expected", rows[0])
        self.assertIn("observed", rows[0])

    def test_gate_csv_contains_one_row_per_check(self) -> None:
        gate = self._gate()
        rendered = packet_gate.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_csv(
            gate
        )
        rows = list(csv.DictReader(rendered.splitlines()))
        self.assertEqual(len(rows), gate.check_count)
        self.assertEqual(rows[0]["ordinal"], "0")
        self.assertEqual(rows[-1]["ordinal"], str(gate.check_count - 1))

    def test_assurance_markdown_mentions_every_finding(self) -> None:
        assurance = self._assurance(diff=self._diff())
        rendered = packet_assurance.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_markdown(
            assurance
        )
        self.assertIn("# Catalog Packet Review Assurance", rendered)
        self.assertIn("review-structure", rendered)
        self.assertIn("diff-readiness", rendered)
        self.assertIn(assurance.content_address, rendered)

    def test_gate_markdown_mentions_every_check(self) -> None:
        gate = self._gate()
        rendered = packet_gate.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_markdown(
            gate
        )
        self.assertIn("# Catalog Packet Review Gate", rendered)
        self.assertIn("component-acceptance", rendered)
        self.assertIn("readiness-classification", rendered)
        self.assertIn(gate.content_address, rendered)

    def test_assurance_queries_summary_findings_and_checks(self) -> None:
        assurance = self._assurance(diff=self._diff())
        summary = packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
            assurance, resource="summary"
        )
        findings = packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
            assurance, resource="findings"
        )
        checks = packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
            assurance, resource="checks"
        )
        self.assertEqual(summary["total"], 1)
        self.assertEqual(len(summary["items"]), 1)
        self.assertEqual(findings["total"], assurance.finding_count)
        self.assertEqual(checks["total"], 8)
        self.assertTrue(
            packet_assurance.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_query(
                summary
            )
        )
        self.assertTrue(
            packet_assurance.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_query(
                findings
            )
        )
        self.assertTrue(
            packet_assurance.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_query(
                checks
            )
        )

    def test_gate_queries_summary_and_checks(self) -> None:
        gate = self._gate()
        summary = packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
            gate, resource="summary"
        )
        checks = packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
            gate, resource="checks"
        )
        self.assertEqual(summary["total"], 1)
        self.assertEqual(checks["total"], gate.check_count)
        self.assertTrue(
            packet_gate.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_query(
                summary
            )
        )
        self.assertTrue(
            packet_gate.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_query(
                checks
            )
        )

    def test_assurance_queries_apply_severity_passed_kind_and_text_filters(self) -> None:
        assurance = self._assurance(diff=self._diff())
        for kwargs in (
            {"severity": "blocker"},
            {"passed": True},
            {"kind": "diff-linkage"},
            {"text": "supplied packet"},
        ):
            result = packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, **kwargs
            )
            self.assertTrue(
                packet_assurance.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_query(
                    result
                )
            )
            self.assertGreaterEqual(result["total"], len(result["items"]))
        self.assertEqual(
            packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, kind="diff-linkage"
            )["total"],
            1,
        )

    def test_gate_queries_apply_kind_passed_and_text_filters(self) -> None:
        gate = self._gate()
        for kwargs in (
            {"passed": True},
            {"kind": "diff-link"},
            {"text": "verified packet transition"},
        ):
            result = packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, **kwargs
            )
            self.assertTrue(
                packet_gate.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_query(
                    result
                )
            )
            self.assertGreaterEqual(result["total"], len(result["items"]))
        self.assertEqual(
            packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, kind="diff-link"
            )["total"],
            1,
        )

    def test_assurance_queries_page_with_total_conservation(self) -> None:
        assurance = self._assurance(diff=self._diff())
        result = packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
            assurance, offset=2, limit=3
        )
        self.assertEqual(result["total"], 8)
        self.assertEqual(len(result["items"]), 3)
        self.assertEqual(result["items"][0]["ordinal"], 2)
        beyond = packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
            assurance, offset=99, limit=3
        )
        self.assertEqual(beyond["total"], 8)
        self.assertEqual(beyond["items"], [])

    def test_gate_queries_page_with_total_conservation(self) -> None:
        gate = self._gate()
        result = packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
            gate, offset=2, limit=3
        )
        self.assertEqual(result["total"], 8)
        self.assertEqual(len(result["items"]), 3)
        self.assertEqual(result["items"][0]["ordinal"], 2)
        beyond = packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
            gate, offset=99, limit=3
        )
        self.assertEqual(beyond["total"], 8)
        self.assertEqual(beyond["items"], [])

    def test_assurance_query_receipt_changes_for_every_filter(self) -> None:
        assurance = self._assurance()
        base = packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
            assurance
        )
        variants = (
            packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, severity="blocker"
            ),
            packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, passed=True
            ),
            packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, offset=1
            ),
            packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, limit=1
            ),
        )
        self.assertEqual(len({item["content_address"] for item in (base, *variants)}), 5)

    def test_gate_query_receipt_changes_for_every_filter(self) -> None:
        gate = self._gate()
        base = packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
            gate
        )
        variants = (
            packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, passed=True
            ),
            packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, kind="diff-link"
            ),
            packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, offset=1
            ),
            packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, limit=1
            ),
        )
        self.assertEqual(len({item["content_address"] for item in (base, *variants)}), 5)

    def test_assurance_query_rejects_tampered_receipt(self) -> None:
        result = packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
            self._assurance()
        )
        result["total"] = 0
        with self.assertRaises(ValidationError):
            packet_assurance.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_query(
                result
            )

    def test_gate_query_rejects_tampered_receipt(self) -> None:
        result = packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
            self._gate()
        )
        result["total"] = 0
        with self.assertRaises(ValidationError):
            packet_gate.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_query(
                result
            )

    def test_assurance_query_rejects_invalid_resource_filter_and_bounds(self) -> None:
        assurance = self._assurance(diff=self._diff())
        with self.assertRaises(ValidationError):
            packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, resource="unknown"
            )
        with self.assertRaises(ValidationError):
            packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, severity="pass"
            )
        with self.assertRaises(ValidationError):
            packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, offset=-1
            )
        with self.assertRaises(ValidationError):
            packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, limit=0
            )

    def test_gate_query_rejects_invalid_resource_filter_and_bounds(self) -> None:
        gate = self._gate()
        with self.assertRaises(ValidationError):
            packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, resource="unknown"
            )
        with self.assertRaises(ValidationError):
            packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, offset=-1
            )
        with self.assertRaises(ValidationError):
            packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, limit=0
            )

    def test_assurance_query_exports_are_canonical(self) -> None:
        assurance = self._assurance(diff=self._diff())
        result = packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
            assurance, kind="diff-linkage"
        )
        rendered = packet_assurance.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_query_json(
            result
        )
        self.assertEqual(rendered, canonical_json(json.loads(rendered)) + "\n")
        csv_rendered = packet_assurance.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_query_csv(
            result
        )
        self.assertEqual(len(list(csv.DictReader(csv_rendered.splitlines()))), 1)
        markdown = packet_assurance.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_query_markdown(
            result
        )
        self.assertIn("# Catalog Packet Review Assurance Query", markdown)

    def test_gate_query_exports_are_canonical(self) -> None:
        gate = self._gate()
        result = packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
            gate, kind="diff-link"
        )
        rendered = packet_gate.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_query_json(
            result
        )
        self.assertEqual(rendered, canonical_json(json.loads(rendered)) + "\n")
        csv_rendered = packet_gate.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_query_csv(
            result
        )
        self.assertEqual(len(list(csv.DictReader(csv_rendered.splitlines()))), 1)
        markdown = packet_gate.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_query_markdown(
            result
        )
        self.assertIn("# Catalog Packet Review Gate Query", markdown)

    def test_assurance_schema_and_capabilities_are_identity_free(self) -> None:
        values = (
            packet_assurance.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_schema(),
            packet_assurance.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_capabilities(),
            packet_assurance.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_query_schema(),
            packet_assurance.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_query_capabilities(),
        )
        for value in values:
            rendered = canonical_json(value).casefold()
            self.assertNotIn("agent", rendered)
            self.assertNotIn("language", rendered)
            self.assertNotIn("model", rendered)
            self.assertNotIn("user", rendered)
        self.assertTrue(values[1]["independent_recomputation"])
        self.assertTrue(values[3]["addressed_receipts"])

    def test_gate_schema_and_capabilities_are_identity_free(self) -> None:
        values = (
            packet_gate.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_schema(),
            packet_gate.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_capabilities(),
            packet_gate.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_query_schema(),
            packet_gate.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_query_capabilities(),
        )
        for value in values:
            rendered = canonical_json(value).casefold()
            self.assertNotIn("agent", rendered)
            self.assertNotIn("language", rendered)
            self.assertNotIn("model", rendered)
            self.assertNotIn("user", rendered)
        self.assertTrue(values[1]["independent_component_links"])
        self.assertTrue(values[3]["addressed_receipts"])

    def test_assurance_schema_declares_exact_files_and_resources(self) -> None:
        schema = packet_assurance.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_schema()
        self.assertEqual(schema["exact_files"], ["manifest.json", "assurance.json"])
        self.assertEqual(schema["resources"], ["summary", "findings", "checks"])
        self.assertTrue(schema["bounded"])
        self.assertTrue(schema["path_free"])
        self.assertTrue(schema["timestamp_free"])

    def test_gate_schema_declares_exact_files_and_resources(self) -> None:
        schema = packet_gate.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_schema()
        self.assertEqual(schema["exact_files"], ["manifest.json", "gate.json"])
        self.assertEqual(schema["resources"], ["summary", "checks"])
        self.assertTrue(schema["bounded"])
        self.assertTrue(schema["path_free"])
        self.assertTrue(schema["timestamp_free"])

    def test_assurance_write_and_load_is_an_exact_two_file_round_trip(self) -> None:
        assurance = self._assurance()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "nested" / "assurance"
            written = packet_assurance.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, destination
            )
            self.assertEqual(written, destination)
            self.assertEqual(
                {item.name for item in destination.iterdir()}, {"manifest.json", "assurance.json"}
            )
            loaded = packet_assurance.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                destination
            )
            self.assertEqual(loaded.content_address, assurance.content_address)
            self.assertEqual(loaded.to_dict(), assurance.to_dict())
            self.assertTrue(
                packet_assurance.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                    loaded
                ).accepted
            )

    def test_gate_write_and_load_is_an_exact_two_file_round_trip(self) -> None:
        gate = self._gate()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "nested" / "gate"
            written = packet_gate.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, destination
            )
            self.assertEqual(written, destination)
            self.assertEqual(
                {item.name for item in destination.iterdir()}, {"manifest.json", "gate.json"}
            )
            loaded = packet_gate.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                destination
            )
            self.assertEqual(loaded.content_address, gate.content_address)
            self.assertEqual(canonical_json(loaded.to_dict()), canonical_json(gate.to_dict()))
            self.assertTrue(
                packet_gate.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                    loaded
                ).accepted
            )

    def test_assurance_write_bytes_are_stable_across_destinations(self) -> None:
        assurance = self._assurance()
        with tempfile.TemporaryDirectory() as root:
            first = Path(root) / "first"
            second = Path(root) / "second"
            packet_assurance.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, first
            )
            packet_assurance.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, second
            )
            for name in ("manifest.json", "assurance.json"):
                self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())

    def test_gate_write_bytes_are_stable_across_destinations(self) -> None:
        gate = self._gate()
        with tempfile.TemporaryDirectory() as root:
            first = Path(root) / "first"
            second = Path(root) / "second"
            packet_gate.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, first
            )
            packet_gate.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, second
            )
            for name in ("manifest.json", "gate.json"):
                self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())

    def test_assurance_write_rejects_existing_destination_without_overwrite(self) -> None:
        assurance = self._assurance()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "assurance"
            packet_assurance.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, destination
            )
            with self.assertRaises(ValidationError):
                packet_assurance.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                    assurance, destination
                )
            packet_assurance.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, destination, overwrite=True
            )
            self.assertEqual(
                packet_assurance.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                    destination
                ).content_address,
                assurance.content_address,
            )

    def test_gate_write_rejects_existing_destination_without_overwrite(self) -> None:
        gate = self._gate()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "gate"
            packet_gate.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, destination
            )
            with self.assertRaises(ValidationError):
                packet_gate.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                    gate, destination
                )
            packet_gate.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, destination, overwrite=True
            )
            self.assertEqual(
                packet_gate.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                    destination
                ).content_address,
                gate.content_address,
            )

    def test_assurance_manifest_conserves_document_count_and_bytes(self) -> None:
        assurance = self._assurance()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "assurance"
            packet_assurance.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, destination
            )
            manifest = json.loads((destination / "manifest.json").read_text())
            document = (destination / "assurance.json").read_bytes()
            self.assertEqual(manifest["byte_count"], len(document))
            self.assertEqual(manifest["assurance"], json.loads(document))
            self.assertEqual(
                manifest["manifest_version"],
                packet_assurance.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_VERSION,
            )
            self.assertEqual(
                canonical_bytes(manifest), (destination / "manifest.json").read_bytes()
            )

    def test_gate_manifest_conserves_document_count_and_bytes(self) -> None:
        gate = self._gate()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "gate"
            packet_gate.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, destination
            )
            manifest = json.loads((destination / "manifest.json").read_text())
            document = (destination / "gate.json").read_bytes()
            self.assertEqual(manifest["byte_count"], len(document))
            self.assertEqual(manifest["gate"], json.loads(document))
            self.assertEqual(
                manifest["manifest_version"],
                packet_gate.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_VERSION,
            )
            self.assertEqual(
                canonical_bytes(manifest), (destination / "manifest.json").read_bytes()
            )

    def test_assurance_loader_rejects_mutated_document_bytes(self) -> None:
        assurance = self._assurance()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "assurance"
            packet_assurance.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, destination
            )
            document = json.loads((destination / "assurance.json").read_text())
            document["detail"] = "tampered"
            (destination / "assurance.json").write_bytes(canonical_bytes(document))
            with self.assertRaises(ValidationError):
                packet_assurance.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                    destination
                )

    def test_gate_loader_rejects_mutated_document_bytes(self) -> None:
        gate = self._gate()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "gate"
            packet_gate.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, destination
            )
            document = json.loads((destination / "gate.json").read_text())
            document["decision"] = "hold"
            (destination / "gate.json").write_bytes(canonical_bytes(document))
            with self.assertRaises(ValidationError):
                packet_gate.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                    destination
                )

    def test_assurance_loader_rejects_noncanonical_document_json(self) -> None:
        assurance = self._assurance()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "assurance"
            packet_assurance.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, destination
            )
            document = json.loads((destination / "assurance.json").read_text())
            (destination / "assurance.json").write_text(json.dumps(document, indent=2) + "\n")
            with self.assertRaises(ValidationError):
                packet_assurance.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                    destination
                )

    def test_gate_loader_rejects_noncanonical_manifest_json(self) -> None:
        gate = self._gate()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "gate"
            packet_gate.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, destination
            )
            manifest = json.loads((destination / "manifest.json").read_text())
            (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
            with self.assertRaises(ValidationError):
                packet_gate.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                    destination
                )

    def test_assurance_loader_rejects_missing_and_extra_files(self) -> None:
        assurance = self._assurance()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "assurance"
            packet_assurance.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, destination
            )
            (destination / "manifest.json").unlink()
            with self.assertRaises(ValidationError):
                packet_assurance.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                    destination
                )
            packet_assurance.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, destination, overwrite=True
            )
            (destination / "extra.json").write_bytes(b"{}")
            with self.assertRaises(ValidationError):
                packet_assurance.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                    destination
                )

    def test_gate_loader_rejects_missing_and_extra_files(self) -> None:
        gate = self._gate()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "gate"
            packet_gate.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, destination
            )
            (destination / "gate.json").unlink()
            with self.assertRaises(ValidationError):
                packet_gate.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                    destination
                )
            packet_gate.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, destination, overwrite=True
            )
            (destination / "extra.json").write_bytes(b"{}")
            with self.assertRaises(ValidationError):
                packet_gate.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                    destination
                )

    def test_assurance_loader_rejects_manifest_address_and_version_mutations(self) -> None:
        assurance = self._assurance()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "assurance"
            packet_assurance.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, destination
            )
            manifest = json.loads((destination / "manifest.json").read_text())
            manifest["manifest_address"] = "tampered:manifest"
            (destination / "manifest.json").write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                packet_assurance.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                    destination
                )
            packet_assurance.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, destination, overwrite=True
            )
            manifest = json.loads((destination / "manifest.json").read_text())
            manifest["manifest_version"] = "wrong-version"
            (destination / "manifest.json").write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                packet_assurance.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                    destination
                )

    def test_gate_loader_rejects_manifest_address_and_version_mutations(self) -> None:
        gate = self._gate()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "gate"
            packet_gate.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, destination
            )
            manifest = json.loads((destination / "manifest.json").read_text())
            manifest["manifest_address"] = "tampered:manifest"
            (destination / "manifest.json").write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                packet_gate.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                    destination
                )
            packet_gate.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, destination, overwrite=True
            )
            manifest = json.loads((destination / "manifest.json").read_text())
            manifest["manifest_version"] = "wrong-version"
            (destination / "manifest.json").write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                packet_gate.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                    destination
                )

    def test_assurance_loader_rejects_directory_file_and_symlink_shapes(self) -> None:
        assurance = self._assurance()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "assurance"
            packet_assurance.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, destination
            )
            (destination / "child").mkdir()
            with self.assertRaises(ValidationError):
                packet_assurance.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                    destination
                )
            (destination / "child").rmdir()
            link = destination / "link.json"
            try:
                link.symlink_to(destination / "manifest.json")
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are unavailable in this environment")
            with self.assertRaises(ValidationError):
                packet_assurance.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                    destination
                )

    def test_gate_loader_rejects_directory_file_and_symlink_shapes(self) -> None:
        gate = self._gate()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "gate"
            packet_gate.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, destination
            )
            (destination / "child").mkdir()
            with self.assertRaises(ValidationError):
                packet_gate.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                    destination
                )
            (destination / "child").rmdir()
            link = destination / "link.json"
            try:
                link.symlink_to(destination / "manifest.json")
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are unavailable in this environment")
            with self.assertRaises(ValidationError):
                packet_gate.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                    destination
                )

    def test_assurance_from_directories_builds_a_path_free_verified_value(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            assurance = packet_assurance.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_from_directories(
                left, right, assurance_id="directory-assurance"
            )
            self.assertEqual(assurance.assurance_id, "directory-assurance")
            self.assertTrue(assurance.accepted)
            self.assertTrue(assurance.release_ready)
            self.assertNotIn(str(left), canonical_json(assurance.to_dict()))
            self.assertNotIn(str(right), canonical_json(assurance.to_dict()))

    def test_gate_from_directories_builds_a_path_free_verified_value(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            gate = packet_gate.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_from_directories(
                left, right, gate_id="directory-gate"
            )
            self.assertEqual(gate.gate_id, "directory-gate")
            self.assertEqual(gate.state, "ready")
            self.assertTrue(gate.accepted)
            self.assertTrue(gate.release_ready)
            self.assertNotIn(str(left), canonical_json(gate.to_dict()))
            self.assertNotIn(str(right), canonical_json(gate.to_dict()))

    def test_assurance_from_directories_preserves_explicit_hold_decision(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            left, right = self._nonready_pair_directories(root)
            assurance = packet_assurance.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_from_directories(
                left, right, decision="hold", decision_id="decision:hold", detail="manual hold"
            )
            self.assertEqual(assurance.review_state, "held")
            self.assertTrue(assurance.accepted)
            self.assertFalse(assurance.release_ready)

    def test_gate_from_directories_preserves_explicit_block_decision(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            left, right = self._nonready_pair_directories(root)
            gate = packet_gate.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_from_directories(
                left, right, decision="block", decision_id="decision:block", detail="manual block"
            )
            self.assertEqual(gate.decision, "block")
            self.assertEqual(gate.state, "blocked")
            self.assertFalse(gate.accepted)
            self.assertFalse(gate.release_ready)

    def test_cli_assurance_and_gate_commands_build_real_packet_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            assurance_path = Path(root) / "assurance.json"
            gate_path = Path(root) / "gate.json"
            assurance_command = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-assurance"
            gate_command = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate"
            self.assertEqual(
                main(
                    [
                        assurance_command,
                        "--left-packet-directory",
                        str(left),
                        "--right-packet-directory",
                        str(right),
                        "--format",
                        "summary",
                        "--output",
                        str(assurance_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        gate_command,
                        "--left-packet-directory",
                        str(left),
                        "--right-packet-directory",
                        str(right),
                        "--format",
                        "summary",
                        "--output",
                        str(gate_path),
                    ]
                ),
                0,
            )
            assurance_summary = json.loads(assurance_path.read_text())
            gate_summary = json.loads(gate_path.read_text())
            self.assertEqual(assurance_summary["finding_count"], 8)
            self.assertTrue(assurance_summary["release_ready"])
            self.assertEqual(gate_summary["state"], "ready")
            self.assertTrue(gate_summary["release_ready"])

    def test_cli_assurance_and_gate_commands_render_csv_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            assurance_command = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-assurance"
            gate_command = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate"
            for command, marker in (
                (assurance_command, "ordinal,kind,severity"),
                (gate_command, "ordinal,kind,state"),
            ):
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
                            "csv",
                        ]
                    )
                self.assertEqual(result, 0)
                self.assertIn(marker, output.getvalue())
            for command, marker in (
                (assurance_command, "# Catalog Packet Review Assurance"),
                (gate_command, "# Catalog Packet Review Gate"),
            ):
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
                            "markdown",
                        ]
                    )
                self.assertEqual(result, 0)
                self.assertIn(marker, output.getvalue())

    def test_cli_assurance_and_gate_query_commands_filter_and_page(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            assurance_command = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-assurance-query"
            gate_command = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-query"
            assurance_path = Path(root) / "assurance-query.json"
            gate_path = Path(root) / "gate-query.json"
            self.assertEqual(
                main(
                    [
                        assurance_command,
                        "--left-packet-directory",
                        str(left),
                        "--right-packet-directory",
                        str(right),
                        "--kind",
                        "diff-linkage",
                        "--output",
                        str(assurance_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        gate_command,
                        "--left-packet-directory",
                        str(left),
                        "--right-packet-directory",
                        str(right),
                        "--kind",
                        "diff-link",
                        "--output",
                        str(gate_path),
                    ]
                ),
                0,
            )
            assurance_result = json.loads(assurance_path.read_text())
            gate_result = json.loads(gate_path.read_text())
            self.assertEqual(assurance_result["total"], 1)
            self.assertEqual(assurance_result["items"][0]["kind"], "diff-linkage")
            self.assertEqual(gate_result["total"], 1)
            self.assertEqual(gate_result["items"][0]["kind"], "diff-link")

    def test_cli_schema_and_capability_commands_are_discoverable(self) -> None:
        commands = (
            "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-assurance-schema",
            "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-assurance-capabilities",
            "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-assurance-query-schema",
            "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-assurance-query-capabilities",
            "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-schema",
            "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-capabilities",
            "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-query-schema",
            "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-query-capabilities",
        )
        for command in commands:
            output = StringIO()
            with redirect_stdout(output):
                result = main([command])
            self.assertEqual(result, 0)
            self.assertTrue(json.loads(output.getvalue()))

    @staticmethod
    def _http_json(server, path: str, params: dict[str, str]):
        connection = HTTPConnection("127.0.0.1", server.server_address[1], timeout=15)
        connection.request("GET", path + "?" + urlencode(params))
        response = connection.getresponse()
        body = response.read().decode("utf-8")
        content_type = response.getheader("Content-Type", "")
        connection.close()
        return response.status, content_type, body

    def test_http_assurance_and_gate_routes_build_summaries_queries_and_schemas(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            server = create_server("127.0.0.1", 0, str(Path(root) / "data"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            assurance_base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/assurance"
            gate_base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate"
            params = {"left_packet_directory": str(left), "right_packet_directory": str(right)}
            try:
                cases = (
                    (assurance_base, params, "ready"),
                    (assurance_base + "/query", params | {"kind": "diff-linkage"}, "query"),
                    (assurance_base + "/schema", {}, "schema"),
                    (assurance_base + "/capabilities", {}, "schema"),
                    (assurance_base + "/query/schema", {}, "schema"),
                    (assurance_base + "/query/capabilities", {}, "schema"),
                    (gate_base, params, "ready"),
                    (gate_base + "/query", params | {"kind": "diff-link"}, "query"),
                    (gate_base + "/schema", {}, "schema"),
                    (gate_base + "/capabilities", {}, "schema"),
                    (gate_base + "/query/schema", {}, "schema"),
                    (gate_base + "/query/capabilities", {}, "schema"),
                )
                for path, case_params, expected in cases:
                    status, content_type, body = self._http_json(server, path, case_params)
                    self.assertEqual(status, 200)
                    self.assertIn("application/json", content_type)
                    decoded = json.loads(body)
                    if expected == "ready":
                        self.assertEqual(decoded.get("state", decoded.get("review_state")), "ready")
                    elif expected == "query":
                        self.assertEqual(decoded["total"], 1)
                    else:
                        self.assertTrue(decoded)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_http_assurance_and_gate_routes_negotiate_csv_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            server = create_server("127.0.0.1", 0, str(Path(root) / "data"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            assurance_base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/assurance"
            gate_base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate"
            params = {"left_packet_directory": str(left), "right_packet_directory": str(right)}
            try:
                for base, csv_marker, markdown_marker in (
                    (assurance_base, "ordinal,kind,severity", "# Catalog Packet Review Assurance"),
                    (gate_base, "ordinal,kind,state", "# Catalog Packet Review Gate"),
                ):
                    for output_format, content_type, marker in (
                        ("csv", "text/csv", csv_marker),
                        ("markdown", "text/markdown", markdown_marker),
                    ):
                        status, actual_type, body = self._http_json(
                            server, base, params | {"format": output_format}
                        )
                        self.assertEqual(status, 200)
                        self.assertIn(content_type, actual_type)
                        self.assertIn(marker, body)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_http_directory_aliases_are_supported_for_both_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            server = create_server("127.0.0.1", 0, str(Path(root) / "data"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            assurance_base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/assurance"
            gate_base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate"
            try:
                for base, expected in ((assurance_base, "ready"), (gate_base, "ready")):
                    status, _, body = self._http_json(
                        server, base, {"left_directory": str(left), "right_directory": str(right)}
                    )
                    self.assertEqual(status, 200)
                    value = json.loads(body)
                    self.assertEqual(value.get("state", value.get("review_state")), expected)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_http_missing_packet_directories_fail_closed(self) -> None:
        server = create_server("127.0.0.1", 0, tempfile.mkdtemp())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/assurance"
        try:
            status, _, body = self._http_json(server, base, {})
            self.assertGreaterEqual(status, 400)
            self.assertTrue(body)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_held_assurance_can_be_persisted_and_reloaded(self) -> None:
        diff = self._diff(
            right=self._packet(
                self._catalog(self._store("held", state="held", release_ready=False)),
                packet_id="held-right",
            )
        )
        review = self._review(diff, decision="hold", detail="awaiting evidence")
        assurance = self._assurance(review, diff)
        self.assertTrue(assurance.accepted)
        self.assertFalse(assurance.release_ready)
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "held-assurance"
            packet_assurance.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, destination
            )
            loaded = packet_assurance.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                destination
            )
            self.assertTrue(loaded.accepted)
            self.assertFalse(loaded.release_ready)
            self.assertEqual(loaded.content_address, assurance.content_address)

    def test_blocked_gate_can_be_persisted_and_reloaded_as_rejection_evidence(self) -> None:
        diff = self._diff(
            right=self._packet(
                self._catalog(
                    self._store("blocked", state="blocked", release_ready=False, accepted=False)
                ),
                packet_id="blocked-right",
            )
        )
        review = self._review(diff, decision="block", detail="candidate is blocked")
        assurance = self._assurance(review, diff)
        gate = self._gate(diff, review, assurance)
        self.assertFalse(gate.accepted)
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "blocked-gate"
            packet_gate.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, destination
            )
            loaded = packet_gate.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                destination
            )
            self.assertFalse(loaded.accepted)
            self.assertEqual(loaded.state, "blocked")
            self.assertEqual(loaded.content_address, gate.content_address)

    def test_ready_review_cannot_be_held_or_blocked_without_changed_release_state(self) -> None:
        diff = self._diff()
        with self.assertRaises(ValidationError):
            self._review(diff, decision="hold", detail="invalid hold")
        with self.assertRaises(ValidationError):
            self._review(diff, decision="block", detail="invalid block")

    def test_nonready_review_cannot_be_promoted(self) -> None:
        diff = self._diff(
            right=self._packet(
                self._catalog(self._store("held", state="held", release_ready=False)),
                packet_id="held-right",
            )
        )
        with self.assertRaises(ValidationError):
            self._review(diff, decision="promote", detail="invalid promotion")

    def test_each_nonready_decision_has_explicit_gate_semantics(self) -> None:
        diff = self._diff(
            right=self._packet(
                self._catalog(self._store("held", state="held", release_ready=False)),
                packet_id="held-right",
            )
        )
        for decision, expected_state, expected_acceptance in (
            ("hold", "held", True),
            ("supersede", "held", True),
            ("block", "blocked", False),
        ):
            review = self._review(diff, decision=decision, detail=f"decision {decision}")
            assurance = self._assurance(review, diff)
            gate = self._gate(diff, review, assurance)
            self.assertEqual(gate.state, expected_state)
            self.assertEqual(gate.accepted, expected_acceptance)
            self.assertFalse(gate.release_ready)

    def test_assurance_release_readiness_depends_on_review_state_and_flag(self) -> None:
        diff = self._diff()
        ready = self._assurance(self._review(diff), diff)
        self.assertTrue(ready.release_ready)
        held_diff = self._diff(
            right=self._packet(
                self._catalog(self._store("held", state="held", release_ready=False)),
                packet_id="held-right",
            )
        )
        held_review = self._review(held_diff, decision="hold", detail="not ready")
        held_assurance = self._assurance(held_review, held_diff)
        self.assertTrue(held_assurance.accepted)
        self.assertFalse(held_assurance.release_ready)

    def test_assurance_verification_reports_review_link_failure(self) -> None:
        diff = self._diff()
        review = self._review(diff)
        assurance = self._assurance(review, diff)
        review.content_address = "tampered:review"
        verification = packet_assurance.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
            assurance, review=review, diff=diff
        )
        self.assertFalse(verification.accepted)
        self.assertFalse(verification.checks[-1].passed)

    def test_assurance_verification_reports_diff_link_failure(self) -> None:
        diff = self._diff()
        review = self._review(diff)
        assurance = self._assurance(review, diff)
        assurance.diff_address = "tampered:diff"
        verification = packet_assurance.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
            assurance, review=review, diff=diff
        )
        self.assertFalse(verification.accepted)
        self.assertFalse(verification.checks[0].passed)

    def test_assurance_verification_reports_count_and_acceptance_mutations(self) -> None:
        for field, value in (
            ("finding_count", 7),
            ("passed_count", 0),
            ("failed_count", 8),
            ("blocker_count", 1),
            ("warning_count", 1),
            ("accepted", False),
            ("release_ready", False),
        ):
            assurance = self._assurance(diff=self._diff())
            setattr(assurance, field, value)
            verification = packet_assurance.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance
            )
            self.assertFalse(verification.accepted, field)

    def test_gate_verification_reports_decision_state_and_readiness_mutations(self) -> None:
        for field, value in (
            ("decision", "hold"),
            ("state", "held"),
            ("release_ready", False),
            ("accepted", False),
            ("check_count", 7),
            ("passed_count", 0),
            ("failed_count", 8),
        ):
            gate = self._gate()
            setattr(gate, field, value)
            verification = packet_gate.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate
            )
            self.assertFalse(verification.accepted, field)

    def test_assurance_finding_state_is_derived_from_pass_boolean(self) -> None:
        assurance = self._assurance(diff=self._diff())
        for finding in assurance.findings:
            original = finding.passed
            finding.passed = not original
            self.assertEqual(finding.state, "failed" if original else "passed")
            finding.passed = original

    def test_gate_check_state_is_serialized_from_pass_boolean(self) -> None:
        gate = self._gate()
        for check in gate.checks:
            document = check.to_dict()
            self.assertEqual(document["state"], "passed" if check.passed else "failed")

    def test_projection_flags_omit_nested_findings_and_checks(self) -> None:
        assurance = self._assurance(diff=self._diff())
        gate = self._gate()
        self.assertNotIn("findings", assurance.to_dict(include_findings=False))
        self.assertIn("findings", assurance.to_dict(include_findings=True))
        self.assertNotIn("checks", gate.to_dict(include_checks=False))
        self.assertIn("checks", gate.to_dict(include_checks=True))

    def test_assurance_and_gate_summaries_are_minimal_public_projections(self) -> None:
        assurance = self._assurance(diff=self._diff())
        gate = self._gate()
        for summary in (assurance.summary(), gate.summary()):
            encoded = canonical_json(summary).casefold()
            for forbidden in (
                "left_packet",
                "right_packet",
                "path",
                "timestamp",
                "agent",
                "language",
                "model",
                "user",
            ):
                self.assertNotIn(forbidden, encoded)

    def test_assurance_and_gate_schema_versions_are_distinct_from_query_versions(self) -> None:
        assurance_schema = packet_assurance.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_schema()
        assurance_query_schema = packet_assurance.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_query_schema()
        gate_schema = packet_gate.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_schema()
        gate_query_schema = packet_gate.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_query_schema()
        self.assertNotEqual(assurance_schema["version"], assurance_query_schema["version"])
        self.assertNotEqual(gate_schema["version"], gate_query_schema["version"])

    def test_assurance_and_gate_capabilities_declare_fail_closed_atomic_contracts(self) -> None:
        assurance = packet_assurance.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_capabilities()
        gate = packet_gate.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_capabilities()
        for value in (assurance, gate):
            self.assertTrue(value["atomic_write"])
            self.assertTrue(value["canonical_json"])
            self.assertTrue(value["fail_closed"])
            self.assertTrue(value["identity_free"])

    def test_assurance_query_capabilities_declare_bounded_receipts(self) -> None:
        value = packet_assurance.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_query_capabilities()
        self.assertTrue(value["bounded"])
        self.assertTrue(value["addressed_receipts"])
        self.assertEqual(value["resources"], ["summary", "findings", "checks"])

    def test_gate_query_capabilities_declare_bounded_receipts(self) -> None:
        value = packet_gate.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_query_capabilities()
        self.assertTrue(value["bounded"])
        self.assertTrue(value["addressed_receipts"])
        self.assertEqual(value["resources"], ["summary", "checks"])

    def test_assurance_query_empty_text_and_overlong_text_are_rejected(self) -> None:
        assurance = self._assurance()
        with self.assertRaises(ValidationError):
            packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, text=""
            )
        with self.assertRaises(ValidationError):
            packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, text="x" * 4097
            )

    def test_gate_query_empty_text_and_overlong_text_are_rejected(self) -> None:
        gate = self._gate()
        with self.assertRaises(ValidationError):
            packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, text=""
            )
        with self.assertRaises(ValidationError):
            packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, text="x" * 4097
            )

    def test_assurance_query_accepts_maximum_limit_and_rejects_large_limit(self) -> None:
        assurance = self._assurance()
        result = packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
            assurance, limit=512
        )
        self.assertEqual(result["total"], 5)
        with self.assertRaises(ValidationError):
            packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, limit=513
            )

    def test_gate_query_accepts_maximum_limit_and_rejects_large_limit(self) -> None:
        gate = self._gate()
        result = packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
            gate, limit=512
        )
        self.assertEqual(result["total"], 8)
        with self.assertRaises(ValidationError):
            packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, limit=513
            )

    def test_assurance_query_rejects_non_boolean_pass_filter(self) -> None:
        with self.assertRaises(ValidationError):
            packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                self._assurance(), passed="true"
            )

    def test_gate_query_rejects_non_boolean_pass_filter(self) -> None:
        with self.assertRaises(ValidationError):
            packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                self._gate(), passed="true"
            )

    def test_assurance_query_summary_ignores_row_filters_but_retains_filter_receipt(self) -> None:
        assurance = self._assurance()
        result = packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
            assurance, resource="summary", severity="blocker", passed=True, kind="review-structure"
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["query"]["severity"], "blocker")
        self.assertTrue(
            packet_assurance.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_query(
                result
            )
        )

    def test_gate_query_summary_ignores_row_filters_but_retains_filter_receipt(self) -> None:
        gate = self._gate()
        result = packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
            gate, resource="summary", kind="diff-link", passed=True
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["query"]["kind"], "diff-link")
        self.assertTrue(
            packet_gate.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_query(
                result
            )
        )

    def test_assurance_and_gate_query_json_round_trips_through_canonical_bytes(self) -> None:
        assurance_result = packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
            self._assurance()
        )
        gate_result = packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
            self._gate()
        )
        for value, renderer in (
            (
                assurance_result,
                packet_assurance.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_query_json,
            ),
            (
                gate_result,
                packet_gate.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_query_json,
            ),
        ):
            raw = renderer(value)
            parsed = json.loads(raw)
            self.assertEqual(raw, canonical_json(parsed) + "\n")
            self.assertEqual(parsed["content_address"], value["content_address"])

    def test_assurance_and_gate_content_addresses_change_when_ids_change(self) -> None:
        base_assurance = self._assurance()
        changed_assurance = self._assurance(assurance_id="assurance-other")
        base_gate = self._gate()
        changed_gate = self._gate(gate_id="gate-other")
        self.assertNotEqual(base_assurance.content_address, changed_assurance.content_address)
        self.assertNotEqual(base_gate.content_address, changed_gate.content_address)

    def test_assurance_and_gate_content_addresses_exclude_transport_paths(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            left, right = self._pair_directories(root)
            assurance = packet_assurance.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_from_directories(
                left, right
            )
            gate = packet_gate.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_from_directories(
                left, right
            )
            for value in (assurance.to_dict(), gate.to_dict()):
                encoded = canonical_json(value)
                self.assertNotIn(str(Path(root)), encoded)
                self.assertNotIn(str(left), encoded)
                self.assertNotIn(str(right), encoded)

    def test_assurance_loader_rejects_invalid_root_shapes(self) -> None:
        assurance = self._assurance()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "assurance"
            packet_assurance.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, destination
            )
            with self.assertRaises(ValidationError):
                packet_assurance.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                    destination / "missing"
                )
            file_path = Path(root) / "file"
            file_path.write_bytes(b"not a directory")
            with self.assertRaises(ValidationError):
                packet_assurance.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                    file_path
                )

    def test_gate_loader_rejects_invalid_root_shapes(self) -> None:
        gate = self._gate()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "gate"
            packet_gate.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, destination
            )
            with self.assertRaises(ValidationError):
                packet_gate.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                    destination / "missing"
                )
            file_path = Path(root) / "file"
            file_path.write_bytes(b"not a directory")
            with self.assertRaises(ValidationError):
                packet_gate.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                    file_path
                )

    def test_assurance_loader_rejects_malformed_manifest_and_document_json(self) -> None:
        assurance = self._assurance()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "assurance"
            packet_assurance.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, destination
            )
            (destination / "manifest.json").write_bytes(b"{")
            with self.assertRaises(ValidationError):
                packet_assurance.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                    destination
                )
            packet_assurance.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, destination, overwrite=True
            )
            (destination / "assurance.json").write_bytes(b"{")
            with self.assertRaises(ValidationError):
                packet_assurance.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                    destination
                )

    def test_gate_loader_rejects_malformed_manifest_and_document_json(self) -> None:
        gate = self._gate()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "gate"
            packet_gate.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, destination
            )
            (destination / "manifest.json").write_bytes(b"{")
            with self.assertRaises(ValidationError):
                packet_gate.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                    destination
                )
            packet_gate.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, destination, overwrite=True
            )
            (destination / "gate.json").write_bytes(b"{")
            with self.assertRaises(ValidationError):
                packet_gate.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                    destination
                )

    def test_assurance_loader_rejects_unknown_manifest_keys(self) -> None:
        assurance = self._assurance()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "assurance"
            packet_assurance.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, destination
            )
            manifest = json.loads((destination / "manifest.json").read_text())
            manifest["unknown"] = True
            (destination / "manifest.json").write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                packet_assurance.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                    destination
                )

    def test_gate_loader_rejects_unknown_manifest_keys(self) -> None:
        gate = self._gate()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "gate"
            packet_gate.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, destination
            )
            manifest = json.loads((destination / "manifest.json").read_text())
            manifest["unknown"] = True
            (destination / "manifest.json").write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                packet_gate.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                    destination
                )

    def test_assurance_loader_rejects_wrong_document_byte_address(self) -> None:
        assurance = self._assurance()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "assurance"
            packet_assurance.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, destination
            )
            manifest = json.loads((destination / "manifest.json").read_text())
            manifest["byte_address"] = "tampered:bytes"
            (destination / "manifest.json").write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                packet_assurance.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                    destination
                )

    def test_gate_loader_rejects_wrong_document_byte_address(self) -> None:
        gate = self._gate()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "gate"
            packet_gate.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, destination
            )
            manifest = json.loads((destination / "manifest.json").read_text())
            manifest["byte_address"] = "tampered:bytes"
            (destination / "manifest.json").write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                packet_gate.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                    destination
                )

    def test_assurance_writer_rejects_mutated_unverified_record(self) -> None:
        assurance = self._assurance()
        assurance.accepted = False
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValidationError):
                packet_assurance.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                    assurance, Path(root) / "assurance"
                )

    def test_gate_writer_rejects_mutated_unverified_record(self) -> None:
        gate = self._gate()
        gate.accepted = False
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValidationError):
                packet_gate.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                    gate, Path(root) / "gate"
                )

    def test_assurance_and_gate_writers_create_deep_missing_parents(self) -> None:
        assurance = self._assurance()
        gate = self._gate()
        with tempfile.TemporaryDirectory() as root:
            assurance_destination = Path(root) / "a" / "b" / "assurance"
            gate_destination = Path(root) / "c" / "d" / "gate"
            packet_assurance.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, assurance_destination
            )
            packet_gate.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, gate_destination
            )
            self.assertTrue((assurance_destination / "assurance.json").is_file())
            self.assertTrue((gate_destination / "gate.json").is_file())

    def test_assurance_and_gate_loaded_documents_are_byte_identical_to_renderings(self) -> None:
        assurance = self._assurance()
        gate = self._gate()
        with tempfile.TemporaryDirectory() as root:
            assurance_destination = Path(root) / "assurance"
            gate_destination = Path(root) / "gate"
            packet_assurance.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, assurance_destination
            )
            packet_gate.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, gate_destination
            )
            self.assertEqual(
                (assurance_destination / "assurance.json").read_text(),
                packet_assurance.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_json(
                    assurance
                ).rstrip("\n"),
            )
            self.assertEqual(
                (gate_destination / "gate.json").read_text(),
                packet_gate.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_json(
                    gate
                ).rstrip("\n"),
            )

    def test_real_downloaded_packet_can_build_assurance_and_gate(self) -> None:
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
        assurance = self._assurance(review, diff, assurance_id="real-assurance")
        gate = self._gate(diff, review, assurance, gate_id="real-gate")
        self.assertEqual(diff.state, "exact")
        self.assertTrue(diff.accepted)
        self.assertTrue(review.accepted)
        self.assertTrue(assurance.accepted)
        self.assertTrue(gate.accepted)
        self.assertTrue(gate.release_ready)

    def test_real_downloaded_packet_assurance_and_gate_persist_round_trip(self) -> None:
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
        assurance = self._assurance(review, diff, assurance_id="real-assurance")
        gate = self._gate(diff, review, assurance, gate_id="real-gate")
        with tempfile.TemporaryDirectory() as root:
            assurance_destination = Path(root) / "assurance"
            gate_destination = Path(root) / "gate"
            packet_assurance.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance, assurance_destination
            )
            packet_gate.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                gate, gate_destination
            )
            self.assertEqual(
                packet_assurance.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                    assurance_destination
                ).content_address,
                assurance.content_address,
            )
            self.assertEqual(
                packet_gate.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                    gate_destination
                ).content_address,
                gate.content_address,
            )

    def test_assurance_and_gate_document_projections_are_replayable(self) -> None:
        assurance = self._assurance(diff=self._diff())
        gate = self._gate()
        for value, module, verifier in (
            (assurance, packet_assurance, module_assurance_verify),
            (gate, packet_gate, module_gate_verify),
        ):
            document = value.to_dict()
            self.assertEqual(
                canonical_json(document), canonical_json(json.loads(canonical_json(document)))
            )
            self.assertTrue(verifier(value).accepted)
            self.assertIn(
                value.content_address,
                module.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_json(
                    value
                )
                if module is packet_assurance
                else module.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_json(
                    value
                ),
            )

    def test_assurance_check_receipt_is_public_and_addressed(self) -> None:
        assurance = self._assurance(diff=self._diff())
        verification = module_assurance_verify(assurance)
        for check in verification.checks:
            self.assertIn(":", check.content_address)
            encoded = canonical_json(check.to_dict()).casefold()
            for forbidden in ("agent", "language", "model", "user", "path", "timestamp"):
                self.assertNotIn(forbidden, encoded)

    def test_gate_check_receipt_is_public_and_addressed(self) -> None:
        gate = self._gate()
        verification = module_gate_verify(gate)
        for check in verification.checks:
            self.assertIn(":", check.content_address)
            encoded = canonical_json(check.to_dict()).casefold()
            for forbidden in ("agent", "language", "model", "user", "path", "timestamp"):
                self.assertNotIn(forbidden, encoded)

    def test_assurance_verification_receipt_address_changes_after_value_mutation(self) -> None:
        assurance = self._assurance()
        first = module_assurance_verify(assurance)
        assurance.review_release_ready = False
        second = module_assurance_verify(assurance)
        self.assertNotEqual(first.content_address, second.content_address)
        self.assertFalse(second.accepted)

    def test_gate_verification_receipt_address_changes_after_value_mutation(self) -> None:
        gate = self._gate()
        first = module_gate_verify(gate)
        gate.review_state = "held"
        second = module_gate_verify(gate)
        self.assertNotEqual(first.content_address, second.content_address)
        self.assertFalse(second.accepted)

    def test_assurance_finding_and_check_counts_are_conserved_in_every_projection(self) -> None:
        assurance = self._assurance(diff=self._diff())
        verification = module_assurance_verify(assurance)
        self.assertEqual(assurance.finding_count, len(assurance.to_dict()["findings"]))
        self.assertEqual(verification.check_count, len(verification.to_dict()["checks"]))
        self.assertEqual(
            verification.passed_count + verification.failed_count, verification.check_count
        )

    def test_gate_check_counts_are_conserved_in_every_projection(self) -> None:
        gate = self._gate()
        verification = module_gate_verify(gate)
        self.assertEqual(gate.check_count, len(gate.to_dict()["checks"]))
        self.assertEqual(verification.check_count, len(verification.to_dict()["checks"]))
        self.assertEqual(
            verification.passed_count + verification.failed_count, verification.check_count
        )

    def test_assurance_queries_are_case_insensitive_for_text(self) -> None:
        assurance = self._assurance(diff=self._diff())
        lower = packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
            assurance, text="supplied packet"
        )
        upper = packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
            assurance, text="SUPPLIED PACKET"
        )
        self.assertEqual(lower["total"], upper["total"])
        self.assertEqual(
            [item["kind"] for item in lower["items"]], [item["kind"] for item in upper["items"]]
        )

    def test_gate_queries_are_case_insensitive_for_text(self) -> None:
        gate = self._gate()
        lower = packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
            gate, text="verified packet transition"
        )
        upper = packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
            gate, text="VERIFIED PACKET TRANSITION"
        )
        self.assertEqual(lower["total"], upper["total"])
        self.assertEqual(
            [item["kind"] for item in lower["items"]], [item["kind"] for item in upper["items"]]
        )

    def test_assurance_query_preserves_requested_offset_and_limit(self) -> None:
        result = packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
            self._assurance(), offset=2, limit=4
        )
        self.assertEqual(result["offset"], 2)
        self.assertEqual(result["limit"], 4)
        self.assertEqual(len(result["items"]), 3)

    def test_gate_query_preserves_requested_offset_and_limit(self) -> None:
        result = packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
            self._gate(), offset=2, limit=4
        )
        self.assertEqual(result["offset"], 2)
        self.assertEqual(result["limit"], 4)
        self.assertEqual(len(result["items"]), 4)

    def test_assurance_query_checks_are_recomputed_from_the_assurance_value(self) -> None:
        assurance = self._assurance()
        result = packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
            assurance, resource="checks"
        )
        self.assertEqual(result["items"][0]["kind"], "aggregate-address")
        self.assertEqual(result["items"][-1]["kind"], "public-boundary")

    def test_gate_query_checks_are_recomputed_from_the_gate_value(self) -> None:
        gate = self._gate()
        result = packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
            gate, resource="checks"
        )
        self.assertEqual(result["items"][0]["kind"], "diff-link")
        self.assertEqual(result["items"][-1]["kind"], "public-boundary")

    def test_assurance_query_summary_contains_assurance_address(self) -> None:
        assurance = self._assurance()
        result = packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
            assurance, resource="summary"
        )
        self.assertEqual(result["assurance"]["content_address"], assurance.content_address)
        self.assertEqual(result["items"][0]["content_address"], assurance.content_address)

    def test_gate_query_summary_contains_gate_address(self) -> None:
        gate = self._gate()
        result = packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
            gate, resource="summary"
        )
        self.assertEqual(result["gate"]["content_address"], gate.content_address)
        self.assertEqual(result["items"][0]["content_address"], gate.content_address)

    def test_assurance_query_filter_metadata_is_explicitly_null_when_unset(self) -> None:
        result = packet_assurance.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
            self._assurance()
        )
        self.assertEqual(result["query"]["severity"], None)
        self.assertEqual(result["query"]["passed"], None)
        self.assertEqual(result["query"]["kind"], None)
        self.assertEqual(result["query"]["text"], None)

    def test_gate_query_filter_metadata_is_explicitly_null_when_unset(self) -> None:
        result = packet_gate.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
            self._gate()
        )
        self.assertEqual(result["query"]["kind"], None)
        self.assertEqual(result["query"]["passed"], None)
        self.assertEqual(result["query"]["text"], None)

    def test_assurance_verifier_rejects_an_untyped_value(self) -> None:
        with self.assertRaises(ValidationError):
            module_assurance_verify(SimpleNamespace())

    def test_gate_verifier_rejects_an_untyped_value(self) -> None:
        with self.assertRaises(ValidationError):
            module_gate_verify(SimpleNamespace())

    def test_assurance_query_verifier_rejects_an_unaddressed_mapping(self) -> None:
        with self.assertRaises(ValidationError):
            packet_assurance.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_query(
                {}
            )

    def test_gate_query_verifier_rejects_an_unaddressed_mapping(self) -> None:
        with self.assertRaises(ValidationError):
            packet_gate.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_query(
                {}
            )

    def test_assurance_and_gate_ids_are_bounded(self) -> None:
        with self.assertRaises(ValidationError):
            self._assurance(assurance_id="x" * 257)
        with self.assertRaises(ValidationError):
            self._gate(gate_id="x" * 257)

    def test_assurance_and_gate_details_are_not_required_for_default_decisions(self) -> None:
        assurance = self._assurance()
        gate = self._gate()
        self.assertTrue(assurance.accepted)
        self.assertTrue(gate.accepted)

    def test_explicit_decision_details_are_carried_into_review_evidence(self) -> None:
        diff = self._diff(
            right=self._packet(
                self._catalog(self._store("held", state="held", release_ready=False)),
                packet_id="held-right",
            )
        )
        review = self._review(diff, decision="hold", detail="manual evidence review")
        self.assertEqual(review.entries[0].detail, "manual evidence review")
        assurance = self._assurance(review, diff)
        self.assertTrue(any("review" in item.detail for item in assurance.findings))

    def test_gate_summary_reports_component_acceptance_independently(self) -> None:
        gate = self._gate()
        self.assertTrue(gate.diff_accepted)
        self.assertTrue(gate.review_accepted)
        self.assertTrue(gate.assurance_accepted)
        self.assertEqual(
            gate.accepted, all((gate.diff_accepted, gate.review_accepted, gate.assurance_accepted))
        )

    def test_gate_hold_summary_reports_accepted_nonready_evidence(self) -> None:
        diff = self._diff(
            right=self._packet(
                self._catalog(self._store("held", state="held", release_ready=False)),
                packet_id="held-right",
            )
        )
        review = self._review(diff, decision="hold", detail="manual hold")
        assurance = self._assurance(review, diff)
        gate = self._gate(diff, review, assurance)
        summary = gate.summary()
        self.assertTrue(summary["accepted"])
        self.assertFalse(summary["release_ready"])
        self.assertEqual(summary["state"], "held")

    def test_gate_block_summary_reports_rejected_evidence_without_losing_reason(self) -> None:
        diff = self._diff(
            right=self._packet(
                self._catalog(
                    self._store("blocked", state="blocked", release_ready=False, accepted=False)
                ),
                packet_id="blocked-right",
            )
        )
        review = self._review(diff, decision="block", detail="manual block")
        assurance = self._assurance(review, diff)
        gate = self._gate(diff, review, assurance)
        self.assertFalse(gate.summary()["accepted"])
        self.assertEqual(gate.summary()["state"], "blocked")
        self.assertGreater(gate.summary()["failed_count"], 0)
