"""Deep contracts for consensus remediation plans and projections."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import registry_federation_consensus as consensus_model
from glio_noncode import registry_federation_consensus_remediation as remediation_model
from glio_noncode import registry_federation_consensus_remediation_audit as audit_model
from glio_noncode import registry_federation_consensus_remediation_query as query_model
from glio_noncode import registry_federation_consensus_runtime as runtime_model
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry as registry_model
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry_federation as federation_model
from glio_noncode.errors import ValidationError
from glio_noncode.cli import main
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package import DurableCatalogPromotionPackageFixture


class RegistryFederationConsensusRemediationTests(DurableCatalogPromotionPackageFixture):
    """Verify action-to-step conversion without performing source mutations."""

    def _registries(self, root: Path):
        ready_package = self.package_for(root / "ready-input", package_id="remediation-package")
        held_package = self.package_for(root / "held-input", package_id="remediation-package", held=True)
        ready = registry_model.build_registry((ready_package,), registry_id="remediation-ready")
        copy = registry_model.build_registry((ready_package,), registry_id="remediation-copy")
        held = registry_model.build_registry((held_package,), registry_id="remediation-held")
        paths = (root / "ready", root / "copy", root / "held")
        for value, path in zip((ready, copy, held), paths, strict=True):
            registry_model.write_registry(value, path)
        return paths

    def _consensus(self, root: Path, divergent: bool = False):
        ready, copy, held = self._registries(root)
        peers = (("primary", ready), ("archive", held if divergent else copy))
        federation = federation_model.build_federation_from_directories(peers, federation_id="remediation-federation")
        return consensus_model.build_consensus(federation, consensus_id="remediation-consensus")

    def test_clean_consensus_has_empty_ready_plan(self):
        with tempfile.TemporaryDirectory() as temporary:
            consensus = self._consensus(Path(temporary))
            value = remediation_model.build_remediation(consensus, remediation_id="clean-remediation")
            self.assertEqual((value.step_count, value.blocking_count, value.review_count, value.ready), (0, 0, 0, True))
            self.assertEqual(remediation_model.remediation_from_mapping(value.to_dict()).to_dict(), value.to_dict())
            self.assertEqual(json.loads(remediation_model.remediation_json(value))["ready"], True)
            self.assertTrue(remediation_model.render_remediation_markdown(value).startswith("# Consensus Remediation Plan"))

    def test_divergence_becomes_required_inspection_and_hold_steps(self):
        with tempfile.TemporaryDirectory() as temporary:
            consensus = self._consensus(Path(temporary), divergent=True)
            value = remediation_model.build_remediation(consensus)
            self.assertEqual((value.step_count, value.blocking_count, value.review_count, value.ready), (2, 2, 0, False))
            self.assertEqual(tuple(step.kind for step in value.steps), ("inspect-divergence", "hold-package"))
            self.assertTrue(all(step.status == "required" for step in value.steps))
            self.assertTrue(all(step.evidence_addresses for step in value.steps))
            self.assertTrue(remediation_model.remediation_csv(value).startswith("ordinal,action_id,package_id"))

    def test_independent_audit_recomputes_readiness_and_addresses(self):
        with tempfile.TemporaryDirectory() as temporary:
            consensus = self._consensus(Path(temporary), divergent=True)
            value = remediation_model.build_remediation(consensus)
            audit = audit_model.audit_remediation(value)
            self.assertEqual((audit.passed_count, audit.check_count, audit.failed_count, audit.accepted), (11, 11, 0, True))
            self.assertEqual(audit_model.audit_from_mapping(audit.to_dict()).to_dict(), audit.to_dict())
            self.assertEqual(json.loads(audit_model.audit_json(audit))["accepted"], True)

    def test_audit_and_plan_fail_closed_on_counter_or_step_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = remediation_model.build_remediation(self._consensus(Path(temporary), divergent=True))
            corrupted = value.to_dict()
            corrupted["blocking_count"] = 0
            with self.assertRaises(ValidationError):
                remediation_model.remediation_from_mapping(corrupted)
            corrupted = value.to_dict()
            corrupted["steps"] = list(corrupted["steps"])
            corrupted["steps"][0] = dict(corrupted["steps"][0])
            corrupted["steps"][0]["content_address"] = value.steps[0].content_address + "-tampered"
            with self.assertRaises(ValidationError):
                remediation_model.remediation_from_mapping(corrupted)

    def test_query_exposes_summary_steps_required_and_evidence_with_filters(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = remediation_model.build_remediation(self._consensus(Path(temporary), divergent=True))
            result = query_model.query_remediation(value, resources=("all",), status="required", limit=1)
            self.assertEqual((result.matched_count, result.returned_count, result.next_offset, result.truncated), (3, 1, 1, True))
            self.assertTrue(all(row.status == "required" for row in result.rows))
            second = query_model.query_remediation(value, resources=("steps",), kind="hold-package")
            self.assertEqual((second.matched_count, second.returned_count, second.rows[0].kind), (1, 1, "hold-package"))
            evidence = query_model.query_remediation(value, resources=("evidence",), limit=query_model.MAX_ROWS)
            self.assertGreaterEqual(evidence.returned_count, 1)
            self.assertEqual(query_model.query_from_mapping(result.to_dict()).to_dict(), result.to_dict())
            self.assertIn("required", query_model.render_query_markdown(result))
            self.assertTrue(query_model.query_csv(result).startswith("ordinal,resource,row_id"))

    def test_query_rejects_invalid_resources_and_corrupted_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = remediation_model.build_remediation(self._consensus(Path(temporary), divergent=True))
            with self.assertRaises(ValidationError):
                query_model.build_query(value, resources=("unknown",))
            with self.assertRaises(ValidationError):
                query_model.query_remediation(value, limit=0)
            result = query_model.query_remediation(value)
            corrupted = result.to_dict()
            corrupted["returned_count"] = 0
            with self.assertRaises(ValidationError):
                query_model.query_from_mapping(corrupted)

    def test_runtime_links_remediation_plan_audit_and_query(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ready, _, held = self._registries(root)
            value = runtime_model.run_consensus_runtime((("primary", ready), ("archive", held)), runtime_id="remediation-runtime")
            self.assertEqual(value.remediation.consensus_address, value.consensus.content_address)
            self.assertEqual(value.remediation_audit.remediation_address, value.remediation.content_address)
            self.assertEqual(value.remediation_query.query.remediation_address, value.remediation.content_address)
            self.assertFalse(value.remediation.ready)
            self.assertEqual(runtime_model.runtime_from_mapping(value.to_dict()).to_dict(), value.to_dict())

    def test_schema_and_capability_contracts_are_complete(self):
        self.assertEqual(remediation_model.remediation_schema()["required"], list(remediation_model.RegistryFederationConsensusRemediation.FIELDS))
        self.assertEqual(remediation_model.step_schema()["required"], list(remediation_model.RegistryFederationConsensusRemediationStep.FIELDS))
        self.assertEqual(audit_model.audit_schema()["required"], list(audit_model.RegistryFederationConsensusRemediationAudit.FIELDS))
        self.assertEqual(audit_model.check_schema()["required"], list(audit_model.RegistryFederationConsensusRemediationAuditFinding.FIELDS))
        self.assertEqual(query_model.query_schema()["required"], list(query_model.RegistryFederationConsensusRemediationQuery.FIELDS))
        self.assertEqual(query_model.row_schema()["required"], list(query_model.RegistryFederationConsensusRemediationQueryRow.FIELDS))
        self.assertEqual(query_model.result_schema()["required"], list(query_model.RegistryFederationConsensusRemediationQueryResult.FIELDS))
        self.assertEqual(tuple(remediation_model.capabilities()["statuses"]), ("required", "recommended"))

    def test_cli_emits_plan_audit_and_bounded_query(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            consensus = self._consensus(root, divergent=True)
            consensus_path = root / "consensus.json"
            consensus_path.write_text(consensus_model.consensus_json(consensus), encoding="utf-8")
            remediation_path = root / "remediation.json"
            self.assertEqual(main(["registry-federation-consensus-remediation", "--input", str(consensus_path), "--format", "json", "--output", str(remediation_path)]), 2)
            self.assertEqual(main(["registry-federation-consensus-remediation-audit", "--input", str(remediation_path), "--format", "summary"]), 0)
            self.assertEqual(main(["registry-federation-consensus-remediation-query", "--input", str(remediation_path), "--resource", "required", "--status", "required", "--format", "summary"]), 0)
            self.assertEqual(main(["registry-federation-consensus-remediation-query-result-schema"]), 0)


if __name__ == "__main__":
    unittest.main()
