"""Deep contracts for independent review-decision assurance and gating."""

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
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_decision_ledger_assurance as assurance,
)
from glio_noncode import (
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_decision_ledger as decision_model,
)
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_bytes, canonical_json
from tests.test_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_decision_ledger import (
    DecisionFixture,
)


class AssuranceFixture(DecisionFixture):
    def build_ready_assurance_gate(self):
        return assurance.build_decision_assurance_gate(self.build_ready_ledger())

    def build_held_assurance_gate(self):
        return assurance.build_decision_assurance_gate(self.build_held_ledger())

    def build_blocked_assurance_gate(self):
        return assurance.build_decision_assurance_gate(self.build_blocked_ledger())

    def write_assurance_gate(self, value, destination, **kwargs):
        return assurance.write_decision_assurance_gate(value, destination, **kwargs)


class AssuranceCoreTests(AssuranceFixture):
    def test_ready_ledger_has_independent_warning_free_assurance_and_promote_gate(self):
        value = self.build_ready_assurance_gate()
        self.assertEqual(value.assurance.finding_count, 12)
        self.assertEqual(value.assurance.passed_count, 12)
        self.assertEqual(value.assurance.warning_count, 0)
        self.assertEqual(value.assurance.blocker_count, 0)
        self.assertEqual(value.assurance.state, "passed")
        self.assertTrue(value.assurance.accepted)
        self.assertTrue(value.assurance.release_ready)
        self.assertEqual(value.gate.check_count, 8)
        self.assertEqual(value.gate.passed_count, 8)
        self.assertEqual(value.gate.state, "promote")
        self.assertTrue(value.gate.accepted)
        self.assertTrue(value.gate.release_ready)

    def test_held_ledger_assurance_passes_but_gate_holds_source_readiness(self):
        value = self.build_held_assurance_gate()
        self.assertEqual(value.assurance.state, "passed")
        self.assertTrue(value.assurance.accepted)
        self.assertTrue(value.assurance.release_ready)
        self.assertEqual(value.gate.state, "hold")
        self.assertTrue(value.gate.accepted)
        self.assertFalse(value.gate.release_ready)
        self.assertGreater(value.gate.warning_count, 0)
        failed = assurance.query_decision_assurance(value, resource="checks", passed=False, limit=32)
        self.assertGreater(failed.total_count, 0)
        self.assertTrue(all(not item["passed"] for item in failed.items))

    def test_blocked_ledger_is_blocked_by_independent_assurance(self):
        value = self.build_blocked_assurance_gate()
        self.assertEqual(value.assurance.state, "blocked")
        self.assertEqual(value.assurance.blocker_count, 1)
        self.assertFalse(value.assurance.accepted)
        self.assertEqual(value.gate.state, "block")
        self.assertFalse(value.gate.accepted)
        self.assertFalse(value.gate.release_ready)
        blockers = assurance.query_decision_assurance(value, resource="blockers", limit=32)
        self.assertEqual(blockers.total_count, 1)
        self.assertEqual(blockers.items[0]["kind"], "state-replay")

    def test_assurance_and_gate_addresses_are_deterministic(self):
        first = self.build_ready_assurance_gate()
        second = self.build_ready_assurance_gate()
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(assurance.address_decision_assurance(first.assurance), first.assurance.content_address)
        self.assertEqual(assurance.address_decision_gate(first.gate), first.gate.content_address)
        self.assertEqual(assurance.address_decision_assurance_gate(first), first.content_address)

    def test_assurance_projection_is_public_and_path_free(self):
        value = self.build_ready_assurance_gate()
        payload = canonical_json(value.to_dict()).casefold()
        self.assertNotIn("source_path", payload)
        self.assertNotIn(str(self.real_packet()).casefold(), payload)
        for forbidden in ("agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"):
            self.assertNotIn(f'"{forbidden}"', payload)

    def test_assurance_gate_keeps_source_queue_authoritative_after_adjudication(self):
        ledger_value = self.build_held_ledger()
        adjudicated = self.close_all_open(ledger_value)
        value = assurance.build_decision_assurance_gate(adjudicated)
        self.assertEqual(adjudicated.state, "closed")
        self.assertTrue(adjudicated.accepted)
        self.assertTrue(value.assurance.release_ready)
        self.assertEqual(value.gate.state, "hold")
        self.assertFalse(value.gate.release_ready)
        self.assertFalse(value.gate.source_queue_release_ready)

    def test_finding_and_check_addresses_recompute(self):
        value = self.build_ready_assurance_gate()
        self.assertTrue(all(assurance.address_assurance_finding(item) == item.content_address for item in value.assurance.findings))
        self.assertTrue(all(assurance.address_gate_check(item) == item.content_address for item in value.gate.checks))
        self.assertEqual(value.gate.assurance_address, value.assurance.content_address)
        self.assertEqual(value.gate.ledger_address, value.assurance.ledger_address)

    def test_mapping_round_trip_preserves_nested_assurance_gate(self):
        value = self.build_ready_assurance_gate()
        restored = assurance.decision_assurance_gate_from_mapping(value.to_dict())
        self.assertEqual(restored.to_dict(), value.to_dict())
        self.assertEqual(restored.content_address, value.content_address)
        self.assertEqual(assurance.decision_assurance_from_mapping(value.assurance.to_dict()).to_dict(), value.assurance.to_dict())
        self.assertEqual(assurance.decision_gate_from_mapping(value.gate.to_dict()).to_dict(), value.gate.to_dict())

    def test_mapping_rejects_unknown_fields_and_tampered_addresses(self):
        body = self.build_ready_assurance_gate().to_dict()
        body["private"] = True
        with self.assertRaises(ValidationError):
            assurance.decision_assurance_gate_from_mapping(body)
        body = self.build_ready_assurance_gate().to_dict()
        body["content_address"] = "bundle:tampered"
        with self.assertRaises(ValidationError):
            assurance.decision_assurance_gate_from_mapping(body)
        body = self.build_ready_assurance_gate().assurance.to_dict()
        body["findings"][0]["detail"] = "tampered"
        with self.assertRaises(ValidationError):
            assurance.decision_assurance_from_mapping(body)

    def test_gate_checks_distinguish_required_and_optional_failures(self):
        held = self.build_held_assurance_gate()
        self.assertTrue(all(check.required is False for check in held.gate.checks if not check.passed))
        blocked = self.build_blocked_assurance_gate()
        self.assertTrue(any(check.required and not check.passed for check in blocked.gate.checks))
        self.assertEqual(blocked.gate.state, "block")


class AssuranceQueryExportTests(AssuranceFixture):
    def test_summary_findings_checks_and_failed_resources(self):
        value = self.build_blocked_assurance_gate()
        summary = assurance.query_decision_assurance(value)
        self.assertEqual(summary.total_count, 1)
        self.assertEqual(summary.items[0]["gate_state"], "block")
        findings = assurance.query_decision_assurance(value, resource="findings", limit=32)
        self.assertEqual(findings.total_count, 12)
        checks = assurance.query_decision_assurance(value, resource="checks", limit=32)
        self.assertEqual(checks.total_count, 8)
        failed = assurance.query_decision_assurance(value, resource="failed", limit=32)
        self.assertEqual(failed.total_count, 1)
        self.assertFalse(failed.items[0]["passed"])

    def test_query_filters_and_pagination_are_deterministic(self):
        value = self.build_held_assurance_gate()
        checks = assurance.query_decision_assurance(value, resource="checks", required=False, offset=1, limit=2)
        self.assertEqual(checks.total_count, 4)
        self.assertEqual(checks.returned_count, 2)
        self.assertEqual(checks.items[0]["ordinal"], 3)
        text = assurance.query_decision_assurance(value, resource="checks", text="SOURCE QUEUE", limit=32)
        self.assertGreaterEqual(text.total_count, 1)
        with self.assertRaises(ValidationError):
            assurance.AssuranceQuery(resource="findings", offset=4090, limit=10)
        with self.assertRaises(ValidationError):
            assurance.query_decision_assurance(value, assurance.AssuranceQuery(resource="findings"), limit=2)

    def test_json_csv_and_markdown_exports(self):
        value = self.build_ready_assurance_gate()
        self.assertEqual(assurance.assurance_json(value.assurance), canonical_json(value.assurance.to_dict()))
        self.assertEqual(assurance.gate_json(value.gate), canonical_json(value.gate.to_dict()))
        self.assertEqual(assurance.assurance_gate_json(value), canonical_json(value.to_dict()))
        result = assurance.query_decision_assurance(value, resource="checks", limit=32)
        self.assertEqual(assurance.query_json(result), canonical_json(result.to_dict()))
        finding_rows = list(csv.DictReader(StringIO(assurance.assurance_csv(value.assurance))))
        self.assertEqual(len(finding_rows), 12)
        self.assertEqual(list(finding_rows[0]), ["ordinal", "finding_id", "plane", "kind", "severity", "required", "passed", "detail", "remediation", "evidence_address", "content_address"])
        check_rows = list(csv.DictReader(StringIO(assurance.gate_csv(value.gate))))
        self.assertEqual(len(check_rows), 8)
        self.assertIn("# Federation Review Decision Assurance", assurance.render_assurance_markdown(value.assurance))
        self.assertIn("# Federation Review Decision Release Gate", assurance.render_gate_markdown(value.gate))
        self.assertIn("# Federation Review Decision Assurance Gate", assurance.render_assurance_gate_markdown(value))
        self.assertIn("# Federation Review Decision Assurance Query", assurance.render_query_markdown(result))

    def test_empty_query_is_explicit(self):
        value = self.build_ready_assurance_gate()
        result = assurance.query_decision_assurance(value, resource="failed", limit=32)
        self.assertEqual(result.total_count, 0)
        self.assertIn("No records.", assurance.render_query_markdown(result))
        self.assertEqual(assurance.query_csv(result), "")

    def test_schemas_and_capabilities_are_versioned(self):
        for schema in (assurance.assurance_schema(), assurance.gate_schema(), assurance.assurance_gate_schema()):
            self.assertEqual(schema["type"], "object")
            self.assertFalse(schema["additionalProperties"])
            self.assertIn(assurance.VERSION, json.dumps(schema))
        query_schema = assurance.query_schema()
        self.assertIn("failed", json.dumps(query_schema))
        capabilities = assurance.capabilities()
        self.assertEqual(capabilities["version"], assurance.VERSION)
        self.assertEqual(capabilities["assurance"]["findings"], 12)
        self.assertEqual(capabilities["gate"]["checks"], 8)
        self.assertTrue(capabilities["gate"]["source_queue_authoritative"])
        self.assertTrue(capabilities["persistence"]["atomic_write"])


class AssuranceDiffTests(AssuranceFixture):
    def test_identical_snapshots_are_unchanged_and_address_stable(self):
        baseline = self.build_ready_assurance_gate()
        candidate = self.build_ready_assurance_gate()
        value = assurance.build_decision_assurance_diff(baseline, candidate)
        repeat = assurance.build_decision_assurance_diff(baseline, candidate)
        self.assertEqual(value.to_dict(), repeat.to_dict())
        self.assertEqual(value.content_address, repeat.content_address)
        self.assertEqual(value.item_count, 20)
        self.assertEqual(value.unchanged_count, 20)
        self.assertEqual(value.changed_count, 0)
        self.assertEqual(value.improved_count, 0)
        self.assertEqual(value.regressed_count, 0)
        self.assertEqual(value.state, "unchanged")
        self.assertTrue(all(item.action == "unchanged" for item in value.items))
        self.assertEqual(assurance.address_decision_assurance_diff(value), value.content_address)
        self.assertEqual(assurance.verify_decision_assurance_diff(value).content_address, value.content_address)

    def test_held_to_ready_snapshot_is_classified_as_improved(self):
        value = assurance.build_decision_assurance_diff(self.build_held_assurance_gate(), self.build_ready_assurance_gate())
        self.assertEqual(value.item_count, 20)
        self.assertGreater(value.changed_count, 0)
        self.assertGreater(value.improved_count, 0)
        self.assertEqual(value.regressed_count, 0)
        self.assertEqual(value.state, "improved")
        improved = assurance.query_decision_assurance_diff(value, resource="improved", limit=32)
        self.assertEqual(improved.total_count, value.improved_count)
        self.assertTrue(all(item["candidate_passed"] or item["candidate_required"] is False for item in improved.items))
        actions = assurance.query_decision_assurance_diff(value, resource="actions", action="changed", limit=32)
        self.assertEqual(actions.total_count, value.changed_count)

    def test_ready_to_blocked_snapshot_is_classified_as_regressed(self):
        value = assurance.build_decision_assurance_diff(self.build_ready_assurance_gate(), self.build_blocked_assurance_gate())
        self.assertGreater(value.changed_count, 0)
        self.assertGreater(value.regressed_count, 0)
        self.assertEqual(value.improved_count, 0)
        self.assertEqual(value.state, "regressed")
        blockers = assurance.query_decision_assurance_diff(value, resource="regressed", plane="ledger", limit=32)
        self.assertGreaterEqual(blockers.total_count, 1)
        self.assertTrue(all(item["plane"] == "ledger" for item in blockers.items))

    def test_diff_records_are_sorted_and_preserve_snapshot_linkage(self):
        baseline = self.build_held_assurance_gate()
        candidate = self.build_ready_assurance_gate()
        value = assurance.build_decision_assurance_diff(baseline, candidate, diff_id="diff:ordered")
        self.assertEqual([item.ordinal for item in value.items], list(range(value.item_count)))
        self.assertEqual([item.key for item in value.items], sorted(item.key for item in value.items))
        self.assertEqual(value.diff_id, "diff:ordered")
        self.assertEqual(value.baseline_address, baseline.content_address)
        self.assertEqual(value.candidate_address, candidate.content_address)
        self.assertEqual(value.baseline_ledger_address, baseline.gate.ledger_address)
        self.assertEqual(value.candidate_ledger_address, candidate.gate.ledger_address)

    def test_diff_mapping_rejects_unknown_fields_and_tampered_item(self):
        value = assurance.build_decision_assurance_diff(self.build_held_assurance_gate(), self.build_ready_assurance_gate())
        body = value.to_dict()
        body["private"] = True
        with self.assertRaises(ValidationError):
            assurance.decision_assurance_diff_from_mapping(body)
        body = value.to_dict()
        body["items"][0]["detail"] = "tampered"
        with self.assertRaises(ValidationError):
            assurance.decision_assurance_diff_from_mapping(body)
        item = value.items[0].to_dict()
        item["private"] = True
        with self.assertRaises(ValidationError):
            assurance.decision_assurance_diff_item_from_mapping(item)

    def test_diff_item_rules_reject_missing_snapshot_addresses(self):
        common = {"ordinal": 0, "key": "assurance:ledger:ledger-address", "plane": "ledger", "kind": "ledger-address", "baseline_severity": None, "candidate_severity": "pass", "baseline_required": None, "candidate_required": True, "baseline_passed": None, "candidate_passed": True, "baseline_address": None, "candidate_address": "finding:present", "detail": "added", "content_address": "pending:item"}
        with self.assertRaises(ValidationError):
            assurance.DecisionAssuranceDiffItem(**common, action="removed")
        with self.assertRaises(ValidationError):
            assurance.DecisionAssuranceDiffItem(**{**common, "candidate_address": None}, action="added")
        with self.assertRaises(ValidationError):
            assurance.DecisionAssuranceDiffItem(**{**common, "candidate_address": None}, action="changed")

    def test_diff_queries_filter_text_and_paginate(self):
        value = assurance.build_decision_assurance_diff(self.build_held_assurance_gate(), self.build_ready_assurance_gate())
        query = assurance.AssuranceDiffQuery(resource="changed", plane="policy", text="source", offset=0, limit=2)
        result = assurance.query_decision_assurance_diff(value, query)
        self.assertLessEqual(result.returned_count, 2)
        self.assertEqual(result.query.to_dict(), query.to_dict())
        self.assertTrue(all(item["plane"] == "policy" and "source" in assurance.canonical_json(item).casefold() for item in result.items))
        with self.assertRaises(ValidationError):
            assurance.AssuranceDiffQuery(resource="not-a-resource")
        with self.assertRaises(ValidationError):
            assurance.AssuranceDiffQuery(resource="changed", offset=4090, limit=10)
        with self.assertRaises(ValidationError):
            assurance.query_decision_assurance_diff(value, query, limit=1)

    def test_diff_exports_include_summary_schema_and_contracts(self):
        value = assurance.build_decision_assurance_diff(self.build_held_assurance_gate(), self.build_ready_assurance_gate())
        self.assertEqual(assurance.decision_assurance_diff_json(value), canonical_json(value.to_dict()))
        rows = list(csv.DictReader(StringIO(assurance.decision_assurance_diff_csv(value))))
        self.assertEqual(len(rows), value.item_count)
        result = assurance.query_decision_assurance_diff(value, resource="changed", limit=4)
        self.assertEqual(assurance.decision_assurance_diff_query_json(result), canonical_json(result.to_dict()))
        if result.items:
            query_rows = list(csv.DictReader(StringIO(assurance.decision_assurance_diff_query_csv(result))))
            self.assertEqual(len(query_rows), result.returned_count)
        self.assertIn("# Federation Review Decision Assurance Diff", assurance.render_decision_assurance_diff_markdown(value))
        self.assertIn("# Federation Review Decision Assurance Diff Query", assurance.render_decision_assurance_diff_query_markdown(result))
        schema = assurance.decision_assurance_diff_schema()
        self.assertFalse(schema["additionalProperties"])
        self.assertIn(assurance.VERSION, json.dumps(schema))
        self.assertIn("regressed", json.dumps(assurance.decision_assurance_diff_query_schema()))
        capabilities = assurance.capabilities()
        self.assertIn("diff", capabilities)
        self.assertEqual(capabilities["diff"]["maximum_items"], assurance.MAX_DIFF_ITEMS)
        self.assertIn("persistence_files", capabilities["diff"])


class AssuranceDiffPersistenceTests(AssuranceFixture):
    def write_diff(self, value, destination, **kwargs):
        return assurance.write_decision_assurance_diff(value, destination, **kwargs)

    def test_diff_persistence_has_exact_two_files_and_round_trips(self):
        value = assurance.build_decision_assurance_diff(self.build_held_assurance_gate(), self.build_ready_assurance_gate())
        with tempfile.TemporaryDirectory() as root_text:
            destination = self.write_diff(value, Path(root_text) / "diff")
            self.assertEqual({item.name for item in destination.iterdir()}, {"manifest.json", "diff.json"})
            loaded = assurance.load_decision_assurance_diff(destination)
            self.assertEqual(loaded.to_dict(), value.to_dict())
            self.assertEqual(loaded.content_address, value.content_address)

    def test_diff_persistence_bytes_are_repeatable_and_manifest_is_linked(self):
        value = assurance.build_decision_assurance_diff(self.build_held_assurance_gate(), self.build_ready_assurance_gate())
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            first = self.write_diff(value, root / "first")
            second = self.write_diff(value, root / "second")
            self.assertEqual({path.name: path.read_bytes() for path in first.iterdir()}, {path.name: path.read_bytes() for path in second.iterdir()})
            manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["artifact_count"], 1)
            self.assertEqual(manifest["files"], ["manifest.json", "diff.json"])
            self.assertEqual(manifest["diff_id"], value.diff_id)
            self.assertEqual(manifest["baseline_address"], value.baseline_address)
            self.assertEqual(manifest["candidate_address"], value.candidate_address)
            self.assertEqual(manifest["manifest_address"], assurance._diff_manifest_address({**manifest, "manifest_address": None}))

    def test_diff_persistence_rejects_missing_extra_noncanonical_and_tampered_files(self):
        value = assurance.build_decision_assurance_diff(self.build_held_assurance_gate(), self.build_ready_assurance_gate())
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            missing = self.write_diff(value, root / "missing")
            (missing / "diff.json").unlink()
            with self.assertRaises(ValidationError):
                assurance.load_decision_assurance_diff(missing)
            extra = self.write_diff(value, root / "extra")
            (extra / "extra.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                assurance.load_decision_assurance_diff(extra)
            noncanonical = self.write_diff(value, root / "noncanonical")
            manifest = json.loads((noncanonical / "manifest.json").read_text(encoding="utf-8"))
            (noncanonical / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            with self.assertRaises(ValidationError):
                assurance.load_decision_assurance_diff(noncanonical)
            tampered = self.write_diff(value, root / "tampered")
            body = json.loads((tampered / "diff.json").read_text(encoding="utf-8"))
            body["state"] = "blocked"
            (tampered / "diff.json").write_bytes(canonical_bytes(body))
            with self.assertRaises(ValidationError):
                assurance.load_decision_assurance_diff(tampered)

    def test_diff_persistence_rejects_manifest_address_and_symlink_tampering(self):
        value = assurance.build_decision_assurance_diff(self.build_held_assurance_gate(), self.build_ready_assurance_gate())
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            manifest_dir = self.write_diff(value, root / "manifest")
            manifest = json.loads((manifest_dir / "manifest.json").read_text(encoding="utf-8"))
            manifest["manifest_address"] = "manifest:tampered"
            (manifest_dir / "manifest.json").write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                assurance.load_decision_assurance_diff(manifest_dir)
            symlink_dir = self.write_diff(value, root / "symlink")
            source = root / "diff-source.json"
            source.write_bytes((symlink_dir / "diff.json").read_bytes())
            (symlink_dir / "diff.json").unlink()
            try:
                (symlink_dir / "diff.json").symlink_to(source)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable in this environment")
            with self.assertRaises(ValidationError):
                assurance.load_decision_assurance_diff(symlink_dir)
            alias = root / "alias"
            try:
                alias.symlink_to(symlink_dir, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks unavailable in this environment")
            with self.assertRaises(ValidationError):
                assurance.load_decision_assurance_diff(alias)

    def test_diff_persistence_overwrite_guard_and_input_validation(self):
        value = assurance.build_decision_assurance_diff(self.build_held_assurance_gate(), self.build_ready_assurance_gate())
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            destination = self.write_diff(value, root / "diff")
            with self.assertRaises(ValidationError):
                self.write_diff(value, destination)
            replacement = assurance.build_decision_assurance_diff(self.build_ready_assurance_gate(), self.build_blocked_assurance_gate())
            self.write_diff(replacement, destination, overwrite=True)
            self.assertEqual(assurance.load_decision_assurance_diff(destination).to_dict(), replacement.to_dict())
            source = root / "file"
            source.write_text("not a directory", encoding="utf-8")
            with self.assertRaises(ValidationError):
                assurance.load_decision_assurance_diff(source)


class AssurancePersistenceTests(AssuranceFixture):
    def test_persistence_has_exact_three_files(self):
        with tempfile.TemporaryDirectory() as root_text:
            destination = self.write_assurance_gate(self.build_ready_assurance_gate(), Path(root_text) / "gate")
            self.assertEqual({item.name for item in destination.iterdir()}, {"manifest.json", "assurance.json", "gate.json"})

    def test_persistence_round_trip_is_exact(self):
        value = self.build_held_assurance_gate()
        with tempfile.TemporaryDirectory() as root_text:
            loaded = assurance.load_decision_assurance_gate(self.write_assurance_gate(value, Path(root_text) / "gate"))
            self.assertEqual(loaded.to_dict(), value.to_dict())
            self.assertEqual(loaded.content_address, value.content_address)

    def test_persistence_bytes_are_repeatable(self):
        value = self.build_ready_assurance_gate()
        with tempfile.TemporaryDirectory() as root_text:
            first = self.write_assurance_gate(value, Path(root_text) / "first")
            second = self.write_assurance_gate(value, Path(root_text) / "second")
            self.assertEqual({path.name: path.read_bytes() for path in first.iterdir()}, {path.name: path.read_bytes() for path in second.iterdir()})

    def test_manifest_contains_two_artifacts_and_nested_addresses(self):
        value = self.build_ready_assurance_gate()
        with tempfile.TemporaryDirectory() as root_text:
            destination = self.write_assurance_gate(value, Path(root_text) / "gate")
            manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["artifact_count"], 2)
            self.assertEqual(manifest["files"], ["manifest.json", "assurance.json", "gate.json"])
            self.assertEqual(manifest["ledger_id"], value.gate.ledger_id)
            self.assertEqual(manifest["ledger_address"], value.gate.ledger_address)
            self.assertEqual(manifest["assurance_address"], value.assurance.content_address)
            self.assertEqual(manifest["gate_address"], value.gate.content_address)
            self.assertEqual(manifest["manifest_address"], assurance._manifest_address({**manifest, "manifest_address": None}))

    def test_persistence_rejects_missing_or_extra_files(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            destination = self.write_assurance_gate(self.build_ready_assurance_gate(), root / "missing")
            (destination / "gate.json").unlink()
            with self.assertRaises(ValidationError):
                assurance.load_decision_assurance_gate(destination)
            destination = self.write_assurance_gate(self.build_ready_assurance_gate(), root / "extra")
            (destination / "extra.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                assurance.load_decision_assurance_gate(destination)

    def test_persistence_rejects_noncanonical_manifest_and_tampered_bytes(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            destination = self.write_assurance_gate(self.build_ready_assurance_gate(), root / "noncanonical")
            manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
            (destination / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            with self.assertRaises(ValidationError):
                assurance.load_decision_assurance_gate(destination)
            destination = self.write_assurance_gate(self.build_ready_assurance_gate(), root / "tampered")
            (destination / "assurance.json").write_bytes((destination / "assurance.json").read_bytes() + b" ")
            with self.assertRaises(ValidationError):
                assurance.load_decision_assurance_gate(destination)

    def test_persistence_rejects_tampered_nested_payload_and_manifest_address(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            destination = self.write_assurance_gate(self.build_ready_assurance_gate(), root / "payload")
            body = json.loads((destination / "gate.json").read_text(encoding="utf-8"))
            body["state"] = "block"
            (destination / "gate.json").write_bytes(canonical_bytes(body))
            with self.assertRaises(ValidationError):
                assurance.load_decision_assurance_gate(destination)
            destination = self.write_assurance_gate(self.build_ready_assurance_gate(), root / "manifest")
            manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
            manifest["manifest_address"] = "manifest:tampered"
            (destination / "manifest.json").write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                assurance.load_decision_assurance_gate(destination)

    def test_persistence_rejects_symlinked_files_and_directory(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            destination = self.write_assurance_gate(self.build_ready_assurance_gate(), root / "gate")
            source = root / "gate-source.json"
            source.write_bytes((destination / "gate.json").read_bytes())
            (destination / "gate.json").unlink()
            try:
                (destination / "gate.json").symlink_to(source)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable in this environment")
            with self.assertRaises(ValidationError):
                assurance.load_decision_assurance_gate(destination)
            alias = root / "alias"
            try:
                alias.symlink_to(destination, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks unavailable in this environment")
            with self.assertRaises(ValidationError):
                assurance.load_decision_assurance_gate(alias)

    def test_persistence_overwrite_guard_and_replacement(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            destination = self.write_assurance_gate(self.build_ready_assurance_gate(), root / "gate")
            with self.assertRaises(ValidationError):
                self.write_assurance_gate(self.build_held_assurance_gate(), destination)
            replacement = self.build_held_assurance_gate()
            self.write_assurance_gate(replacement, destination, overwrite=True)
            self.assertEqual(assurance.load_decision_assurance_gate(destination).to_dict(), replacement.to_dict())

    def test_load_rejects_non_directory_input(self):
        with tempfile.TemporaryDirectory() as root_text:
            source = Path(root_text) / "file"
            source.write_text("not a directory", encoding="utf-8")
            with self.assertRaises(ValidationError):
                assurance.load_decision_assurance_gate(source)


class AssuranceCliTests(AssuranceFixture):
    base = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decisions-assurance"

    @staticmethod
    def run_cli_json(arguments):
        output = StringIO()
        with redirect_stdout(output):
            status = main(arguments)
        text = output.getvalue()
        return status, json.loads(text) if text.strip() else None, text

    def test_cli_assurance_gate_exports_and_verify(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            ledger_directory = self.write_ledger(self.build_ready_ledger(), root / "ledger")
            destination = root / "assurance-gate"
            status, payload, _ = self.run_cli_json([self.base, "--input", str(ledger_directory), "--destination", str(destination), "--format", "summary"])
            self.assertEqual(status, 0)
            self.assertEqual(payload["gate"]["state"], "promote")
            self.assertTrue(payload["gate"]["release_ready"])
            status, payload, _ = self.run_cli_json([self.base + "-verify", "--input", str(destination)])
            self.assertEqual(status, 0)
            self.assertTrue(payload["gate"]["accepted"])
            self.assertTrue(payload["assurance"]["accepted"])

    def test_cli_query_and_component_contract_commands(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            value = assurance.build_decision_assurance_gate(self.build_blocked_ledger())
            destination = self.write_assurance_gate(value, root / "gate")
            status, payload, _ = self.run_cli_json([self.base + "-query", "--input", str(destination), "--resource", "blockers", "--limit", "32"])
            self.assertEqual(status, 0)
            self.assertEqual(payload["total_count"], 1)
            for suffix in ("-schema", "-capabilities", "-assurance-schema", "-gate-schema", "-query-schema"):
                output_path = root / (suffix[1:] + ".json")
                self.assertEqual(main([self.base + suffix, "--output", str(output_path)]), 0)
                self.assertIsInstance(json.loads(output_path.read_text(encoding="utf-8")), dict)
            for output_format, marker in (("csv", "finding_id"), ("markdown", "# Federation Review Decision Assurance Query")):
                output = StringIO()
                with redirect_stdout(output):
                    status = main([self.base + "-query", "--input", str(destination), "--resource", "findings", "--limit", "2", "--format", output_format])
                self.assertEqual(status, 0)
                self.assertIn(marker, output.getvalue())

    def test_cli_diff_build_query_persist_verify_and_contract_commands(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            baseline = self.write_assurance_gate(self.build_held_assurance_gate(), root / "baseline")
            candidate = self.write_assurance_gate(self.build_ready_assurance_gate(), root / "candidate")
            expected = assurance.build_decision_assurance_diff(self.build_held_assurance_gate(), self.build_ready_assurance_gate())
            destination = root / "diff"
            status, payload, _ = self.run_cli_json([self.base + "-diff", "--baseline", str(baseline), "--candidate", str(candidate), "--destination", str(destination), "--format", "summary"])
            self.assertEqual(status, 0)
            self.assertEqual(payload["state"], "improved")
            self.assertGreater(payload["improved_count"], 0)
            status, payload, _ = self.run_cli_json([self.base + "-diff-verify", "--input", str(destination)])
            self.assertEqual(status, 0)
            self.assertEqual(payload["content_address"], expected.content_address)
            status, payload, _ = self.run_cli_json([self.base + "-diff-query", "--baseline", str(baseline), "--candidate", str(candidate), "--resource", "improved", "--limit", "32"])
            self.assertEqual(status, 0)
            self.assertGreater(payload["total_count"], 0)
            status, payload, _ = self.run_cli_json([self.base + "-diff-capabilities"])
            self.assertEqual(status, 0)
            self.assertIn("diff", payload)
            for suffix in ("-diff-schema", "-diff-query-schema", "-diff-query-capabilities"):
                output_path = root / (suffix[1:] + ".json")
                self.assertEqual(main([self.base + suffix, "--output", str(output_path)]), 0)
                self.assertIsInstance(json.loads(output_path.read_text(encoding="utf-8")), dict)
            output = StringIO()
            with redirect_stdout(output):
                status = main([self.base + "-diff-query", "--baseline", str(baseline), "--candidate", str(candidate), "--resource", "changed", "--limit", "2", "--format", "csv"])
            self.assertEqual(status, 0)
            self.assertIn("ordinal", output.getvalue())


class AssuranceApiTests(AssuranceFixture):
    base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decisions"

    def start_server(self, root: Path):
        server = create_server("127.0.0.1", 0, root / "api-data")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def test_api_assurance_gate_routes(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            ledger_directory = self.write_ledger(self.build_ready_ledger(), root / "ledger")
            gate_directory = self.write_assurance_gate(self.build_ready_assurance_gate(), root / "gate")
            server, thread = self.start_server(root)
            try:
                for suffix in ("/schema", "/capabilities", "/assurance-schema", "/gate-schema", "/query-schema"):
                    status, _, payload = self.http_json(server, self.base + suffix)
                    self.assertEqual(status, 200, suffix)
                    self.assertIsInstance(payload, dict)
                status, _, payload = self.http_json(server, self.base, {"input": str(ledger_directory), "format": "summary"})
                self.assertEqual(status, 200)
                self.assertEqual(payload["gate"]["state"], "promote")
                status, _, payload = self.http_json(server, self.base + "/verify", {"input": str(gate_directory)})
                self.assertEqual(status, 200)
                self.assertTrue(payload["gate"]["accepted"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_api_query_and_text_exports(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            gate_directory = self.write_assurance_gate(self.build_blocked_assurance_gate(), root / "gate")
            server, thread = self.start_server(root)
            try:
                status, _, payload = self.http_json(server, self.base + "/query", {"input": str(gate_directory), "resource": "failed", "limit": "32"})
                self.assertEqual(status, 200)
                self.assertEqual(payload["total_count"], 1)
                for output_format, marker in (("csv", "finding_id"), ("markdown", "# Federation Review Decision Assurance Query")):
                    status, content_type, body = self.http_text(server, self.base + "/query", {"input": str(gate_directory), "resource": "findings", "limit": "2", "format": output_format})
                    self.assertEqual(status, 200)
                    self.assertIn(marker, body)
                    self.assertTrue(content_type)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_api_diff_build_query_verify_and_contract_routes(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            baseline = self.write_assurance_gate(self.build_held_assurance_gate(), root / "baseline")
            candidate = self.write_assurance_gate(self.build_ready_assurance_gate(), root / "candidate")
            persisted = assurance.build_decision_assurance_diff(self.build_held_assurance_gate(), self.build_ready_assurance_gate())
            diff_directory = assurance.write_decision_assurance_diff(persisted, root / "diff")
            server, thread = self.start_server(root)
            try:
                diff_base = self.base + "/assurance-diff"
                status, _, payload = self.http_json(server, diff_base, {"baseline": str(baseline), "candidate": str(candidate), "format": "summary"})
                self.assertEqual(status, 200)
                self.assertEqual(payload["state"], "improved")
                status, _, payload = self.http_json(server, diff_base + "/query", {"baseline": str(baseline), "candidate": str(candidate), "resource": "improved", "limit": "32"})
                self.assertEqual(status, 200)
                self.assertGreater(payload["total_count"], 0)
                status, _, payload = self.http_json(server, diff_base + "/verify", {"input": str(diff_directory)})
                self.assertEqual(status, 200)
                self.assertEqual(payload["content_address"], persisted.content_address)
                status, _, payload = self.http_json(server, diff_base + "/capabilities")
                self.assertEqual(status, 200)
                self.assertIn("diff", payload)
                for suffix in ("/schema", "/query/schema"):
                    status, _, payload = self.http_json(server, diff_base + suffix)
                    self.assertEqual(status, 200, suffix)
                    self.assertIsInstance(payload, dict)
                status, content_type, body = self.http_text(server, diff_base + "/query", {"baseline": str(baseline), "candidate": str(candidate), "resource": "changed", "limit": "2", "format": "markdown"})
                self.assertEqual(status, 200)
                self.assertIn("# Federation Review Decision Assurance Diff Query", body)
                self.assertTrue(content_type)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


class AssuranceRealDataTests(AssuranceFixture):
    def test_downloaded_packet_can_reach_independent_decision_assurance(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            source_gate = self.build_real_gate(root / "real")
            queue = review_model.build_review_queue(source_gate, queue_id="queue:real-assurance")
            real_ledger = decision_model.build_decision_ledger(queue, ledger_id="ledger:real-assurance")
            self.assertTrue(source_gate.release_ready)
            value = assurance.build_decision_assurance_gate(real_ledger)
            destination = self.write_assurance_gate(value, root / "gate")
            loaded = assurance.load_decision_assurance_gate(destination)
            self.assertEqual(loaded.assurance.finding_count, 12)
            self.assertEqual(loaded.gate.check_count, 8)
            self.assertTrue(loaded.gate.release_ready)
            self.assertEqual(loaded.assurance.ledger_address, value.assurance.ledger_address)
            self.assertEqual(loaded.assurance.queue_address, queue.content_address)
            payload = canonical_json(loaded.to_dict()).casefold()
            self.assertNotIn(str(self.real_packet()).casefold(), payload)
            self.assertNotIn("source_path", payload)

    def test_two_real_downloaded_rebuilds_produce_an_unchanged_assurance_diff(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            source_one = self.build_real_gate(root / "real-one")
            source_two = self.build_real_gate(root / "real-two")
            queue_one = review_model.build_review_queue(source_one, queue_id="queue:real-diff-one")
            queue_two = review_model.build_review_queue(source_two, queue_id="queue:real-diff-two")
            ledger_one = decision_model.build_decision_ledger(queue_one, ledger_id="ledger:real-diff-one")
            ledger_two = decision_model.build_decision_ledger(queue_two, ledger_id="ledger:real-diff-two")
            baseline = assurance.build_decision_assurance_gate(ledger_one)
            candidate = assurance.build_decision_assurance_gate(ledger_two)
            value = assurance.build_decision_assurance_diff(baseline, candidate, diff_id="diff:real-download")
            self.assertEqual(value.item_count, 20)
            self.assertEqual(value.unchanged_count, 20)
            self.assertEqual(value.state, "unchanged")
            destination = assurance.write_decision_assurance_diff(value, root / "diff")
            loaded = assurance.load_decision_assurance_diff(destination)
            self.assertEqual(loaded.to_dict(), value.to_dict())
            payload = canonical_json(loaded.to_dict()).casefold()
            self.assertNotIn(str(self.real_packet()).casefold(), payload)
            self.assertNotIn("source_path", payload)


if __name__ == "__main__":
    unittest.main()
