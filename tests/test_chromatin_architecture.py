"""Comprehensive tests for the D07 chromatin architecture aggregate."""

from __future__ import annotations

import unittest

from glio_noncode.chromatin_architecture_access import chromatin_architecture_access_policy
from glio_noncode.chromatin_architecture_compliance import assess_chromatin_architecture_compliance
from glio_noncode.chromatin_architecture_data_dictionary import (
    chromatin_architecture_data_dictionary,
)
from glio_noncode.chromatin_architecture_depth import chromatin_architecture_depth_report
from glio_noncode.chromatin_architecture_failures import classify_chromatin_architecture_failures
from glio_noncode.chromatin_architecture_invariants import check_chromatin_architecture_invariants
from glio_noncode.chromatin_architecture_ledger import build_chromatin_architecture_ledger
from glio_noncode.chromatin_architecture_lineage import (
    build_chromatin_architecture_lineage,
    verify_chromatin_architecture_lineage,
)
from glio_noncode.chromatin_architecture_metrics import materialize_chromatin_architecture_metrics
from glio_noncode.chromatin_architecture_operations import evaluate_chromatin_architecture_fixture
from glio_noncode.chromatin_architecture_plan import compile_chromatin_architecture_plan
from glio_noncode.chromatin_architecture_policy import score_chromatin_architecture_policy
from glio_noncode.chromatin_architecture_public_data import (
    audit_chromatin_architecture_data,
    default_chromatin_architecture_fixture,
)
from glio_noncode.chromatin_architecture_quality import assess_chromatin_architecture_quality
from glio_noncode.chromatin_architecture_release import release_chromatin_architecture
from glio_noncode.chromatin_architecture_replay import replay_chromatin_architecture_fixture
from glio_noncode.chromatin_architecture_review import build_chromatin_architecture_review_queue
from glio_noncode.chromatin_architecture_runtime import run_chromatin_architecture
from glio_noncode.chromatin_architecture_scenarios import (
    build_chromatin_architecture_scenario_matrix,
)
from glio_noncode.chromatin_architecture_schema import validate_chromatin_architecture_schema
from glio_noncode.chromatin_architecture_source_registry import (
    build_chromatin_architecture_source_registry,
)
from glio_noncode.chromatin_architecture_validation import validate_chromatin_architecture_matrix


class ChromatinArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_chromatin_architecture_fixture()
        cls.evaluation = evaluate_chromatin_architecture_fixture(cls.fixture)

    def test_fixture_has_four_families_and_closed_cardinality(self) -> None:
        self.assertEqual(len(self.fixture.sources), 19)
        self.assertEqual(len(self.fixture.operations), 16)
        self.assertEqual(len(self.fixture.cases), 64)
        self.assertEqual(len(self.fixture.positive_cases), 16)
        self.assertEqual(len(self.fixture.control_cases), 48)
        self.assertTrue(all(item.public_aggregate for item in self.fixture.sources))
        self.assertTrue(all(item.delegate_context_key for item in self.fixture.cases))
        self.assertEqual(
            {item.family.value for item in self.fixture.operations},
            {
                "chromatin_context_frontier",
                "methylation_frontier",
                "chromatin_alpha_frontier",
                "chromatin_frontier",
            },
        )

    def test_data_audit_and_source_joins_pass(self) -> None:
        report = audit_chromatin_architecture_data(self.fixture)
        self.assertTrue(report.accepted)
        self.assertEqual(report.failed_check_ids, ())
        self.assertTrue(
            all(
                set(item.source_ids) <= {source.source_id for source in self.fixture.sources}
                for item in self.fixture.cases
            )
        )

    def test_evaluation_runs_family_delegates_and_controls(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.receipts), 64)
        self.assertEqual(len(self.evaluation.checks), 458)
        self.assertTrue(all(item.passed for item in self.evaluation.receipts))
        controls = {
            item.case_id: item
            for item in self.evaluation.receipts
            if item.expected_state.value == "review"
        }
        self.assertEqual(len(controls), 48)
        self.assertEqual(
            controls["D07-C01-foreign_context"].observed_issue_codes, ("context_mismatch",)
        )
        self.assertEqual(controls["D07-C08-malformed_input"].observed_result_state, "invalid")
        self.assertEqual(
            controls["D07-C16-identity_conflict"].observed_result_state, "contradictory"
        )

    def test_cross_assay_positive_operations_are_functional(self) -> None:
        positives = {
            item.case_id: item
            for item in self.evaluation.receipts
            if item.expected_state.value == "accepted"
        }
        self.assertEqual(positives["D07-C13-positive"].observed_result_state, "accepted")
        self.assertEqual(positives["D07-C14-positive"].observed_result_state, "accepted")
        self.assertEqual(positives["D07-C15-positive"].observed_result_state, "accepted")
        self.assertEqual(positives["D07-C16-positive"].observed_result_state, "published")
        execution = next(
            item for item in self.evaluation.executions if item.case_id == "D07-C13-positive"
        )
        self.assertEqual(execution.summary["imputed_ids"], ["chr7:180-220"])
        self.assertEqual(
            next(
                item for item in self.evaluation.executions if item.case_id == "D07-C14-positive"
            ).summary["supported_ids"],
            ["chr7:100-140"],
        )

    def test_plan_policy_review_lineage_and_ledger_close(self) -> None:
        plan = compile_chromatin_architecture_plan(self.fixture)
        policy = score_chromatin_architecture_policy(self.evaluation)
        review = build_chromatin_architecture_review_queue(
            self.fixture.fixture_id, self.fixture.cases
        )
        lineage = build_chromatin_architecture_lineage(self.fixture, self.evaluation)
        ledger = build_chromatin_architecture_ledger(self.fixture, self.evaluation)
        self.assertTrue(plan.accepted)
        self.assertEqual(len(plan.nodes), 16)
        self.assertTrue(policy.accepted)
        self.assertEqual(policy.accepted_count, 16)
        self.assertEqual(policy.review_count, 48)
        self.assertTrue(review.accepted)
        self.assertEqual(len(review.items), 48)
        self.assertTrue(
            verify_chromatin_architecture_lineage(lineage, self.fixture, self.evaluation)
        )
        self.assertEqual(len(ledger.events), 64)

    def test_metrics_schema_invariants_and_validation_matrix(self) -> None:
        metrics = materialize_chromatin_architecture_metrics(self.evaluation)
        schema = validate_chromatin_architecture_schema(self.fixture, self.evaluation)
        invariants = check_chromatin_architecture_invariants(self.fixture, self.evaluation)
        matrix = validate_chromatin_architecture_matrix(self.fixture, self.evaluation)
        self.assertEqual(metrics.receipt_count, 64)
        self.assertEqual(metrics.family_counts["methylation_frontier"], 16)
        self.assertTrue(schema.accepted)
        self.assertEqual(len(schema.schema.fields), 33)
        self.assertTrue(all(item.passed for item in invariants))
        self.assertTrue(matrix.accepted)
        self.assertEqual(len(matrix.cells), 80)

    def test_depth_compliance_source_registry_and_dictionary(self) -> None:
        depth = chromatin_architecture_depth_report(self.fixture, self.evaluation)
        compliance = assess_chromatin_architecture_compliance(self.fixture)
        registry = build_chromatin_architecture_source_registry(self.fixture)
        dictionary = chromatin_architecture_data_dictionary(self.fixture)
        self.assertGreater(depth.addressed_count, 400)
        self.assertTrue(compliance.accepted)
        self.assertTrue(registry.accepted)
        self.assertEqual(len(registry.bindings), 19)
        self.assertEqual(len(dictionary.fields), 30)
        self.assertEqual(len(dictionary.checks), 6)

    def test_replay_access_release_and_quality_gate(self) -> None:
        plan = compile_chromatin_architecture_plan(self.fixture)
        policy = score_chromatin_architecture_policy(self.evaluation)
        review = build_chromatin_architecture_review_queue(
            self.fixture.fixture_id, self.fixture.cases
        )
        lineage = build_chromatin_architecture_lineage(self.fixture, self.evaluation)
        ledger = build_chromatin_architecture_ledger(self.fixture, self.evaluation)
        metrics = materialize_chromatin_architecture_metrics(self.evaluation)
        schema = validate_chromatin_architecture_schema(self.fixture, self.evaluation)
        replay = replay_chromatin_architecture_fixture(self.fixture)
        from glio_noncode.chromatin_architecture_artifacts import (
            materialize_chromatin_architecture_artifacts,
        )

        artifacts = materialize_chromatin_architecture_artifacts(
            self.fixture, self.evaluation, policy, review, lineage, ledger, metrics
        )
        release = release_chromatin_architecture(self.fixture, self.evaluation, artifacts)
        quality = assess_chromatin_architecture_quality(
            self.fixture,
            audit_chromatin_architecture_data(self.fixture),
            plan,
            self.evaluation,
            policy,
            review,
            lineage,
            metrics,
            schema,
            replay,
            classify_chromatin_architecture_failures(self.evaluation),
            release,
        )
        self.assertTrue(replay.accepted)
        self.assertTrue(release.state.value == "published")
        self.assertTrue(chromatin_architecture_access_policy(artifacts).accepted)
        self.assertTrue(quality.accepted)
        self.assertEqual(len(quality.checks), 14)

    def test_runtime_has_twenty_four_stages_and_six_artifacts(self) -> None:
        runtime = run_chromatin_architecture(self.fixture)
        self.assertTrue(runtime.accepted)
        self.assertEqual(len(runtime.stages), 24)
        self.assertEqual(len(runtime.artifacts), 6)
        self.assertEqual(runtime.release.state.value, "published")
        self.assertEqual(len(runtime.quality.checks), 14)
        self.assertEqual(runtime.depth.check_count, 458)
        self.assertEqual(runtime.depth.state_count, 6)
        self.assertTrue(runtime.compliance.accepted)
        self.assertEqual(runtime.stages[-1].stage_id, "runtime-finalized")

    def test_scenario_matrix_is_balanced(self) -> None:
        matrix = build_chromatin_architecture_scenario_matrix(self.fixture, self.evaluation)
        self.assertTrue(matrix.accepted)
        self.assertEqual(
            matrix.scenario_counts,
            {"positive": 16, "foreign_context": 16, "malformed_input": 16, "identity_conflict": 16},
        )

    def test_failure_classification_keeps_expected_controls_visible(self) -> None:
        report = classify_chromatin_architecture_failures(self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(report.class_counts["none"], 16)
        self.assertEqual(report.class_counts["context"], 16)
        self.assertEqual(report.class_counts["input"], 16)
        self.assertEqual(report.class_counts["identity"], 16)


if __name__ == "__main__":
    unittest.main()
