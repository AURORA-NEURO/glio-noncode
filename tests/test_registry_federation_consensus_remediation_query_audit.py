"""Contracts for independent remediation query-result audits."""

# ruff: noqa: E501, I001

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from glio_noncode import registry_federation_consensus as consensus_model
from glio_noncode import registry_federation_consensus_remediation as remediation_model
from glio_noncode import registry_federation_consensus_remediation_query as query_model
from glio_noncode import registry_federation_consensus_remediation_query_audit as audit_model
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry as registry_model
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry_federation as federation_model
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package import DurableCatalogPromotionPackageFixture


class RegistryFederationConsensusRemediationQueryAuditTests(DurableCatalogPromotionPackageFixture):
    """Verify filters and page boundaries independently of query construction."""

    def _remediation(self, root: Path):
        ready_package = self.package_for(root / "ready-input", package_id="query-audit-package")
        held_package = self.package_for(root / "held-input", package_id="query-audit-package", held=True)
        ready = registry_model.build_registry((ready_package,), registry_id="query-audit-ready")
        held = registry_model.build_registry((held_package,), registry_id="query-audit-held")
        ready_path, held_path = root / "ready", root / "held"
        registry_model.write_registry(ready, ready_path)
        registry_model.write_registry(held, held_path)
        federation = federation_model.build_federation_from_directories((("primary", ready_path), ("archive", held_path)), federation_id="query-audit-federation")
        return remediation_model.build_remediation(consensus_model.build_consensus(federation, consensus_id="query-audit-consensus"))

    def test_audit_accepts_filtered_paginated_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            remediation = self._remediation(Path(temporary))
            result = query_model.query_remediation(remediation, resources=("all",), status="required", limit=1)
            value = audit_model.audit_query(result)
            self.assertEqual((value.passed_count, value.check_count, value.failed_count, value.accepted), (11, 11, 0, True))
            self.assertEqual(audit_model.audit_from_mapping(value.to_dict()).to_dict(), value.to_dict())
            self.assertIn("pagination", audit_model.render_audit_markdown(value))

    def test_audit_catches_invalid_result_before_reporting(self):
        with tempfile.TemporaryDirectory() as temporary:
            remediation = self._remediation(Path(temporary))
            result = query_model.query_remediation(remediation, resources=("steps",), severity="blocking")
            corrupted = result.to_dict()
            corrupted["truncated"] = True
            corrupted["next_offset"] = 0
            with self.assertRaises(ValidationError):
                audit_model.audit_query(query_model.query_from_mapping(corrupted))

    def test_schema_and_capability_contracts_are_stable(self):
        self.assertEqual(audit_model.audit_schema()["required"], list(audit_model.RegistryFederationConsensusRemediationQueryAudit.FIELDS))
        self.assertEqual(audit_model.check_schema()["required"], list(audit_model.RegistryFederationConsensusRemediationQueryAuditFinding.FIELDS))
        self.assertEqual(len(audit_model.CHECK_IDS), 11)
        self.assertIn("resource and filter conservation", audit_model.capabilities()["features"])


if __name__ == "__main__":
    unittest.main()
