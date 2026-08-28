"""Deep contracts for independent assurance of review decision ledgers."""

# ruff: noqa: E501, I001

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

from glio_noncode import assurance_history_series_release_registry_federation_gate_review as review
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance as assurance
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_bytes, canonical_json
from tests.test_assurance_history_series_release_registry_federation_gate_review import ReviewFixture


class AssuranceFixture(ReviewFixture):
    """Create current-format downloaded-style review ledgers."""

    def setUp(self):
        super().setUp()
        self.ready_ledger = review.build_decision_ledger(self.ready_review, ledger_id="ledger:assurance-ready")
        self.held_ledger = review.build_decision_ledger(self.held_review, ledger_id="ledger:assurance-held")
        self.blocked_ledger = review.build_decision_ledger(self.blocked_review, ledger_id="ledger:assurance-blocked")

    @staticmethod
    def build(value):
        return assurance.build_assurance_gate(value)

    @staticmethod
    def write_ledger(value, root: Path, name: str = "ledger") -> Path:
        target = root / name
        review.write_decision_ledger(value, target)
        return target

    @staticmethod
    def write_assurance(value, root: Path, name: str = "assurance") -> Path:
        target = root / name
        assurance.write_assurance_gate(value, target)
        return target

    @staticmethod
    def capture(argv):
        output = StringIO()
        with redirect_stdout(output):
            status = main(argv)
        return status, output.getvalue()

    @staticmethod
    def public_keys(value):
        if isinstance(value, dict):
            result = set(value)
            for nested in value.values():
                result.update(AssuranceFixture.public_keys(nested))
            return result
        if isinstance(value, (list, tuple)):
            result = set()
            for nested in value:
                result.update(AssuranceFixture.public_keys(nested))
            return result
        return set()

    def assert_public(self, value):
        payload = value.to_dict() if hasattr(value, "to_dict") else value
        self.assertFalse(self.public_keys(payload) & assurance._FORBIDDEN_KEYS)
        serialized = canonical_json(payload)
        self.assertNotIn("C:\\", serialized)
        self.assertNotIn("/Users/", serialized)


class AssuranceBuildTests(AssuranceFixture):
    def test_ready_ledger_is_fully_assured_and_promoted(self):
        value = self.build(self.ready_ledger)
        self.assertEqual(value.assurance.finding_count, 14)
        self.assertEqual(value.assurance.passed_count, 14)
        self.assertEqual(value.assurance.state, assurance.AssuranceState.PASSED.value)
        self.assertEqual(value.gate.check_count, 10)
        self.assertEqual(value.gate.state, assurance.GateState.PROMOTE.value)
        self.assertTrue(value.gate.release_ready)

    def test_held_source_is_accepted_but_not_promotable(self):
        value = self.build(self.held_ledger)
        self.assertTrue(value.assurance.accepted)
        self.assertTrue(value.assurance.release_ready)
        self.assertEqual(value.gate.state, assurance.GateState.HOLD.value)
        self.assertFalse(value.gate.release_ready)
        source_checks = [item for item in value.gate.checks if item.kind == "source-release-ready"]
        self.assertEqual(len(source_checks), 1)
        self.assertFalse(source_checks[0].passed)
        self.assertFalse(source_checks[0].required)

    def test_blocked_source_is_blocked_by_source_acceptance(self):
        value = self.build(self.blocked_ledger)
        self.assertEqual(value.gate.state, assurance.GateState.BLOCK.value)
        self.assertFalse(value.gate.accepted)
        self.assertFalse(value.gate.release_ready)
        self.assertTrue(any(not item.passed and item.required for item in value.gate.checks))

    def test_build_is_deterministic(self):
        first = self.build(self.ready_ledger)
        second = self.build(self.ready_ledger)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(assurance.address_assurance(first.assurance), first.assurance.content_address)
        self.assertEqual(assurance.address_gate(first.gate), first.gate.content_address)
        self.assertEqual(assurance.address_assurance_gate(first), first.content_address)

    def test_custom_ids_change_identity_but_not_contract(self):
        value = assurance.build_assurance_gate(self.ready_ledger, assurance_id="assurance:custom", gate_id="gate:custom")
        self.assertEqual(value.assurance.assurance_id, "assurance:custom")
        self.assertEqual(value.gate.gate_id, "gate:custom")
        self.assertNotEqual(value.assurance.content_address, self.build(self.ready_ledger).assurance.content_address)
        self.assertTrue(value.gate.release_ready)

    def test_all_findings_and_checks_are_addressed(self):
        value = self.build(self.ready_ledger)
        for item in value.assurance.findings:
            self.assertEqual(assurance.address_finding(item), item.content_address)
        for item in value.gate.checks:
            self.assertEqual(assurance.address_check(item), item.content_address)

    def test_assurance_and_gate_linkage_is_conserved(self):
        value = self.build(self.ready_ledger)
        self.assertEqual(value.gate.ledger_id, value.assurance.ledger_id)
        self.assertEqual(value.gate.ledger_address, value.assurance.ledger_address)
        self.assertEqual(value.gate.assurance_address, value.assurance.content_address)
        self.assertEqual(value.assurance.queue_address, self.ready_ledger.queue_address)

    def test_public_boundary_is_recursive(self):
        self.assert_public(self.build(self.ready_ledger))
        self.assert_public(self.build(self.held_ledger))
        self.assert_public(self.build(self.blocked_ledger))

    def test_capabilities_are_public_and_descriptive(self):
        value = assurance.capabilities()
        self.assertEqual(value["assurance"]["findings"], 14)
        self.assertEqual(value["gate"]["checks"], 10)
        self.assertTrue(value["gate"]["source_authoritative"])
        self.assertEqual(tuple(value["persistence"]["files"]), assurance.FILES)
        self.assert_public(value)

    def test_schema_surfaces_are_public(self):
        for builder in (assurance.assurance_schema, assurance.finding_schema, assurance.gate_schema, assurance.check_schema, assurance.assurance_gate_schema, assurance.query_schema, assurance.diff_schema, assurance.diff_item_schema, assurance.diff_query_schema):
            value = builder()
            self.assertIsInstance(value, dict)
            self.assertTrue(value["additionalProperties"] is False or builder is assurance.assurance_gate_schema)
            self.assert_public(value)

    def test_mapping_round_trip_for_bundle(self):
        value = self.build(self.ready_ledger)
        loaded = assurance.assurance_gate_from_mapping(value.to_dict())
        self.assertEqual(loaded.to_dict(), value.to_dict())

    def test_mapping_round_trip_for_findings_and_checks(self):
        value = self.build(self.ready_ledger)
        for item in value.assurance.findings:
            self.assertEqual(assurance.finding_from_mapping(item.to_dict()).to_dict(), item.to_dict())
        for item in value.gate.checks:
            self.assertEqual(assurance.check_from_mapping(item.to_dict()).to_dict(), item.to_dict())

    def test_verifiers_require_the_typed_boundary(self):
        for verifier in (assurance.verify_assurance, assurance.verify_gate, assurance.verify_assurance_gate, assurance.verify_diff):
            with self.assertRaises(ValidationError):
                verifier({})


class AssuranceRecomputationTests(AssuranceFixture):
    def test_tampered_ledger_address_becomes_required_finding(self):
        self.ready_ledger.content_address = "ledger:tampered"
        value = assurance.build_assurance_gate(self.ready_ledger)
        finding = next(item for item in value.assurance.findings if item.kind == "ledger-address")
        self.assertFalse(finding.passed)
        self.assertTrue(finding.required)
        self.assertEqual(value.gate.state, assurance.GateState.BLOCK.value)

    def test_tampered_item_address_is_detected(self):
        self.ready_ledger.items[0].content_address = "item:tampered"
        value = assurance.build_assurance_gate(self.ready_ledger)
        finding = next(item for item in value.assurance.findings if item.kind == "item-addresses")
        self.assertFalse(finding.passed)
        self.assertEqual(value.assurance.state, assurance.AssuranceState.BLOCKED.value)

    def test_tampered_entry_address_is_detected(self):
        item = self.failed_item(self.held_ledger)
        ledger = review.append_decision(self.held_ledger, item_id=item.item_id, action="acknowledge", rationale="start", expected_head_address=review.INITIAL_HEAD)
        ledger.entries[0].content_address = "decision:tampered"
        value = assurance.build_assurance_gate(ledger)
        finding = next(item for item in value.assurance.findings if item.kind == "entry-chain")
        self.assertFalse(finding.passed)
        self.assertTrue(finding.required)

    def test_tampered_action_counter_is_detected(self):
        self.ready_ledger.acknowledge_count = 1
        value = assurance.build_assurance_gate(self.ready_ledger)
        finding = next(item for item in value.assurance.findings if item.kind == "action-counters")
        self.assertFalse(finding.passed)

    def test_tampered_evidence_policy_is_detected(self):
        value = review.append_decision(self.held_ledger, item_id=self.failed_item(self.held_ledger).item_id, action="escalate", rationale="route", expected_head_address=review.INITIAL_HEAD)
        value.entries[0].evidence_address = "evidence:unexpected"
        assured = assurance.build_assurance_gate(value)
        finding = next(item for item in assured.assurance.findings if item.kind == "evidence-policy")
        self.assertFalse(finding.passed)

    def test_tampered_replay_counts_are_detected(self):
        self.ready_ledger.replay.clear_count = 0
        value = assurance.build_assurance_gate(self.ready_ledger)
        finding = next(item for item in value.assurance.findings if item.kind == "replay-projection")
        self.assertFalse(finding.passed)

    def test_tampered_source_authority_is_detected(self):
        self.ready_ledger.release_ready = False
        value = assurance.build_assurance_gate(self.ready_ledger)
        finding = next(item for item in value.assurance.findings if item.kind == "source-authority")
        self.assertFalse(finding.passed)

    def test_tampered_public_field_is_detected(self):
        self.ready_ledger.to_dict = lambda: {"private": "must-not-cross"}
        value = assurance.build_assurance_gate(self.ready_ledger)
        finding = next(item for item in value.assurance.findings if item.kind == "public-boundary")
        self.assertFalse(finding.passed)

    def test_tampered_replay_item_address_is_detected(self):
        self.ready_ledger.replay.items[0].content_address = "replay-item:tampered"
        value = assurance.build_assurance_gate(self.ready_ledger)
        finding = next(item for item in value.assurance.findings if item.kind == "replay-addresses")
        self.assertFalse(finding.passed)

    def test_transition_recomputation_accepts_valid_entry(self):
        item = self.failed_item(self.held_ledger)
        value = review.append_decision(self.held_ledger, item_id=item.item_id, action="remediate", rationale="evidence attached", evidence_address="evidence:one", expected_head_address=review.INITIAL_HEAD)
        assured = assurance.build_assurance_gate(value)
        finding = next(item for item in assured.assurance.findings if item.kind == "transition-policy")
        self.assertTrue(finding.passed)

    def test_transition_recomputation_rejects_invalid_sequence(self):
        item = self.failed_item(self.held_ledger)
        value = review.append_decision(self.held_ledger, item_id=item.item_id, action="acknowledge", rationale="start", expected_head_address=review.INITIAL_HEAD)
        value.entries[0].action = "remediate"
        assured = assurance.build_assurance_gate(value)
        finding = next(item for item in assured.assurance.findings if item.kind == "transition-policy")
        self.assertFalse(finding.passed)

    def test_independent_findings_do_not_use_source_verifier(self):
        original = review.verify_decision_ledger
        try:
            review.verify_decision_ledger = lambda value: (_ for _ in ()).throw(AssertionError("source verifier called"))
            value = assurance.build_assurance_gate(self.ready_ledger)
        finally:
            review.verify_decision_ledger = original
        self.assertTrue(value.gate.release_ready)

    def test_held_source_readiness_is_an_optional_assurance_warning_only_at_gate(self):
        value = self.build(self.held_ledger)
        self.assertFalse(any(not item.passed for item in value.assurance.findings))
        self.assertTrue(any(not item.passed and not item.required for item in value.gate.checks))


class AssuranceQueryTests(AssuranceFixture):
    def setUp(self):
        super().setUp()
        self.value = self.build(self.ready_ledger)

    def test_summary_query_includes_gate_projection(self):
        result = assurance.query_assurance(self.value, resource="summary")
        self.assertEqual(result.total_count, 1)
        self.assertEqual(result.items[0]["gate_state"], "promote")
        self.assertEqual(result.source_address, self.value.content_address)

    def test_each_assurance_resource_is_bounded(self):
        expected = {"findings": 14, "blockers": 0, "warnings": 0, "failed": 0, "checks": 10}
        for resource, count in expected.items():
            result = assurance.query_assurance(self.value, resource=resource, limit=4096)
            self.assertEqual(result.total_count, count)
            self.assertEqual(result.returned_count, count)

    def test_query_filters_by_plane_and_text(self):
        result = assurance.query_assurance(self.value, resource="findings", plane="replay", text="replay", limit=50)
        self.assertGreaterEqual(result.total_count, 1)
        self.assertTrue(all(item["plane"] == "replay" for item in result.items))
        self.assertTrue(all("replay" in canonical_json(item).casefold() for item in result.items))

    def test_query_filters_by_pass_state_and_required_flag(self):
        result = assurance.query_assurance(self.value, resource="findings", passed=True, required=True, limit=50)
        self.assertGreater(result.total_count, 0)
        self.assertTrue(all(item["passed"] and item["required"] for item in result.items))
        result = assurance.query_assurance(self.value, resource="checks", passed=True, required=True, limit=50)
        self.assertGreater(result.total_count, 0)

    def test_query_paginates(self):
        first = assurance.query_assurance(self.value, resource="findings", offset=0, limit=3)
        second = assurance.query_assurance(self.value, resource="findings", offset=3, limit=3)
        self.assertEqual(first.returned_count, 3)
        self.assertEqual(second.returned_count, 3)
        self.assertNotEqual(first.items, second.items)

    def test_query_rejects_bad_resource_and_window(self):
        with self.assertRaises(ValidationError):
            assurance.query_assurance(self.value, resource="bad")
        with self.assertRaises(ValidationError):
            assurance.query_assurance(self.value, resource="findings", offset=4090, limit=50)

    def test_query_object_and_kwargs_are_mutually_exclusive(self):
        query = assurance.AssuranceQuery(resource="findings")
        with self.assertRaises(ValidationError):
            assurance.query_assurance(self.value, query, resource="findings")

    def test_query_result_is_addressed_and_public(self):
        result = assurance.query_assurance(self.value, resource="findings")
        self.assert_public(result)
        self.assertIn(":", result.content_address)

    def test_query_serializers_are_stable(self):
        result = assurance.query_assurance(self.value, resource="findings", limit=2)
        self.assertEqual(json.loads(assurance.query_json(result)), result.to_dict())
        self.assertIn("finding_id", assurance.query_csv(result))
        self.assertIn("Release-Registry", assurance.render_query_markdown(result))


class AssurancePersistenceTests(AssuranceFixture):
    def test_bundle_writes_exact_three_files_and_reloads(self):
        value = self.build(self.ready_ledger)
        with tempfile.TemporaryDirectory() as temporary:
            target = self.write_assurance(value, Path(temporary))
            self.assertEqual(tuple(sorted(item.name for item in target.iterdir())), tuple(sorted(assurance.FILES)))
            loaded = assurance.load_assurance_gate(target)
            self.assertEqual(loaded.to_dict(), value.to_dict())
            self.assertEqual(assurance.load_assurance_gate(target).content_address, value.content_address)

    def test_bundle_manifest_is_canonical_and_addressed(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = self.write_assurance(self.build(self.ready_ledger), Path(temporary))
            raw = (target / assurance.MANIFEST_NAME).read_bytes()
            document = json.loads(raw)
            self.assertEqual(canonical_bytes(document), raw)
            self.assertEqual(document["artifact_count"], 2)
            self.assertEqual(tuple(document["files"]), assurance.FILES)
            self.assertIn("manifest_address", document)

    def test_bundle_rejects_extra_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = self.write_assurance(self.build(self.ready_ledger), Path(temporary))
            (target / "unexpected.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                assurance.load_assurance_gate(target)

    def test_bundle_rejects_noncanonical_assurance_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = self.write_assurance(self.build(self.ready_ledger), Path(temporary))
            path = target / assurance.ASSURANCE_NAME
            document = json.loads(path.read_text(encoding="utf-8"))
            path.write_text(json.dumps(document, indent=2), encoding="utf-8")
            with self.assertRaises(ValidationError):
                assurance.load_assurance_gate(target)

    def test_bundle_rejects_tampered_artifact_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = self.write_assurance(self.build(self.ready_ledger), Path(temporary))
            path = target / assurance.GATE_NAME
            document = json.loads(path.read_text(encoding="utf-8"))
            document["state"] = "hold"
            path.write_bytes(canonical_bytes(document))
            with self.assertRaises(ValidationError):
                assurance.load_assurance_gate(target)

    def test_bundle_rejects_manifest_linkage_tamper(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = self.write_assurance(self.build(self.ready_ledger), Path(temporary))
            path = target / assurance.MANIFEST_NAME
            document = json.loads(path.read_text(encoding="utf-8"))
            document["ledger_id"] = "ledger:wrong"
            document["manifest_address"] = assurance._manifest_address({**document, "manifest_address": None})
            path.write_bytes(canonical_bytes(document))
            with self.assertRaises(ValidationError):
                assurance.load_assurance_gate(target)

    def test_bundle_refuses_existing_destination_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = self.write_assurance(self.build(self.ready_ledger), Path(temporary))
            with self.assertRaises(ValidationError):
                assurance.write_assurance_gate(self.build(self.ready_ledger), target)

    def test_bundle_overwrite_is_explicit(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = self.write_assurance(self.build(self.ready_ledger), Path(temporary))
            next_value = self.build(self.held_ledger)
            assurance.write_assurance_gate(next_value, target, overwrite=True)
            self.assertEqual(assurance.load_assurance_gate(target).content_address, next_value.content_address)

    def test_symlink_bundle_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = self.write_assurance(self.build(self.ready_ledger), root, "target")
            link = root / "link"
            try:
                link.symlink_to(target, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks are unavailable")
            with self.assertRaises(ValidationError):
                assurance.load_assurance_gate(link)


class AssuranceDiffTests(AssuranceFixture):
    def test_diff_of_identical_snapshots_is_unchanged(self):
        value = self.build(self.ready_ledger)
        diff = assurance.build_diff(value, value)
        self.assertEqual(diff.state, assurance.DiffState.UNCHANGED.value)
        self.assertTrue(all(item.action == assurance.DiffAction.UNCHANGED.value for item in diff.items))
        self.assertEqual(diff.improved_count, 0)
        self.assertEqual(diff.regressed_count, 0)

    def test_diff_detects_source_readiness_change(self):
        baseline = self.build(self.ready_ledger)
        candidate = self.build(self.held_ledger)
        diff = assurance.build_diff(baseline, candidate)
        self.assertGreater(diff.changed_count, 0)
        self.assertIn(diff.state, tuple(item.value for item in assurance.DiffState))
        self.assertTrue(any(item.key == "gate:source:source-release-ready" for item in diff.items))

    def test_diff_records_are_addressed_and_mapped(self):
        diff = assurance.build_diff(self.build(self.ready_ledger), self.build(self.held_ledger))
        for item in diff.items:
            self.assertEqual(assurance.address_diff_item(item), item.content_address)
            self.assertEqual(assurance.diff_item_from_mapping(item.to_dict()).to_dict(), item.to_dict())
        self.assertEqual(assurance.diff_from_mapping(diff.to_dict()).to_dict(), diff.to_dict())

    def test_diff_queries_support_actions_and_outcomes(self):
        diff = assurance.build_diff(self.build(self.ready_ledger), self.build(self.held_ledger))
        for resource in assurance.DiffQuery.RESOURCES:
            result = assurance.query_diff(diff, resource=resource, limit=4096)
            self.assertLessEqual(result.returned_count, result.total_count)
        changed = assurance.query_diff(diff, resource="changed", limit=4096)
        self.assertEqual(changed.total_count, diff.changed_count)

    def test_diff_query_filters(self):
        diff = assurance.build_diff(self.build(self.ready_ledger), self.build(self.held_ledger))
        result = assurance.query_diff(diff, resource="actions", action="changed", plane="source", text="source", limit=50)
        self.assertTrue(all(item["action"] == "changed" and item["plane"] == "source" for item in result.items))

    def test_diff_serializers_are_stable(self):
        diff = assurance.build_diff(self.build(self.ready_ledger), self.build(self.held_ledger))
        self.assertEqual(json.loads(assurance.diff_json(diff)), diff.to_dict())
        self.assertIn("key", assurance.diff_csv(diff))
        self.assertIn("Assurance Diff", assurance.render_diff_markdown(diff))
        result = assurance.query_diff(diff, resource="changed")
        self.assertEqual(json.loads(assurance.diff_query_json(result)), result.to_dict())
        self.assertIn("Assurance Diff Query", assurance.render_diff_query_markdown(result))

    def test_diff_rejects_invalid_mapping(self):
        diff = assurance.build_diff(self.build(self.ready_ledger), self.build(self.held_ledger))
        document = diff.to_dict()
        document["state"] = "invalid"
        with self.assertRaises(ValidationError):
            assurance.diff_from_mapping(document)

    def test_diff_writes_exact_two_files_and_reloads(self):
        diff = assurance.build_diff(self.build(self.ready_ledger), self.build(self.held_ledger))
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "diff"
            assurance.write_diff(diff, target)
            self.assertEqual(tuple(sorted(item.name for item in target.iterdir())), tuple(sorted(assurance.DIFF_FILES)))
            self.assertEqual(assurance.load_diff(target).to_dict(), diff.to_dict())

    def test_diff_rejects_tampered_manifest_and_artifact(self):
        diff = assurance.build_diff(self.build(self.ready_ledger), self.build(self.held_ledger))
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "diff"
            assurance.write_diff(diff, target)
            manifest = json.loads((target / assurance.MANIFEST_NAME).read_text(encoding="utf-8"))
            manifest["candidate_address"] = "bundle:wrong"
            manifest["manifest_address"] = assurance._diff_manifest_address({**manifest, "manifest_address": None})
            (target / assurance.MANIFEST_NAME).write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                assurance.load_diff(target)


class AssuranceCliTests(AssuranceFixture):
    BASE = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-series-release-registry-federation-gate-review"
    LEDGER_ASSURANCE = BASE + "-decision-ledger-assurance"
    DIFF = LEDGER_ASSURANCE + "-diff"

    def test_cli_builds_verifies_and_queries_assurance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ledger_directory = self.write_ledger(self.ready_ledger, root)
            destination = root / "assurance"
            status, output = self.capture([self.LEDGER_ASSURANCE, "--input", str(ledger_directory), "--destination", str(destination), "--format", "summary"])
            self.assertEqual(status, 0)
            self.assertTrue(json.loads(output)["gate"]["release_ready"])
            status, output = self.capture([self.LEDGER_ASSURANCE + "-verify", "--input", str(destination)])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output)["gate"]["state"], "promote")
            status, output = self.capture([self.LEDGER_ASSURANCE + "-query", "--input", str(destination), "--resource", "findings", "--format", "json"])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output)["total_count"], 14)

    def test_cli_hold_status_is_two(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ledger_directory = self.write_ledger(self.held_ledger, root)
            destination = root / "assurance"
            status, output = self.capture([self.LEDGER_ASSURANCE, "--input", str(ledger_directory), "--destination", str(destination), "--format", "summary"])
            self.assertEqual(status, 2)
            self.assertEqual(json.loads(output)["gate"]["state"], "hold")

    def test_cli_schema_commands_are_all_available(self):
        for suffix in ("schema", "assurance-schema", "finding-schema", "gate-schema", "check-schema", "query-schema", "capabilities"):
            status, output = self.capture([self.LEDGER_ASSURANCE + "-" + suffix])
            self.assertEqual(status, 0)
            self.assertIsInstance(json.loads(output), dict)
        for suffix in ("schema", "item-schema", "query-schema", "capabilities"):
            status, output = self.capture([self.DIFF + "-" + suffix])
            self.assertEqual(status, 0)
            self.assertIsInstance(json.loads(output), dict)

    def test_cli_diff_build_verify_query(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.write_assurance(self.build(self.ready_ledger), root, "baseline")
            candidate = self.write_assurance(self.build(self.held_ledger), root, "candidate")
            diff_directory = root / "diff"
            status, output = self.capture([self.DIFF, "--baseline", str(baseline), "--candidate", str(candidate), "--destination", str(diff_directory), "--format", "summary"])
            self.assertEqual(status, 0)
            self.assertGreater(json.loads(output)["changed_count"], 0)
            status, output = self.capture([self.DIFF + "-verify", "--input", str(diff_directory)])
            self.assertEqual(status, 0)
            status, output = self.capture([self.DIFF + "-query", "--input", str(diff_directory), "--resource", "changed"])
            self.assertEqual(status, 0)
            self.assertGreater(json.loads(output)["total_count"], 0)

    def test_cli_output_formats(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ledger_directory = self.write_ledger(self.ready_ledger, root)
            destination = root / "assurance"
            self.capture([self.LEDGER_ASSURANCE, "--input", str(ledger_directory), "--destination", str(destination)])
            for output_format, marker in (("json", "assurance"), ("markdown", "Release-Registry")):
                status, output = self.capture([self.LEDGER_ASSURANCE + "-query", "--input", str(destination), "--format", output_format])
                self.assertEqual(status, 0)
                self.assertIn(marker, output)


class AssuranceApiTests(AssuranceFixture):
    PREFIX = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review"

    def _server(self):
        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def test_api_assurance_build_schemas_and_capabilities(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ledger_directory = self.write_ledger(self.ready_ledger, root)
            server, thread = self._server()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                prefix = self.PREFIX + "/decision-ledger/assurance"
                for suffix in ("/schema", "/assurance-schema", "/finding-schema", "/gate-schema", "/check-schema", "/query-schema", "/diff-schema", "/diff-item-schema", "/diff-query-schema", "/capabilities"):
                    with urlopen(base + prefix + suffix) as response:
                        self.assertEqual(response.status, 200)
                        self.assertIsInstance(json.loads(response.read()), dict)
                with urlopen(base + prefix + "?input=" + str(ledger_directory) + "&format=summary") as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read())["gate"]["state"], "promote")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_api_verify_query_and_diff_round_trip(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.write_assurance(self.build(self.ready_ledger), root, "baseline")
            candidate = self.write_assurance(self.build(self.held_ledger), root, "candidate")
            diff = root / "diff"
            assurance.write_diff(assurance.build_diff(self.build(self.ready_ledger), self.build(self.held_ledger)), diff)
            server, thread = self._server()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                prefix = self.PREFIX + "/decision-ledger/assurance"
                with urlopen(base + prefix + "/verify?input=" + str(baseline)) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read())["gate"]["state"], "promote")
                with urlopen(base + prefix + "/query?input=" + str(baseline) + "&resource=findings") as response:
                    self.assertEqual(json.loads(response.read())["total_count"], 14)
                with urlopen(base + prefix + "/diff?baseline=" + str(baseline) + "&candidate=" + str(candidate)) as response:
                    self.assertEqual(response.status, 200)
                    self.assertGreater(json.loads(response.read())["changed_count"], 0)
                with urlopen(base + prefix + "/diff/verify?input=" + str(diff)) as response:
                    self.assertEqual(response.status, 200)
                    self.assertIsInstance(json.loads(response.read()), dict)
                with urlopen(base + prefix + "/diff/query?input=" + str(diff) + "&resource=changed") as response:
                    self.assertGreater(json.loads(response.read())["total_count"], 0)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_api_returns_unprocessable_for_held_build(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger_directory = self.write_ledger(self.held_ledger, Path(temporary))
            server, thread = self._server()
            try:
                request = Request(f"http://127.0.0.1:{server.server_port}{self.PREFIX}/decision-ledger/assurance?input={ledger_directory}")
                with self.assertRaises(HTTPError) as raised:
                    urlopen(request)
                self.assertEqual(raised.exception.code, 422)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


class AssuranceFailureMatrixTests(AssuranceFixture):
    def test_finding_from_mapping_rejects_unknown_fields(self):
        finding = self.build(self.ready_ledger).assurance.findings[0].to_dict()
        finding["agent"] = "forbidden"
        with self.assertRaises(ValidationError):
            assurance.finding_from_mapping(finding)

    def test_check_from_mapping_rejects_missing_fields(self):
        check = self.build(self.ready_ledger).gate.checks[0].to_dict()
        check.pop("detail")
        with self.assertRaises(ValidationError):
            assurance.check_from_mapping(check)

    def test_assurance_from_mapping_rejects_unknown_fields(self):
        document = self.build(self.ready_ledger).assurance.to_dict()
        document["language"] = "python"
        with self.assertRaises(ValidationError):
            assurance.assurance_from_mapping(document)

    def test_gate_from_mapping_rejects_unknown_fields(self):
        document = self.build(self.ready_ledger).gate.to_dict()
        document["model"] = "unknown"
        with self.assertRaises(ValidationError):
            assurance.gate_from_mapping(document)

    def test_bundle_from_mapping_rejects_unknown_fields(self):
        document = self.build(self.ready_ledger).to_dict()
        document["private"] = True
        with self.assertRaises(ValidationError):
            assurance.assurance_gate_from_mapping(document)

    def test_query_rejects_bad_enums(self):
        with self.assertRaises(ValidationError):
            assurance.AssuranceQuery(resource="findings", severity="bad")
        with self.assertRaises(ValidationError):
            assurance.AssuranceQuery(resource="findings", plane="bad")
        with self.assertRaises(ValidationError):
            assurance.DiffQuery(resource="changed", action="bad")

    def test_diff_item_rejects_missing_snapshot_side(self):
        body = {"ordinal": 0, "action": "added", "key": "assurance:ledger:test", "plane": "ledger", "kind": "test", "baseline_severity": None, "candidate_severity": "pass", "baseline_required": None, "candidate_required": False, "baseline_passed": None, "candidate_passed": True, "baseline_address": None, "candidate_address": "finding:test", "detail": "test", "content_address": "diff-item:test"}
        self.assertEqual(assurance.diff_item_from_mapping(body).action, "added")
        body["candidate_address"] = None
        with self.assertRaises(ValidationError):
            assurance.diff_item_from_mapping(body)

    def test_diff_loader_rejects_extra_file(self):
        diff = assurance.build_diff(self.build(self.ready_ledger), self.build(self.held_ledger))
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "diff"
            assurance.write_diff(diff, target)
            (target / "extra.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                assurance.load_diff(target)

    def test_write_rejects_non_directory_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "file"
            target.write_text("x", encoding="utf-8")
            with self.assertRaises(ValidationError):
                assurance.write_assurance_gate(self.build(self.ready_ledger), target)

    def test_diff_query_object_and_kwargs_are_mutually_exclusive(self):
        diff = assurance.build_diff(self.build(self.ready_ledger), self.build(self.held_ledger))
        query = assurance.DiffQuery(resource="changed")
        with self.assertRaises(ValidationError):
            assurance.query_diff(diff, query, resource="changed")

    def test_diff_public_boundary(self):
        self.assert_public(assurance.build_diff(self.build(self.ready_ledger), self.build(self.held_ledger)))


class AssuranceAdditionalCoverageTests(AssuranceFixture):
    """Exercise small boundary cases that are easy to miss in a happy path."""

    def test_assurance_gate_from_directory_uses_current_ledger(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = self.write_ledger(self.ready_ledger, Path(temporary))
            value = assurance.build_assurance_gate_from_directory(directory)
            self.assertEqual(value.gate.ledger_address, self.ready_ledger.content_address)

    def test_assurance_gate_can_be_proved_against_exact_ledger(self):
        value = self.build(self.ready_ledger)
        self.assertIs(assurance.verify_assurance_gate_against_ledger(value, self.ready_ledger), value)

    def test_assurance_gate_against_ledger_rejects_cross_snapshot(self):
        value = self.build(self.ready_ledger)
        with self.assertRaises(ValidationError):
            assurance.verify_assurance_gate_against_ledger(value, self.held_ledger)

    def test_assurance_gate_against_ledger_rejects_projection_drift(self):
        value = self.build(self.ready_ledger)
        value.gate.checks[0].detail = "changed after persistence"
        with self.assertRaises(ValidationError):
            assurance.verify_assurance_gate_against_ledger(value, self.ready_ledger)

    def test_assurance_gate_loader_rejects_missing_directory(self):
        with self.assertRaises(ValidationError):
            assurance.load_assurance_gate(Path(tempfile.gettempdir()) / "missing-glio-ledger-assurance")

    def test_diff_is_deterministic_for_rebuilt_inputs(self):
        first = assurance.build_diff(self.build(self.ready_ledger), self.build(self.held_ledger))
        second = assurance.build_diff(self.build(self.ready_ledger), self.build(self.held_ledger))
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(assurance.address_diff(first), first.content_address)

    def test_custom_diff_id_is_preserved(self):
        value = assurance.build_diff(self.build(self.ready_ledger), self.build(self.held_ledger), diff_id="diff:custom")
        self.assertEqual(value.diff_id, "diff:custom")

    def test_diff_overwrite_requires_explicit_flag(self):
        value = assurance.build_diff(self.build(self.ready_ledger), self.build(self.held_ledger))
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "diff"
            assurance.write_diff(value, target)
            with self.assertRaises(ValidationError):
                assurance.write_diff(value, target)
            assurance.write_diff(value, target, overwrite=True)

    def test_diff_loader_rejects_noncanonical_json(self):
        value = assurance.build_diff(self.build(self.ready_ledger), self.build(self.held_ledger))
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "diff"
            assurance.write_diff(value, target)
            document = json.loads((target / assurance.DIFF_NAME).read_text(encoding="utf-8"))
            (target / assurance.DIFF_NAME).write_text(json.dumps(document, indent=2), encoding="utf-8")
            with self.assertRaises(ValidationError):
                assurance.load_diff(target)

    def test_diff_loader_rejects_manifest_extra_field(self):
        value = assurance.build_diff(self.build(self.ready_ledger), self.build(self.held_ledger))
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "diff"
            assurance.write_diff(value, target)
            manifest = json.loads((target / assurance.MANIFEST_NAME).read_text(encoding="utf-8"))
            manifest["extra"] = True
            (target / assurance.MANIFEST_NAME).write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                assurance.load_diff(target)

    def test_assurance_query_supports_every_plane(self):
        value = self.build(self.ready_ledger)
        for plane in assurance.AssurancePlane:
            result = assurance.query_assurance(value, resource="findings", plane=plane.value, limit=50)
            self.assertLessEqual(result.total_count, value.assurance.finding_count)

    def test_gate_query_supports_every_plane(self):
        value = self.build(self.ready_ledger)
        for plane in assurance.AssurancePlane:
            result = assurance.query_assurance(value, resource="checks", plane=plane.value, limit=50)
            self.assertLessEqual(result.total_count, value.gate.check_count)

    def test_diff_query_supports_every_action(self):
        value = assurance.build_diff(self.build(self.ready_ledger), self.build(self.held_ledger))
        for action in assurance.DiffAction:
            result = assurance.query_diff(value, resource="actions", action=action.value, limit=50)
            self.assertLessEqual(result.total_count, value.item_count)

    def test_empty_diff_query_serializes_empty_rows(self):
        value = assurance.build_diff(self.build(self.ready_ledger), self.build(self.ready_ledger))
        result = assurance.query_diff(value, resource="improved")
        self.assertEqual(result.total_count, 0)
        self.assertEqual(assurance.diff_query_csv(result), "")

    def test_query_offsets_past_end_are_valid(self):
        value = self.build(self.ready_ledger)
        result = assurance.query_assurance(value, resource="findings", offset=100, limit=3)
        self.assertEqual(result.total_count, 14)
        self.assertEqual(result.returned_count, 0)

    def test_query_result_addresses_change_with_query_window(self):
        value = self.build(self.ready_ledger)
        first = assurance.query_assurance(value, resource="findings", offset=0, limit=2)
        second = assurance.query_assurance(value, resource="findings", offset=1, limit=2)
        self.assertNotEqual(first.content_address, second.content_address)

    def test_finding_schema_has_strict_fields(self):
        schema = assurance.finding_schema()
        self.assertFalse(schema["additionalProperties"])
        self.assertIn("remediation", schema["required"])

    def test_check_schema_has_strict_fields(self):
        schema = assurance.check_schema()
        self.assertFalse(schema["additionalProperties"])
        self.assertIn("evidence_address", schema["required"])

    def test_diff_schema_declares_bounded_items(self):
        schema = assurance.diff_schema()
        self.assertEqual(schema["properties"]["items"]["maxItems"], assurance.MAX_DIFF_ITEMS)

    def test_capabilities_declare_all_diff_resources(self):
        capabilities = assurance.capabilities()
        self.assertEqual(tuple(capabilities["diff"]["query_resources"]), assurance.DiffQuery.RESOURCES)

    def test_rendered_outputs_do_not_include_local_input_path(self):
        value = self.build(self.ready_ledger)
        rendered = assurance.render_assurance_gate_markdown(value)
        self.assertNotIn("C:\\", rendered)
        self.assertNotIn("/Users/", rendered)

    def test_assurance_csv_has_fixed_columns(self):
        value = self.build(self.ready_ledger)
        header = assurance.assurance_csv(value.assurance).splitlines()[0]
        self.assertEqual(header.split(",")[0], "ordinal")
        self.assertIn("evidence_address", header)

    def test_gate_csv_has_fixed_columns(self):
        value = self.build(self.ready_ledger)
        header = assurance.gate_csv(value.gate).splitlines()[0]
        self.assertEqual(header.split(",")[0], "ordinal")
        self.assertIn("content_address", header)

    def test_diff_csv_has_fixed_columns(self):
        value = assurance.build_diff(self.build(self.ready_ledger), self.build(self.held_ledger))
        header = assurance.diff_csv(value).splitlines()[0]
        self.assertEqual(header.split(",")[0], "ordinal")
        self.assertIn("candidate_address", header)

    def test_bundle_summary_has_no_nested_source_paths(self):
        value = self.build(self.ready_ledger)
        self.assert_public({"assurance": value.assurance.summary(), "gate": value.gate.summary(), "content_address": value.content_address})

    def test_assurance_state_enums_are_fixed(self):
        self.assertEqual(tuple(item.value for item in assurance.AssuranceState), ("passed", "warning", "blocked"))
        self.assertEqual(tuple(item.value for item in assurance.GateState), ("promote", "hold", "block"))

    def test_diff_state_enums_are_fixed(self):
        self.assertEqual(tuple(item.value for item in assurance.DiffState), ("unchanged", "improved", "regressed", "changed"))

    def test_persisted_bundle_round_trip_preserves_gate_state(self):
        value = self.build(self.held_ledger)
        with tempfile.TemporaryDirectory() as temporary:
            target = self.write_assurance(value, Path(temporary))
            loaded = assurance.load_assurance_gate(target)
            self.assertEqual(loaded.gate.state, "hold")
            self.assertFalse(loaded.gate.release_ready)

    def test_persisted_diff_round_trip_preserves_direction_counters(self):
        value = assurance.build_diff(self.build(self.ready_ledger), self.build(self.held_ledger))
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "diff"
            assurance.write_diff(value, target)
            loaded = assurance.load_diff(target)
            self.assertEqual((loaded.improved_count, loaded.regressed_count), (value.improved_count, value.regressed_count))

    def test_older_downloaded_directory_is_not_accepted_as_assurance(self):
        old_shape = Path(r"C:\Users\murar\AppData\Local\Temp\glio-noncode-real-downloaded-replay-768c568d74044655acf09834ad693ea0")
        if old_shape.exists():
            with self.assertRaises(ValidationError):
                assurance.load_assurance_gate(old_shape)

    def test_assurance_package_files_are_public_names(self):
        self.assertEqual(assurance.FILES, ("manifest.json", "assurance.json", "gate.json"))
        self.assertEqual(assurance.DIFF_FILES, ("manifest.json", "diff.json"))


if __name__ == "__main__":
    unittest.main()
