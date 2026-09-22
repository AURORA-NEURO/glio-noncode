"""Focused contract tests for the Domain 12 C09-C12 depth plane."""

from __future__ import annotations

import unittest
from dataclasses import replace

from glio_noncode.cohort_alpha import CohortAlphaState, CrossCohortReplicationEngine
from glio_noncode.cohort_alpha_frontier_adapters import default_cohort_alpha_frontier_adapters, validate_cohort_alpha_frontier_payload
from glio_noncode.cohort_alpha_frontier_api_contract import default_cohort_alpha_frontier_api_contract
from glio_noncode.cohort_alpha_frontier_boundary_cases import build_cohort_alpha_frontier_boundary_index
from glio_noncode.cohort_alpha_frontier_boundary_explanations import build_cohort_alpha_frontier_boundary_explanations
from glio_noncode.cohort_alpha_frontier_claim_boundary import build_cohort_alpha_frontier_claim_boundary
from glio_noncode.cohort_alpha_frontier_claim_dictionary import build_cohort_alpha_frontier_claim_dictionary
from glio_noncode.cohort_alpha_frontier_claim_evidence import (
    CohortAlphaFrontierClaimEvidenceReport,
    build_cohort_alpha_frontier_claim_evidence,
)
from glio_noncode.cohort_alpha_frontier_contracts import default_cohort_alpha_frontier_contracts
from glio_noncode.cohort_alpha_frontier_data_freshness import assess_cohort_alpha_frontier_freshness
from glio_noncode.cohort_alpha_frontier_dataset_manifest import (
    CohortAlphaFrontierDatasetManifest,
    build_cohort_alpha_frontier_dataset_manifest,
)
from glio_noncode.cohort_alpha_frontier_fixture_eval import evaluate_cohort_alpha_frontier_fixture
from glio_noncode.cohort_alpha_frontier_governance import CohortAlphaFrontierDisposition, materialize_cohort_alpha_frontier_policy
from glio_noncode.cohort_alpha_frontier_normalization import normalize_cohort_alpha_frontier_fixture
from glio_noncode.cohort_alpha_frontier_operation_catalog import build_cohort_alpha_frontier_operation_catalog
from glio_noncode.cohort_alpha_frontier_operation_parameters import build_cohort_alpha_frontier_parameter_report
from glio_noncode.cohort_alpha_frontier_package import assemble_cohort_alpha_frontier_package
from glio_noncode.cohort_alpha_frontier_partition import build_cohort_alpha_frontier_partitions
from glio_noncode.cohort_alpha_frontier_public_data import C09_C12_CONTEXT, CohortAlphaFrontierFixture, CohortAlphaFrontierRecord, audit_cohort_alpha_frontier_data
from glio_noncode.cohort_alpha_frontier_query import CohortAlphaFrontierQuery, query_cohort_alpha_frontier
from glio_noncode.cohort_alpha_frontier_runtime import run_cohort_alpha_frontier_pipeline
from glio_noncode.cohort_alpha_frontier_report import (
    CohortAlphaFrontierReport,
    build_cohort_alpha_frontier_report,
)
from glio_noncode.cohort_alpha_frontier_schema import default_cohort_alpha_frontier_schema, validate_cohort_alpha_frontier_schema
from glio_noncode.cohort_alpha_frontier_schema_projection import build_cohort_alpha_frontier_schema_projection
from glio_noncode.cohort_alpha_frontier_source_registry import build_cohort_alpha_frontier_source_registry
from glio_noncode.cohort_alpha_frontier_state_distribution import build_cohort_alpha_frontier_state_distribution
from glio_noncode.cohort_alpha_frontier_test_vectors import build_cohort_alpha_frontier_test_vectors
from glio_noncode.cohort_alpha_frontier_thresholds import assess_cohort_alpha_frontier_thresholds
from glio_noncode.serialization import content_hash


class CohortAlphaFrontierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = run_cohort_alpha_frontier_pipeline()
        cls.fixture = cls.runtime.fixture
        cls.evaluation = cls.runtime.evaluation
        cls.contracts = cls.runtime.contracts
        cls.policy = cls.runtime.policy

    def _fixture_with_records(
        self, records: tuple[CohortAlphaFrontierRecord, ...]
    ) -> CohortAlphaFrontierFixture:
        body = {
            "fixture_id": self.fixture.fixture_id,
            "fixture_version": self.fixture.fixture_version,
            "context_key": self.fixture.context_key,
            "foreign_context_key": self.fixture.foreign_context_key,
            "boundary": self.fixture.boundary,
            "sources": self.fixture.sources,
            "records": records,
        }
        return CohortAlphaFrontierFixture(
            fixture_id=self.fixture.fixture_id,
            fixture_version=self.fixture.fixture_version,
            context_key=self.fixture.context_key,
            foreign_context_key=self.fixture.foreign_context_key,
            boundary=self.fixture.boundary,
            sources=self.fixture.sources,
            records=records,
            metadata=self.fixture.metadata,
            content_address=content_hash(body, prefix="alpha-fixture"),
        )

    def _coverage_reports(
        self, fixture: CohortAlphaFrontierFixture
    ) -> tuple[
        CohortAlphaFrontierDatasetManifest,
        CohortAlphaFrontierClaimEvidenceReport,
        CohortAlphaFrontierReport,
    ]:
        audit = audit_cohort_alpha_frontier_data(fixture)
        dataset = build_cohort_alpha_frontier_dataset_manifest(fixture, audit)
        evaluation = evaluate_cohort_alpha_frontier_fixture(fixture)
        policy = materialize_cohort_alpha_frontier_policy(evaluation, self.contracts)
        claims = build_cohort_alpha_frontier_claim_evidence(fixture, policy, dataset)
        report = build_cohort_alpha_frontier_report(
            self.runtime.evaluation,
            self.runtime.metrics,
            self.runtime.policy,
            self.runtime.review,
            self.runtime.quality,
            self.runtime.manifest,
            dataset_manifest=dataset,
            claim_evidence=claims,
        )
        return dataset, claims, report

    def test_public_fixture_has_closed_cardinality_and_sources(self) -> None:
        audit = audit_cohort_alpha_frontier_data(self.fixture)
        registry = build_cohort_alpha_frontier_source_registry(self.fixture)
        self.assertTrue(audit.accepted)
        self.assertEqual(audit.record_count, 16)
        self.assertEqual(audit.foreign_context_count, 4)
        self.assertTrue(registry.closed)
        self.assertEqual(registry.sources[0].url.startswith("https://"), True)

    def test_manifest_and_claim_report_use_distinct_expected_denominators(self) -> None:
        dataset, claims, report = self._coverage_reports(self.fixture)

        self.assertEqual(dataset.coverage_state, "complete")
        self.assertEqual(dataset.expected_record_count, 16)
        self.assertEqual(dataset.record_count, 16)
        self.assertEqual(dataset.operations, ("C09", "C10", "C11", "C12"))
        self.assertEqual(dataset.expected_claim_count, 4)
        self.assertTrue(claims.accepted)
        self.assertEqual(claims.expected_claim_count, 4)
        self.assertEqual(claims.complete_claim_count, 4)
        self.assertEqual(report.coverage_state, "complete")
        self.assertEqual(report.structural_record_count, 16)
        self.assertEqual(report.expected_structural_record_count, 16)
        self.assertEqual(report.missing_structural_record_count, 0)
        self.assertEqual(report.extra_structural_record_count, 0)
        self.assertEqual(report.complete_pipeline_claim_count, 4)
        self.assertEqual(report.expected_pipeline_claim_count, 4)
        self.assertEqual(report.dataset_manifest_address, dataset.content_address)
        self.assertEqual(report.claim_evidence_address, claims.content_address)
        self.assertEqual(claims.dataset_manifest_address, dataset.content_address)
        self.assertTrue(report.accepted)

    def test_stale_or_crossed_manifests_cannot_certify_claim_coverage(self) -> None:
        full_audit = audit_cohort_alpha_frontier_data(self.fixture)
        full_dataset = build_cohort_alpha_frontier_dataset_manifest(self.fixture, full_audit)
        partial_fixture = self._fixture_with_records(
            tuple(record for record in self.fixture.records if record.record_id != "c09-positive")
        )
        partial_evaluation = evaluate_cohort_alpha_frontier_fixture(partial_fixture)
        partial_policy = materialize_cohort_alpha_frontier_policy(partial_evaluation, self.contracts)

        stale_claims = build_cohort_alpha_frontier_claim_evidence(
            partial_fixture, partial_policy, full_dataset
        )
        self.assertEqual(stale_claims.coverage_state, "inconsistent")
        self.assertFalse(stale_claims.accepted)

        partial_dataset, partial_claims, _ = self._coverage_reports(partial_fixture)
        crossed_report = build_cohort_alpha_frontier_report(
            self.runtime.evaluation,
            self.runtime.metrics,
            self.runtime.policy,
            self.runtime.review,
            self.runtime.quality,
            self.runtime.manifest,
            dataset_manifest=full_dataset,
            claim_evidence=partial_claims,
        )
        self.assertNotEqual(partial_dataset.content_address, full_dataset.content_address)
        self.assertEqual(crossed_report.coverage_state, "inconsistent")
        self.assertFalse(crossed_report.accepted)

    def test_missing_supported_record_keeps_claim_and_report_partial(self) -> None:
        partial_fixture = self._fixture_with_records(
            tuple(record for record in self.fixture.records if record.record_id != "c09-positive")
        )
        dataset, claims, report = self._coverage_reports(partial_fixture)
        c09 = next(item for item in claims.claims if item.operation == "C09")

        self.assertEqual(dataset.coverage_state, "partial")
        self.assertEqual(dataset.missing_record_ids_by_operation[0], ("C09", ("c09-positive",)))
        self.assertFalse(dataset.accepted)
        self.assertEqual(claims.coverage_state, "partial")
        self.assertEqual(claims.missing_claim_count, 1)
        self.assertEqual(c09.missing_evidence_record_ids, ("c09-positive",))
        self.assertFalse(c09.allowed)
        self.assertEqual(report.coverage_state, "partial")
        self.assertEqual(report.structural_record_count, 15)
        self.assertEqual(report.expected_structural_record_count, 16)
        self.assertEqual(report.missing_structural_record_count, 1)
        self.assertEqual(report.extra_structural_record_count, 0)
        self.assertEqual(report.missing_pipeline_claim_count, 1)
        self.assertFalse(report.accepted)
        self.assertIn("coverage state: partial", report.sections[1].body)

    def test_extra_supported_record_is_reported_and_never_earns_complete_credit(self) -> None:
        positive = next(record for record in self.fixture.records if record.record_id == "c09-positive")
        extra_id = "c09-extra-positive"
        extra_body = {
            "operation": positive.operation,
            "record_id": extra_id,
            "payload": positive.payload,
            "expected_state": positive.expected_state,
            "control_class": "positive",
            "source_ids": positive.source_ids,
            "rationale": "unexpected positive row used to verify manifest reconciliation",
        }
        extra_record = replace(
            positive,
            record_id=extra_id,
            control_class="positive",
            rationale=extra_body["rationale"],
            content_address=content_hash(extra_body, prefix="alpha-record"),
        )
        extra_fixture = self._fixture_with_records(self.fixture.records + (extra_record,))
        dataset, claims, report = self._coverage_reports(extra_fixture)
        c09 = next(item for item in claims.claims if item.operation == "C09")

        self.assertEqual(dataset.coverage_state, "unexpected")
        self.assertEqual(dataset.extra_record_ids_by_operation[0], ("C09", (extra_id,)))
        self.assertEqual(claims.coverage_state, "unexpected")
        self.assertEqual(claims.extra_claim_count, 1)
        self.assertEqual(c09.unexpected_evidence_record_ids, (extra_id,))
        self.assertFalse(c09.allowed)
        self.assertEqual(report.coverage_state, "unexpected")
        self.assertEqual(report.structural_record_count, 17)
        self.assertEqual(report.expected_structural_record_count, 16)
        self.assertEqual(report.missing_structural_record_count, 0)
        self.assertEqual(report.extra_structural_record_count, 1)
        self.assertEqual(report.extra_pipeline_claim_count, 1)
        self.assertFalse(report.accepted)

    def test_partial_fixture_is_rejected_by_full_pipeline_with_partial_status(self) -> None:
        partial_fixture = self._fixture_with_records(
            tuple(record for record in self.fixture.records if record.record_id != "c09-positive")
        )
        runtime = run_cohort_alpha_frontier_pipeline(partial_fixture)

        self.assertFalse(runtime.accepted)
        self.assertEqual(runtime.dataset.coverage_state, "partial")
        self.assertEqual(runtime.report.coverage_state, "partial")
        self.assertEqual(runtime.claims.missing_claim_count, 1)
        self.assertFalse(runtime.report.accepted)

    def test_report_without_manifest_inputs_is_unverified_and_rejected(self) -> None:
        report = build_cohort_alpha_frontier_report(
            self.runtime.evaluation,
            self.runtime.metrics,
            self.runtime.policy,
            self.runtime.review,
            self.runtime.quality,
            self.runtime.manifest,
        )

        self.assertEqual(report.coverage_state, "unverified")
        self.assertFalse(report.accepted)

    def test_state_matrix_reconciles_all_operations(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(self.evaluation.supported_count, 4)
        self.assertEqual(self.evaluation.control_count, 12)
        self.assertEqual(self.evaluation.mismatch_count, 0)
        distribution = build_cohort_alpha_frontier_state_distribution(self.evaluation)
        self.assertTrue(distribution.accepted)
        self.assertEqual({row.operation for row in distribution.rows}, {"C09", "C10", "C11", "C12"})

    def test_policy_partitions_publication_review_and_quarantine(self) -> None:
        self.assertEqual(self.policy.publishable_count, 4)
        self.assertEqual(self.policy.review_count, 4)
        self.assertEqual(self.policy.quarantine_count, 8)
        self.assertEqual(sum(item.disposition is CohortAlphaFrontierDisposition.PUBLISH for item in self.policy.decisions), 4)
        partitions = build_cohort_alpha_frontier_partitions(self.policy)
        self.assertTrue(partitions.accepted)
        self.assertEqual(partitions.total_count, 16)

    def test_contract_schema_and_adapters_are_strict(self) -> None:
        schema = default_cohort_alpha_frontier_schema()
        adapters = default_cohort_alpha_frontier_adapters()
        self.assertTrue(validate_cohort_alpha_frontier_schema(schema))
        self.assertEqual(len(adapters.specs), 4)
        self.assertTrue(validate_cohort_alpha_frontier_payload("C09", {"observations": (), "clonal_threshold": 0.6, "subclonal_threshold": 0.2}, adapters).accepted)
        self.assertFalse(validate_cohort_alpha_frontier_payload("C12", {"observations": ()}, adapters).accepted)
        catalog = build_cohort_alpha_frontier_operation_catalog(self.contracts)
        self.assertTrue(catalog.accepted)
        self.assertEqual(len(default_cohort_alpha_frontier_api_contract().operations), 5)

    def test_boundary_and_claim_controls_are_explicit(self) -> None:
        boundary = build_cohort_alpha_frontier_boundary_index(self.evaluation)
        explanations = build_cohort_alpha_frontier_boundary_explanations(self.evaluation)
        claim_boundary = build_cohort_alpha_frontier_claim_boundary(self.contracts)
        claim_dictionary = build_cohort_alpha_frontier_claim_dictionary(claim_boundary)
        self.assertTrue(boundary.accepted)
        self.assertTrue(explanations.accepted)
        self.assertTrue(claim_boundary.accepted)
        self.assertTrue(claim_dictionary.accepted)
        self.assertEqual(len(boundary.cases), 12)

    def test_thresholds_normalization_and_parameters_pass(self) -> None:
        threshold_report = assess_cohort_alpha_frontier_thresholds(self.evaluation)
        normalization = normalize_cohort_alpha_frontier_fixture(self.fixture)
        self.assertTrue(threshold_report.accepted)
        self.assertTrue(normalization.accepted)
        self.assertEqual(len(normalization.rows), 16)
        self.assertTrue(all(row.context in {C09_C12_CONTEXT, self.fixture.foreign_context_key, ""} for row in normalization.rows))
        from glio_noncode.cohort_alpha_frontier_calibration import build_cohort_alpha_frontier_calibration

        parameters = build_cohort_alpha_frontier_parameter_report(build_cohort_alpha_frontier_calibration(threshold_report))
        self.assertTrue(parameters.accepted)

    def test_freshness_queries_vectors_and_schema_projection(self) -> None:
        freshness = assess_cohort_alpha_frontier_freshness(self.fixture)
        query = query_cohort_alpha_frontier(self.evaluation, CohortAlphaFrontierQuery(operation="C12", state="ambiguous"))
        vectors = build_cohort_alpha_frontier_test_vectors(self.evaluation)
        projection = build_cohort_alpha_frontier_schema_projection(default_cohort_alpha_frontier_schema())
        self.assertTrue(freshness.accepted)
        self.assertEqual(query.count, 1)
        self.assertTrue(vectors.accepted)
        self.assertTrue(projection.accepted)

    def test_exact_context_engine_preserves_out_of_domain_state(self) -> None:
        result = CrossCohortReplicationEngine().replicate(({"feature_id": "f", "cohort_id": "a", "effect": 1.0, "support": 1.0, "sample_count": 10, "context_key": "foreign"},), context_key=C09_C12_CONTEXT, minimum_cohorts=1, minimum_concordance=0.5)
        self.assertEqual(result.state, CohortAlphaState.OUT_OF_DOMAIN)

    def test_runtime_has_ordered_extended_depth(self) -> None:
        report = self.runtime
        self.assertTrue(report.accepted)
        self.assertGreaterEqual(len(report.stages), 70)
        self.assertEqual(tuple(stage.ordinal for stage in report.stages), tuple(range(1, len(report.stages) + 1)))
        self.assertEqual(report.policy.publishable_count, 4)
        self.assertTrue(report.quality.accepted)
        self.assertTrue(report.replay.deterministic)
        self.assertTrue(report.package.accepted)
        self.assertTrue(report.claims.accepted)
        self.assertEqual(report.report.coverage_state, "complete")
        self.assertEqual(report.claims.expected_claim_count, 4)
        self.assertEqual(report.evaluation.rows[0].operation, "C09")
        self.assertEqual(len(report.extended), 23)

    def test_runtime_replay_is_content_deterministic(self) -> None:
        first = self.runtime
        second = run_cohort_alpha_frontier_pipeline()
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.evaluation.content_address, second.evaluation.content_address)
        self.assertEqual(first.stages, second.stages)


if __name__ == "__main__":
    unittest.main()
