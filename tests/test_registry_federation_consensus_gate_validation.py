"""Adversarial and replay validation for the consensus release-control plane."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from examples.registry_federation_real_downloaded_data_demo import run as run_downloaded_demo
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


class RegistryFederationConsensusGateValidationTests(DurableCatalogPromotionPackageFixture):
    """Keep public mappings and content-addressed transitions fail-closed."""

    def _registries(self, root: Path) -> tuple[Path, Path, Path]:
        from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry as registry_model

        ready_package = self.package_for(root / "ready-input", package_id="validation-package")
        held_package = self.package_for(root / "held-input", package_id="validation-package", held=True)
        values = (
            registry_model.build_registry((ready_package,), registry_id="validation-ready"),
            registry_model.build_registry((ready_package,), registry_id="validation-copy"),
            registry_model.build_registry((held_package,), registry_id="validation-held"),
        )
        paths = (root / "ready", root / "copy", root / "held")
        for value, path in zip(values, paths, strict=True):
            registry_model.write_registry(value, path)
        return paths

    def _runtime(self, root: Path, *, divergent: bool = False, limit: int = 100) -> runtime_model.RegistryFederationConsensusGateRuntime:
        ready, copy, held = self._registries(root / "registries")
        second = held if divergent else copy
        return runtime_model.run_gate_runtime((("primary", ready), ("replica", second)), runtime_id="validation-runtime-divergent" if divergent else "validation-runtime", federation_id="validation-federation", consensus_id="validation-consensus-divergent" if divergent else "validation-consensus", gate_id="validation-gate", resources=query_model.DEFAULT_RESOURCES, limit=limit)

    def _strict_policy(self, minimum_quorum: int) -> gate_model.RegistryFederationConsensusGatePolicy:
        pending = gate_model.RegistryFederationConsensusGatePolicy("validation-strict-policy", ("consistent",), ("accept",), 1, minimum_quorum, 1, 0, 0, True, True, True, False, gate_model.POLICY_PREFIX + ":pending")
        return gate_model.RegistryFederationConsensusGatePolicy(pending.policy_id, pending.allowed_states, pending.allowed_decisions, pending.minimum_peer_count, pending.minimum_quorum, pending.minimum_selected_packages, pending.maximum_unresolved_packages, pending.maximum_blocking_steps, pending.require_consensus_audit, pending.require_remediation_audit, pending.require_remediation_query_audit, pending.require_complete_queries, gate_model.address_policy(pending))

    def test_every_gate_check_has_a_unique_address_and_public_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            gate = self._runtime(Path(temporary)).gate
            addresses = tuple(item.content_address for item in gate.checks)
            self.assertEqual(len(addresses), len(set(addresses)))
            self.assertTrue(all(address.startswith(gate_model.CHECK_PREFIX + ":") for address in addresses))
            self.assertTrue(all(item.evidence_addresses for item in gate.checks))
            self.assertTrue(all("/" not in evidence and "\\" not in evidence for item in gate.checks for evidence in item.evidence_addresses))
            self.assertEqual(tuple(item.check_id for item in gate.checks), gate_model.CHECK_IDS)
            self.assertEqual(tuple(item.ordinal for item in gate.checks), tuple(range(1, 21)))

    def test_gate_mapping_rejects_missing_unknown_and_reordered_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            mapping = self._runtime(Path(temporary)).gate.to_dict()
            missing = dict(mapping)
            del missing["accepted"]
            with self.assertRaises(ValidationError):
                gate_model.gate_from_mapping(missing)
            unknown = dict(mapping)
            unknown["private_note"] = "not-public"
            with self.assertRaises(ValidationError):
                gate_model.gate_from_mapping(unknown)
            checks = list(mapping["checks"])
            reordered = dict(mapping)
            reordered["checks"] = list(reversed(checks))
            with self.assertRaises(ValidationError):
                gate_model.gate_from_mapping(reordered)
            corrupted = dict(mapping)
            corrupted["check_count"] = mapping["check_count"] + 1
            with self.assertRaises(ValidationError):
                gate_model.gate_from_mapping(corrupted)

    def test_policy_mapping_rejects_unsupported_disposition_and_bad_address(self):
        policy = gate_model.default_policy(policy_id="validation-policy")
        bad_state = policy.to_dict()
        bad_state["allowed_states"] = ["blocked"]
        with self.assertRaises(ValidationError):
            gate_model.RegistryFederationConsensusGatePolicy.from_mapping(bad_state)
        bad_decision = policy.to_dict()
        bad_decision["allowed_decisions"] = ["hold"]
        with self.assertRaises(ValidationError):
            gate_model.RegistryFederationConsensusGatePolicy.from_mapping(bad_decision)
        bad_address = policy.to_dict()
        bad_address["content_address"] = gate_model.POLICY_PREFIX + ":wrong"
        with self.assertRaises(ValidationError):
            gate_model.RegistryFederationConsensusGatePolicy.from_mapping(bad_address)
        empty_states = policy.to_dict()
        empty_states["allowed_states"] = []
        with self.assertRaises(ValidationError):
            gate_model.RegistryFederationConsensusGatePolicy.from_mapping(empty_states)

    def test_runtime_mapping_rejects_child_substitution_and_persistence_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self._runtime(Path(temporary))
            mapping = value.to_dict()
            bad_gate = dict(mapping)
            bad_gate["gate"] = dict(mapping["gate"])
            bad_gate["gate"]["runtime_address"] = runtime_model.RUNTIME_PREFIX + ":substituted"
            with self.assertRaises(ValidationError):
                runtime_model.runtime_from_mapping(bad_gate)
            bad_persistence = dict(mapping)
            bad_persistence["persisted"] = True
            bad_persistence["package_address"] = ""
            with self.assertRaises(ValidationError):
                runtime_model.runtime_from_mapping(bad_persistence)
            bad_query = dict(mapping)
            bad_query["query"] = dict(mapping["query"])
            bad_query["query"]["gate_id"] = "different-gate"
            with self.assertRaises(ValidationError):
                runtime_model.runtime_from_mapping(bad_query)

    def test_runtime_content_address_is_stable_across_json_and_nested_replays(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self._runtime(Path(temporary), limit=7)
            encoded = runtime_model.runtime_json(value)
            decoded = json.loads(encoded)
            replayed = runtime_model.runtime_from_mapping(decoded)
            self.assertEqual(replayed.content_address, value.content_address)
            self.assertEqual(replayed.to_dict(), value.to_dict())
            self.assertEqual(runtime_model.address_runtime(replayed), value.content_address)
            self.assertEqual(replayed.query.query.limit, 7)
            self.assertEqual(replayed.consensus_runtime.query.query.limit, 7)
            self.assertEqual(replayed.gate.content_address, value.gate.content_address)
            self.assertEqual(replayed.audit.content_address, value.audit.content_address)

    def test_query_resource_partitions_are_disjoint_and_complete(self):
        with tempfile.TemporaryDirectory() as temporary:
            gate = self._runtime(Path(temporary)).gate
            summary = query_model.query_gate(gate, resources=("summary",))
            checks = query_model.query_gate(gate, resources=("checks",))
            failures = query_model.query_gate(gate, resources=("failures",))
            evidence = query_model.query_gate(gate, resources=("evidence",))
            self.assertEqual(summary.matched_count, 1)
            self.assertEqual(summary.rows[0].row_id, "summary")
            self.assertEqual(checks.matched_count, 20)
            self.assertEqual(failures.matched_count, 0)
            self.assertEqual(evidence.matched_count, sum(len(item.evidence_addresses) for item in gate.checks))
            self.assertEqual(tuple(row.ordinal for row in checks.rows), tuple(range(1, 21)))
            self.assertEqual(tuple(row.ordinal for row in failures.rows), ())
            self.assertTrue(all(row.resource == "evidence" for row in evidence.rows))
            all_rows = query_model.query_gate(gate)
            self.assertEqual(all_rows.matched_count, summary.matched_count + checks.matched_count + failures.matched_count + evidence.matched_count)

    def test_query_pagination_is_deterministic_at_edges(self):
        with tempfile.TemporaryDirectory() as temporary:
            gate = self._runtime(Path(temporary)).gate
            total = query_model.query_gate(gate, resources=("checks",)).total_count
            empty = query_model.query_gate(gate, resources=("checks",), offset=total, limit=10)
            self.assertEqual(empty.returned_count, 0)
            self.assertFalse(empty.truncated)
            self.assertEqual(empty.next_offset, 0)
            tail = query_model.query_gate(gate, resources=("checks",), offset=total - 1, limit=10)
            self.assertEqual(tail.returned_count, 1)
            self.assertEqual(tail.rows[0].ordinal, total)
            self.assertFalse(tail.truncated)
            page = query_model.query_gate(gate, resources=("checks",), offset=2, limit=4)
            repeat = query_model.query_gate(gate, resources=("checks",), offset=2, limit=4)
            self.assertEqual(page.content_address, repeat.content_address)
            self.assertEqual(page.to_dict(), repeat.to_dict())

    def test_divergent_gate_retains_failed_evidence_for_each_blocking_reason(self):
        with tempfile.TemporaryDirectory() as temporary:
            gate = self._runtime(Path(temporary), divergent=True).gate
            failures = query_model.query_gate(gate, resources=("failures",), passed=False)
            failed_ids = {row.check_id for row in failures.rows}
            self.assertGreaterEqual(len(failed_ids), 5)
            self.assertIn("runtime-accepted", failed_ids)
            self.assertIn("unresolved-packages", failed_ids)
            self.assertTrue(all(row.evidence_addresses for row in failures.rows))
            self.assertEqual(failures.matched_count, gate.failed_count)
            self.assertEqual(failures.returned_count, gate.failed_count)
            self.assertEqual(failures.query.passed, False)

    def test_audit_acceptance_is_independent_of_gate_acceptance(self):
        with tempfile.TemporaryDirectory() as temporary:
            accepted = self._runtime(Path(temporary) / "accepted")
            rejected = self._runtime(Path(temporary) / "rejected", divergent=True)
            accepted_audit = gate_audit_model.audit_gate(accepted.gate)
            rejected_audit = gate_audit_model.audit_gate(rejected.gate)
            self.assertTrue(accepted.gate.accepted)
            self.assertTrue(accepted_audit.accepted)
            self.assertFalse(rejected.gate.accepted)
            self.assertTrue(rejected_audit.accepted)
            self.assertEqual(accepted_audit.failed_count, 0)
            self.assertEqual(rejected_audit.failed_count, 0)
            self.assertNotEqual(accepted.gate.content_address, rejected.gate.content_address)
            self.assertNotEqual(accepted_audit.gate_address, rejected_audit.gate_address)

    def test_package_member_bytes_replay_exactly_and_are_path_free(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self._runtime(root)
            package = package_model.build_package(runtime.consensus_runtime, runtime.gate, audit=runtime.audit, query=runtime.query, package_id="byte-checked-package")
            members = package_model.package_bytes(package)
            self.assertEqual(tuple(sorted(members)), tuple(sorted(package_model.FILES)))
            self.assertEqual(members[package_model.MANIFEST_NAME], json.dumps(members and json.loads(members[package_model.MANIFEST_NAME]), separators=(",", ":"), sort_keys=True).encode("utf-8"))
            self.assertTrue(all(b"\\" not in payload and b"/" not in payload for payload in members.values()))
            self.assertNotIn(b"agent", b"".join(members.values()).lower())
            self.assertEqual(json.loads(members[package_model.PACKAGE_NAME].decode("utf-8"))["package_id"], "byte-checked-package")
            self.assertEqual(json.loads(members[package_model.RUNTIME_NAME].decode("utf-8"))["runtime_id"], runtime.consensus_runtime.runtime_id)
            self.assertEqual(json.loads(members[package_model.GATE_NAME].decode("utf-8"))["gate_id"], runtime.gate.gate_id)

    def test_package_audit_fails_closed_on_replaced_nested_addresses(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = self._runtime(Path(temporary))
            package = package_model.build_package(runtime.consensus_runtime, runtime.gate, audit=runtime.audit, query=runtime.query)
            mapping = package.to_dict()
            mapping["audit"] = dict(mapping["audit"])
            mapping["audit"]["gate_address"] = gate_model.GATE_PREFIX + ":substituted"
            with self.assertRaises(ValidationError):
                package_model.package_from_mapping(mapping)
            mapping = package.to_dict()
            mapping["query"] = dict(mapping["query"])
            mapping["query"]["gate_id"] = "substituted"
            with self.assertRaises(ValidationError):
                package_model.package_from_mapping(mapping)
            audit = package_audit_model.audit_package(package)
            corrupted = audit.to_dict()
            corrupted["checks"] = list(corrupted["checks"])
            corrupted["checks"][0] = dict(corrupted["checks"][0])
            corrupted["checks"][0]["observed"] = "substituted"
            with self.assertRaises(ValidationError):
                package_audit_model.audit_from_mapping(corrupted)

    def test_diff_same_gate_is_empty_and_replays_as_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            gate = self._runtime(Path(temporary)).gate
            value = diff_model.build_diff(gate, gate, diff_id="identity-diff")
            self.assertEqual((value.item_count, value.added_count, value.removed_count, value.changed_count), (0, 0, 0, 0))
            self.assertEqual((value.left_state, value.right_state, value.left_accepted, value.right_accepted), ("eligible", "eligible", True, True))
            self.assertEqual(diff_model.diff_from_mapping(value.to_dict()).to_dict(), value.to_dict())
            audit = diff_audit_model.audit_diff(value)
            self.assertTrue(audit.accepted)
            self.assertEqual(audit.failed_count, 0)

    def test_diff_value_hashes_are_not_raw_gate_payloads(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = self._runtime(Path(temporary))
            strict = gate_model.evaluate_gate(runtime.consensus_runtime, policy=self._strict_policy(runtime.consensus_runtime.federation.peer_count + 1), gate_id="strict-gate")
            value = diff_model.build_diff(runtime.gate, strict)
            for item in value.items:
                if item.left_value:
                    self.assertTrue(item.left_value.startswith(diff_model.ITEM_PREFIX + "-value:"))
                if item.right_value:
                    self.assertTrue(item.right_value.startswith(diff_model.ITEM_PREFIX + "-value:"))
                self.assertTrue(all("/" not in evidence and "\\" not in evidence for evidence in item.evidence_addresses))
            self.assertTrue(value.left.checks)
            self.assertTrue(value.right.checks)

    def test_history_content_address_changes_when_append_changes_entry_set(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self._runtime(root)
            strict = gate_model.evaluate_gate(runtime.consensus_runtime, policy=self._strict_policy(runtime.consensus_runtime.federation.peer_count + 1), gate_id="strict-gate")
            value = history_model.build_history(((runtime.gate, runtime.audit),), history_id="history-address")
            appended = history_model.append_history(value, strict, gate_audit_model.audit_gate(strict))
            self.assertNotEqual(value.content_address, appended.content_address)
            self.assertEqual(value.entry_count, 1)
            self.assertEqual(appended.entry_count, 2)
            self.assertEqual(appended.entries[0].content_address, value.entries[0].content_address)
            self.assertEqual(appended.entries[1].ordinal, 2)
            self.assertEqual(history_model.address_history(value), value.content_address)
            self.assertEqual(history_model.address_history(appended), appended.content_address)

    def test_history_audit_rejects_ordinal_and_counter_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = self._runtime(Path(temporary))
            value = history_model.build_history(((runtime.gate, runtime.audit),), history_id="history-audit")
            audit = history_audit_model.audit_history(value)
            self.assertTrue(audit.accepted)
            mapping = value.to_dict()
            mapping["entries"] = [dict(mapping["entries"][0])]
            mapping["entries"][0]["ordinal"] = 3
            with self.assertRaises(ValidationError):
                history_model.history_from_mapping(mapping)
            mapping = value.to_dict()
            mapping["accepted_count"] = 0
            with self.assertRaises(ValidationError):
                history_model.history_from_mapping(mapping)
            audit_mapping = audit.to_dict()
            audit_mapping["failed_count"] = 1
            with self.assertRaises(ValidationError):
                history_audit_model.audit_from_mapping(audit_mapping)

    def test_observatory_content_address_and_query_address_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = self._runtime(Path(temporary))
            strict = gate_model.evaluate_gate(runtime.consensus_runtime, policy=self._strict_policy(runtime.consensus_runtime.federation.peer_count + 1), gate_id="strict-gate")
            history = history_model.build_history(((runtime.gate, runtime.audit), (strict, gate_audit_model.audit_gate(strict))), history_id="observatory-history")
            value = observatory_model.build_observatory((history,), observatory_id="observatory-address")
            result = observatory_model.query_observatory(value, state="review", offset=0, limit=1)
            self.assertEqual(result.matched_count, 1)
            self.assertEqual(result.returned_count, 1)
            self.assertEqual(observatory_model.observatory_from_mapping(value.to_dict()).to_dict(), value.to_dict())
            self.assertEqual(observatory_model.query_from_mapping(result.to_dict()).to_dict(), result.to_dict())
            self.assertEqual(observatory_model.address_observatory(value), value.content_address)
            self.assertEqual(observatory_model.address_result(result), result.content_address)
            audit = observatory_audit_model.audit_observatory(value)
            self.assertTrue(audit.accepted)
            self.assertEqual(audit.observatory_address, value.content_address)

    def test_observatory_query_filters_return_no_false_positives(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = self._runtime(Path(temporary))
            strict = gate_model.evaluate_gate(runtime.consensus_runtime, policy=self._strict_policy(runtime.consensus_runtime.federation.peer_count + 1), gate_id="strict-gate")
            history = history_model.build_history(((runtime.gate, runtime.audit), (strict, gate_audit_model.audit_gate(strict))), history_id="filter-history")
            value = observatory_model.build_observatory((history,), observatory_id="filter-observatory")
            for state, decision, accepted, expected in (("eligible", "promote", True, 1), ("review", "review", False, 1), ("blocked", "hold", False, 0), ("", "", None, 2)):
                result = observatory_model.query_observatory(value, state=state, decision=decision, accepted=accepted, offset=0, limit=10)
                self.assertEqual(result.matched_count, expected)
                self.assertTrue(all((not state or row.state == state) and (not decision or row.decision == decision) and (accepted is None or row.accepted == accepted) for row in result.rows))

    def test_real_downloaded_demo_reports_acceptance_package_replay_and_transition_audits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ready, copy, _ = self._registries(root / "registries")
            report = run_downloaded_demo(ready, copy, federation_id="validation-downloaded-data", destination=None, limit=100)
            self.assertTrue(report["federation"]["accepted"])
            self.assertTrue(report["gate"]["accepted"])
            self.assertTrue(report["consensus"]["accepted"])
            self.assertTrue(report["consensus_gate"]["accepted"])
            self.assertTrue(report["consensus_gate_audit"]["accepted"])
            self.assertTrue(report["consensus_gate_diff_audit"]["accepted"])
            self.assertTrue(report["consensus_gate_history_audit"]["accepted"])
            self.assertTrue(report["consensus_gate_observatory_audit"]["accepted"])
            self.assertTrue(report["consensus_gate_package_audit"]["accepted"])
            self.assertTrue(report["consensus_gate_package_disk_replay"])
            self.assertEqual(report["consensus_gate_history"]["entry_count"], 2)
            self.assertEqual(report["consensus_gate_observatory"]["review_count"], 1)

    def test_real_downloaded_demo_preserves_divergence_as_hold(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ready, _, held = self._registries(root / "registries")
            report = run_downloaded_demo(ready, held, federation_id="validation-divergent-data", destination=None, limit=100)
            self.assertFalse(report["federation"]["accepted"])
            self.assertFalse(report["gate"]["accepted"])
            self.assertFalse(report["consensus"]["accepted"])
            self.assertFalse(report["consensus_gate"]["accepted"])
            self.assertEqual(report["consensus_gate"]["state"], "blocked")
            self.assertEqual(report["consensus_gate"]["decision"], "hold")
            self.assertTrue(report["consensus_gate_audit"]["accepted"])
            self.assertTrue(report["consensus_gate_diff_audit"]["accepted"])
            self.assertTrue(report["consensus_gate_package_audit"]["accepted"])
            self.assertTrue(report["consensus_gate_package_disk_replay"])

    def test_schema_required_fields_match_every_typed_gate_family(self):
        self.assertEqual(gate_model.policy_schema()["required"], list(gate_model.RegistryFederationConsensusGatePolicy.FIELDS))
        self.assertEqual(gate_model.check_schema()["required"], list(gate_model.RegistryFederationConsensusGateCheck.FIELDS))
        self.assertEqual(gate_model.gate_schema()["required"], list(gate_model.RegistryFederationConsensusGate.FIELDS))
        self.assertEqual(gate_audit_model.check_schema()["required"], list(gate_audit_model.RegistryFederationConsensusGateAuditFinding.FIELDS))
        self.assertEqual(gate_audit_model.audit_schema()["required"], list(gate_audit_model.RegistryFederationConsensusGateAudit.FIELDS))
        self.assertEqual(query_model.query_schema()["required"], list(query_model.RegistryFederationConsensusGateQuery.FIELDS))
        self.assertEqual(query_model.row_schema()["required"], list(query_model.RegistryFederationConsensusGateQueryRow.FIELDS))
        self.assertEqual(query_model.result_schema()["required"], list(query_model.RegistryFederationConsensusGateQueryResult.FIELDS))
        self.assertEqual(package_model.package_schema()["required"], list(package_model.RegistryFederationConsensusGatePackage.FIELDS))
        self.assertEqual(runtime_model.runtime_schema()["required"], list(runtime_model.FIELDS))
        self.assertEqual(diff_model.item_schema()["required"], list(diff_model.RegistryFederationConsensusGateDiffItem.FIELDS))
        self.assertEqual(diff_model.diff_schema()["required"], list(diff_model.RegistryFederationConsensusGateDiff.FIELDS))
        self.assertEqual(history_model.entry_schema()["required"], list(history_model.RegistryFederationConsensusGateHistoryEntry.FIELDS))
        self.assertEqual(history_model.history_schema()["required"], list(history_model.RegistryFederationConsensusGateHistory.FIELDS))
        self.assertEqual(observatory_model.observation_schema()["required"], list(observatory_model.RegistryFederationConsensusGateObservation.FIELDS))
        self.assertEqual(observatory_model.observatory_schema()["required"], list(observatory_model.RegistryFederationConsensusGateObservatory.FIELDS))
        self.assertEqual(observatory_model.query_schema()["required"], list(observatory_model.RegistryFederationConsensusGateObservatoryQuery.FIELDS))
        self.assertEqual(observatory_model.row_schema()["required"], list(observatory_model.RegistryFederationConsensusGateObservatoryQueryRow.FIELDS))
        self.assertEqual(observatory_model.result_schema()["required"], list(observatory_model.RegistryFederationConsensusGateObservatoryQueryResult.FIELDS))


if __name__ == "__main__":
    unittest.main()
