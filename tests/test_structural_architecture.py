"""Focused contract, adapter, runtime, and release tests for D02."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.structural_architecture_access import (
    build_structural_architecture_access_manifest,
)
from glio_noncode.structural_architecture_bundle import (
    build_structural_architecture_artifacts,
    build_structural_architecture_release,
    render_structural_architecture_markdown,
    render_structural_architecture_review_csv,
    write_structural_architecture_bundle,
)
from glio_noncode.structural_architecture_contracts import (
    STRUCTURAL_ARCHITECTURE_CASE_COUNT,
    STRUCTURAL_ARCHITECTURE_CONTEXT,
    StructuralArchitectureOperation,
    StructuralArchitectureScenario,
    StructuralArchitectureState,
)
from glio_noncode.structural_architecture_depth import audit_structural_architecture_depth
from glio_noncode.structural_architecture_exports import export_structural_architecture_json
from glio_noncode.structural_architecture_failures import run_structural_architecture_failure_probes
from glio_noncode.structural_architecture_invariants import run_structural_architecture_invariants
from glio_noncode.structural_architecture_lineage import (
    build_structural_architecture_ledger,
)
from glio_noncode.structural_architecture_metrics import measure_structural_architecture
from glio_noncode.structural_architecture_observability import observe_structural_architecture
from glio_noncode.structural_architecture_operations import (
    evaluate_structural_architecture_fixture,
    execute_structural_architecture_case,
)
from glio_noncode.structural_architecture_plan import (
    compile_structural_architecture_plan,
    plan_is_executable,
)
from glio_noncode.structural_architecture_policy import (
    evaluate_structural_architecture_policy,
)
from glio_noncode.structural_architecture_public_data import (
    audit_structural_architecture_data,
    default_structural_architecture_fixture,
    structural_architecture_fixture_json,
)
from glio_noncode.structural_architecture_quality import evaluate_structural_architecture_quality
from glio_noncode.structural_architecture_query import query_structural_architecture
from glio_noncode.structural_architecture_replay import (
    replay_is_deterministic,
    replay_structural_architecture,
)
from glio_noncode.structural_architecture_review import build_structural_architecture_review_queue
from glio_noncode.structural_architecture_runbook import (
    build_structural_architecture_runbook,
    runbook_is_executable,
)
from glio_noncode.structural_architecture_runtime import run_structural_architecture
from glio_noncode.structural_architecture_schema import (
    default_structural_architecture_schema,
    validate_structural_architecture_schema,
)
from glio_noncode.structural_architecture_validation import (
    build_structural_architecture_validation_matrix,
)


class StructuralArchitectureFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_structural_architecture_fixture()
        cls.evaluation = evaluate_structural_architecture_fixture(cls.fixture)

    def test_fixture_cardinality_and_context(self) -> None:
        self.assertEqual(self.fixture.context_key, STRUCTURAL_ARCHITECTURE_CONTEXT)
        self.assertEqual(len(self.fixture.operations), 16)
        self.assertEqual(len(self.fixture.cases), STRUCTURAL_ARCHITECTURE_CASE_COUNT)
        self.assertEqual(len(self.fixture.positive_cases), 16)
        self.assertEqual(len(self.fixture.control_cases), 48)

    def test_fixture_source_receipts_are_public(self) -> None:
        self.assertGreaterEqual(len(self.fixture.sources), 6)
        self.assertEqual(len(self.fixture.source_ids), len(self.fixture.sources))
        self.assertTrue(all(item.uri.startswith("https://") for item in self.fixture.sources))
        self.assertTrue(all(item.scope == "public_aggregate" for item in self.fixture.sources))

    def test_fixture_content_address_is_stable(self) -> None:
        first = structural_architecture_fixture_json(self.fixture)
        second = structural_architecture_fixture_json(default_structural_architecture_fixture())
        self.assertEqual(first, second)
        self.assertIn("structural-architecture-public-aggregate", first)

    def test_source_and_case_audit(self) -> None:
        report = audit_structural_architecture_data(self.fixture)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 11)
        self.assertTrue(all(item.content_address for item in report.checks))

    def test_operation_ids_are_closed(self) -> None:
        expected = tuple(item.value for item in StructuralArchitectureOperation)
        self.assertEqual(self.fixture.operation_ids, expected)
        self.assertEqual(
            tuple(item.ordinal for item in self.fixture.operations), tuple(range(1, 17))
        )


class StructuralArchitectureEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_structural_architecture_fixture()
        cls.evaluation = evaluate_structural_architecture_fixture(cls.fixture)

    def test_all_cases_execute_and_pass(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.receipts), 64)
        self.assertTrue(all(item.passed for item in self.evaluation.receipts))
        self.assertTrue(
            all(item.content_address.startswith("sha256:") for item in self.evaluation.receipts)
        )

    def test_positive_and_control_counts(self) -> None:
        self.assertEqual(self.evaluation.positive_count, 16)
        self.assertEqual(self.evaluation.control_count, 48)
        self.assertEqual(len(self.evaluation.checks), 308)

    def test_control_scenarios_are_held(self) -> None:
        controls = [
            item
            for item in self.evaluation.receipts
            if item.expected_state is StructuralArchitectureState.REVIEW
        ]
        self.assertEqual(len(controls), 48)
        self.assertEqual(
            {item.observed_result_state for item in controls},
            {"out_of_domain", "invalid", "contradictory"},
        )
        self.assertEqual(
            {code for item in controls for code in item.observed_issue_codes},
            {"context_mismatch", "malformed_input", "duplicate_identity"},
        )

    def test_each_operation_has_four_receipts(self) -> None:
        for operation in self.fixture.operation_ids:
            with self.subTest(operation=operation):
                receipts = [
                    item for item in self.evaluation.receipts if item.operation_id == operation
                ]
                self.assertEqual(len(receipts), 4)
                self.assertEqual(
                    sum(
                        item.expected_state is StructuralArchitectureState.ACCEPTED
                        for item in receipts
                    ),
                    1,
                )

    def test_direct_control_policy(self) -> None:
        case = next(
            item
            for item in self.fixture.cases
            if item.scenario is StructuralArchitectureScenario.FOREIGN_CONTEXT
        )
        decision = evaluate_structural_architecture_policy(case)
        execution = execute_structural_architecture_case(case, self.fixture.context_key)
        self.assertFalse(decision.allowed)
        self.assertEqual(execution.issue_codes, ("context_mismatch",))
        self.assertEqual(execution.observed_state, StructuralArchitectureState.REVIEW)


class StructuralArchitectureRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_structural_architecture_fixture()
        cls.runtime = run_structural_architecture(cls.fixture, run_id="test-runtime")

    def test_runtime_is_published(self) -> None:
        self.assertTrue(self.runtime.accepted)
        self.assertEqual(self.runtime.state, StructuralArchitectureState.PUBLISHED)
        self.assertEqual(len(self.runtime.stages), 20)
        self.assertEqual(tuple(item.ordinal for item in self.runtime.stages), tuple(range(1, 21)))

    def test_runtime_stage_addresses_and_details(self) -> None:
        self.assertTrue(all(item.input_address for item in self.runtime.stages))
        self.assertTrue(all(item.output_address for item in self.runtime.stages))
        self.assertTrue(all(item.detail for item in self.runtime.stages))
        self.assertEqual(self.runtime.stages[0].stage_id, "fixture-loaded")
        self.assertEqual(self.runtime.stages[-1].stage_id, "runtime-finalized")

    def test_plan_and_validation_matrix(self) -> None:
        plan = compile_structural_architecture_plan(self.fixture)
        matrix = build_structural_architecture_validation_matrix(
            self.fixture, self.runtime.evaluation
        )
        self.assertTrue(plan_is_executable(plan))
        self.assertEqual(len(plan.nodes), 16)
        self.assertEqual(len(matrix.cells), 112)
        self.assertTrue(matrix.accepted)

    def test_review_ledger_and_release(self) -> None:
        queue = build_structural_architecture_review_queue(self.runtime.evaluation)
        ledger = build_structural_architecture_ledger(self.fixture, self.runtime.evaluation)
        artifacts = build_structural_architecture_artifacts(
            self.fixture, self.runtime.evaluation, ledger
        )
        release = build_structural_architecture_release(
            self.fixture, artifacts, self.runtime.evaluation, ledger
        )
        self.assertTrue(queue.accepted)
        self.assertEqual(len(queue.items), 48)
        self.assertTrue(ledger.accepted)
        self.assertEqual(len(ledger.events), 64)
        self.assertTrue(build_structural_architecture_access_manifest(artifacts).accepted)
        self.assertTrue(release.published)

    def test_release_quality_and_depth(self) -> None:
        quality = evaluate_structural_architecture_quality(self.runtime)
        depth = audit_structural_architecture_depth(self.runtime)
        self.assertTrue(quality.passed)
        self.assertTrue(depth.accepted)
        self.assertEqual(depth.addressed_count, 64)

    def test_metrics_query_and_observability(self) -> None:
        metrics = measure_structural_architecture(self.fixture, self.runtime.evaluation)
        query = query_structural_architecture(
            self.runtime.evaluation, operation_id="focal_amplification"
        )
        trace = observe_structural_architecture(self.runtime)
        self.assertEqual(len(metrics.operations), 16)
        self.assertEqual(metrics.case_count, 64)
        self.assertEqual(len(query.matched_case_ids), 4)
        self.assertTrue(trace.accepted)
        self.assertEqual(len(trace.events), 20)

    def test_schema_runbook_failures_and_invariants(self) -> None:
        self.assertTrue(default_structural_architecture_schema().accepted)
        self.assertTrue(validate_structural_architecture_schema(self.fixture).accepted)
        runbook = build_structural_architecture_runbook()
        self.assertTrue(runbook_is_executable(runbook))
        self.assertTrue(run_structural_architecture_failure_probes(self.fixture).accepted)
        self.assertTrue(run_structural_architecture_invariants(self.runtime).accepted)

    def test_replay_is_deterministic(self) -> None:
        replay = replay_structural_architecture(self.fixture)
        self.assertTrue(replay_is_deterministic(replay))
        self.assertEqual(replay.first_address, replay.second_address)

    def test_bounded_exports(self) -> None:
        self.assertIn('"fixture_id"', export_structural_architecture_json(self.runtime))
        csv_text = render_structural_architecture_review_csv(self.runtime.evaluation)
        markdown = render_structural_architecture_markdown(self.runtime.release)
        self.assertIn("case_id,operation_id", csv_text)
        self.assertIn("# Structural architecture release", markdown)

    def test_bundle_write_is_recoverable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            release = write_structural_architecture_bundle(
                self.fixture, self.runtime.evaluation, self.runtime.ledger, directory
            )
            files = {item.name for item in Path(directory).iterdir()}
            self.assertTrue(release.published)
            self.assertEqual(
                files,
                {
                    "fixture.json",
                    "evaluation.json",
                    "lineage.json",
                    "review.csv",
                    "release.md",
                    "release.json",
                },
            )
            self.assertEqual(
                json.loads((Path(directory) / "release.json").read_text())["state"], "published"
            )


if __name__ == "__main__":
    unittest.main()
