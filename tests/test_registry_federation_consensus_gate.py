"""Contract tests for the consensus release-control gate family."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import registry_federation_consensus_gate as gate_model
from glio_noncode import registry_federation_consensus_gate_audit as gate_audit_model
from glio_noncode import registry_federation_consensus_gate_diff as diff_model
from glio_noncode import registry_federation_consensus_gate_diff_audit as diff_audit_model
from glio_noncode import registry_federation_consensus_gate_history as history_model
from glio_noncode import registry_federation_consensus_gate_history_audit as history_audit_model
from glio_noncode import registry_federation_consensus_gate_observatory as observatory_model
from glio_noncode import registry_federation_consensus_gate_observatory_audit as observatory_audit_model
from glio_noncode import registry_federation_consensus_gate_package as package_model
from glio_noncode import registry_federation_consensus_gate_package_audit as package_audit_model
from glio_noncode import registry_federation_consensus_gate_query as query_model
from glio_noncode import registry_federation_consensus_gate_runtime as runtime_model
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package import DurableCatalogPromotionPackageFixture


class RegistryFederationConsensusGateTests(DurableCatalogPromotionPackageFixture):
    """Exercise the release decision boundary using generated registry data."""

    def _registries(self, root: Path) -> tuple[Path, Path, Path]:
        ready_package = self.package_for(root / "ready-input", package_id="gate-package")
        held_package = self.package_for(root / "held-input", package_id="gate-package", held=True)
        ready = self.registry_for(root / "ready", ready_package, registry_id="gate-ready")
        copy = self.registry_for(root / "copy", ready_package, registry_id="gate-copy")
        held = self.registry_for(root / "held", held_package, registry_id="gate-held")
        return ready, copy, held

    def registry_for(self, path: Path, package, *, registry_id: str) -> Path:
        from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry as registry_model

        value = registry_model.build_registry((package,), registry_id=registry_id)
        registry_model.write_registry(value, path)
        return path

    def _runtime(self, root: Path, *names: str) -> runtime_model.RegistryFederationConsensusGateRuntime:
        ready, copy, held = self._registries(root / "registries")
        paths = {"primary": ready, "replica": copy, "archive": held}
        return runtime_model.run_gate_runtime(tuple((name, paths[name]) for name in names), runtime_id="gate-test-runtime", federation_id="gate-test-federation", consensus_id="gate-test-consensus", gate_id="gate-test", resources=("summary", "checks", "failures", "evidence"), limit=100)

    def _strict_policy(self, minimum_quorum: int) -> gate_model.RegistryFederationConsensusGatePolicy:
        pending = gate_model.RegistryFederationConsensusGatePolicy("strict-policy", ("consistent",), ("accept",), 1, minimum_quorum, 1, 0, 0, True, True, True, False, gate_model.POLICY_PREFIX + ":pending")
        return gate_model.RegistryFederationConsensusGatePolicy(pending.policy_id, pending.allowed_states, pending.allowed_decisions, pending.minimum_peer_count, pending.minimum_quorum, pending.minimum_selected_packages, pending.maximum_unresolved_packages, pending.maximum_blocking_steps, pending.require_consensus_audit, pending.require_remediation_audit, pending.require_remediation_query_audit, pending.require_complete_queries, gate_model.address_policy(pending))

    def test_clean_runtime_is_eligible_and_replays_all_child_links(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self._runtime(Path(temporary), "primary", "replica")
            self.assertTrue(value.gate.accepted)
            self.assertEqual((value.gate.state, value.gate.decision), ("eligible", "promote"))
            self.assertEqual((value.gate.check_count, value.gate.passed_count, value.gate.failed_count), (20, 20, 0))
            self.assertEqual(value.gate.runtime_address, value.consensus_runtime.content_address)
            self.assertEqual(value.gate.consensus_address, value.consensus_runtime.consensus.content_address)
            self.assertEqual(value.audit.gate_address, value.gate.content_address)
            self.assertEqual(value.query.query.gate_address, value.gate.content_address)
            self.assertEqual(runtime_model.runtime_from_mapping(value.to_dict()).to_dict(), value.to_dict())
            self.assertEqual(json.loads(runtime_model.runtime_json(value))["gate"]["decision"], "promote")

    def test_divergent_runtime_is_blocked_even_when_child_audits_are_valid(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self._runtime(Path(temporary), "primary", "archive")
            self.assertFalse(value.consensus_runtime.consensus.accepted)
            self.assertTrue(value.consensus_runtime.audit.accepted)
            self.assertFalse(value.gate.accepted)
            self.assertEqual((value.gate.state, value.gate.decision), ("blocked", "hold"))
            self.assertGreater(value.gate.failed_count, 0)
            failed = {item.check_id for item in value.gate.checks if not item.passed}
            self.assertIn("runtime-accepted", failed)
            self.assertIn("state-allowed", failed)
            self.assertIn("decision-allowed", failed)
            self.assertEqual(value.summary()["accepted"], False)

    def test_gate_policy_can_create_a_review_transition_without_mutating_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self._runtime(Path(temporary), "primary", "replica")
            original_address = value.consensus_runtime.content_address
            strict = gate_model.evaluate_gate(value.consensus_runtime, policy=self._strict_policy(value.consensus_runtime.federation.peer_count + 1), gate_id="strict-gate")
            self.assertFalse(strict.accepted)
            self.assertEqual((strict.state, strict.decision), ("review", "review"))
            self.assertIn("minimum-quorum", {item.check_id for item in strict.checks if not item.passed})
            self.assertEqual(value.consensus_runtime.content_address, original_address)
            self.assertTrue(value.gate.accepted)

    def test_default_policy_is_content_addressed_and_conserves_limits(self):
        policy = gate_model.default_policy(policy_id="policy-test")
        self.assertEqual(gate_model.address_policy(policy), policy.content_address)
        self.assertEqual(policy.allowed_states, ("consistent",))
        self.assertEqual(policy.allowed_decisions, ("accept",))
        self.assertEqual(policy.minimum_peer_count, 1)
        self.assertEqual(policy.minimum_quorum, 1)
        self.assertTrue(policy.require_consensus_audit)
        self.assertTrue(policy.require_remediation_audit)
        self.assertTrue(policy.require_remediation_query_audit)
        self.assertFalse(policy.require_complete_queries)
        self.assertEqual(set(policy.to_dict()), set(gate_model.RegistryFederationConsensusGatePolicy.FIELDS))
        self.assertEqual(gate_model.RegistryFederationConsensusGatePolicy.from_mapping(policy.to_dict()).to_dict(), policy.to_dict())

    def test_gate_serializers_keep_public_fields_and_deterministic_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            gate = self._runtime(Path(temporary), "primary", "replica").gate
            document = json.loads(gate_model.gate_json(gate))
            self.assertEqual(gate_model.gate_from_mapping(document).to_dict(), gate.to_dict())
            self.assertEqual(tuple(document["checks"][index]["ordinal"] for index in range(20)), tuple(range(1, 21)))
            self.assertIn("# Consensus Release Gate", gate_model.render_gate_markdown(gate))
            csv_text = gate_model.gate_csv(gate)
            self.assertTrue(csv_text.startswith("ordinal,check_id,passed,detail,evidence_addresses,content_address"))
            self.assertNotIn("/", gate_model.gate_json(gate))
            self.assertNotIn("\\", gate_model.gate_json(gate))
            self.assertNotIn('"agent"', gate_model.gate_json(gate))

    def test_gate_audit_recomputes_every_check_independently(self):
        with tempfile.TemporaryDirectory() as temporary:
            gate = self._runtime(Path(temporary), "primary", "replica").gate
            value = gate_audit_model.audit_gate(gate)
            self.assertTrue(value.accepted)
            self.assertEqual((value.check_count, value.passed_count, value.failed_count), (16, 16, 0))
            self.assertEqual(value.gate_address, gate.content_address)
            self.assertEqual(gate_audit_model.audit_from_mapping(value.to_dict()).to_dict(), value.to_dict())
            self.assertEqual(json.loads(gate_audit_model.audit_json(value))["accepted"], True)
            self.assertIn("independent policy-gate structure checks", gate_audit_model.capabilities()["features"])

    def test_gate_audit_rejects_modified_check_and_modified_summary(self):
        with tempfile.TemporaryDirectory() as temporary:
            gate = self._runtime(Path(temporary), "primary", "replica").gate
            audit = gate_audit_model.audit_gate(gate)
            corrupted = audit.to_dict()
            corrupted["passed_count"] = 0
            with self.assertRaises(ValidationError):
                gate_audit_model.audit_from_mapping(corrupted)
            corrupted = audit.to_dict()
            corrupted["checks"] = list(corrupted["checks"])
            corrupted["checks"][0] = dict(corrupted["checks"][0])
            corrupted["checks"][0]["detail"] = "changed"
            with self.assertRaises(ValidationError):
                gate_audit_model.audit_from_mapping(corrupted)
            corrupted = audit.to_dict()
            corrupted["content_address"] = gate_audit_model.AUDIT_PREFIX + ":tampered"
            with self.assertRaises(ValidationError):
                gate_audit_model.audit_from_mapping(corrupted)

    def test_query_supports_resources_filters_and_bounded_pagination(self):
        with tempfile.TemporaryDirectory() as temporary:
            gate = self._runtime(Path(temporary), "primary", "replica").gate
            all_rows = query_model.query_gate(gate, resources=query_model.DEFAULT_RESOURCES, limit=100)
            self.assertEqual(all_rows.total_count, 59)
            self.assertEqual(all_rows.matched_count, 59)
            self.assertEqual(all_rows.returned_count, 59)
            self.assertFalse(all_rows.truncated)
            self.assertEqual(query_model.query_from_mapping(all_rows.to_dict()).to_dict(), all_rows.to_dict())
            first = query_model.query_gate(gate, resources=("checks",), offset=0, limit=3)
            second = query_model.query_gate(gate, resources=("checks",), offset=3, limit=3)
            self.assertEqual(first.returned_count, 3)
            self.assertTrue(first.truncated)
            self.assertEqual(first.next_offset, 3)
            self.assertEqual(tuple(row.ordinal for row in first.rows), (1, 2, 3))
            self.assertEqual(tuple(row.ordinal for row in second.rows), (4, 5, 6))
            failures = query_model.query_gate(gate, resources=("failures",), passed=False)
            self.assertEqual(failures.matched_count, 0)
            selected = query_model.query_gate(gate, resources=("checks",), check_id="minimum-quorum")
            self.assertEqual(selected.matched_count, 1)
            self.assertEqual(selected.rows[0].check_id, "minimum-quorum")
            evidence = query_model.query_gate(gate, resources=("evidence",))
            self.assertEqual(evidence.matched_count, 38)
            self.assertTrue(all(row.evidence_addresses for row in evidence.rows))

    def test_query_rejects_unknown_resource_and_invalid_page(self):
        with tempfile.TemporaryDirectory() as temporary:
            gate = self._runtime(Path(temporary), "primary", "replica").gate
            with self.assertRaises(ValidationError):
                query_model.query_gate(gate, resources=("unknown",))
            with self.assertRaises(ValidationError):
                query_model.query_gate(gate, offset=-1)
            with self.assertRaises(ValidationError):
                query_model.query_gate(gate, limit=0)
            with self.assertRaises(ValidationError):
                query_model.query_from_mapping({"query": {}})

    def test_package_has_exact_six_files_and_replays_nested_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self._runtime(root, "primary", "replica")
            package = package_model.build_package(runtime.consensus_runtime, runtime.gate, audit=runtime.audit, query=runtime.query, package_id="gate-handoff")
            destination = root / "package"
            package_model.write_package(package, destination)
            self.assertEqual(tuple(sorted(item.name for item in destination.iterdir())), tuple(sorted(package_model.FILES)))
            replayed = package_model.load_package(destination)
            self.assertEqual(replayed.to_dict(), package.to_dict())
            self.assertEqual(replayed.runtime.content_address, runtime.consensus_runtime.content_address)
            self.assertEqual(replayed.gate.content_address, runtime.gate.content_address)
            self.assertEqual(replayed.audit.content_address, runtime.audit.content_address)
            self.assertEqual(replayed.query.content_address, runtime.query.content_address)
            self.assertEqual(package_model.package_from_mapping(package.to_dict()).to_dict(), package.to_dict())
            self.assertEqual(json.loads(package_model.package_json(package))["package_id"], "gate-handoff")
            package_bytes = package_model.package_bytes(package)
            self.assertEqual(tuple(sorted(package_bytes)), tuple(sorted(package_model.FILES)))
            self.assertEqual(package_bytes[package_model.PACKAGE_NAME], package_model.package_json(package).encode("utf-8"))

    def test_package_write_is_atomic_and_requires_explicit_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self._runtime(root, "primary", "replica")
            package = package_model.build_package(runtime.consensus_runtime, runtime.gate, audit=runtime.audit, query=runtime.query)
            destination = root / "package"
            package_model.write_package(package, destination)
            with self.assertRaises(ValidationError):
                package_model.write_package(package, destination)
            package_model.write_package(package, destination, overwrite=True)
            self.assertEqual(package_model.verify_package_directory(destination).content_address, package.content_address)
            self.assertEqual(tuple(sorted(item.name for item in destination.iterdir())), tuple(sorted(package_model.FILES)))

    def test_package_loader_rejects_each_projection_tamper(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self._runtime(root, "primary", "replica")
            package = package_model.build_package(runtime.consensus_runtime, runtime.gate, audit=runtime.audit, query=runtime.query)
            destination = root / "package"
            for name, field, replacement in ((package_model.MANIFEST_NAME, "package_id", "changed"), (package_model.PACKAGE_NAME, "package_id", "changed"), (package_model.RUNTIME_NAME, "runtime_id", "changed"), (package_model.GATE_NAME, "accepted", False), (package_model.AUDIT_NAME, "accepted", False), (package_model.QUERY_NAME, "returned_count", 0)):
                package_model.write_package(package, destination, overwrite=True)
                path = destination / name
                document = json.loads(path.read_text(encoding="utf-8"))
                document[field] = replacement
                path.write_text(json.dumps(document, separators=(",", ":")), encoding="utf-8")
                with self.assertRaises(ValidationError):
                    package_model.load_package(destination)

    def test_package_audit_recomputes_member_set_and_replays_mapping(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self._runtime(root, "primary", "replica")
            package = package_model.build_package(runtime.consensus_runtime, runtime.gate, audit=runtime.audit, query=runtime.query)
            value = package_audit_model.audit_package(package)
            self.assertTrue(value.accepted)
            self.assertEqual((value.check_count, value.passed_count, value.failed_count), (12, 12, 0))
            self.assertEqual(package_audit_model.audit_from_mapping(value.to_dict()).to_dict(), value.to_dict())
            self.assertIn("independent package member checks", package_audit_model.capabilities()["features"])
            corrupted = value.to_dict()
            corrupted["passed_count"] = 1
            with self.assertRaises(ValidationError):
                package_audit_model.audit_from_mapping(corrupted)

    def test_diff_attributes_clean_to_strict_gate_transition(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = self._runtime(Path(temporary), "primary", "replica")
            strict = gate_model.evaluate_gate(runtime.consensus_runtime, policy=self._strict_policy(runtime.consensus_runtime.federation.peer_count + 1), gate_id="strict-gate")
            value = diff_model.build_diff(runtime.gate, strict, diff_id="gate-transition")
            self.assertEqual((value.left_state, value.left_decision, value.left_accepted), ("eligible", "promote", True))
            self.assertEqual((value.right_state, value.right_decision, value.right_accepted), ("review", "review", False))
            self.assertGreater(value.item_count, 0)
            self.assertEqual(value.added_count + value.removed_count + value.changed_count, value.item_count)
            self.assertEqual(diff_model.diff_from_mapping(value.to_dict()).to_dict(), value.to_dict())
            self.assertIn("policy", {item.resource for item in value.items})
            self.assertIn("disposition", {item.resource for item in value.items})
            self.assertIn("# Consensus Release Gate Diff", diff_model.render_diff_markdown(value))
            self.assertTrue(diff_model.diff_csv(value).startswith("ordinal,resource,item_id,change"))

    def test_diff_audit_recomputes_transition_and_rejects_counter_tamper(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = self._runtime(Path(temporary), "primary", "replica")
            strict = gate_model.evaluate_gate(runtime.consensus_runtime, policy=self._strict_policy(runtime.consensus_runtime.federation.peer_count + 1), gate_id="strict-gate")
            diff = diff_model.build_diff(runtime.gate, strict)
            value = diff_audit_model.audit_diff(diff)
            self.assertTrue(value.accepted)
            self.assertEqual((value.check_count, value.passed_count, value.failed_count), (13, 13, 0))
            self.assertEqual(diff_audit_model.audit_from_mapping(value.to_dict()).to_dict(), value.to_dict())
            corrupted = value.to_dict()
            corrupted["passed_count"] = 0
            with self.assertRaises(ValidationError):
                diff_audit_model.audit_from_mapping(corrupted)
            corrupted = value.to_dict()
            corrupted["content_address"] = diff_audit_model.AUDIT_PREFIX + ":tampered"
            with self.assertRaises(ValidationError):
                diff_audit_model.audit_from_mapping(corrupted)

    def test_history_is_append_only_and_counters_follow_gate_dispositions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self._runtime(root, "primary", "replica")
            strict = gate_model.evaluate_gate(runtime.consensus_runtime, policy=self._strict_policy(runtime.consensus_runtime.federation.peer_count + 1), gate_id="strict-gate")
            strict_audit = gate_audit_model.audit_gate(strict)
            value = history_model.build_history(((runtime.gate, runtime.audit), (strict, strict_audit)), history_id="gate-history")
            self.assertEqual((value.entry_count, value.accepted_count, value.review_count, value.blocked_count), (2, 1, 1, 0))
            self.assertEqual(tuple(item.ordinal for item in value.entries), (1, 2))
            self.assertEqual(value.entries[0].gate_address, runtime.gate.content_address)
            self.assertEqual(value.entries[1].audit_address, strict_audit.content_address)
            appended = history_model.append_history(value, runtime.gate, runtime.audit)
            self.assertEqual((appended.entry_count, appended.accepted_count), (3, 2))
            self.assertEqual(tuple(item.ordinal for item in appended.entries), (1, 2, 3))
            destination = root / "history"
            history_model.write_history(value, destination)
            self.assertEqual(history_model.load_history(destination).to_dict(), value.to_dict())
            self.assertEqual(history_model.verify_history_directory(destination).content_address, value.content_address)
            self.assertIn("# Consensus Release Gate History", history_model.render_history_markdown(value))
            self.assertTrue(history_model.history_csv(value).startswith("ordinal,gate_id,runtime_id"))

    def test_history_loader_rejects_manifest_and_entry_projection_tamper(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self._runtime(root, "primary", "replica")
            value = history_model.build_history(((runtime.gate, runtime.audit),), history_id="gate-history")
            destination = root / "history"
            history_model.write_history(value, destination)
            for name, field, replacement in ((history_model.MANIFEST_NAME, "entry_count", 2), (history_model.HISTORY_NAME, "accepted_count", 0), (history_model.ENTRIES_NAME, "state", "blocked")):
                history_model.write_history(value, destination, overwrite=True)
                path = destination / name
                document = json.loads(path.read_text(encoding="utf-8"))
                if name == history_model.ENTRIES_NAME:
                    document[0][field] = replacement
                else:
                    document[field] = replacement
                path.write_text(json.dumps(document, separators=(",", ":")), encoding="utf-8")
                with self.assertRaises(ValidationError):
                    history_model.load_history(destination)

    def test_history_audit_recomputes_order_and_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = self._runtime(Path(temporary), "primary", "replica")
            value = history_model.build_history(((runtime.gate, runtime.audit),), history_id="gate-history")
            audit = history_audit_model.audit_history(value)
            self.assertTrue(audit.accepted)
            self.assertEqual((audit.check_count, audit.passed_count, audit.failed_count), (12, 12, 0))
            self.assertEqual(history_audit_model.audit_from_mapping(audit.to_dict()).to_dict(), audit.to_dict())
            self.assertIn("entry ordering and counter conservation", history_audit_model.capabilities()["features"])

    def test_observatory_aggregates_history_and_filters_review_entries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self._runtime(root, "primary", "replica")
            strict = gate_model.evaluate_gate(runtime.consensus_runtime, policy=self._strict_policy(runtime.consensus_runtime.federation.peer_count + 1), gate_id="strict-gate")
            value = observatory_model.build_observatory((history_model.build_history(((runtime.gate, runtime.audit), (strict, gate_audit_model.audit_gate(strict))), history_id="gate-history"),), observatory_id="gate-observatory")
            self.assertEqual((value.history_count, value.observation_count, value.accepted_count, value.review_count, value.blocked_count), (1, 2, 1, 1, 0))
            selected = observatory_model.query_observatory(value, accepted=False, offset=0, limit=10)
            self.assertEqual((selected.matched_count, selected.returned_count), (1, 1))
            self.assertEqual(selected.rows[0].decision, "review")
            self.assertEqual(observatory_model.observatory_from_mapping(value.to_dict()).to_dict(), value.to_dict())
            self.assertEqual(observatory_model.verify_query_result(selected).to_dict(), selected.to_dict())
            self.assertIn("# Consensus Release Gate Observatory", observatory_model.render_observatory_markdown(value))

    def test_observatory_audit_and_schema_contract_are_stable(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = self._runtime(Path(temporary), "primary", "replica")
            history = history_model.build_history(((runtime.gate, runtime.audit),), history_id="gate-history")
            value = observatory_model.build_observatory((history,), observatory_id="gate-observatory")
            audit = observatory_audit_model.audit_observatory(value)
            self.assertTrue(audit.accepted)
            self.assertEqual((audit.check_count, audit.passed_count, audit.failed_count), (12, 12, 0))
            self.assertEqual(observatory_audit_model.audit_from_mapping(audit.to_dict()).to_dict(), audit.to_dict())
            self.assertEqual(observatory_model.observatory_schema()["required"], list(observatory_model.RegistryFederationConsensusGateObservatory.FIELDS))
            self.assertEqual(observatory_model.result_schema()["required"], list(observatory_model.RegistryFederationConsensusGateObservatoryQueryResult.FIELDS))
            self.assertEqual(package_model.manifest_schema()["required"][-1], "manifest_address")
            self.assertEqual(len(gate_model.CHECK_IDS), 20)

    def test_public_capabilities_do_not_advertise_private_paths_or_agent_metadata(self):
        modules = (gate_model, gate_audit_model, query_model, package_model, package_audit_model, runtime_model, diff_model, diff_audit_model, history_model, history_audit_model, observatory_model, observatory_audit_model)
        for module in modules:
            payload = json.dumps(module.capabilities(), sort_keys=True)
            self.assertNotIn("agent", payload.lower(), module.__name__)
            self.assertNotIn("\\", payload, module.__name__)
            self.assertNotIn('"/', payload, module.__name__)


if __name__ == "__main__":
    unittest.main()
