"""Focused contract tests for the Domain 12 C09-C12 depth plane."""

from __future__ import annotations

import unittest

from glio_noncode.cohort_alpha import CohortAlphaState, CrossCohortReplicationEngine
from glio_noncode.cohort_alpha_frontier_adapters import default_cohort_alpha_frontier_adapters, validate_cohort_alpha_frontier_payload
from glio_noncode.cohort_alpha_frontier_api_contract import default_cohort_alpha_frontier_api_contract
from glio_noncode.cohort_alpha_frontier_boundary_cases import build_cohort_alpha_frontier_boundary_index
from glio_noncode.cohort_alpha_frontier_boundary_explanations import build_cohort_alpha_frontier_boundary_explanations
from glio_noncode.cohort_alpha_frontier_claim_boundary import build_cohort_alpha_frontier_claim_boundary
from glio_noncode.cohort_alpha_frontier_claim_dictionary import build_cohort_alpha_frontier_claim_dictionary
from glio_noncode.cohort_alpha_frontier_contracts import default_cohort_alpha_frontier_contracts
from glio_noncode.cohort_alpha_frontier_data_freshness import assess_cohort_alpha_frontier_freshness
from glio_noncode.cohort_alpha_frontier_fixture_eval import evaluate_cohort_alpha_frontier_fixture
from glio_noncode.cohort_alpha_frontier_governance import CohortAlphaFrontierDisposition, materialize_cohort_alpha_frontier_policy
from glio_noncode.cohort_alpha_frontier_normalization import normalize_cohort_alpha_frontier_fixture
from glio_noncode.cohort_alpha_frontier_operation_catalog import build_cohort_alpha_frontier_operation_catalog
from glio_noncode.cohort_alpha_frontier_operation_parameters import build_cohort_alpha_frontier_parameter_report
from glio_noncode.cohort_alpha_frontier_package import assemble_cohort_alpha_frontier_package
from glio_noncode.cohort_alpha_frontier_partition import build_cohort_alpha_frontier_partitions
from glio_noncode.cohort_alpha_frontier_public_data import C09_C12_CONTEXT, audit_cohort_alpha_frontier_data, default_cohort_alpha_frontier_fixture
from glio_noncode.cohort_alpha_frontier_query import CohortAlphaFrontierQuery, query_cohort_alpha_frontier
from glio_noncode.cohort_alpha_frontier_runtime import run_cohort_alpha_frontier_pipeline
from glio_noncode.cohort_alpha_frontier_schema import default_cohort_alpha_frontier_schema, validate_cohort_alpha_frontier_schema
from glio_noncode.cohort_alpha_frontier_schema_projection import build_cohort_alpha_frontier_schema_projection
from glio_noncode.cohort_alpha_frontier_source_registry import build_cohort_alpha_frontier_source_registry
from glio_noncode.cohort_alpha_frontier_state_distribution import build_cohort_alpha_frontier_state_distribution
from glio_noncode.cohort_alpha_frontier_test_vectors import build_cohort_alpha_frontier_test_vectors
from glio_noncode.cohort_alpha_frontier_thresholds import assess_cohort_alpha_frontier_thresholds


class CohortAlphaFrontierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_cohort_alpha_frontier_fixture()
        cls.evaluation = evaluate_cohort_alpha_frontier_fixture(cls.fixture)
        cls.contracts = default_cohort_alpha_frontier_contracts()
        cls.policy = materialize_cohort_alpha_frontier_policy(cls.evaluation, cls.contracts)

    def test_public_fixture_has_closed_cardinality_and_sources(self) -> None:
        audit = audit_cohort_alpha_frontier_data(self.fixture)
        registry = build_cohort_alpha_frontier_source_registry(self.fixture)
        self.assertTrue(audit.accepted)
        self.assertEqual(audit.record_count, 16)
        self.assertEqual(audit.foreign_context_count, 4)
        self.assertTrue(registry.closed)
        self.assertEqual(registry.sources[0].url.startswith("https://"), True)

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
        report = run_cohort_alpha_frontier_pipeline()
        self.assertTrue(report.accepted)
        self.assertGreaterEqual(len(report.stages), 70)
        self.assertEqual(tuple(stage.ordinal for stage in report.stages), tuple(range(1, len(report.stages) + 1)))
        self.assertEqual(report.policy.publishable_count, 4)
        self.assertTrue(report.quality.accepted)
        self.assertTrue(report.replay.deterministic)
        self.assertTrue(report.package.accepted)
        self.assertEqual(report.evaluation.rows[0].operation, "C09")
        self.assertEqual(len(report.extended), 23)

    def test_runtime_replay_is_content_deterministic(self) -> None:
        first = run_cohort_alpha_frontier_pipeline()
        second = run_cohort_alpha_frontier_pipeline()
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.evaluation.content_address, second.evaluation.content_address)
        self.assertEqual(first.stages, second.stages)


if __name__ == "__main__":
    unittest.main()
