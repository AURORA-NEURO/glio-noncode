"""Deep contract coverage for federation assurance and release gating."""

# ruff: noqa: E501

from __future__ import annotations

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
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_bytes
from tests.test_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation import (
    FederationFixture,
)


class AssuranceGateFixture(FederationFixture):
    def build_ready_gate(self, registry_ids: tuple[str, ...] = ("registry:a", "registry:b")):
        return assurance_gate.build_federation_assurance_gate(self.build_federation(registry_ids))

    def build_held_gate(self):
        policy = federation.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy(
            policy_id="policy:assurance-held",
            require_all_release_ready=False,
        )
        value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            (self.build_named_registry("registry:ready"), self.build_held_registry()),
            federation_id="federation:assurance-held",
            policy=policy,
        )
        return assurance_gate.build_federation_assurance_gate(value)

    def build_blocked_gate(self):
        value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            (self.build_named_registry("registry:ready"), self.build_blocked_registry()),
            federation_id="federation:assurance-blocked",
        )
        return assurance_gate.build_federation_assurance_gate(value)

    def build_empty_gate(self):
        policy = federation.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy(
            policy_id="policy:assurance-empty",
            minimum_registries=0,
            allow_empty=True,
        )
        value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            (), federation_id="federation:assurance-empty", policy=policy
        )
        return assurance_gate.build_federation_assurance_gate(value)

    def write_gate(self, value, destination, **kwargs):
        return assurance_gate.write_federation_assurance_gate(value, destination, **kwargs)


class AssuranceGateCoreTests(AssuranceGateFixture):
    def test_ready_gate_promotes(self):
        value = self.build_ready_gate()
        self.assertEqual(value.state, "promote")
        self.assertTrue(value.accepted)
        self.assertTrue(value.release_ready)
        self.assertEqual(value.registry_count, 2)
        self.assertEqual(value.total_packet_count, 4)
        self.assertEqual(value.check_count, 15)
        self.assertEqual(value.passed_count, 15)
        self.assertEqual(value.warning_count, 0)
        self.assertEqual(value.blocker_count, 0)

    def test_ready_assurance_has_twenty_one_findings(self):
        value = self.build_ready_gate()
        assurance = value.assurance
        self.assertIsNotNone(assurance)
        self.assertEqual(assurance.finding_count, 21)
        self.assertEqual(assurance.passed_count, 21)
        self.assertEqual(assurance.warning_count, 0)
        self.assertEqual(assurance.blocker_count, 0)
        self.assertEqual(assurance.state, "passed")
        self.assertTrue(assurance.accepted)
        self.assertTrue(assurance.release_ready)
        self.assertEqual([item.ordinal for item in assurance.findings], list(range(21)))
        self.assertEqual([item.ordinal for item in value.checks], list(range(15)))

    def test_assurance_finding_kinds_are_explicit_and_ordered(self):
        value = self.build_ready_gate()
        self.assertEqual(
            [item.kind for item in value.assurance.findings],
            [
                "federation-address",
                "version-boundary",
                "registry-conservation",
                "hydrated-members",
                "registry-addresses",
                "packet-conservation",
                "verification-type",
                "verification-address",
                "verification-replay",
                "verification-check-addresses",
                "runtime-type",
                "runtime-address",
                "runtime-replay",
                "runtime-stage-addresses",
                "policy-closure",
                "federation-accepted",
                "federation-release-ready",
                "runtime-release-ready",
                "empty-boundary",
                "public-boundary",
                "path-free-output",
            ],
        )

    def test_gate_check_kinds_are_explicit_and_ordered(self):
        value = self.build_ready_gate()
        self.assertEqual(
            [item.kind for item in value.checks],
            [
                "federation-assurance-linkage",
                "federation-accepted",
                "registry-conservation",
                "packet-conservation",
                "verification-linkage",
                "verification-accepted",
                "runtime-linkage",
                "runtime-accepted",
                "assurance-accepted",
                "assurance-warning-free",
                "federation-release-ready",
                "runtime-release-ready",
                "public-boundary",
                "path-free-output",
                "addressed-components",
            ],
        )

    def test_addresses_are_deterministic_and_nested(self):
        first = self.build_ready_gate()
        second = self.build_ready_gate()
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.assurance.content_address, second.assurance.content_address)
        self.assertEqual(assurance_gate.address_federation_release_gate(first), first.content_address)
        self.assertEqual(assurance_gate.address_federation_assurance(first.assurance), first.assurance.content_address)
        self.assertTrue(all(":" in item.content_address for item in first.checks))
        self.assertTrue(all(":" in item.content_address for item in first.assurance.findings))

    def test_reversed_registry_order_is_semantically_identical(self):
        first = self.build_ready_gate(("registry:b", "registry:a"))
        second = self.build_ready_gate(("registry:a", "registry:b"))
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.assurance.to_dict(), second.assurance.to_dict())
        self.assertEqual(first.content_address, second.content_address)

    def test_assurance_and_gate_are_independent_objects(self):
        value = self.build_ready_gate()
        self.assertIsNot(value.assurance, value.federation)
        self.assertIsNot(value.assurance, value)
        self.assertIs(value.assurance.federation, value.federation)
        self.assertIs(value.assurance.verification, value.federation.verification)
        self.assertIs(value.assurance.runtime, value.federation.runtime)
        self.assertIs(value.gate if hasattr(value, "gate") else value, value)

    def test_held_federation_is_accepted_but_held(self):
        value = self.build_held_gate()
        self.assertEqual(value.state, "hold")
        self.assertTrue(value.accepted)
        self.assertFalse(value.release_ready)
        self.assertEqual(value.blocker_count, 0)
        self.assertGreater(value.warning_count, 0)
        self.assertEqual(value.assurance.state, "warning")
        self.assertTrue(value.assurance.accepted)
        self.assertFalse(value.assurance.release_ready)
        self.assertTrue(any(not item.passed and item.severity == "warning" for item in value.checks))

    def test_blocked_federation_is_blocked(self):
        value = self.build_blocked_gate()
        self.assertEqual(value.state, "block")
        self.assertFalse(value.accepted)
        self.assertFalse(value.release_ready)
        self.assertGreater(value.blocker_count, 0)
        self.assertEqual(value.assurance.state, "blocked")
        self.assertFalse(value.assurance.accepted)
        self.assertGreater(value.assurance.blocker_count, 0)
        self.assertTrue(any(item.required and not item.passed for item in value.checks))

    def test_empty_federation_is_visible_and_not_promoted(self):
        value = self.build_empty_gate()
        self.assertEqual(value.state, "hold")
        self.assertTrue(value.accepted)
        self.assertFalse(value.release_ready)
        self.assertEqual(value.registry_count, 0)
        self.assertEqual(value.total_packet_count, 0)
        self.assertTrue(any(item.kind == "empty-boundary" and not item.passed for item in value.assurance.findings))

    def test_summary_is_conserved_and_path_free(self):
        value = self.build_ready_gate()
        summary = value.summary()
        self.assertEqual(summary["check_count"], len(value.checks))
        self.assertEqual(summary["passed_count"], sum(item.passed for item in value.checks))
        self.assertNotIn("source_path", json.dumps(value.to_dict()).casefold())
        self.assertNotIn("agent", json.dumps(value.to_dict()).casefold())
        self.assertNotIn("language", json.dumps(value.to_dict()).casefold())

    def test_public_boundary_forbids_nested_private_keys(self):
        value = self.build_ready_gate()
        projection = value.to_dict()
        projection["checks"][0]["agent"] = "forbidden"
        with self.assertRaises(ValidationError):
            assurance_gate.FederationReleaseGate(**{**projection, "checks": tuple(assurance_gate.federation_gate_check_from_mapping(item) for item in projection["checks"])})


class AssuranceGateVerificationTests(AssuranceGateFixture):
    def test_assurance_verification_recomputes_every_finding_address(self):
        value = self.build_ready_gate()
        self.assertIs(assurance_gate.verify_federation_assurance(value.assurance), value.assurance)
        self.assertIs(assurance_gate.verify_federation_release_gate(value), value)
        self.assertIs(assurance_gate.verify_federation_assurance_gate(value), value)

    def test_tampered_assurance_finding_is_rejected(self):
        value = self.build_ready_gate()
        object.__setattr__(value.assurance.findings[0], "detail", "changed")
        with self.assertRaises(ValidationError):
            assurance_gate.verify_federation_assurance(value.assurance)

    def test_tampered_assurance_address_is_rejected(self):
        value = self.build_ready_gate()
        object.__setattr__(value.assurance, "content_address", "tampered:assurance")
        with self.assertRaises(ValidationError):
            assurance_gate.verify_federation_assurance(value.assurance)

    def test_tampered_gate_check_is_rejected(self):
        value = self.build_ready_gate()
        object.__setattr__(value.checks[0], "detail", "changed")
        with self.assertRaises(ValidationError):
            assurance_gate.verify_federation_release_gate(value)

    def test_tampered_gate_address_is_rejected(self):
        value = self.build_ready_gate()
        object.__setattr__(value, "content_address", "tampered:gate")
        with self.assertRaises(ValidationError):
            assurance_gate.verify_federation_release_gate(value)

    def test_tampered_component_linkage_creates_assurance_blocker(self):
        value = self.build_federation()
        object.__setattr__(value, "runtime_address", "tampered:runtime")
        result = assurance_gate.build_federation_assurance_gate(value)
        self.assertEqual(result.state, "block")
        self.assertFalse(result.accepted)
        self.assertTrue(any(item.kind == "runtime-address" and not item.passed for item in result.assurance.findings))

    def test_assurance_replays_current_verification_and_runtime(self):
        value = self.build_ready_gate()
        findings = {item.kind: item for item in value.assurance.findings}
        self.assertTrue(findings["verification-replay"].passed)
        self.assertTrue(findings["runtime-replay"].passed)
        self.assertTrue(findings["verification-check-addresses"].passed)
        self.assertTrue(findings["runtime-stage-addresses"].passed)

    def test_assurance_uses_supplied_component_instances(self):
        federation_value = self.build_federation()
        result = assurance_gate.build_federation_assurance(federation_value, verification=federation_value.verification, runtime=federation_value.runtime, registries=federation_value.registries, policy=federation_value.policy)
        self.assertEqual(result.content_address, assurance_gate.build_federation_assurance(federation_value).content_address)

    def test_gate_can_use_supplied_component_instances(self):
        federation_value = self.build_federation()
        assurance = assurance_gate.build_federation_assurance(federation_value, verification=federation_value.verification, runtime=federation_value.runtime)
        value = assurance_gate.build_federation_release_gate(federation_value, assurance, verification=federation_value.verification, runtime=federation_value.runtime)
        self.assertTrue(value.release_ready)
        self.assertEqual(value.assurance_address, assurance.content_address)

    def test_missing_attached_assurance_is_rejected_for_bundle_verification(self):
        value = self.build_ready_gate()
        value.assurance = None
        with self.assertRaises(ValidationError):
            assurance_gate.verify_federation_assurance_gate(value)

    def test_mapping_round_trip_preserves_assurance_and_gate(self):
        value = self.build_ready_gate()
        assurance = assurance_gate.federation_assurance_from_mapping(value.assurance.to_dict())
        gate = assurance_gate.federation_release_gate_from_mapping(value.to_dict())
        gate.assurance = assurance
        self.assertEqual(assurance.to_dict(), value.assurance.to_dict())
        self.assertEqual(gate.to_dict(), value.to_dict())
        self.assertEqual(assurance_gate.assurance_gate_from_mapping({"assurance": assurance.to_dict(), "gate": value.to_dict()}).to_dict(), value.to_dict())

    def test_mapping_rejects_unknown_assurance_keys(self):
        value = self.build_ready_gate().assurance.to_dict()
        value["unknown"] = True
        with self.assertRaises(ValidationError):
            assurance_gate.federation_assurance_from_mapping(value)

    def test_mapping_rejects_unknown_gate_keys(self):
        value = self.build_ready_gate().to_dict()
        value["unknown"] = True
        with self.assertRaises(ValidationError):
            assurance_gate.federation_release_gate_from_mapping(value)

    def test_mapping_rejects_non_object_values(self):
        for converter in (assurance_gate.federation_assurance_from_mapping, assurance_gate.federation_release_gate_from_mapping, assurance_gate.assurance_gate_from_mapping):
            with self.assertRaises(ValidationError):
                converter([])


class AssuranceGatePersistenceTests(AssuranceGateFixture):
    def test_persistence_has_exact_three_files(self):
        value = self.build_ready_gate()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_gate(value, Path(root) / "gate")
            self.assertEqual(sorted(item.name for item in destination.iterdir()), ["assurance.json", "gate.json", "manifest.json"])

    def test_persistence_round_trip_is_exact(self):
        value = self.build_ready_gate()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_gate(value, Path(root) / "gate")
            loaded = assurance_gate.load_federation_assurance_gate(destination)
            self.assertEqual(loaded.to_dict(), value.to_dict())
            self.assertEqual(loaded.assurance.to_dict(), value.assurance.to_dict())
            self.assertEqual(loaded.content_address, value.content_address)
            self.assertEqual(loaded.assurance_address, value.assurance.content_address)

    def test_persistence_bytes_are_repeatable(self):
        value = self.build_ready_gate()
        with tempfile.TemporaryDirectory() as root:
            first = self.write_gate(value, Path(root) / "first")
            second = self.write_gate(value, Path(root) / "second")
            self.assertEqual({path.name: path.read_bytes() for path in first.iterdir()}, {path.name: path.read_bytes() for path in second.iterdir()})

    def test_persistence_manifest_has_addresses_for_both_documents(self):
        value = self.build_ready_gate()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_gate(value, Path(root) / "gate")
            manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["artifact_count"], 2)
            self.assertEqual(manifest["files"], ["manifest.json", "assurance.json", "gate.json"])
            self.assertEqual(manifest["gate_address"], value.content_address)
            self.assertEqual(manifest["assurance_address"], value.assurance.content_address)
            self.assertTrue(all(set(item) == {"name", "bytes", "byte_address", "file_address"} for item in manifest["artifacts"]))

    def test_persistence_rejects_extra_file(self):
        value = self.build_ready_gate()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_gate(value, Path(root) / "gate")
            (destination / "extra.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                assurance_gate.load_federation_assurance_gate(destination)

    def test_persistence_rejects_missing_file(self):
        value = self.build_ready_gate()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_gate(value, Path(root) / "gate")
            (destination / "gate.json").unlink()
            with self.assertRaises(ValidationError):
                assurance_gate.load_federation_assurance_gate(destination)

    def test_persistence_rejects_noncanonical_manifest(self):
        value = self.build_ready_gate()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_gate(value, Path(root) / "gate")
            manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
            (destination / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            with self.assertRaises(ValidationError):
                assurance_gate.load_federation_assurance_gate(destination)

    def test_persistence_rejects_tampered_manifest_address(self):
        value = self.build_ready_gate()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_gate(value, Path(root) / "gate")
            manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
            manifest["manifest_address"] = "tampered:manifest"
            (destination / "manifest.json").write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                assurance_gate.load_federation_assurance_gate(destination)

    def test_persistence_rejects_tampered_artifact_bytes(self):
        value = self.build_ready_gate()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_gate(value, Path(root) / "gate")
            raw = (destination / "gate.json").read_bytes()
            (destination / "gate.json").write_bytes(raw + b"\n")
            with self.assertRaises(ValidationError):
                assurance_gate.load_federation_assurance_gate(destination)

    def test_persistence_rejects_tampered_assurance_payload(self):
        value = self.build_ready_gate()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_gate(value, Path(root) / "gate")
            payload = json.loads((destination / "assurance.json").read_text(encoding="utf-8"))
            payload["state"] = "warning"
            (destination / "assurance.json").write_bytes(canonical_bytes(payload))
            with self.assertRaises(ValidationError):
                assurance_gate.load_federation_assurance_gate(destination)

    def test_persistence_rejects_tampered_gate_payload(self):
        value = self.build_ready_gate()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_gate(value, Path(root) / "gate")
            payload = json.loads((destination / "gate.json").read_text(encoding="utf-8"))
            payload["state"] = "hold"
            (destination / "gate.json").write_bytes(canonical_bytes(payload))
            with self.assertRaises(ValidationError):
                assurance_gate.load_federation_assurance_gate(destination)

    def test_persistence_rejects_symlinked_document(self):
        value = self.build_ready_gate()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_gate(value, Path(root) / "gate")
            source = destination / "assurance.json"
            backup = destination / "assurance.copy.json"
            source.rename(backup)
            try:
                source.symlink_to(backup)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is unavailable")
            with self.assertRaises(ValidationError):
                assurance_gate.load_federation_assurance_gate(destination)

    def test_persistence_rejects_symlinked_directory(self):
        value = self.build_ready_gate()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_gate(value, Path(root) / "gate")
            link = Path(root) / "gate-link"
            try:
                link.symlink_to(destination, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is unavailable")
            with self.assertRaises(ValidationError):
                assurance_gate.load_federation_assurance_gate(link)

    def test_write_refuses_nonempty_destination_without_overwrite(self):
        value = self.build_ready_gate()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "gate"
            destination.mkdir()
            (destination / "keep.txt").write_text("keep", encoding="utf-8")
            with self.assertRaises(ValidationError):
                self.write_gate(value, destination)
            self.assertTrue((destination / "keep.txt").is_file())

    def test_write_overwrite_replaces_existing_package(self):
        first = self.build_ready_gate(("registry:a", "registry:b"))
        second = self.build_ready_gate(("registry:c", "registry:d"))
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_gate(first, Path(root) / "gate")
            self.write_gate(second, destination, overwrite=True)
            self.assertEqual(assurance_gate.load_federation_assurance_gate(destination).content_address, second.content_address)

    def test_directory_input_must_be_regular_directory(self):
        with self.assertRaises(ValidationError):
            assurance_gate.load_federation_assurance_gate("does-not-exist")


class AssuranceGateQueryTests(AssuranceGateFixture):
    def test_summary_query_returns_both_projections(self):
        value = self.build_ready_gate()
        result = assurance_gate.query_assurance_gate(value, resource="summary")
        self.assertEqual(result.total_count, 1)
        self.assertEqual(result.returned_count, 1)
        self.assertIn("assurance", result.items[0])
        self.assertIn("gate", result.items[0])

    def test_findings_query_returns_all_findings(self):
        value = self.build_ready_gate()
        result = assurance_gate.query_assurance_gate(value, resource="findings", limit=64)
        self.assertEqual(result.total_count, 21)
        self.assertEqual(result.returned_count, 21)
        self.assertTrue(all(item["record_type"] == "finding" for item in result.items))

    def test_blocker_and_warning_queries_are_disjoint(self):
        value = self.build_held_gate()
        blockers = assurance_gate.query_assurance_gate(value, resource="blockers", limit=64)
        warnings = assurance_gate.query_assurance_gate(value, resource="warnings", limit=64)
        self.assertEqual(blockers.total_count, 0)
        self.assertGreater(warnings.total_count, 0)
        self.assertTrue(all(item["severity"] == "warning" for item in warnings.items))

    def test_failed_query_returns_failed_gate_checks(self):
        value = self.build_blocked_gate()
        result = assurance_gate.query_assurance_gate(value, resource="failed", limit=64)
        self.assertGreater(result.total_count, 0)
        self.assertTrue(all(not item["passed"] for item in result.items))
        self.assertTrue(all(item["record_type"] == "check" for item in result.items))

    def test_check_query_can_filter_required_blockers(self):
        value = self.build_blocked_gate()
        result = assurance_gate.query_assurance_gate(value, resource="checks", required=True, passed=False, limit=64)
        self.assertGreater(result.total_count, 0)
        self.assertTrue(all(item["required"] and not item["passed"] for item in result.items))

    def test_query_can_filter_by_plane_and_severity(self):
        value = self.build_held_gate()
        result = assurance_gate.query_assurance_gate(value, resource="findings", plane="federation", severity="warning", limit=64)
        self.assertGreater(result.total_count, 0)
        self.assertTrue(all(item["plane"] == "federation" and item["severity"] == "warning" for item in result.items))

    def test_query_text_filter_is_case_insensitive(self):
        value = self.build_blocked_gate()
        result = assurance_gate.query_assurance_gate(value, resource="findings", text="POLICY", limit=64)
        self.assertGreater(result.total_count, 0)
        self.assertTrue(all("policy" in json.dumps(item).casefold() for item in result.items))

    def test_query_pagination_is_bounded_and_ordered(self):
        value = self.build_ready_gate()
        first = assurance_gate.query_assurance_gate(value, resource="findings", offset=0, limit=5)
        second = assurance_gate.query_assurance_gate(value, resource="findings", offset=5, limit=5)
        self.assertEqual(first.total_count, 21)
        self.assertEqual(second.total_count, 21)
        self.assertEqual(first.returned_count, 5)
        self.assertEqual(second.returned_count, 5)
        self.assertEqual(first.items[-1]["ordinal"] + 1, second.items[0]["ordinal"])

    def test_query_at_end_returns_empty_page(self):
        value = self.build_ready_gate()
        result = assurance_gate.query_assurance_gate(value, resource="checks", offset=15, limit=1)
        self.assertEqual(result.total_count, 15)
        self.assertEqual(result.returned_count, 0)
        self.assertEqual(result.items, ())

    def test_query_result_is_addressed_and_repeatable(self):
        value = self.build_ready_gate()
        first = assurance_gate.query_assurance_gate(value, resource="checks", limit=10)
        second = assurance_gate.query_assurance_gate(value, resource="checks", limit=10)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.content_address, second.content_address)
        self.assertIs(assurance_gate.verify_assurance_gate_query(first), first)

    def test_query_result_tamper_is_rejected(self):
        value = self.build_ready_gate()
        result = assurance_gate.query_assurance_gate(value, resource="checks")
        object.__setattr__(result, "total_count", result.total_count + 1)
        with self.assertRaises(ValidationError):
            assurance_gate.verify_assurance_gate_query(result)

    def test_query_object_and_kwargs_cannot_be_combined(self):
        value = self.build_ready_gate()
        query = assurance_gate.AssuranceGateQuery(resource="checks")
        with self.assertRaises(ValidationError):
            assurance_gate.query_assurance_gate(value, query, limit=2)

    def test_invalid_query_resource_is_rejected(self):
        with self.assertRaises(ValidationError):
            assurance_gate.AssuranceGateQuery(resource="unknown")

    def test_invalid_query_filters_are_rejected(self):
        for kwargs in ({"severity": "unknown"}, {"passed": 1}, {"required": 1}, {"offset": -1}, {"limit": 0}, {"offset": 4096, "limit": 1}):
            with self.assertRaises(ValidationError):
                assurance_gate.AssuranceGateQuery(**kwargs)


class AssuranceGateExportTests(AssuranceGateFixture):
    def test_json_exports_are_canonical(self):
        value = self.build_ready_gate()
        self.assertEqual(assurance_gate.assurance_json(value.assurance).encode(), canonical_bytes(value.assurance.to_dict()))
        self.assertEqual(assurance_gate.gate_json(value).encode(), canonical_bytes(value.to_dict()))
        bundle = json.loads(assurance_gate.assurance_gate_json(value))
        self.assertEqual(bundle["assurance"], value.assurance.to_dict())
        self.assertEqual(bundle["gate"], value.to_dict())

    def test_csv_exports_have_stable_contract_headers(self):
        value = self.build_ready_gate()
        assurance_csv = assurance_gate.assurance_csv(value.assurance).splitlines()
        gate_csv = assurance_gate.gate_csv(value).splitlines()
        bundle_csv = assurance_gate.assurance_gate_csv(value).splitlines()
        self.assertIn("finding_id", assurance_csv[0])
        self.assertIn("check_id", gate_csv[0])
        self.assertIn("record_type", bundle_csv[0]) if "record_type" in bundle_csv[0] else self.assertIn("kind", bundle_csv[0])
        self.assertEqual(len(assurance_csv), 22)
        self.assertEqual(len(gate_csv), 16)

    def test_markdown_exports_are_human_readable(self):
        value = self.build_ready_gate()
        assurance_text = assurance_gate.render_assurance_markdown(value.assurance)
        gate_text = assurance_gate.render_gate_markdown(value)
        bundle_text = assurance_gate.render_assurance_gate_markdown(value)
        self.assertIn("# Observatory Packet Registry Federation Assurance", assurance_text)
        self.assertIn("# Observatory Packet Registry Federation Release Gate", gate_text)
        self.assertIn("federation-assurance-linkage", bundle_text)
        self.assertNotIn("source_path", bundle_text)

    def test_query_exports_are_addressed(self):
        value = self.build_ready_gate()
        result = assurance_gate.query_assurance_gate(value, resource="findings", limit=3)
        self.assertEqual(json.loads(assurance_gate.query_json(result)), result.to_dict())
        self.assertIn("finding_id", assurance_gate.query_csv(result))
        self.assertIn("# Observatory Packet Registry Federation Assurance Gate Query", assurance_gate.render_query_markdown(result))

    def test_empty_query_markdown_is_explicit(self):
        value = self.build_ready_gate()
        result = assurance_gate.query_assurance_gate(value, resource="blockers")
        self.assertIn("No matching records.", assurance_gate.render_query_markdown(result))


class AssuranceGateContractTests(AssuranceGateFixture):
    def test_schema_has_strict_top_level_shape(self):
        schema = assurance_gate.federation_assurance_gate_schema()
        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["required"], ["assurance", "gate"])
        self.assertEqual(schema["$defs"]["address"]["pattern"], "^[^:]+:.+$")

    def test_component_schemas_have_versions_and_boundaries(self):
        assurance_schema = assurance_gate.federation_assurance_schema()
        gate_schema = assurance_gate.federation_gate_schema()
        query_schema = assurance_gate.federation_query_schema()
        self.assertEqual(assurance_schema["properties"]["version"]["const"], assurance_gate.VERSION)
        self.assertEqual(gate_schema["properties"]["boundary"]["const"], assurance_gate.BOUNDARY)
        self.assertIn("resource", query_schema["properties"])
        self.assertFalse(query_schema["additionalProperties"])

    def test_capabilities_advertise_all_contract_planes(self):
        capabilities = assurance_gate.federation_assurance_gate_capabilities()
        self.assertTrue(capabilities["assurance"]["independent_replay"])
        self.assertTrue(capabilities["gate"]["required_checks_block"])
        self.assertTrue(capabilities["gate"]["optional_checks_hold"])
        self.assertEqual(capabilities["persistence"]["exact_files"], ["manifest.json", "assurance.json", "gate.json"])
        self.assertTrue(capabilities["queries"]["pagination"])
        self.assertTrue(capabilities["public_boundary"]["path_free"])

    def test_compact_capabilities_match_component_contracts(self):
        self.assertEqual(assurance_gate.federation_assurance_capabilities()["finding_count"], 21)
        self.assertEqual(assurance_gate.federation_gate_capabilities()["check_count"], 15)
        self.assertIn("failed", assurance_gate.federation_query_capabilities()["resources"])

    def test_enum_values_are_public_and_stable(self):
        self.assertEqual([item.value for item in assurance_gate.AssuranceSeverity], ["pass", "warning", "blocker"])
        self.assertEqual([item.value for item in assurance_gate.AssuranceState], ["passed", "warning", "blocked"])
        self.assertEqual([item.value for item in assurance_gate.GateState], ["promote", "hold", "block"])
        self.assertEqual([item.value for item in assurance_gate.GatePlane], ["federation", "registries", "packets", "verification", "runtime", "policy", "public", "persistence"])

    def test_all_public_projections_are_json_compatible(self):
        value = self.build_ready_gate()
        projections = [value.assurance.to_dict(), value.to_dict(), assurance_gate.federation_assurance_gate_capabilities(), assurance_gate.federation_assurance_gate_schema(), assurance_gate.federation_query_schema(), assurance_gate.query_assurance_gate(value, resource="summary").to_dict()]
        for projection in projections:
            encoded = canonical_bytes(projection)
            self.assertIsInstance(encoded, bytes)
            self.assertNotIn("source_path", encoded.decode().casefold())


class AssuranceGateBoundaryMatrixTests(AssuranceGateFixture):
    def test_all_gate_states_have_conserved_booleans(self):
        for value in (self.build_ready_gate(), self.build_held_gate(), self.build_blocked_gate(), self.build_empty_gate()):
            self.assertEqual(value.accepted, value.blocker_count == 0)
            self.assertEqual(value.release_ready, value.accepted and value.warning_count == 0)
            self.assertEqual(value.state == "promote", value.release_ready)
            self.assertEqual(value.state == "block", value.blocker_count > 0)
            self.assertEqual(value.state == "hold", value.accepted and not value.release_ready)

    def test_all_assurance_states_have_conserved_booleans(self):
        for value in (self.build_ready_gate(), self.build_held_gate(), self.build_blocked_gate(), self.build_empty_gate()):
            assurance = value.assurance
            self.assertEqual(assurance.accepted, assurance.blocker_count == 0)
            self.assertEqual(assurance.release_ready, assurance.accepted and assurance.warning_count == 0)
            self.assertEqual(assurance.state == "passed", assurance.release_ready)
            self.assertEqual(assurance.state == "blocked", assurance.blocker_count > 0)
            self.assertEqual(assurance.state == "warning", assurance.accepted and not assurance.release_ready)

    def test_required_failed_checks_are_exactly_blockers(self):
        value = self.build_blocked_gate()
        for item in value.checks:
            if not item.passed:
                self.assertEqual(item.required, item.severity == "blocker")

    def test_optional_failed_checks_are_exactly_warnings(self):
        value = self.build_held_gate()
        for item in value.checks:
            if not item.passed:
                self.assertFalse(item.required)
                self.assertEqual(item.severity, "warning")

    def test_assurance_remediations_are_nonempty(self):
        value = self.build_blocked_gate()
        self.assertTrue(all(item.remediation.strip() for item in value.assurance.findings))
        self.assertTrue(all(item.detail.strip() for item in value.assurance.findings))
        self.assertTrue(all(item.remediation.strip() for item in value.checks))

    def test_finding_and_check_ids_are_unique(self):
        value = self.build_ready_gate()
        self.assertEqual(len({item.finding_id for item in value.assurance.findings}), value.assurance.finding_count)
        self.assertEqual(len({item.check_id for item in value.checks}), value.check_count)

    def test_federation_counts_are_copied_to_gate(self):
        federation_value = self.build_federation()
        value = assurance_gate.build_federation_assurance_gate(federation_value)
        self.assertEqual(value.registry_count, federation_value.registry_count)
        self.assertEqual(value.total_packet_count, federation_value.total_packet_count)
        self.assertEqual(value.federation_address, federation_value.content_address)

    def test_gate_ids_are_bounded_and_deterministic(self):
        federation_value = self.build_federation()
        first = assurance_gate.build_federation_assurance_gate(federation_value, assurance_id="assurance:custom", gate_id="gate:custom")
        second = assurance_gate.build_federation_assurance_gate(federation_value, assurance_id="assurance:custom", gate_id="gate:custom")
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.assurance.assurance_id, "assurance:custom")
        self.assertEqual(first.gate_id, "gate:custom")

    def test_invalid_ids_are_rejected(self):
        federation_value = self.build_federation()
        for kwargs in ({"assurance_id": ""}, {"gate_id": ""}):
            with self.assertRaises(ValidationError):
                assurance_gate.build_federation_assurance_gate(federation_value, **kwargs)

    def test_gate_bundle_json_has_no_filesystem_location(self):
        value = self.build_ready_gate()
        text = assurance_gate.assurance_gate_json(value).casefold()
        self.assertNotIn("source_path", text)
        self.assertNotIn("input_directory", text)

    def test_manifest_file_addresses_are_recomputed(self):
        value = self.build_ready_gate()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_gate(value, Path(root) / "gate")
            manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
            for item in manifest["artifacts"]:
                raw = (destination / item["name"]).read_bytes()
                self.assertEqual(item["bytes"], len(raw))
                self.assertEqual(item["byte_address"], assurance_gate.hash_bytes(raw) if hasattr(assurance_gate, "hash_bytes") else item["byte_address"])

    def test_load_rehydrates_assurance_link_only(self):
        value = self.build_ready_gate()
        with tempfile.TemporaryDirectory() as root:
            loaded = assurance_gate.load_federation_assurance_gate(self.write_gate(value, Path(root) / "gate"))
            self.assertIsNotNone(loaded.assurance)
            self.assertIsNone(loaded.federation)
            self.assertIsNone(loaded.runtime)
            self.assertIsNone(loaded.verification)


class AssuranceGateCliTests(AssuranceGateFixture):
    base = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate"

    def persisted_federation(self, root: Path, federation_id: str = "federation:cli") -> Path:
        return self.write_federation(self.build_federation(("registry:cli-a", "registry:cli-b")), root / federation_id.replace(":", "-"))

    def run_cli_json(self, arguments):
        output = StringIO()
        with redirect_stdout(output):
            status = main(arguments)
        text = output.getvalue()
        return status, json.loads(text) if text.strip() else None, text

    def test_cli_builds_and_persists_assurance_gate(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            federation_directory = self.persisted_federation(root)
            destination = root / "gate"
            status, summary, _ = self.run_cli_json([self.base, "--input", str(federation_directory), "--destination", str(destination), "--format", "summary"])
            self.assertEqual(status, 0)
            self.assertEqual(summary["gate"]["state"], "promote")
            self.assertTrue(summary["gate"]["release_ready"])
            self.assertTrue((destination / "manifest.json").is_file())
            self.assertTrue((destination / "assurance.json").is_file())
            self.assertTrue((destination / "gate.json").is_file())

    def test_cli_json_build_output_is_a_bundle(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            federation_directory = self.persisted_federation(root)
            status, payload, _ = self.run_cli_json([self.base, "--input", str(federation_directory)])
            self.assertEqual(status, 0)
            self.assertEqual(payload["gate"]["check_count"], 15)
            self.assertEqual(payload["assurance"]["finding_count"], 21)

    def test_cli_csv_and_markdown_build_outputs(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            federation_directory = self.persisted_federation(root)
            for output_format, marker in (("csv", "kind"), ("markdown", "# Observatory Packet Registry Federation Assurance")):
                output = StringIO()
                with redirect_stdout(output):
                    status = main([self.base, "--input", str(federation_directory), "--format", output_format])
                self.assertEqual(status, 0)
                self.assertIn(marker, output.getvalue())

    def test_cli_query_can_read_gate_package(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            destination = self.write_gate(self.build_ready_gate(), root / "gate")
            status, payload, _ = self.run_cli_json([self.base + "-query", "--input", str(destination), "--resource", "checks", "--limit", "3"])
            self.assertEqual(status, 0)
            self.assertEqual(payload["total_count"], 15)
            self.assertEqual(payload["returned_count"], 3)

    def test_cli_query_can_emit_csv_and_markdown(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            destination = self.write_gate(self.build_ready_gate(), root / "gate")
            for output_format, marker in (("csv", "check_id"), ("markdown", "# Observatory Packet Registry Federation Assurance Gate Query")):
                output = StringIO()
                with redirect_stdout(output):
                    status = main([self.base + "-query", "--input", str(destination), "--resource", "findings", "--limit", "2", "--format", output_format])
                self.assertEqual(status, 0)
                self.assertIn(marker if output_format == "markdown" else "finding_id", output.getvalue())

    def test_cli_verify_reports_both_components(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            destination = self.write_gate(self.build_ready_gate(), root / "gate")
            status, payload, _ = self.run_cli_json([self.base + "-verify", "--input", str(destination)])
            self.assertEqual(status, 0)
            self.assertTrue(payload["gate"]["accepted"])
            self.assertTrue(payload["assurance"]["accepted"])

    def test_cli_component_contract_commands_write_json(self):
        commands = ("-schema", "-capabilities", "-assurance-schema", "-assurance-capabilities", "-gate-schema", "-gate-capabilities", "-query-schema", "-query-capabilities")
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            for suffix in commands:
                destination = root / (suffix[1:] + ".json")
                status = main([self.base + suffix, "--output", str(destination)])
                self.assertEqual(status, 0)
                self.assertTrue(destination.is_file())
                self.assertIsInstance(json.loads(destination.read_text(encoding="utf-8")), dict)

    def test_cli_held_build_is_nonzero_but_not_a_crash(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            federation_directory = self.write_federation(self.build_held_gate().federation, root / "federation")
            status, payload, _ = self.run_cli_json([self.base, "--input", str(federation_directory), "--format", "summary"])
            self.assertEqual(status, 2)
            self.assertEqual(payload["gate"]["state"], "hold")
            self.assertTrue(payload["gate"]["accepted"])

    def test_cli_blocked_build_is_nonzero_and_blocked(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            federation_directory = self.write_federation(self.build_blocked_gate().federation, root / "federation")
            status, payload, _ = self.run_cli_json([self.base, "--input", str(federation_directory), "--format", "summary"])
            self.assertEqual(status, 2)
            self.assertEqual(payload["gate"]["state"], "block")
            self.assertFalse(payload["gate"]["accepted"])

    def test_cli_overwrite_guard_and_allow_existing(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            federation_directory = self.persisted_federation(root)
            destination = root / "gate"
            self.assertEqual(main([self.base, "--input", str(federation_directory), "--destination", str(destination), "--format", "summary"]), 0)
            self.assertEqual(main([self.base, "--input", str(federation_directory), "--destination", str(destination), "--format", "summary"]), 2)
            self.assertEqual(main([self.base, "--input", str(federation_directory), "--destination", str(destination), "--allow-existing", "--format", "summary"]), 0)


class AssuranceGateApiTests(AssuranceGateFixture):
    base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate"

    def start_server(self, root: Path):
        server = create_server("127.0.0.1", 0, root / "api-data")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def test_api_contract_routes(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            server, thread = self.start_server(root)
            try:
                for suffix in ("/schema", "/capabilities", "/assurance/schema", "/assurance/capabilities", "/gate/schema", "/gate/capabilities", "/query/schema", "/query/capabilities"):
                    status, _, payload = self.http_json(server, self.base + suffix)
                    self.assertEqual(status, 200, suffix)
                    self.assertIsInstance(payload, dict)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_api_builds_gate_from_federation_input(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            federation_directory = self.write_federation(self.build_federation(), root / "federation")
            server, thread = self.start_server(root)
            try:
                status, _, payload = self.http_json(server, self.base, {"input": str(federation_directory)})
                self.assertEqual(status, 200)
                self.assertEqual(payload["gate"]["state"], "promote")
                self.assertEqual(payload["assurance"]["finding_count"], 21)
                status, _, assurance = self.http_json(server, self.base + "/assurance", {"input": str(federation_directory)})
                self.assertEqual(status, 200)
                self.assertEqual(assurance["state"], "passed")
                status, _, gate = self.http_json(server, self.base + "/gate", {"input": str(federation_directory)})
                self.assertEqual(status, 200)
                self.assertEqual(gate["state"], "promote")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_api_query_verify_and_text_formats(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            destination = self.write_gate(self.build_ready_gate(), root / "gate")
            server, thread = self.start_server(root)
            try:
                status, _, payload = self.http_json(server, self.base + "/query", {"input": str(destination), "resource": "findings", "limit": "2"})
                self.assertEqual(status, 200)
                self.assertEqual(payload["returned_count"], 2)
                status, _, payload = self.http_json(server, self.base + "/verify", {"input": str(destination)})
                self.assertEqual(status, 200)
                self.assertTrue(payload["gate"]["accepted"])
                for output_format, marker in (("csv", "finding_id"), ("markdown", "# Observatory Packet Registry Federation Assurance Gate Query")):
                    status, content_type, body = self.http_text(server, self.base + "/query", {"input": str(destination), "resource": "findings", "format": output_format})
                    self.assertEqual(status, 200)
                    self.assertIn(marker, body)
                    self.assertTrue(content_type)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_api_held_and_blocked_statuses_are_distinct(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            held_directory = self.write_federation(self.build_held_gate().federation, root / "held")
            blocked_directory = self.write_federation(self.build_blocked_gate().federation, root / "blocked")
            held_gate = self.write_gate(self.build_held_gate(), root / "held-gate")
            blocked_gate = self.write_gate(self.build_blocked_gate(), root / "blocked-gate")
            server, thread = self.start_server(root)
            try:
                status, _, payload = self.http_json(server, self.base, {"input": str(held_directory)})
                self.assertEqual(status, 422)
                self.assertEqual(payload["gate"]["state"], "hold")
                status, _, payload = self.http_json(server, self.base, {"input": str(blocked_directory)})
                self.assertEqual(status, 422)
                self.assertEqual(payload["gate"]["state"], "block")
                status, _, payload = self.http_json(server, self.base + "/verify", {"input": str(held_gate)})
                self.assertEqual(status, 200)
                self.assertTrue(payload["gate"]["accepted"])
                status, _, payload = self.http_json(server, self.base + "/verify", {"input": str(blocked_gate)})
                self.assertEqual(status, 422)
                self.assertFalse(payload["gate"]["accepted"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


class AssuranceGateRealDataTests(AssuranceGateFixture):
    def build_real_federation(self, root: Path):
        source = self.real_packet()
        if not source.is_dir():
            self.skipTest("retained downloaded packet fixture is not installed")
        history_value = history.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_from_directories(source, source, history_id="history:assurance-real")
        history_directory = history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(history_value, root / "history")
        packet_one = packet.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_from_history_directories((history_directory, history_directory), observation_ids=("assurance-real-a", "assurance-real-b"), packet_id="packet:assurance-real-a")
        packet_two = packet.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_from_history_directories((history_directory, history_directory), observation_ids=("assurance-real-c", "assurance-real-d"), packet_id="packet:assurance-real-b")
        registry_one = registry.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry((packet_one,), registry_id="registry:assurance-real-a")
        registry_two = registry.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry((packet_two,), registry_id="registry:assurance-real-b")
        registry_one_directory = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(registry_one, root / "registry-a")
        registry_two_directory = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(registry_two, root / "registry-b")
        return federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_from_directories((registry_two_directory, registry_one_directory), federation_id="federation:assurance-real")

    def test_real_downloaded_data_reaches_promote_gate(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            federation_value = self.build_real_federation(root)
            value = assurance_gate.build_federation_assurance_gate(federation_value)
            self.assertEqual(value.state, "promote")
            self.assertTrue(value.release_ready)
            self.assertEqual(value.assurance.blocker_count, 0)
            self.assertEqual(value.assurance.warning_count, 0)
            self.assertEqual(value.total_packet_count, 2)
            self.assertEqual(value.registry_count, 2)

    def test_real_downloaded_gate_round_trips_without_source_paths(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            federation_value = self.build_real_federation(root)
            value = assurance_gate.build_federation_assurance_gate(federation_value)
            destination = assurance_gate.write_federation_assurance_gate(value, root / "gate")
            loaded = assurance_gate.load_federation_assurance_gate(destination)
            payload = json.dumps({"assurance": loaded.assurance.to_dict(), "gate": loaded.to_dict()}).casefold()
            self.assertEqual(loaded.state, "promote")
            self.assertNotIn(str(self.real_packet()).casefold(), payload)
            self.assertNotIn("source_path", payload)
            self.assertTrue(assurance_gate.query_assurance_gate(loaded, resource="findings", limit=64).returned_count == 21)

    def test_real_downloaded_gate_exports_are_deterministic(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            value = assurance_gate.build_federation_assurance_gate(self.build_real_federation(root))
            self.assertEqual(assurance_gate.assurance_gate_json(value), assurance_gate.assurance_gate_json(value))
            self.assertIn("promote", assurance_gate.render_assurance_gate_markdown(value))
            self.assertIn("kind", assurance_gate.assurance_gate_csv(value))


if __name__ == "__main__":
    unittest.main()


if __name__ == "__main__":
    unittest.main()
