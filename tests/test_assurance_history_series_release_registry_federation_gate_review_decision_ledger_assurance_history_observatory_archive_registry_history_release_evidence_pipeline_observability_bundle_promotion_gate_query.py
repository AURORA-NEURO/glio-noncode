"""Deep contracts for promotion-gate query resources and replay."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_promotion_gate as gate
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_promotion_gate_query as query
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_diff import RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffFixture


class RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGateQueryTests(RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffFixture):
    def test_all_bounded_resources_have_deterministic_denominators(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = self.bundle_for(Path(temporary), "same")
            value = gate.build_promotion_gate_from_directories(source, source)
            expected = {"summary": 1, "checks": gate.MAX_CHECKS, "passed": gate.MAX_CHECKS, "failed": 0, "blocking": 0, "holds": 0, "evidence": gate.MAX_CHECKS}
            for resource, total in expected.items():
                result = query.query_gate(value, resource=resource, limit=query.MAX_LIMIT)
                self.assertEqual(result.total_count, total)
                self.assertEqual(result.returned_count, total)
                self.assertEqual(query.address_query(result), result.content_address)

    def test_failed_hold_and_text_filters_are_composable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.bundle_for(root / "baseline", "baseline")
            candidate = self.bundle_for(root / "candidate", "candidate")
            value = gate.build_promotion_gate_from_directories(baseline, candidate)
            result = query.query_gate(value, resource="failed", passed=False, severity="hold", text="policy", offset=0, limit=2)
            self.assertGreaterEqual(result.total_count, 1)
            self.assertLessEqual(result.returned_count, 2)
            self.assertTrue(all(not record["passed"] and record["severity"] == "hold" for record in result.records))
            self.assertEqual(query.query_result_from_mapping(json.loads(query.query_json(result))).to_dict(), result.to_dict())

    def test_query_contracts_reject_unknown_fields_and_crossing_addresses(self):
        query_value = query.RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGateQuery(resource="evidence", limit=1)
        with self.assertRaises(ValidationError):
            query.RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGateQuery.from_mapping(query_value.to_dict() | {"unexpected": True})
        self.assert_public(query.query_schema())
        self.assert_public(query.query_result_schema())
        self.assert_public(query.capabilities())


if __name__ == "__main__":
    unittest.main()
