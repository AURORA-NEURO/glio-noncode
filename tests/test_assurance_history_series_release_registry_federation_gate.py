"""Deep contracts for the independent release-registry federation gate."""

# ruff: noqa: E501

from __future__ import annotations

import copy
import json
import os
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

from examples.release_registry_federation_gate_demo import (
    build_argument_parser,
    build_downloaded_gate,
    discover_downloaded_registries,
    inspect_downloaded_registries,
    render_downloaded_gate,
    run_downloaded_gate_demo,
)

from glio_noncode import assurance_history_series_release_registry as registry
from glio_noncode import assurance_history_series_release_registry_federation as federation
from glio_noncode import assurance_history_series_release_registry_federation_gate as gate
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_bytes, canonical_json
from tests.test_assurance_history_series_release_registry_federation import FederationFixture


class FederationGateFixture(FederationFixture):
    """Build source bundles through the existing downloaded-data fixture path."""

    def setUp(self):
        self.ready_source = self.build((self.ready_registry("one"), self.ready_registry("two")))
        self.held_source = self.build((self.ready_registry("one"), self.held_registry("two")))
        self.blocked_source = self.build((self.ready_registry("one"), self.blocked_registry("two")))

    @staticmethod
    def build_gate(value, **kwargs):
        return gate.build_federation_assurance_gate(value, **kwargs)

    @staticmethod
    def write_gate(value, path, **kwargs):
        return gate.write_federation_assurance_gate(value, path, **kwargs)

    @staticmethod
    def persist_source(value, path):
        return federation.write_federation(value, path)

    @staticmethod
    def capture_cli(argv):
        stream = StringIO()
        with redirect_stdout(stream):
            status = main(argv)
        return status, stream.getvalue()

    @staticmethod
    def source_state(value):
        return value.federation.state

    @staticmethod
    def gate_state(value):
        return value.gate.state

    @staticmethod
    def all_public_keys(value):
        if isinstance(value, dict):
            output = set(value)
            for nested in value.values():
                output.update(FederationGateFixture.all_public_keys(nested))
            return output
        if isinstance(value, (list, tuple)):
            output = set()
            for nested in value:
                output.update(FederationGateFixture.all_public_keys(nested))
            return output
        return set()

    def assert_public_projection(self, value):
        keys = self.all_public_keys(value.to_dict() if hasattr(value, "to_dict") else value)
        self.assertFalse(keys & gate._FORBIDDEN_KEYS)
        encoded = canonical_json(value.to_dict() if hasattr(value, "to_dict") else value)
        for forbidden in gate._FORBIDDEN_KEYS:
            self.assertNotIn(f'"{forbidden}"', encoded)

    def assert_json_document(self, path):
        raw = path.read_bytes()
        decoded = raw.decode("utf-8")
        self.assertEqual(raw, decoded.encode("utf-8"))
        self.assertEqual(raw, canonical_bytes(json.loads(decoded)))
        self.assertEqual(json.loads(decoded), json.loads(canonical_json(json.loads(decoded))))


class FederationGateStateTests(FederationGateFixture):
    def test_ready_source_promotes_independent_assurance_and_gate(self):
        value = self.build_gate(self.ready_source)
        self.assertEqual(value.assurance.state, gate.GateState.PROMOTE.value)
        self.assertEqual(value.gate.state, gate.GateState.PROMOTE.value)
        self.assertEqual(value.gate.decision, "promote")
        self.assertTrue(value.assurance.accepted)
        self.assertTrue(value.assurance.release_ready)
        self.assertTrue(value.gate.accepted)
        self.assertTrue(value.gate.release_ready)
        self.assertEqual(value.assurance.finding_count, 10)
        self.assertEqual(value.assurance.failed_count, 0)
        self.assertEqual(value.gate.check_count, 8)
        self.assertEqual(value.gate.failed_count, 0)

    def test_held_source_holds_without_becoming_a_block(self):
        value = self.build_gate(self.held_source)
        self.assertEqual(value.assurance.state, "hold")
        self.assertEqual(value.gate.state, "hold")
        self.assertEqual(value.gate.decision, "hold")
        self.assertTrue(value.assurance.accepted)
        self.assertFalse(value.assurance.release_ready)
        self.assertTrue(value.gate.accepted)
        self.assertFalse(value.gate.release_ready)
        self.assertEqual(value.assurance.blocker_count, 0)
        self.assertGreater(value.assurance.warning_count, 0)
        self.assertEqual(value.gate.required_failure_count, 0)
        self.assertGreater(value.gate.optional_failure_count, 0)

    def test_blocked_source_blocks_and_is_not_accepted(self):
        value = self.build_gate(self.blocked_source)
        self.assertEqual(value.assurance.state, "block")
        self.assertEqual(value.gate.state, "block")
        self.assertEqual(value.gate.decision, "block")
        self.assertFalse(value.assurance.accepted)
        self.assertFalse(value.assurance.release_ready)
        self.assertFalse(value.gate.accepted)
        self.assertFalse(value.gate.release_ready)
        self.assertGreater(value.assurance.blocker_count, 0)
        self.assertGreater(value.gate.required_failure_count, 0)

    def test_empty_source_is_explicitly_held_when_policy_allows_empty(self):
        source = self.build((), policy=federation.default_federation_policy(allow_empty=True))
        value = self.build_gate(source)
        self.assertEqual(source.federation.state, "empty")
        self.assertEqual(value.assurance.state, "hold")
        self.assertEqual(value.gate.state, "hold")
        self.assertTrue(value.assurance.accepted)
        self.assertFalse(value.assurance.release_ready)
        self.assertTrue(value.gate.accepted)
        self.assertFalse(value.gate.release_ready)

    def test_each_source_state_maps_to_the_same_gate_state(self):
        cases = (
            (self.ready_source, "ready", "promote"),
            (self.held_source, "held", "hold"),
            (self.blocked_source, "blocked", "block"),
        )
        for source, source_state, expected in cases:
            with self.subTest(source_state=source_state):
                value = self.build_gate(source)
                self.assertEqual(value.gate.state, expected)
                self.assertEqual(value.gate.decision, expected)

    def test_custom_gate_ids_do_not_change_source_addresses(self):
        first = self.build_gate(self.ready_source, gate_id="gate:one")
        second = self.build_gate(self.ready_source, gate_id="gate:two")
        self.assertEqual(first.assurance.to_dict(), second.assurance.to_dict())
        self.assertNotEqual(first.gate.content_address, second.gate.content_address)
        self.assertEqual(first.gate.federation_address, second.gate.federation_address)
        self.assertEqual(first.gate.runtime_address, second.gate.runtime_address)
        self.assertEqual(first.gate.assurance_address, second.gate.assurance_address)

    def test_source_input_order_does_not_change_any_gate_address(self):
        first_source = self.build((self.ready_registry("one"), self.held_registry("two")))
        second_source = self.build((self.held_registry("two"), self.ready_registry("one")))
        first = self.build_gate(first_source)
        second = self.build_gate(second_source)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.assurance.content_address, second.assurance.content_address)
        self.assertEqual(first.gate.content_address, second.gate.content_address)

    def test_assurance_findings_are_contiguous_and_addressed(self):
        value = self.build_gate(self.held_source)
        for ordinal, finding in enumerate(value.assurance.findings):
            with self.subTest(ordinal=ordinal, finding_id=finding.finding_id):
                self.assertEqual(finding.ordinal, ordinal)
                self.assertTrue(finding.content_address.startswith(gate.FINDING_PREFIX + ":"))
                self.assertEqual(gate.address_finding(finding), finding.content_address)
                self.assertTrue(finding.evidence_address)
                self.assertIn(finding.plane, tuple(gate.GatePlane))
                self.assertIn(finding.severity, tuple(gate.FindingSeverity))

    def test_gate_checks_are_contiguous_and_addressed(self):
        value = self.build_gate(self.held_source)
        for ordinal, check in enumerate(value.gate.checks):
            with self.subTest(ordinal=ordinal, check_id=check.check_id):
                self.assertEqual(check.ordinal, ordinal)
                self.assertTrue(check.content_address.startswith(gate.CHECK_PREFIX + ":"))
                self.assertEqual(gate.address_gate_check(check), check.content_address)
                self.assertTrue(check.evidence_address)
                self.assertIn(check.severity, tuple(gate.FindingSeverity))

    def test_findings_cover_each_recomputed_plane(self):
        value = self.build_gate(self.ready_source)
        planes = {finding.plane for finding in value.assurance.findings}
        self.assertEqual(
            planes,
            {
                "source",
                "verification",
                "policy",
                "runtime",
                "boundary",
            },
        )

    def test_assurance_and_gate_retain_the_same_source_receipts(self):
        value = self.build_gate(self.ready_source)
        self.assertEqual(value.assurance.federation_address, self.ready_source.federation.content_address)
        self.assertEqual(value.assurance.runtime_address, self.ready_source.runtime.content_address)
        self.assertEqual(value.gate.federation_address, value.assurance.federation_address)
        self.assertEqual(value.gate.runtime_address, value.assurance.runtime_address)
        self.assertEqual(value.gate.assurance_address, value.assurance.content_address)

    def test_bundle_summary_is_a_gate_summary_with_assurance_rollup(self):
        value = self.build_gate(self.ready_source)
        summary = value.summary()
        for key, item in value.gate.summary().items():
            self.assertEqual(summary[key], item)
        self.assertEqual(summary["assurance_finding_count"], 10)
        self.assertEqual(summary["assurance_failed_count"], 0)
        self.assertEqual(summary["assurance_state"], "promote")


class FederationGateIndependentFindingTests(FederationGateFixture):
    def test_assurance_recomputes_the_source_verification_receipt(self):
        value = self.build_gate(self.ready_source)
        finding = next(item for item in value.assurance.findings if item.finding_id == "verification-recomputed")
        self.assertTrue(finding.passed)
        self.assertEqual(finding.plane, "verification")
        self.assertEqual(finding.severity, "blocker")
        self.assertIn(value.gate.federation_address, finding.detail)

    def test_assurance_recomputes_the_policy_receipt(self):
        value = self.build_gate(self.held_source)
        finding = next(item for item in value.assurance.findings if item.finding_id == "policy-recomputed")
        self.assertTrue(finding.passed)
        self.assertEqual(finding.plane, "policy")
        self.assertEqual(finding.severity, "blocker")

    def test_assurance_recomputes_the_runtime_receipt(self):
        value = self.build_gate(self.blocked_source)
        finding = next(item for item in value.assurance.findings if item.finding_id == "runtime-recomputed")
        self.assertTrue(finding.passed)
        self.assertEqual(finding.plane, "runtime")
        self.assertEqual(finding.severity, "blocker")

    def test_assurance_marks_source_release_readiness_as_a_warning(self):
        value = self.build_gate(self.held_source)
        finding = next(item for item in value.assurance.findings if item.finding_id == "source-release-ready")
        self.assertFalse(finding.passed)
        self.assertEqual(finding.severity, "warning")
        self.assertEqual(finding.plane, "runtime")

    def test_assurance_marks_source_release_readiness_clean_for_ready_source(self):
        value = self.build_gate(self.ready_source)
        finding = next(item for item in value.assurance.findings if item.finding_id == "source-release-ready")
        self.assertTrue(finding.passed)
        self.assertEqual(value.assurance.warning_count, 0)

    def test_gate_checks_separate_required_and_optional_failures(self):
        held = self.build_gate(self.held_source)
        blocked = self.build_gate(self.blocked_source)
        self.assertEqual(held.gate.required_failure_count, 0)
        self.assertGreater(held.gate.optional_failure_count, 0)
        self.assertGreater(blocked.gate.required_failure_count, 0)
        self.assertGreaterEqual(blocked.gate.optional_failure_count, 0)

    def test_gate_source_state_check_fails_for_blocked_source(self):
        value = self.build_gate(self.blocked_source)
        check = next(item for item in value.gate.checks if item.check_id == "source-state-allowed")
        self.assertFalse(check.passed)
        self.assertEqual(check.severity, "blocker")
        self.assertIn("blocked", check.detail)

    def test_gate_warning_free_check_fails_for_held_source(self):
        value = self.build_gate(self.held_source)
        check = next(item for item in value.gate.checks if item.check_id == "assurance-warning-free")
        self.assertFalse(check.passed)
        self.assertEqual(check.severity, "warning")

    def test_gate_public_boundary_check_is_required(self):
        value = self.build_gate(self.ready_source)
        check = next(item for item in value.gate.checks if item.check_id == "public-boundary-closed")
        self.assertTrue(check.passed)
        self.assertEqual(check.severity, "blocker")

    def test_independent_assurance_does_not_copy_source_release_decision(self):
        value = copy.deepcopy(self.ready_source)
        value.federation.release_ready = False
        with self.assertRaises(ValidationError):
            self.build_gate(value)

    def test_independent_assurance_rejects_non_bundle_input(self):
        with self.assertRaises(ValidationError):
            gate.build_federation_assurance({})

    def test_independent_gate_rejects_non_assurance_input(self):
        with self.assertRaises(ValidationError):
            gate.build_federation_release_gate(self.ready_source, {})

    def test_assurance_verification_is_idempotent(self):
        value = self.build_gate(self.held_source)
        first = gate.verify_federation_assurance(value.assurance)
        second = gate.verify_federation_assurance(first)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.content_address, second.content_address)

    def test_release_gate_verification_is_idempotent(self):
        value = self.build_gate(self.ready_source)
        first = gate.verify_federation_release_gate(value.gate)
        second = gate.verify_federation_release_gate(first)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.content_address, second.content_address)

    def test_bundle_verification_is_idempotent(self):
        value = self.build_gate(self.ready_source)
        first = gate.verify_federation_assurance_gate(value)
        second = gate.verify_federation_assurance_gate(first)
        self.assertEqual(first.to_dict(), second.to_dict())


class FederationGateAddressTests(FederationGateFixture):
    def test_address_functions_are_stable_for_repeated_builds(self):
        first = self.build_gate(self.ready_source)
        second = self.build_gate(self.ready_source)
        self.assertEqual(first.assurance.content_address, second.assurance.content_address)
        self.assertEqual(first.gate.content_address, second.gate.content_address)
        self.assertEqual(
            [item.content_address for item in first.assurance.findings],
            [item.content_address for item in second.assurance.findings],
        )
        self.assertEqual(
            [item.content_address for item in first.gate.checks],
            [item.content_address for item in second.gate.checks],
        )

    def test_address_functions_exclude_ordinal_from_item_identity(self):
        value = self.build_gate(self.ready_source)
        finding = value.assurance.findings[0]
        check = value.gate.checks[0]
        finding_copy = gate.FederationAssuranceFinding(
            finding.ordinal + 1,
            finding.finding_id,
            finding.plane,
            finding.severity,
            finding.passed,
            finding.detail,
            finding.evidence_address,
            "pending:finding",
        )
        check_copy = gate.FederationGateCheck(
            check.ordinal + 1,
            check.check_id,
            check.severity,
            check.passed,
            check.detail,
            check.evidence_address,
            "pending:check",
        )
        self.assertEqual(gate.address_finding(finding), gate.address_finding(finding_copy))
        self.assertEqual(gate.address_gate_check(check), gate.address_gate_check(check_copy))

    def test_assurance_address_excludes_its_own_content_address(self):
        value = self.build_gate(self.ready_source)
        body = value.assurance.summary() | {"content_address": None}
        self.assertEqual(gate.address_assurance(value.assurance), gate.content_hash(body, prefix=gate.ASSURANCE_PREFIX))

    def test_gate_address_excludes_its_own_content_address(self):
        value = self.build_gate(self.ready_source)
        body = value.gate.summary() | {"content_address": None}
        self.assertEqual(gate.address_gate(value.gate), gate.content_hash(body, prefix=gate.PREFIX))

    def test_query_address_is_stable(self):
        value = self.build_gate(self.ready_source)
        first = gate.query_federation_assurance_gate(value, resource="findings", limit=4)
        second = gate.query_federation_assurance_gate(value, resource="findings", limit=4)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(gate.address_query(first), first.content_address)

    def test_public_projection_contains_only_explicit_contract_fields(self):
        value = self.build_gate(self.ready_source)
        self.assert_public_projection(value)
        self.assert_public_projection(value.assurance)
        self.assert_public_projection(value.gate)
        for finding in value.assurance.findings:
            self.assert_public_projection(finding)
        for check in value.gate.checks:
            self.assert_public_projection(check)

    def test_version_and_boundary_are_explicit(self):
        value = self.build_gate(self.ready_source)
        self.assertEqual(value.assurance.summary()["version"], gate.VERSION)
        self.assertEqual(value.assurance.summary()["boundary"], gate.BOUNDARY)
        self.assertEqual(value.gate.version, gate.VERSION)
        self.assertEqual(value.gate.boundary, gate.BOUNDARY)


class FederationGateMappingTests(FederationGateFixture):
    def setUp(self):
        super().setUp()
        self.value = self.build_gate(self.held_source)

    def test_finding_mapping_round_trip(self):
        for finding in self.value.assurance.findings:
            with self.subTest(finding_id=finding.finding_id):
                rebuilt = gate.finding_from_mapping(finding.to_dict())
                self.assertEqual(rebuilt.to_dict(), finding.to_dict())

    def test_assurance_mapping_round_trip(self):
        rebuilt = gate.assurance_from_mapping(self.value.assurance.to_dict())
        self.assertEqual(rebuilt.to_dict(), self.value.assurance.to_dict())

    def test_gate_check_mapping_round_trip(self):
        for check in self.value.gate.checks:
            with self.subTest(check_id=check.check_id):
                rebuilt = gate.gate_check_from_mapping(check.to_dict())
                self.assertEqual(rebuilt.to_dict(), check.to_dict())

    def test_gate_mapping_round_trip(self):
        rebuilt = gate.gate_from_mapping(self.value.gate.to_dict())
        self.assertEqual(rebuilt.to_dict(), self.value.gate.to_dict())

    def test_bundle_mapping_round_trip(self):
        rebuilt = gate.assurance_gate_from_mapping(self.value.to_dict())
        self.assertEqual(rebuilt.to_dict(), self.value.to_dict())

    def test_query_mapping_round_trip(self):
        result = gate.query_federation_assurance_gate(self.value, resource="warnings", severity="warning", limit=8)
        rebuilt = gate.gate_query_from_mapping(result.to_dict())
        self.assertEqual(rebuilt.to_dict(), result.to_dict())

    def test_finding_mapping_rejects_each_missing_field(self):
        original = self.value.assurance.findings[0].to_dict()
        for field in original:
            body = dict(original)
            body.pop(field)
            with self.subTest(field=field), self.assertRaises(ValidationError):
                gate.finding_from_mapping(body)

    def test_assurance_mapping_rejects_each_missing_top_level_field(self):
        original = self.value.assurance.to_dict()
        for field in original:
            body = dict(original)
            body.pop(field)
            with self.subTest(field=field), self.assertRaises(ValidationError):
                gate.assurance_from_mapping(body)

    def test_gate_check_mapping_rejects_each_missing_field(self):
        original = self.value.gate.checks[0].to_dict()
        for field in original:
            body = dict(original)
            body.pop(field)
            with self.subTest(field=field), self.assertRaises(ValidationError):
                gate.gate_check_from_mapping(body)

    def test_gate_mapping_rejects_each_missing_top_level_field(self):
        original = self.value.gate.to_dict()
        for field in original:
            body = dict(original)
            body.pop(field)
            with self.subTest(field=field), self.assertRaises(ValidationError):
                gate.gate_from_mapping(body)

    def test_bundle_mapping_rejects_each_missing_document(self):
        original = self.value.to_dict()
        for field in original:
            body = dict(original)
            body.pop(field)
            with self.subTest(field=field), self.assertRaises(ValidationError):
                gate.assurance_gate_from_mapping(body)

    def test_unknown_fields_are_rejected_at_every_mapping_boundary(self):
        cases = (
            (gate.finding_from_mapping, self.value.assurance.findings[0].to_dict()),
            (gate.assurance_from_mapping, self.value.assurance.to_dict()),
            (gate.gate_check_from_mapping, self.value.gate.checks[0].to_dict()),
            (gate.gate_from_mapping, self.value.gate.to_dict()),
            (gate.assurance_gate_from_mapping, self.value.to_dict()),
        )
        for builder, body in cases:
            with self.subTest(builder=builder.__name__), self.assertRaises(ValidationError):
                candidate = dict(body)
                candidate["unexpected"] = True
                builder(candidate)

    def test_private_fields_are_rejected_at_every_mapping_boundary(self):
        cases = (
            (gate.finding_from_mapping, self.value.assurance.findings[0].to_dict()),
            (gate.assurance_from_mapping, self.value.assurance.to_dict()),
            (gate.gate_check_from_mapping, self.value.gate.checks[0].to_dict()),
            (gate.gate_from_mapping, self.value.gate.to_dict()),
            (gate.assurance_gate_from_mapping, self.value.to_dict()),
        )
        for builder, body in cases:
            for field in ("agent", "author", "language", "model", "private", "user"):
                with self.subTest(builder=builder.__name__, field=field), self.assertRaises(ValidationError):
                    candidate = dict(body)
                    candidate[field] = "not-public"
                    builder(candidate)

    def test_mapping_rejects_wrong_container_types(self):
        cases = (
            (gate.finding_from_mapping, []),
            (gate.assurance_from_mapping, []),
            (gate.gate_check_from_mapping, []),
            (gate.gate_from_mapping, []),
            (gate.assurance_gate_from_mapping, []),
            (gate.gate_query_from_mapping, []),
        )
        for builder, value in cases:
            with self.subTest(builder=builder.__name__), self.assertRaises(ValidationError):
                builder(value)

    def test_mapping_rejects_tampered_item_addresses(self):
        finding = self.value.assurance.findings[0].to_dict()
        finding["detail"] = "changed"
        with self.assertRaises(ValidationError):
            gate.finding_from_mapping(finding)
        check = self.value.gate.checks[0].to_dict()
        check["detail"] = "changed"
        with self.assertRaises(ValidationError):
            gate.gate_check_from_mapping(check)

    def test_mapping_rejects_tampered_assurance_counts(self):
        body = self.value.assurance.to_dict()
        body["failed_count"] += 1
        with self.assertRaises(ValidationError):
            gate.assurance_from_mapping(body)

    def test_mapping_rejects_tampered_gate_counts(self):
        body = self.value.gate.to_dict()
        body["failed_count"] += 1
        with self.assertRaises(ValidationError):
            gate.gate_from_mapping(body)

    def test_mapping_rejects_tampered_linkage(self):
        body = self.value.to_dict()
        body["gate"]["assurance_address"] = "tampered:assurance"
        with self.assertRaises(ValidationError):
            gate.assurance_gate_from_mapping(body)

    def test_mapping_accepts_json_decoded_canonical_documents(self):
        decoded = json.loads(gate.assurance_gate_json(self.value))
        rebuilt = gate.assurance_gate_from_mapping(decoded)
        self.assertEqual(rebuilt.to_dict(), self.value.to_dict())


class FederationGatePersistenceTests(FederationGateFixture):
    def setUp(self):
        super().setUp()
        self.value = self.build_gate(self.held_source)

    def persist(self, root):
        return self.write_gate(self.value, root / "gate")

    def test_exact_file_set_is_written(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.persist(Path(temporary))
            self.assertEqual({item.name for item in destination.iterdir()}, set(gate.FILES))
            self.assertEqual(tuple(path.name for path in sorted(destination.iterdir())), tuple(sorted(gate.FILES)))

    def test_each_document_is_canonical_utf8_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.persist(Path(temporary))
            for name in gate.FILES:
                with self.subTest(name=name):
                    self.assert_json_document(destination / name)

    def test_manifest_records_exact_non_manifest_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.persist(Path(temporary))
            manifest = json.loads((destination / gate.MANIFEST_NAME).read_text(encoding="utf-8"))
            self.assertEqual(manifest["files"], list(gate.FILES))
            self.assertEqual(manifest["artifact_count"], 2)
            self.assertEqual([item["name"] for item in manifest["artifacts"]], [gate.ASSURANCE_NAME, gate.GATE_NAME])
            self.assertEqual(manifest["federation_address"], self.value.gate.federation_address)
            self.assertEqual(manifest["runtime_address"], self.value.gate.runtime_address)
            self.assertEqual(manifest["assurance_address"], self.value.assurance.content_address)
            self.assertEqual(manifest["gate_address"], self.value.gate.content_address)
            self.assertEqual(manifest["content_address"], gate._manifest_address(manifest))

    def test_manifest_byte_receipts_match_every_document(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.persist(Path(temporary))
            manifest = json.loads((destination / gate.MANIFEST_NAME).read_text(encoding="utf-8"))
            for artifact in manifest["artifacts"]:
                with self.subTest(name=artifact["name"]):
                    raw = (destination / artifact["name"]).read_bytes()
                    self.assertEqual(artifact["bytes"], len(raw))
                    self.assertEqual(artifact["byte_address"], gate._file_address(artifact["name"], raw))

    def test_load_round_trip_preserves_the_complete_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.persist(Path(temporary))
            loaded = gate.load_federation_assurance_gate(destination)
            self.assertEqual(loaded.to_dict(), self.value.to_dict())
            self.assertEqual(gate.verify_federation_assurance_gate_directory(destination).to_dict(), self.value.to_dict())

    def test_write_rejects_existing_nonempty_destination_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.persist(Path(temporary))
            with self.assertRaises(ValidationError):
                self.write_gate(self.value, destination)

    def test_write_overwrite_replaces_the_complete_destination_atomically(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.persist(Path(temporary))
            old_bytes = {name: (destination / name).read_bytes() for name in gate.FILES}
            replacement = self.build_gate(self.ready_source, gate_id="gate:replacement")
            self.write_gate(replacement, destination, overwrite=True)
            loaded = gate.load_federation_assurance_gate(destination)
            self.assertEqual(loaded.to_dict(), replacement.to_dict())
            self.assertNotEqual(old_bytes[gate.GATE_NAME], (destination / gate.GATE_NAME).read_bytes())
            self.assertEqual({item.name for item in destination.iterdir()}, set(gate.FILES))

    def test_missing_each_document_is_rejected(self):
        for name in gate.FILES:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                destination = self.persist(Path(temporary))
                (destination / name).unlink()
                with self.assertRaises(ValidationError):
                    gate.load_federation_assurance_gate(destination)

    def test_extra_each_common_file_is_rejected(self):
        for name in ("extra.json", "README.md", "nested.txt"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                destination = self.persist(Path(temporary))
                (destination / name).write_text("unexpected", encoding="utf-8")
                with self.assertRaises(ValidationError):
                    gate.load_federation_assurance_gate(destination)

    def test_noncanonical_json_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.persist(Path(temporary))
            path = destination / gate.GATE_NAME
            body = json.loads(path.read_text(encoding="utf-8"))
            path.write_text(json.dumps(body, indent=2), encoding="utf-8")
            with self.assertRaises(ValidationError):
                gate.load_federation_assurance_gate(destination)

    def test_changed_assurance_bytes_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.persist(Path(temporary))
            path = destination / gate.ASSURANCE_NAME
            body = json.loads(path.read_text(encoding="utf-8"))
            body["findings"][0]["detail"] = "changed"
            path.write_bytes(canonical_bytes(body))
            with self.assertRaises(ValidationError):
                gate.load_federation_assurance_gate(destination)

    def test_changed_gate_bytes_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.persist(Path(temporary))
            path = destination / gate.GATE_NAME
            body = json.loads(path.read_text(encoding="utf-8"))
            body["decision"] = "block"
            path.write_bytes(canonical_bytes(body))
            with self.assertRaises(ValidationError):
                gate.load_federation_assurance_gate(destination)

    def test_manifest_linkage_is_checked(self):
        for field in ("federation_address", "runtime_address", "assurance_address", "gate_address"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                destination = self.persist(Path(temporary))
                path = destination / gate.MANIFEST_NAME
                body = json.loads(path.read_text(encoding="utf-8"))
                body[field] = "tampered:" + field
                path.write_bytes(canonical_bytes(body))
                with self.assertRaises(ValidationError):
                    gate.load_federation_assurance_gate(destination)

    def test_manifest_contract_fields_are_checked(self):
        for field, replacement in (("version", "other"), ("boundary", "other"), ("artifact_count", 99), ("files", [gate.GATE_NAME])):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                destination = self.persist(Path(temporary))
                path = destination / gate.MANIFEST_NAME
                body = json.loads(path.read_text(encoding="utf-8"))
                body[field] = replacement
                path.write_bytes(canonical_bytes(body))
                with self.assertRaises(ValidationError):
                    gate.load_federation_assurance_gate(destination)

    def test_manifest_artifact_name_and_size_receipts_are_checked(self):
        for mutation in ("name", "bytes", "byte_address"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                destination = self.persist(Path(temporary))
                path = destination / gate.MANIFEST_NAME
                body = json.loads(path.read_text(encoding="utf-8"))
                body["artifacts"][0][mutation] = "tampered" if mutation != "bytes" else 0
                path.write_bytes(canonical_bytes(body))
                with self.assertRaises(ValidationError):
                    gate.load_federation_assurance_gate(destination)

    def test_manifest_content_address_is_checked(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.persist(Path(temporary))
            path = destination / gate.MANIFEST_NAME
            body = json.loads(path.read_text(encoding="utf-8"))
            body["content_address"] = "tampered:manifest"
            path.write_bytes(canonical_bytes(body))
            with self.assertRaises(ValidationError):
                gate.load_federation_assurance_gate(destination)

    def test_manifest_unknown_fields_are_checked(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.persist(Path(temporary))
            path = destination / gate.MANIFEST_NAME
            body = json.loads(path.read_text(encoding="utf-8"))
            body["unexpected"] = True
            path.write_bytes(canonical_bytes(body))
            with self.assertRaises(ValidationError):
                gate.load_federation_assurance_gate(destination)

    def test_directory_input_must_be_a_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "file"
            path.write_text("not a directory", encoding="utf-8")
            with self.assertRaises(ValidationError):
                gate.load_federation_assurance_gate(path)

    def test_artifact_input_must_be_a_regular_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.persist(Path(temporary))
            (destination / gate.GATE_NAME).unlink()
            (destination / gate.GATE_NAME).mkdir()
            with self.assertRaises(ValidationError):
                gate.load_federation_assurance_gate(destination)

    def test_symlink_artifact_is_rejected_when_platform_can_create_one(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.persist(Path(temporary))
            source = destination / gate.GATE_NAME
            replacement = destination / "gate-target.json"
            source.rename(replacement)
            try:
                source.symlink_to(replacement)
            except (OSError, NotImplementedError):
                source.unlink(missing_ok=True)
                source.write_bytes(replacement.read_bytes())
                self.skipTest("symbolic links are not available for this test process")
            with self.assertRaises(ValidationError):
                gate.load_federation_assurance_gate(destination)

    def test_persisted_file_bytes_are_repeatable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.write_gate(self.value, root / "first")
            second = self.write_gate(self.value, root / "second")
            for name in gate.FILES:
                with self.subTest(name=name):
                    self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())

    def test_persisted_package_has_no_local_path_strings(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.persist(Path(temporary))
            for name in gate.FILES:
                with self.subTest(name=name):
                    text = (destination / name).read_text(encoding="utf-8")
                    self.assertNotIn(str(destination), text)
                    self.assertNotIn(os.getcwd(), text)


class FederationGateExportTests(FederationGateFixture):
    def setUp(self):
        super().setUp()
        self.value = self.build_gate(self.held_source)

    def test_assurance_json_is_canonical_and_complete(self):
        raw = gate.assurance_json(self.value.assurance)
        self.assertEqual(raw, canonical_json(self.value.assurance.to_dict()))
        self.assertEqual(json.loads(raw), self.value.assurance.to_dict())
        self.assertEqual(len(json.loads(raw)["findings"]), 10)

    def test_gate_json_is_canonical_and_complete(self):
        raw = gate.gate_json(self.value.gate)
        self.assertEqual(raw, canonical_json(self.value.gate.to_dict()))
        self.assertEqual(json.loads(raw), self.value.gate.to_dict())
        self.assertEqual(len(json.loads(raw)["checks"]), 8)

    def test_bundle_json_is_canonical_and_complete(self):
        raw = gate.assurance_gate_json(self.value)
        self.assertEqual(raw, canonical_json(self.value.to_dict()))
        self.assertEqual(json.loads(raw), self.value.to_dict())

    def test_assurance_csv_has_stable_header_and_all_findings(self):
        rows = gate.assurance_csv(self.value.assurance).splitlines()
        self.assertEqual(rows[0], "ordinal,finding_id,plane,severity,passed,detail,evidence_address,content_address")
        self.assertEqual(len(rows) - 1, 10)
        self.assertTrue(all(row.count(",") >= 7 for row in rows[1:]))

    def test_gate_csv_has_stable_header_and_all_checks(self):
        rows = gate.gate_csv(self.value.gate).splitlines()
        self.assertEqual(rows[0], "ordinal,check_id,severity,passed,detail,evidence_address,content_address")
        self.assertEqual(len(rows) - 1, 8)
        self.assertTrue(all(row.count(",") >= 6 for row in rows[1:]))

    def test_bundle_csv_is_gate_projection(self):
        self.assertEqual(gate.assurance_gate_csv(self.value), gate.gate_csv(self.value.gate))

    def test_assurance_markdown_has_summary_and_findings(self):
        markdown = gate.render_assurance_markdown(self.value.assurance)
        self.assertIn("# Decision Assurance History Series Release Registry Federation Assurance", markdown)
        self.assertIn("## Summary", markdown)
        self.assertIn("## Items", markdown)
        self.assertIn("source-bundle-verified", markdown)

    def test_gate_markdown_has_summary_and_checks(self):
        markdown = gate.render_gate_markdown(self.value.gate)
        self.assertIn("# Decision Assurance History Series Release Registry Federation Release Gate", markdown)
        self.assertIn("## Summary", markdown)
        self.assertIn("public-boundary-closed", markdown)

    def test_bundle_markdown_has_summary_and_checks(self):
        markdown = gate.render_assurance_gate_markdown(self.value)
        self.assertIn("# Decision Assurance History Series Release Registry Federation Assurance Gate", markdown)
        self.assertIn("assurance_warning_count", markdown)
        self.assertIn("assurance-warning-free", markdown)

    def test_empty_query_csv_retains_a_machine_readable_header(self):
        value = self.build_gate(self.ready_source)
        result = gate.query_federation_assurance_gate(value, resource="failed-findings")
        self.assertEqual(result.returned_count, 0)
        self.assertEqual(gate.query_csv(result).splitlines()[0], "gate_address,resource,total_count,returned_count")

    def test_json_exports_reject_invalid_typed_values(self):
        with self.assertRaises(ValidationError):
            gate.assurance_json({})
        with self.assertRaises(ValidationError):
            gate.gate_json({})
        with self.assertRaises(ValidationError):
            gate.assurance_gate_json({})


class FederationGateQueryTests(FederationGateFixture):
    def setUp(self):
        super().setUp()
        self.value = self.build_gate(self.held_source)

    def test_every_query_resource_is_bounded_and_addressed(self):
        for resource in gate.FederationGateQuery.RESOURCES:
            with self.subTest(resource=resource):
                result = gate.query_federation_assurance_gate(self.value, resource=resource, limit=64)
                self.assertLessEqual(result.returned_count, 64)
                self.assertEqual(result.returned_count, len(result.items))
                self.assertEqual(gate.address_query(result), result.content_address)
                self.assertEqual(result.gate_address, self.value.gate.content_address)
                self.assertEqual(result.assurance_address, self.value.assurance.content_address)

    def test_summary_query_returns_one_rollup(self):
        result = gate.query_federation_assurance_gate(self.value, resource="summary")
        self.assertEqual(result.total_count, 1)
        self.assertEqual(result.returned_count, 1)
        self.assertEqual(result.items[0]["state"], "hold")

    def test_findings_query_returns_all_findings_in_ordinal_order(self):
        result = gate.query_federation_assurance_gate(self.value, resource="findings", limit=64)
        self.assertEqual(result.total_count, 10)
        self.assertEqual([row["ordinal"] for row in result.items], list(range(10)))

    def test_blockers_query_returns_only_failed_blockers(self):
        result = gate.query_federation_assurance_gate(self.value, resource="blockers", limit=64)
        self.assertTrue(all(row["severity"] == "blocker" for row in result.items))
        self.assertTrue(all(not row["passed"] for row in result.items))

    def test_warnings_query_returns_only_failed_warnings(self):
        result = gate.query_federation_assurance_gate(self.value, resource="warnings", limit=64)
        self.assertTrue(all(row["severity"] == "warning" for row in result.items))
        self.assertTrue(all(not row["passed"] for row in result.items))

    def test_failed_findings_query_excludes_passed_findings(self):
        result = gate.query_federation_assurance_gate(self.value, resource="failed-findings", limit=64)
        self.assertTrue(all(not row["passed"] for row in result.items))
        self.assertEqual(result.total_count, self.value.assurance.failed_count)

    def test_checks_query_returns_all_checks(self):
        result = gate.query_federation_assurance_gate(self.value, resource="checks", limit=64)
        self.assertEqual(result.total_count, 8)
        self.assertEqual([row["ordinal"] for row in result.items], list(range(8)))

    def test_failed_checks_query_excludes_passed_checks(self):
        result = gate.query_federation_assurance_gate(self.value, resource="failed-checks", limit=64)
        self.assertTrue(all(not row["passed"] for row in result.items))
        self.assertEqual(result.total_count, self.value.gate.failed_count)

    def test_required_failure_query_returns_blocker_failures(self):
        result = gate.query_federation_assurance_gate(self.value, resource="required-failures", limit=64)
        self.assertTrue(all(row["severity"] == "blocker" and not row["passed"] for row in result.items))
        self.assertEqual(result.total_count, self.value.gate.required_failure_count)

    def test_optional_failure_query_returns_warning_failures(self):
        result = gate.query_federation_assurance_gate(self.value, resource="optional-failures", limit=64)
        self.assertTrue(all(row["severity"] == "warning" and not row["passed"] for row in result.items))
        self.assertEqual(result.total_count, self.value.gate.optional_failure_count)

    def test_plane_filter_selects_assurance_findings(self):
        result = gate.query_federation_assurance_gate(self.value, resource="findings", plane="runtime", limit=64)
        self.assertTrue(result.items)
        self.assertTrue(all(row["plane"] == "runtime" for row in result.items))

    def test_plane_filter_removes_gate_checks_without_a_plane(self):
        result = gate.query_federation_assurance_gate(self.value, resource="checks", plane="runtime", limit=64)
        self.assertEqual(result.total_count, 0)

    def test_severity_filter_selects_blocker_findings(self):
        result = gate.query_federation_assurance_gate(self.value, resource="findings", severity="blocker", limit=64)
        self.assertTrue(result.items)
        self.assertTrue(all(row["severity"] == "blocker" for row in result.items))

    def test_passed_filter_selects_passed_findings(self):
        result = gate.query_federation_assurance_gate(self.value, resource="findings", passed=True, limit=64)
        self.assertTrue(result.items)
        self.assertTrue(all(row["passed"] is True for row in result.items))

    def test_failed_filter_selects_failed_findings(self):
        result = gate.query_federation_assurance_gate(self.value, resource="findings", passed=False, limit=64)
        self.assertTrue(result.items)
        self.assertTrue(all(row["passed"] is False for row in result.items))

    def test_text_filter_matches_case_insensitively_across_row_json(self):
        result = gate.query_federation_assurance_gate(self.value, resource="findings", text="RUNTIME", limit=64)
        self.assertTrue(result.items)
        self.assertTrue(all("runtime" in canonical_json(row).casefold() for row in result.items))

    def test_offset_and_limit_produce_deterministic_pages(self):
        first = gate.query_federation_assurance_gate(self.value, resource="findings", offset=0, limit=3)
        second = gate.query_federation_assurance_gate(self.value, resource="findings", offset=3, limit=3)
        self.assertEqual(first.total_count, second.total_count)
        self.assertEqual(first.returned_count, 3)
        self.assertEqual(second.returned_count, 3)
        self.assertEqual(first.items[-1]["ordinal"] + 1, second.items[0]["ordinal"])

    def test_offset_past_end_returns_zero_rows(self):
        result = gate.query_federation_assurance_gate(self.value, resource="findings", offset=64, limit=3)
        self.assertEqual(result.total_count, 10)
        self.assertEqual(result.returned_count, 0)
        self.assertEqual(result.items, ())

    def test_query_rejects_unknown_resource(self):
        with self.assertRaises(ValidationError):
            gate.query_federation_assurance_gate(self.value, resource="unknown")

    def test_query_rejects_negative_offset(self):
        with self.assertRaises(ValidationError):
            gate.query_federation_assurance_gate(self.value, resource="findings", offset=-1)

    def test_query_rejects_zero_limit(self):
        with self.assertRaises(ValidationError):
            gate.query_federation_assurance_gate(self.value, resource="findings", limit=0)

    def test_query_rejects_limit_above_bound(self):
        with self.assertRaises(ValidationError):
            gate.query_federation_assurance_gate(self.value, resource="findings", limit=gate.MAX_QUERY_ITEMS + 1)

    def test_query_rejects_unknown_plane(self):
        with self.assertRaises(ValidationError):
            gate.query_federation_assurance_gate(self.value, resource="findings", plane="unknown")

    def test_query_rejects_unknown_severity(self):
        with self.assertRaises(ValidationError):
            gate.query_federation_assurance_gate(self.value, resource="findings", severity="unknown")

    def test_typed_query_cannot_be_combined_with_keyword_filters(self):
        typed = gate.FederationGateQuery(resource="findings")
        with self.assertRaises(ValidationError):
            gate.query_federation_assurance_gate(self.value, typed, limit=5)

    def test_query_result_rejects_tampered_item_count(self):
        result = gate.query_federation_assurance_gate(self.value, resource="findings", limit=3)
        body = result.to_dict()
        body["returned_count"] += 1
        with self.assertRaises(ValidationError):
            gate.gate_query_from_mapping(body)

    def test_query_result_rejects_tampered_query_address(self):
        result = gate.query_federation_assurance_gate(self.value, resource="findings", limit=3)
        body = result.to_dict()
        body["content_address"] = "tampered:query"
        with self.assertRaises(ValidationError):
            gate.gate_query_from_mapping(body)

    def test_query_json_round_trip(self):
        result = gate.query_federation_assurance_gate(self.value, resource="failed-findings", limit=64)
        self.assertEqual(json.loads(gate.query_json(result)), result.to_dict())

    def test_query_csv_is_stable_for_nonempty_result(self):
        result = gate.query_federation_assurance_gate(self.value, resource="failed-findings", limit=64)
        raw = gate.query_csv(result)
        self.assertIn("finding_id", raw)
        self.assertEqual(len(raw.splitlines()) - 1, result.returned_count)

    def test_query_markdown_is_stable(self):
        result = gate.query_federation_assurance_gate(self.value, resource="failed-findings", limit=64)
        raw = gate.render_query_markdown(result)
        self.assertIn("# Decision Assurance History Series Release Registry Federation Gate Query", raw)
        self.assertIn("## Summary", raw)


class FederationGateContractSchemaTests(FederationGateFixture):
    def test_finding_schema_is_closed(self):
        schema = gate.finding_schema()
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["title"], "FederationAssuranceFinding")
        self.assertEqual(set(schema["required"]), set(schema["properties"]))

    def test_assurance_schema_is_closed_and_bounded(self):
        schema = gate.assurance_schema()
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["findings"]["maxItems"], gate.MAX_FINDINGS)
        self.assertEqual(schema["properties"]["finding_count"]["maximum"], gate.MAX_FINDINGS)

    def test_gate_check_schema_is_closed(self):
        schema = gate.gate_check_schema()
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["title"], "FederationGateCheck")
        self.assertEqual(set(schema["required"]), set(schema["properties"]))

    def test_gate_schema_is_closed_and_bounded(self):
        schema = gate.gate_schema()
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["checks"]["maxItems"], gate.MAX_CHECKS)
        self.assertEqual(schema["properties"]["check_count"]["maximum"], gate.MAX_CHECKS)

    def test_bundle_schema_references_both_projections(self):
        schema = gate.assurance_gate_schema()
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["required"]), {"assurance", "gate"})
        self.assertIn("assurance", schema["$defs"])
        self.assertIn("gate", schema["$defs"])

    def test_query_schema_exposes_all_resources_and_filters(self):
        schema = gate.query_schema()
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(tuple(schema["properties"]["resource"]["enum"]), gate.FederationGateQuery.RESOURCES)
        self.assertIn("plane", schema["properties"])
        self.assertIn("severity", schema["properties"])
        self.assertIn("passed", schema["properties"])
        self.assertIn("text", schema["properties"])

    def test_manifest_schema_exposes_exact_file_count(self):
        schema = gate.manifest_schema()
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["files"]["const"], list(gate.FILES))
        self.assertEqual(schema["properties"]["artifact_count"]["const"], 2)

    def test_capabilities_describe_every_public_gate_contract(self):
        capabilities = gate.federation_assurance_gate_capabilities()
        self.assertEqual(capabilities["version"], gate.VERSION)
        self.assertEqual(capabilities["boundary"], gate.BOUNDARY)
        self.assertEqual(capabilities["assurance"]["finding_count"], 10)
        self.assertEqual(capabilities["gate"]["check_count"], 8)
        self.assertEqual(capabilities["package"]["files"], list(gate.FILES))
        self.assertEqual(capabilities["queries"]["resources"], list(gate.FederationGateQuery.RESOURCES))
        self.assertFalse(capabilities["public_boundary"]["source_paths"])
        self.assertFalse(capabilities["public_boundary"]["nested_payloads"])
        self.assertTrue(capabilities["public_boundary"]["identity_free"])

    def test_capability_projection_has_no_forbidden_keys(self):
        self.assert_public_projection(gate.federation_assurance_gate_capabilities())

    def test_contract_builders_return_fresh_mappings(self):
        builders = (
            gate.finding_schema,
            gate.assurance_schema,
            gate.gate_check_schema,
            gate.gate_schema,
            gate.assurance_gate_schema,
            gate.query_schema,
            gate.manifest_schema,
            gate.federation_assurance_gate_capabilities,
        )
        for builder in builders:
            with self.subTest(builder=builder.__name__):
                first = builder()
                second = builder()
                self.assertEqual(first, second)
                self.assertIsNot(first, second)


class FederationGateCliTests(FederationGateFixture):
    def setUp(self):
        super().setUp()
        self.value = self.build_gate(self.ready_source)

    def test_cli_builds_and_persists_a_gate_from_a_federation_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.persist_source(self.ready_source, root / "source")
            destination = root / "gate"
            status, output = self.capture_cli([
                gate_command(),
                "--input", str(source),
                "--destination", str(destination),
                "--format", "summary",
            ])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output)["state"], "promote")
            self.assertEqual(json.loads(output)["check_count"], 8)
            self.assertEqual({item.name for item in destination.iterdir()}, set(gate.FILES))

    def test_cli_gate_returns_nonzero_for_held_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.persist_source(self.held_source, root / "source")
            status, output = self.capture_cli([gate_command(), "--input", str(source), "--format", "summary"])
            self.assertEqual(status, 2)
            self.assertEqual(json.loads(output)["state"], "hold")

    def test_cli_gate_returns_nonzero_for_blocked_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.persist_source(self.blocked_source, root / "source")
            status, output = self.capture_cli([gate_command(), "--input", str(source), "--format", "summary"])
            self.assertEqual(status, 2)
            self.assertEqual(json.loads(output)["state"], "block")

    def test_cli_emits_json_csv_and_markdown_gate_projections(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.persist_source(self.ready_source, root / "source")
            destination = root / "gate"
            self.capture_cli([gate_command(), "--input", str(source), "--destination", str(destination), "--format", "summary"])
            for output_format, marker in (("json", '"assurance"'), ("csv", "ordinal,check_id"), ("markdown", "# Decision Assurance")):
                with self.subTest(output_format=output_format):
                    status, output = self.capture_cli([gate_command(), "--input", str(source), "--format", output_format])
                    self.assertEqual(status, 0)
                    self.assertIn(marker, output)

    def test_cli_verifies_persisted_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.persist_source(self.ready_source, root / "source")
            destination = root / "gate"
            self.capture_cli([gate_command(), "--input", str(source), "--destination", str(destination)])
            status, output = self.capture_cli([gate_command() + "-verify", "--input", str(destination)])
            self.assertEqual(status, 0)
            self.assertTrue(json.loads(output)["release_ready"])

    def test_cli_queries_json_csv_and_markdown(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.persist_source(self.held_source, root / "source")
            destination = root / "gate"
            self.capture_cli([gate_command(), "--input", str(source), "--destination", str(destination)])
            cases = (("json", '"items"'), ("csv", "finding_id"), ("markdown", "# Decision Assurance"))
            for output_format, marker in cases:
                with self.subTest(output_format=output_format):
                    status, output = self.capture_cli([gate_command() + "-query", "--input", str(destination), "--resource", "failed-findings", "--format", output_format])
                    self.assertEqual(status, 0)
                    self.assertIn(marker, output)

    def test_cli_query_accepts_plane_severity_passed_text_and_page_filters(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.persist_source(self.held_source, root / "source")
            destination = root / "gate"
            self.capture_cli([gate_command(), "--input", str(source), "--destination", str(destination)])
            status, output = self.capture_cli([
                gate_command() + "-query", "--input", str(destination), "--resource", "findings",
                "--plane", "runtime", "--severity", "warning", "--text", "release",
                "--offset", "0", "--limit", "10",
            ])
            self.assertEqual(status, 0)
            body = json.loads(output)
            self.assertTrue(all(item["plane"] == "runtime" for item in body["items"]))
            self.assertTrue(all(item["severity"] == "warning" for item in body["items"]))

    def test_cli_emits_all_contract_commands(self):
        suffixes = ("schema", "assurance-schema", "finding-schema", "gate-schema", "gate-check-schema", "query-schema", "manifest-schema", "capabilities")
        for suffix in suffixes:
            with self.subTest(suffix=suffix):
                status, output = self.capture_cli([gate_command() + "-" + suffix])
                self.assertEqual(status, 0)
                self.assertTrue(output.strip())

    def test_cli_writes_output_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.persist_source(self.ready_source, root / "source")
            output = root / "summary.json"
            status, stdout = self.capture_cli([gate_command(), "--input", str(source), "--format", "summary", "--output", str(output)])
            self.assertEqual(status, 0)
            self.assertEqual(stdout, "")
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["state"], "promote")


class FederationGateApiTests(FederationGateFixture):
    def setUp(self):
        super().setUp()
        self.value = self.build_gate(self.ready_source)

    def test_api_builds_gate_from_source_and_reads_summary(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.persist_source(self.ready_source, root / "source")
            server = create_server("127.0.0.1", 0)
            server.glio_assurance_history_series_release_registry_federation_directory = str(source)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = api_gate_base(server)
                body = json.loads(urlopen(url + "?format=summary", timeout=10).read().decode())
                self.assertEqual(body["state"], "promote")
                self.assertTrue(body["release_ready"])
                self.assertEqual(body["check_count"], 8)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)

    def test_api_reads_persisted_gate_verify_and_query_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.persist_source(self.ready_source, root / "source")
            persisted = self.write_gate(self.value, root / "gate")
            server = create_server("127.0.0.1", 0)
            server.glio_assurance_history_series_release_registry_federation_directory = str(source)
            server.glio_assurance_history_series_release_registry_federation_gate_directory = str(persisted)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = api_gate_base(server)
                verified = json.loads(urlopen(url + "/verify?input=" + str(persisted), timeout=10).read().decode())
                self.assertTrue(verified["release_ready"])
                query = json.loads(urlopen(url + "/query?input=" + str(persisted) + "&resource=checks", timeout=10).read().decode())
                self.assertEqual(query["returned_count"], 8)
                schema = json.loads(urlopen(url + "/schema", timeout=10).read().decode())
                self.assertFalse(schema["additionalProperties"])
                capabilities = json.loads(urlopen(url + "/capabilities", timeout=10).read().decode())
                self.assertEqual(capabilities["package"]["files"], list(gate.FILES))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)

    def test_api_supports_assurance_release_csv_and_markdown_projections(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.persist_source(self.ready_source, root / "source")
            server = create_server("127.0.0.1", 0)
            server.glio_assurance_history_series_release_registry_federation_directory = str(source)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = api_gate_base(server)
                assurance = json.loads(urlopen(base + "/assurance", timeout=10).read().decode())
                self.assertEqual(assurance["finding_count"], 10)
                release = json.loads(urlopen(base + "/release", timeout=10).read().decode())
                self.assertEqual(release["check_count"], 8)
                csv_body = urlopen(base + "?format=csv", timeout=10).read().decode()
                self.assertIn("ordinal,check_id", csv_body)
                markdown_body = urlopen(base + "?format=markdown", timeout=10).read().decode()
                self.assertIn("# Decision Assurance", markdown_body)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)

    def test_api_returns_unprocessable_for_held_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.persist_source(self.held_source, root / "source")
            server = create_server("127.0.0.1", 0)
            server.glio_assurance_history_series_release_registry_federation_directory = str(source)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with self.assertRaises(HTTPError) as context:
                    urlopen(api_gate_base(server) + "?format=summary", timeout=10)
                self.assertEqual(context.exception.code, 422)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)


class FederationGateFailureMatrixTests(FederationGateFixture):
    def setUp(self):
        super().setUp()
        self.value = self.build_gate(self.ready_source)

    def assert_fails_after_mutation(self, document_name, mutate):
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.write_gate(self.value, Path(temporary) / "gate")
            path = destination / document_name
            body = json.loads(path.read_text(encoding="utf-8"))
            mutate(body)
            path.write_bytes(canonical_bytes(body))
            with self.assertRaises(ValidationError):
                gate.load_federation_assurance_gate(destination)

    def test_every_assurance_summary_field_is_protected_by_address(self):
        fields = tuple(self.value.assurance.summary())
        for field in fields:
            with self.subTest(field=field):
                def mutate(body, field=field):
                    if isinstance(body[field], bool):
                        body[field] = not body[field]
                    elif isinstance(body[field], int):
                        body[field] += 1
                    elif isinstance(body[field], str):
                        body[field] = "tampered"

                self.assert_fails_after_mutation(gate.ASSURANCE_NAME, mutate)

    def test_every_gate_summary_field_is_protected_by_address(self):
        fields = tuple(self.value.gate.summary())
        for field in fields:
            with self.subTest(field=field):
                def mutate(body, field=field):
                    if isinstance(body[field], bool):
                        body[field] = not body[field]
                    elif isinstance(body[field], int):
                        body[field] += 1
                    elif isinstance(body[field], str):
                        body[field] = "tampered"

                self.assert_fails_after_mutation(gate.GATE_NAME, mutate)

    def test_each_finding_field_is_protected_by_item_address(self):
        fields = tuple(self.value.assurance.findings[0].to_dict())
        for field in fields:
            with self.subTest(field=field):
                def mutate(body, field=field):
                    if field == "ordinal":
                        body["findings"][0][field] += 1
                    elif isinstance(body["findings"][0][field], bool):
                        body["findings"][0][field] = not body["findings"][0][field]
                    else:
                        body["findings"][0][field] = "tampered"

                self.assert_fails_after_mutation(gate.ASSURANCE_NAME, mutate)

    def test_each_check_field_is_protected_by_item_address(self):
        fields = tuple(self.value.gate.checks[0].to_dict())
        for field in fields:
            with self.subTest(field=field):
                def mutate(body, field=field):
                    if field == "ordinal":
                        body["checks"][0][field] += 1
                    elif isinstance(body["checks"][0][field], bool):
                        body["checks"][0][field] = not body["checks"][0][field]
                    else:
                        body["checks"][0][field] = "tampered"

                self.assert_fails_after_mutation(gate.GATE_NAME, mutate)

    def test_reordered_findings_are_rejected(self):
        self.assert_fails_after_mutation(gate.ASSURANCE_NAME, lambda body: body["findings"].reverse())

    def test_reordered_checks_are_rejected(self):
        self.assert_fails_after_mutation(gate.GATE_NAME, lambda body: body["checks"].reverse())

    def test_duplicate_finding_ordinals_are_rejected(self):
        self.assert_fails_after_mutation(gate.ASSURANCE_NAME, lambda body: body["findings"][1].update(ordinal=0))

    def test_duplicate_check_ordinals_are_rejected(self):
        self.assert_fails_after_mutation(gate.GATE_NAME, lambda body: body["checks"][1].update(ordinal=0))

    def test_nested_finding_unknown_field_is_rejected(self):
        self.assert_fails_after_mutation(gate.ASSURANCE_NAME, lambda body: body["findings"][0].update(unexpected=True))

    def test_nested_check_unknown_field_is_rejected(self):
        self.assert_fails_after_mutation(gate.GATE_NAME, lambda body: body["checks"][0].update(unexpected=True))

    def test_assurance_document_with_gate_payload_is_rejected(self):
        self.assert_fails_after_mutation(gate.ASSURANCE_NAME, lambda body: body.update(gate=self.value.gate.to_dict()))

    def test_gate_document_with_assurance_payload_is_rejected(self):
        self.assert_fails_after_mutation(gate.GATE_NAME, lambda body: body.update(assurance=self.value.assurance.to_dict()))

    def test_gate_assurance_linkage_is_protected(self):
        self.assert_fails_after_mutation(gate.GATE_NAME, lambda body: body.update(assurance_address="tampered:assurance"))

    def test_gate_source_linkage_is_protected(self):
        for field in ("federation_address", "runtime_address"):
            with self.subTest(field=field):
                self.assert_fails_after_mutation(gate.GATE_NAME, lambda body, field=field: body.update({field: "tampered:" + field}))

    def test_assurance_source_linkage_is_protected(self):
        for field in ("federation_address", "runtime_address"):
            with self.subTest(field=field):
                self.assert_fails_after_mutation(gate.ASSURANCE_NAME, lambda body, field=field: body.update({field: "tampered:" + field}))

    def test_extra_directory_entry_is_rejected_even_when_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.write_gate(self.value, Path(temporary) / "gate")
            (destination / "extra.json").write_bytes(canonical_bytes({"ok": True}))
            with self.assertRaises(ValidationError):
                gate.load_federation_assurance_gate(destination)


class FederationGateConstructorMatrixTests(unittest.TestCase):
    """Exercise scalar and boundary validation without rebuilding source data per case."""

    @classmethod
    def setUpClass(cls):
        fixture = FederationFixture("runTest")
        source = fixture.build((fixture.ready_registry("constructor-one"), fixture.ready_registry("constructor-two")))
        cls.value = gate.build_federation_assurance_gate(source)

    def finding_body(self):
        return self.value.assurance.findings[0].to_dict()

    def check_body(self):
        return self.value.gate.checks[0].to_dict()

    def assurance_body(self):
        return self.value.assurance.to_dict()

    def gate_body(self):
        return self.value.gate.to_dict()

    def query_body(self):
        return gate.query_federation_assurance_gate(self.value, resource="findings", limit=2).to_dict()

    def assert_finding_invalid(self, field, replacement):
        body = self.finding_body()
        body[field] = replacement
        with self.assertRaises(ValidationError):
            gate.finding_from_mapping(body)

    def assert_check_invalid(self, field, replacement):
        body = self.check_body()
        body[field] = replacement
        with self.assertRaises(ValidationError):
            gate.gate_check_from_mapping(body)

    def assert_assurance_invalid(self, field, replacement):
        body = self.assurance_body()
        body[field] = replacement
        with self.assertRaises(ValidationError):
            gate.assurance_from_mapping(body)

    def assert_gate_invalid(self, field, replacement):
        body = self.gate_body()
        body[field] = replacement
        with self.assertRaises(ValidationError):
            gate.gate_from_mapping(body)

    def assert_query_invalid(self, field, replacement):
        body = self.query_body()
        body["query"][field] = replacement
        with self.assertRaises(ValidationError):
            gate.gate_query_from_mapping(body)

    def test_finding_rejects_none_ordinal(self):
        self.assert_finding_invalid("ordinal", None)

    def test_finding_rejects_negative_ordinal(self):
        self.assert_finding_invalid("ordinal", -1)

    def test_finding_rejects_ordinal_above_bound(self):
        self.assert_finding_invalid("ordinal", gate.MAX_FINDINGS)

    def test_finding_rejects_boolean_ordinal(self):
        self.assert_finding_invalid("ordinal", True)

    def test_finding_rejects_empty_id(self):
        self.assert_finding_invalid("finding_id", "")

    def test_finding_rejects_non_string_id(self):
        self.assert_finding_invalid("finding_id", 3)

    def test_finding_rejects_empty_plane(self):
        self.assert_finding_invalid("plane", "")

    def test_finding_rejects_unknown_plane(self):
        self.assert_finding_invalid("plane", "other")

    def test_finding_rejects_empty_severity(self):
        self.assert_finding_invalid("severity", "")

    def test_finding_rejects_unknown_severity(self):
        self.assert_finding_invalid("severity", "required")

    def test_finding_rejects_non_boolean_passed(self):
        self.assert_finding_invalid("passed", 1)

    def test_finding_rejects_empty_detail(self):
        self.assert_finding_invalid("detail", "")

    def test_finding_rejects_non_string_detail(self):
        self.assert_finding_invalid("detail", {})

    def test_finding_rejects_empty_evidence_address(self):
        self.assert_finding_invalid("evidence_address", "")

    def test_finding_rejects_empty_content_address(self):
        self.assert_finding_invalid("content_address", "")

    def test_finding_rejects_non_string_content_address(self):
        self.assert_finding_invalid("content_address", None)

    def test_gate_check_rejects_none_ordinal(self):
        self.assert_check_invalid("ordinal", None)

    def test_gate_check_rejects_negative_ordinal(self):
        self.assert_check_invalid("ordinal", -1)

    def test_gate_check_rejects_ordinal_above_bound(self):
        self.assert_check_invalid("ordinal", gate.MAX_CHECKS)

    def test_gate_check_rejects_boolean_ordinal(self):
        self.assert_check_invalid("ordinal", False)

    def test_gate_check_rejects_empty_id(self):
        self.assert_check_invalid("check_id", "")

    def test_gate_check_rejects_non_string_id(self):
        self.assert_check_invalid("check_id", 4)

    def test_gate_check_rejects_unknown_severity(self):
        self.assert_check_invalid("severity", "optional")

    def test_gate_check_rejects_none_passed(self):
        self.assert_check_invalid("passed", None)

    def test_gate_check_rejects_empty_detail(self):
        self.assert_check_invalid("detail", "")

    def test_gate_check_rejects_non_string_evidence_address(self):
        self.assert_check_invalid("evidence_address", 4)

    def test_gate_check_rejects_empty_content_address(self):
        self.assert_check_invalid("content_address", "")

    def test_assurance_rejects_wrong_version(self):
        self.assert_assurance_invalid("version", "wrong-version")

    def test_assurance_rejects_wrong_boundary(self):
        self.assert_assurance_invalid("boundary", "wrong-boundary")

    def test_assurance_rejects_negative_finding_count(self):
        self.assert_assurance_invalid("finding_count", -1)

    def test_assurance_rejects_finding_count_above_bound(self):
        self.assert_assurance_invalid("finding_count", gate.MAX_FINDINGS + 1)

    def test_assurance_rejects_boolean_finding_count(self):
        self.assert_assurance_invalid("finding_count", True)

    def test_assurance_rejects_negative_passed_count(self):
        self.assert_assurance_invalid("passed_count", -1)

    def test_assurance_rejects_negative_failed_count(self):
        self.assert_assurance_invalid("failed_count", -1)

    def test_assurance_rejects_negative_blocker_count(self):
        self.assert_assurance_invalid("blocker_count", -1)

    def test_assurance_rejects_negative_warning_count(self):
        self.assert_assurance_invalid("warning_count", -1)

    def test_assurance_rejects_non_boolean_accepted(self):
        self.assert_assurance_invalid("accepted", 1)

    def test_assurance_rejects_non_boolean_release_ready(self):
        self.assert_assurance_invalid("release_ready", 0)

    def test_assurance_rejects_unknown_state(self):
        self.assert_assurance_invalid("state", "ready")

    def test_assurance_rejects_empty_findings_array(self):
        self.assert_assurance_invalid("findings", [])

    def test_assurance_rejects_non_array_findings(self):
        self.assert_assurance_invalid("findings", {})

    def test_assurance_rejects_empty_federation_address(self):
        self.assert_assurance_invalid("federation_address", "")

    def test_assurance_rejects_empty_runtime_address(self):
        self.assert_assurance_invalid("runtime_address", "")

    def test_gate_rejects_empty_gate_id(self):
        self.assert_gate_invalid("gate_id", "")

    def test_gate_rejects_non_string_gate_id(self):
        self.assert_gate_invalid("gate_id", None)

    def test_gate_rejects_wrong_version(self):
        self.assert_gate_invalid("version", "wrong-version")

    def test_gate_rejects_wrong_boundary(self):
        self.assert_gate_invalid("boundary", "wrong-boundary")

    def test_gate_rejects_empty_assurance_address(self):
        self.assert_gate_invalid("assurance_address", "")

    def test_gate_rejects_unknown_state(self):
        self.assert_gate_invalid("state", "ready")

    def test_gate_rejects_decision_drift(self):
        body = self.gate_body()
        body["decision"] = "hold"
        with self.assertRaises(ValidationError):
            gate.gate_from_mapping(body)

    def test_gate_rejects_negative_check_count(self):
        self.assert_gate_invalid("check_count", -1)

    def test_gate_rejects_check_count_above_bound(self):
        self.assert_gate_invalid("check_count", gate.MAX_CHECKS + 1)

    def test_gate_rejects_negative_passed_count(self):
        self.assert_gate_invalid("passed_count", -1)

    def test_gate_rejects_negative_failed_count(self):
        self.assert_gate_invalid("failed_count", -1)

    def test_gate_rejects_negative_required_failure_count(self):
        self.assert_gate_invalid("required_failure_count", -1)

    def test_gate_rejects_negative_optional_failure_count(self):
        self.assert_gate_invalid("optional_failure_count", -1)

    def test_gate_rejects_non_boolean_accepted(self):
        self.assert_gate_invalid("accepted", 1)

    def test_gate_rejects_non_boolean_release_ready(self):
        self.assert_gate_invalid("release_ready", 0)

    def test_gate_rejects_empty_checks_array(self):
        self.assert_gate_invalid("checks", [])

    def test_gate_rejects_non_array_checks(self):
        self.assert_gate_invalid("checks", {})

    def test_query_rejects_unknown_resource(self):
        self.assert_query_invalid("resource", "other")

    def test_query_rejects_unknown_plane(self):
        self.assert_query_invalid("plane", "other")

    def test_query_rejects_unknown_severity(self):
        self.assert_query_invalid("severity", "other")

    def test_query_rejects_non_boolean_passed(self):
        self.assert_query_invalid("passed", "yes")

    def test_query_rejects_non_string_text(self):
        self.assert_query_invalid("text", 4)

    def test_query_rejects_negative_offset(self):
        self.assert_query_invalid("offset", -1)

    def test_query_rejects_offset_above_bound(self):
        self.assert_query_invalid("offset", gate.MAX_QUERY_ITEMS + 1)

    def test_query_rejects_non_integer_offset(self):
        self.assert_query_invalid("offset", "0")

    def test_query_rejects_zero_limit(self):
        self.assert_query_invalid("limit", 0)

    def test_query_rejects_limit_above_bound(self):
        self.assert_query_invalid("limit", gate.MAX_QUERY_ITEMS + 1)

    def test_query_rejects_non_integer_limit(self):
        self.assert_query_invalid("limit", "2")

    def test_query_result_rejects_negative_total_count(self):
        body = self.query_body()
        body["total_count"] = -1
        with self.assertRaises(ValidationError):
            gate.gate_query_from_mapping(body)

    def test_query_result_rejects_negative_returned_count(self):
        body = self.query_body()
        body["returned_count"] = -1
        with self.assertRaises(ValidationError):
            gate.gate_query_from_mapping(body)

    def test_query_result_rejects_non_array_items(self):
        body = self.query_body()
        body["items"] = {}
        with self.assertRaises(ValidationError):
            gate.gate_query_from_mapping(body)

    def test_query_result_rejects_empty_gate_address(self):
        body = self.query_body()
        body["gate_address"] = ""
        with self.assertRaises(ValidationError):
            gate.gate_query_from_mapping(body)

    def test_query_result_rejects_empty_assurance_address(self):
        body = self.query_body()
        body["assurance_address"] = ""
        with self.assertRaises(ValidationError):
            gate.gate_query_from_mapping(body)

    def test_query_result_rejects_non_string_content_address(self):
        body = self.query_body()
        body["content_address"] = None
        with self.assertRaises(ValidationError):
            gate.gate_query_from_mapping(body)

    def test_all_public_enums_are_string_values(self):
        for enum_type in (gate.GateState, gate.FindingSeverity, gate.GatePlane):
            with self.subTest(enum=enum_type.__name__):
                self.assertTrue(all(isinstance(item.value, str) for item in enum_type))

    def test_all_public_enum_values_are_unique(self):
        for enum_type in (gate.GateState, gate.FindingSeverity, gate.GatePlane):
            with self.subTest(enum=enum_type.__name__):
                values = [item.value for item in enum_type]
                self.assertEqual(len(values), len(set(values)))

    def test_all_finding_ids_are_unique(self):
        ids = [item.finding_id for item in self.value.assurance.findings]
        self.assertEqual(len(ids), len(set(ids)))

    def test_all_check_ids_are_unique(self):
        ids = [item.check_id for item in self.value.gate.checks]
        self.assertEqual(len(ids), len(set(ids)))

    def test_all_finding_evidence_addresses_are_nonempty(self):
        self.assertTrue(all(item.evidence_address for item in self.value.assurance.findings))

    def test_all_check_evidence_addresses_are_nonempty(self):
        self.assertTrue(all(item.evidence_address for item in self.value.gate.checks))

    def test_all_finding_details_are_bounded(self):
        self.assertTrue(all(0 < len(item.detail) <= 2048 for item in self.value.assurance.findings))

    def test_all_check_details_are_bounded(self):
        self.assertTrue(all(0 < len(item.detail) <= 2048 for item in self.value.gate.checks))

    def test_assurance_failed_count_equals_failed_findings(self):
        self.assertEqual(self.value.assurance.failed_count, sum(not item.passed for item in self.value.assurance.findings))

    def test_gate_failed_count_equals_failed_checks(self):
        self.assertEqual(self.value.gate.failed_count, sum(not item.passed for item in self.value.gate.checks))

    def test_assurance_blockers_and_warnings_partition_failures(self):
        self.assertEqual(
            self.value.assurance.failed_count,
            self.value.assurance.blocker_count + self.value.assurance.warning_count,
        )

    def test_gate_required_and_optional_failures_partition_failures(self):
        self.assertEqual(
            self.value.gate.failed_count,
            self.value.gate.required_failure_count + self.value.gate.optional_failure_count,
        )

    def test_assurance_ready_state_requires_no_failures(self):
        self.assertEqual(self.value.assurance.release_ready, self.value.assurance.failed_count == 0)

    def test_gate_promote_state_requires_no_failures(self):
        self.assertEqual(self.value.gate.release_ready, self.value.gate.state == "promote")

    def test_bundle_contains_only_assurance_and_gate_documents(self):
        self.assertEqual(set(self.value.to_dict()), {"assurance", "gate"})

    def test_bundle_assurance_address_matches_gate_link(self):
        self.assertEqual(self.value.assurance.content_address, self.value.gate.assurance_address)

    def test_bundle_source_addresses_match(self):
        self.assertEqual(self.value.assurance.federation_address, self.value.gate.federation_address)
        self.assertEqual(self.value.assurance.runtime_address, self.value.gate.runtime_address)

    def test_bundle_acceptance_is_conserved(self):
        self.assertEqual(self.value.assurance.accepted, self.value.gate.accepted)

    def test_bundle_readiness_is_conserved(self):
        self.assertEqual(self.value.assurance.release_ready, self.value.gate.release_ready)


class DownloadedGateDemoTests(unittest.TestCase):
    """Verify the operator-facing demo stays data-driven and path-free."""

    @classmethod
    def setUpClass(cls):
        fixture = FederationFixture("runTest")
        cls.fixture = fixture
        cls.registries = (
            fixture.ready_registry("downloaded-alpha"),
            fixture.held_registry("downloaded-beta"),
        )

    def write_registries(self, root):
        paths = []
        for registry_value in self.registries:
            path = root / registry_value.registry_id.removeprefix("registry:")
            registry.write_decision_assurance_history_series_release_registry(registry_value, path)
            paths.append(path)
        return tuple(paths)

    def test_explicit_downloaded_inputs_build_a_gate_without_synthetic_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = self.write_registries(Path(temporary))
            source, value = build_downloaded_gate(paths, federation_id="demo:federation", gate_id="demo:gate")
            self.assertEqual(source.federation.member_count, 2)
            self.assertEqual(value.gate.gate_id, "demo:gate")
            self.assertEqual(value.gate.state, "hold")
            self.assertEqual({member.registry_id for member in source.federation.members}, {"registry:downloaded-alpha", "registry:downloaded-beta"})

    def test_root_discovery_ignores_unrelated_download_notes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = self.write_registries(root)
            (root / "download-notes.txt").write_text("source notes", encoding="utf-8")
            self.assertEqual(discover_downloaded_registries(root), paths)

    def test_recursive_root_discovery_reaches_nested_download_groups(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            nested = root / "institution-a"
            nested.mkdir()
            for registry_value in self.registries:
                registry.write_decision_assurance_history_series_release_registry(registry_value, nested / registry_value.registry_id.removeprefix("registry:"))
            self.assertEqual(discover_downloaded_registries(root, recursive=True), tuple(sorted(nested.iterdir())))

    def test_inspection_retains_only_stable_registry_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = self.write_registries(Path(temporary))
            previews = inspect_downloaded_registries(paths)
            self.assertEqual(len(previews), 2)
            self.assertEqual({item["registry_id"] for item in previews}, {"registry:downloaded-alpha", "registry:downloaded-beta"})
            self.assertTrue(all(set(item) == {"directory_name", "registry_id", "registry_address", "entry_count", "accepted", "release_ready", "state"} for item in previews))

    def test_run_demo_persists_two_portable_packages(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "downloads"
            root.mkdir()
            self.write_registries(root)
            output = Path(temporary) / "output"
            run = run_downloaded_gate_demo(root=root, output=output)
            self.assertEqual(run.root, root)
            self.assertEqual(run.registry_directories, tuple(sorted(root.iterdir())))
            self.assertEqual({item.name for item in run.federation_directory.iterdir()}, set(federation.FILES))
            self.assertEqual({item.name for item in run.gate_directory.iterdir()}, set(gate.FILES))
            self.assertEqual(gate.load_federation_assurance_gate(run.gate_directory).to_dict(), run.gate.to_dict())

    def test_run_demo_rejects_combined_root_and_explicit_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_registries(root)
            with self.assertRaises(ValidationError):
                run_downloaded_gate_demo(root=root, directories=(root,))

    def test_run_demo_requires_one_source_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValidationError):
                run_downloaded_gate_demo(output=Path(temporary) / "output")

    def test_run_demo_rejects_empty_explicit_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValidationError):
                run_downloaded_gate_demo(directories=(), output=Path(temporary) / "output")

    def test_demo_summary_contains_addresses_and_no_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "downloads"
            root.mkdir()
            self.write_registries(root)
            run = run_downloaded_gate_demo(root=root, output=Path(temporary) / "output")
            summary = run.summary()
            self.assertEqual(summary["registry_count"], 2)
            self.assertIn("content_address", canonical_json(summary))
            self.assertNotIn(str(root), canonical_json(summary))

    def test_demo_json_rendering_is_complete(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = self.write_registries(root)
            source, value = build_downloaded_gate(paths)
            run = run_downloaded_gate_demo(directories=paths, output=Path(temporary) / "output")
            self.assertEqual(json.loads(render_downloaded_gate(run, "json")), value.to_dict())
            self.assertEqual(source.federation.member_count, 2)

    def test_demo_summary_rendering_is_canonical(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = self.write_registries(root)
            run = run_downloaded_gate_demo(directories=paths, output=Path(temporary) / "output")
            rendered = render_downloaded_gate(run, "summary")
            self.assertEqual(rendered, canonical_json(run.summary()))

    def test_demo_csv_and_markdown_renderings_are_available(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = self.write_registries(root)
            run = run_downloaded_gate_demo(directories=paths, output=Path(temporary) / "output")
            self.assertIn("ordinal,check_id", render_downloaded_gate(run, "csv"))
            self.assertIn("# Decision Assurance", render_downloaded_gate(run, "markdown"))

    def test_demo_rejects_duplicate_explicit_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = self.write_registries(root)
            with self.assertRaises(ValidationError):
                build_downloaded_gate((paths[0], paths[0]))

    def test_demo_rejects_non_directory_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "file.txt"
            path.write_text("not a registry", encoding="utf-8")
            with self.assertRaises(ValidationError):
                build_downloaded_gate((path,))

    def test_demo_argument_parser_accepts_root_mode(self):
        args = build_argument_parser().parse_args(["--root", "downloads", "--recursive"])
        self.assertEqual(args.root, "downloads")
        self.assertTrue(args.recursive)

    def test_demo_argument_parser_accepts_repeated_explicit_inputs(self):
        args = build_argument_parser().parse_args(["--input", "one", "--input", "two", "--format", "markdown"])
        self.assertEqual(args.input, ["one", "two"])
        self.assertEqual(args.format, "markdown")

    def test_demo_argument_parser_requires_source_mode(self):
        with self.assertRaises(SystemExit):
            build_argument_parser().parse_args([])

    def test_demo_argument_parser_rejects_both_source_modes(self):
        with self.assertRaises(SystemExit):
            build_argument_parser().parse_args(["--root", "one", "--input", "two"])

    def test_demo_output_can_be_overwritten_explicitly(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "downloads"
            root.mkdir()
            paths = self.write_registries(root)
            destination = Path(temporary) / "output"
            run_downloaded_gate_demo(directories=paths, output=destination)
            with self.assertRaises(ValidationError):
                run_downloaded_gate_demo(directories=paths, output=destination)
            replacement = run_downloaded_gate_demo(directories=paths, output=destination, overwrite=True)
            self.assertEqual(replacement.gate_directory.name, "gate")

    def test_demo_writes_optional_report_without_polluting_gate_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "downloads"
            root.mkdir()
            paths = self.write_registries(root)
            run = run_downloaded_gate_demo(directories=paths, output=Path(temporary) / "output")
            report = Path(temporary) / "report.md"
            report.write_text(render_downloaded_gate(run, "markdown"), encoding="utf-8")
            self.assertTrue(report.exists())
            self.assertEqual({item.name for item in run.gate_directory.iterdir()}, set(gate.FILES))

    def test_demo_gate_summary_is_held_when_one_downloaded_registry_is_held(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = self.write_registries(Path(temporary))
            run = run_downloaded_gate_demo(directories=paths, output=Path(temporary) / "output")
            self.assertEqual(run.gate.gate.state, "hold")
            self.assertTrue(run.gate.gate.accepted)
            self.assertFalse(run.gate.gate.release_ready)


class DownloadedGateDemoContractMatrixTests(unittest.TestCase):
    """Cover the downloaded-data runner's source selection and output contract."""

    @classmethod
    def setUpClass(cls):
        fixture = FederationFixture("runTest")
        cls.fixture = fixture
        cls.registry = fixture.ready_registry("demo-contract")

    def write_registry(self, root, name="registry"):
        path = Path(root) / name
        registry.write_decision_assurance_history_series_release_registry(self.registry, path)
        return path

    def test_explicit_source_has_one_registry_member(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            source, value = build_downloaded_gate((path,))
            self.assertEqual(source.federation.member_count, 1)
            self.assertEqual(value.gate.state, "promote")

    def test_explicit_source_preserves_custom_federation_id(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            source, _ = build_downloaded_gate((path,), federation_id="demo:federation-id")
            self.assertEqual(source.federation.federation_id, "demo:federation-id")

    def test_explicit_source_preserves_custom_gate_id(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            _, value = build_downloaded_gate((path,), gate_id="demo:gate-id")
            self.assertEqual(value.gate.gate_id, "demo:gate-id")

    def test_inspection_returns_the_loaded_registry_address(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            preview = inspect_downloaded_registries((path,))[0]
            self.assertEqual(preview["registry_address"], self.registry.content_address)

    def test_inspection_returns_the_loaded_registry_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            preview = inspect_downloaded_registries((path,))[0]
            self.assertEqual(preview["state"], "ready")
            self.assertEqual(preview["accepted"], self.registry.accepted_count == self.registry.entry_count)
            self.assertEqual(preview["release_ready"], self.registry.release_ready_count == self.registry.entry_count)

    def test_discovery_returns_sorted_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.write_registry(root, "alpha")
            second = self.write_registry(root, "zeta")
            self.assertEqual(discover_downloaded_registries(root), (first, second))

    def test_discovery_requires_an_existing_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "missing"
            with self.assertRaises(ValidationError):
                discover_downloaded_registries(missing)

    def test_discovery_rejects_a_root_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "root.txt"
            path.write_text("not a root", encoding="utf-8")
            with self.assertRaises(ValidationError):
                discover_downloaded_registries(path)

    def test_discovery_rejects_a_root_without_registry_packages(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "notes").mkdir()
            (root / "notes" / "readme.txt").write_text("notes", encoding="utf-8")
            with self.assertRaises(ValidationError):
                discover_downloaded_registries(root)

    def test_discovery_recursive_mode_ignores_non_registry_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            nested = root / "nested"
            nested.mkdir()
            path = self.write_registry(nested)
            (nested / "other").mkdir()
            self.assertEqual(discover_downloaded_registries(root, recursive=True), (path,))

    def test_duplicate_path_detection_is_case_stable(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            with self.assertRaises(ValidationError):
                build_downloaded_gate((path, path))

    def test_duplicate_path_detection_resolves_relative_aliases(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            alias = Path(temporary) / "." / path.name
            with self.assertRaises(ValidationError):
                build_downloaded_gate((path, alias))

    def test_runner_persists_federation_under_named_child_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "downloads"
            root.mkdir()
            path = self.write_registry(root)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual(run.federation_directory.name, "federation")
            self.assertEqual(run.federation_directory.parent.name, "output")

    def test_runner_persists_gate_under_named_child_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual(run.gate_directory.name, "gate")
            self.assertEqual(run.gate_directory.parent.name, "output")

    def test_runner_round_trip_reloads_the_federation(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            loaded = federation.load_federation(run.federation_directory)
            self.assertEqual(loaded.to_dict(), run.federation.to_dict())

    def test_runner_round_trip_reloads_the_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            loaded = gate.load_federation_assurance_gate(run.gate_directory)
            self.assertEqual(loaded.to_dict(), run.gate.to_dict())

    def test_runner_summary_reports_artifact_file_sets(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual(run.summary()["artifacts"]["federation_files"], list(federation.FILES))
            self.assertEqual(run.summary()["artifacts"]["gate_files"], list(gate.FILES))

    def test_runner_summary_reports_gate_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual(run.summary()["gate"]["state"], "promote")

    def test_runner_summary_reports_source_member_count(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual(run.summary()["federation"]["member_count"], 1)

    def test_runner_summary_never_contains_input_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertNotIn(str(path), canonical_json(run.summary()))

    def test_json_rendering_contains_assurance_and_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            document = json.loads(render_downloaded_gate(run, "json"))
            self.assertEqual(set(document), {"assurance", "gate"})

    def test_summary_rendering_contains_federation_rollup(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            document = json.loads(render_downloaded_gate(run, "summary"))
            self.assertIn("federation", document)
            self.assertIn("assurance", document)
            self.assertIn("gate", document)

    def test_csv_rendering_is_gate_check_csv(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual(render_downloaded_gate(run, "csv"), gate.gate_csv(run.gate.gate))

    def test_markdown_rendering_is_gate_markdown(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual(render_downloaded_gate(run, "markdown"), gate.render_assurance_gate_markdown(run.gate))

    def test_rendering_rejects_unknown_format(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            with self.assertRaises(ValidationError):
                render_downloaded_gate(run, "yaml")

    def test_parser_default_format_is_summary(self):
        args = build_argument_parser().parse_args(["--input", "registry"])
        self.assertEqual(args.format, "summary")

    def test_parser_default_output_is_nonempty(self):
        args = build_argument_parser().parse_args(["--input", "registry"])
        self.assertTrue(args.output)

    def test_parser_default_overwrite_is_false(self):
        args = build_argument_parser().parse_args(["--input", "registry"])
        self.assertFalse(args.allow_existing)

    def test_parser_accepts_custom_ids(self):
        args = build_argument_parser().parse_args(["--input", "registry", "--federation-id", "f", "--gate-id", "g"])
        self.assertEqual((args.federation_id, args.gate_id), ("f", "g"))

    def test_parser_accepts_report_path(self):
        args = build_argument_parser().parse_args(["--input", "registry", "--report", "report.json"])
        self.assertEqual(args.report, "report.json")

    def test_parser_accepts_all_formats(self):
        for output_format in ("json", "csv", "markdown", "summary"):
            with self.subTest(output_format=output_format):
                args = build_argument_parser().parse_args(["--input", "registry", "--format", output_format])
                self.assertEqual(args.format, output_format)

    def test_parser_rejects_unknown_format(self):
        with self.assertRaises(SystemExit):
            build_argument_parser().parse_args(["--input", "registry", "--format", "yaml"])

    def test_parser_rejects_unknown_option(self):
        with self.assertRaises(SystemExit):
            build_argument_parser().parse_args(["--input", "registry", "--unknown"])

    def test_gate_capability_file_count_matches_demo_layout(self):
        self.assertEqual(len(gate.FILES), 3)
        self.assertEqual(len(federation.FILES), 8)

    def test_gate_capability_queries_are_public(self):
        capabilities = gate.federation_assurance_gate_capabilities()
        self.assertTrue(capabilities["package"]["canonical_json"])
        self.assertTrue(capabilities["package"]["atomic_write"])

    def test_gate_capability_queries_are_bounded(self):
        capabilities = gate.federation_assurance_gate_capabilities()
        self.assertEqual(capabilities["queries"]["max_limit"], gate.MAX_QUERY_ITEMS)

    def test_gate_capability_states_are_promote_hold_block(self):
        self.assertEqual(tuple(gate.federation_assurance_gate_capabilities()["states"]), ("promote", "hold", "block"))

    def test_gate_capability_planes_include_boundary(self):
        self.assertIn("boundary", gate.federation_assurance_gate_capabilities()["planes"])

    def test_gate_capability_has_no_path_fields(self):
        encoded = canonical_json(gate.federation_assurance_gate_capabilities())
        self.assertNotIn('"path"', encoded.casefold())

    def test_gate_capability_has_no_identity_fields(self):
        encoded = canonical_json(gate.federation_assurance_gate_capabilities())
        for field in ("agent", "author", "language", "model", "user"):
            self.assertNotIn(f'"{field}"', encoded)

    def test_run_value_keeps_registry_directories_as_tuple(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertIsInstance(run.registry_directories, tuple)

    def test_run_value_keeps_gate_directory_as_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertIsInstance(run.gate_directory, Path)

    def test_run_value_keeps_federation_directory_as_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertIsInstance(run.federation_directory, Path)

    def test_run_value_gate_matches_reloaded_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual(run.gate.to_dict(), gate.load_federation_assurance_gate(run.gate_directory).to_dict())

    def test_run_value_federation_matches_reloaded_federation(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual(run.federation.to_dict(), federation.load_federation(run.federation_directory).to_dict())

    def test_demo_preserves_canonical_gate_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            raw = (run.gate_directory / gate.GATE_NAME).read_bytes()
            self.assertEqual(raw, canonical_bytes(json.loads(raw)))

    def test_demo_preserves_canonical_assurance_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            raw = (run.gate_directory / gate.ASSURANCE_NAME).read_bytes()
            self.assertEqual(raw, canonical_bytes(json.loads(raw)))

    def test_demo_preserves_canonical_manifest_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            raw = (run.gate_directory / gate.MANIFEST_NAME).read_bytes()
            self.assertEqual(raw, canonical_bytes(json.loads(raw)))

    def test_demo_gate_has_expected_assurance_finding_count(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual(run.gate.assurance.finding_count, 10)

    def test_demo_gate_has_expected_release_check_count(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual(run.gate.gate.check_count, 8)

    def test_demo_gate_assurance_is_accepted_for_ready_registry(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertTrue(run.gate.assurance.accepted)

    def test_demo_gate_assurance_is_release_ready_for_ready_registry(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertTrue(run.gate.assurance.release_ready)

    def test_demo_gate_release_is_accepted_for_ready_registry(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertTrue(run.gate.gate.accepted)

    def test_demo_gate_release_is_ready_for_ready_registry(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertTrue(run.gate.gate.release_ready)

    def test_demo_gate_finding_addresses_are_unique(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            addresses = [item.content_address for item in run.gate.assurance.findings]
            self.assertEqual(len(addresses), len(set(addresses)))

    def test_demo_gate_check_addresses_are_unique(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            addresses = [item.content_address for item in run.gate.gate.checks]
            self.assertEqual(len(addresses), len(set(addresses)))

    def test_demo_gate_finding_ids_are_stable(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual([item.finding_id for item in run.gate.assurance.findings], [
                "source-bundle-verified", "federation-address", "verification-recomputed",
                "policy-recomputed", "runtime-recomputed", "runtime-accepted",
                "aggregate-counts", "state-coherent", "public-boundary", "source-release-ready",
            ])

    def test_demo_gate_check_ids_are_stable(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual([item.check_id for item in run.gate.gate.checks], [
                "assurance-accepted", "assurance-no-blockers", "source-runtime-accepted",
                "source-state-allowed", "aggregate-counts-conserved", "public-boundary-closed",
                "source-release-ready", "assurance-warning-free",
            ])

    def test_demo_gate_finding_planes_are_stable(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual([item.plane for item in run.gate.assurance.findings], [
                "source", "source", "verification", "policy", "runtime", "runtime",
                "source", "runtime", "boundary", "runtime",
            ])

    def test_demo_gate_finding_severities_are_stable(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual([item.severity for item in run.gate.assurance.findings], [
                "blocker", "blocker", "blocker", "blocker", "blocker", "blocker",
                "blocker", "blocker", "blocker", "warning",
            ])

    def test_demo_gate_all_findings_pass_for_ready_registry(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertTrue(all(item.passed for item in run.gate.assurance.findings))

    def test_demo_gate_all_checks_pass_for_ready_registry(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertTrue(all(item.passed for item in run.gate.gate.checks))

    def test_demo_federation_manifest_has_exact_file_set(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual(json.loads((run.federation_directory / federation.MANIFEST_NAME).read_text(encoding="utf-8"))["files"], list(federation.FILES))

    def test_demo_gate_manifest_has_exact_file_set(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual(json.loads((run.gate_directory / gate.MANIFEST_NAME).read_text(encoding="utf-8"))["files"], list(gate.FILES))

    def test_demo_gate_manifest_artifact_count_is_two(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            manifest = json.loads((run.gate_directory / gate.MANIFEST_NAME).read_text(encoding="utf-8"))
            self.assertEqual(manifest["artifact_count"], 2)

    def test_demo_federation_manifest_artifact_count_matches_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            manifest = json.loads((run.federation_directory / federation.MANIFEST_NAME).read_text(encoding="utf-8"))
            self.assertEqual(manifest["artifact_count"], len(federation.FILES) - 1)

    def test_demo_output_parent_is_created(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            output = Path(temporary) / "missing" / "nested" / "output"
            run = run_downloaded_gate_demo(directories=(path,), output=output)
            self.assertTrue(run.gate_directory.exists())

    def test_demo_input_directory_is_not_modified(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "downloads"
            root.mkdir()
            path = self.write_registry(root)
            before = {item.name for item in root.iterdir()}
            run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual({item.name for item in root.iterdir()}, before)

    def test_demo_output_directory_contains_only_expected_children(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            output = Path(temporary) / "output"
            run_downloaded_gate_demo(directories=(path,), output=output)
            self.assertEqual({item.name for item in output.iterdir()}, {"federation", "gate"})

    def test_demo_gate_package_contains_only_expected_children(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual({item.name for item in run.gate_directory.iterdir()}, set(gate.FILES))

    def test_demo_federation_package_contains_only_expected_children(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual({item.name for item in run.federation_directory.iterdir()}, set(federation.FILES))

    def test_demo_gate_summary_address_matches_gate_document(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual(run.summary()["gate"]["content_address"], run.gate.gate.content_address)

    def test_demo_assurance_summary_address_matches_assurance_document(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual(run.summary()["assurance"]["content_address"], run.gate.assurance.content_address)

    def test_demo_federation_summary_address_matches_federation_document(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual(run.summary()["federation"]["content_address"], run.federation.federation.content_address)

    def test_demo_source_and_gate_addresses_are_linked(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual(run.gate.gate.federation_address, run.federation.federation.content_address)

    def test_demo_gate_runtime_address_matches_source_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual(run.gate.gate.runtime_address, run.federation.runtime.content_address)

    def test_demo_assurance_runtime_address_matches_source_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual(run.gate.assurance.runtime_address, run.federation.runtime.content_address)

    def test_demo_assurance_federation_address_matches_source_federation(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual(run.gate.assurance.federation_address, run.federation.federation.content_address)

    def test_demo_gate_assurance_link_is_stable(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual(run.gate.gate.assurance_address, run.gate.assurance.content_address)

    def test_demo_gate_summary_is_json_serializable(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertEqual(json.loads(canonical_json(run.summary())), run.summary())

    def test_demo_summary_does_not_include_registry_directory_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary, "secret-local-name")
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            self.assertNotIn("secret-local-name", canonical_json(run.summary()))

    def test_demo_gate_has_no_forbidden_public_keys(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            encoded = canonical_json(run.gate.to_dict()).casefold()
            for forbidden in gate._FORBIDDEN_KEYS:
                self.assertNotIn(f'"{forbidden}"', encoded)

    def test_demo_federation_has_no_forbidden_public_keys(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            encoded = canonical_json(run.federation.to_dict()).casefold()
            for forbidden in gate._FORBIDDEN_KEYS:
                self.assertNotIn(f'"{forbidden}"', encoded)

    def test_demo_gate_query_can_find_every_check(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            result = gate.query_federation_assurance_gate(run.gate, resource="checks", limit=64)
            self.assertEqual(result.total_count, 8)

    def test_demo_gate_query_can_find_every_assurance_finding(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            result = gate.query_federation_assurance_gate(run.gate, resource="findings", limit=64)
            self.assertEqual(result.total_count, 10)

    def test_demo_gate_query_summary_matches_run_summary_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            result = gate.query_federation_assurance_gate(run.gate, resource="summary")
            self.assertEqual(result.items[0]["state"], run.summary()["gate"]["state"])

    def test_demo_gate_query_result_is_public(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_registry(temporary)
            run = run_downloaded_gate_demo(directories=(path,), output=Path(temporary) / "output")
            result = gate.query_federation_assurance_gate(run.gate, resource="checks")
            self.assert_public_result(result)

    def assert_public_result(self, result):
        encoded = canonical_json(result.to_dict()).casefold()
        for forbidden in gate._FORBIDDEN_KEYS:
            self.assertNotIn(f'"{forbidden}"', encoded)


def gate_command():
    return "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-series-release-registry-federation-gate"


def api_gate_base(server):
    return f"http://127.0.0.1:{server.server_port}/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate"


if __name__ == "__main__":
    unittest.main()
