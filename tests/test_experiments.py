from __future__ import annotations

import tempfile
import unittest
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path
from typing import cast

from glio_noncode.errors import ValidationError
from glio_noncode.experiments import (
    MAX_EXPERIMENT_EDGES_PER_HYPOTHESIS,
    MAX_EXPERIMENT_HYPOTHESES,
    MAX_EXPERIMENT_TOTAL_EDGES,
    ExperimentPlanner,
    ExperimentPlanningLimits,
)
from glio_noncode.hypotheses import HypothesisBuilder
from glio_noncode.models import (
    AssayType,
    EdgeType,
    Hypothesis,
    HypothesisEdge,
    ReferenceContext,
    SupportLevel,
)
from glio_noncode.runtime import CaseRuntime

from .helpers import fixture_manifest


def _edge(edge_id: str, edge_type: EdgeType) -> HypothesisEdge:
    return HypothesisEdge(
        edge_id=edge_id,
        edge_type=edge_type,
        source_id=f"source-{edge_id}",
        target_id=f"target-{edge_id}",
        support=0.52,
        uncertainty=0.48,
        context_fit=0.91,
        claim_ids=(f"claim-{edge_id}",),
        support_level=SupportLevel.MODERATE,
    )


def _hypothesis(
    hypothesis_id: str,
    edges: tuple[HypothesisEdge, ...],
    *,
    uncertainty: float = 0.5,
    missing_evidence: tuple[str, ...] = ("missing-contact-evidence",),
) -> Hypothesis:
    return Hypothesis(
        hypothesis_id=hypothesis_id,
        variant_id=f"variant-{hypothesis_id}",
        element_id=f"element-{hypothesis_id}",
        gene_id=f"gene-{hypothesis_id}",
        state_id=f"state-{hypothesis_id}",
        mechanism="candidate non-coding regulatory path",
        context=ReferenceContext(
            genome_build="GRCh38",
            disease_class="diffuse_glioma",
            age_group="adult",
            cell_state="stem_like",
            territory="infiltrating_edge",
            treatment_phase="pre_treatment",
        ),
        edges=edges,
        support=0.55,
        uncertainty=uncertainty,
        missing_evidence=missing_evidence,
    )


class ExperimentPlannerTests(unittest.TestCase):
    def test_runtime_exposes_limits_and_rejects_invalid_config_before_storage(self) -> None:
        limits = ExperimentPlanningLimits(max_total_edges=4)
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory, experiment_limits=limits)
            self.assertIs(runtime.planner.limits, limits)

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValidationError, "limits must be"):
                CaseRuntime(
                    directory,
                    experiment_limits=cast(ExperimentPlanningLimits, object()),
                )
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_real_builder_edges_route_by_type_and_test_only_matching_edges(self) -> None:
        hypothesis = (
            HypothesisBuilder()
            .build(
                fixture_manifest(),
                "run-experiment-routing",
            )
            .hypotheses[0]
        )
        self.assertTrue(
            all(edge.edge_type.value not in edge.edge_id for edge in hypothesis.edges),
            "the fixture must retain realistic opaque edge identities",
        )

        options = ExperimentPlanner().plan(hypothesis)
        self.assertEqual(
            tuple(option.assay for option in options),
            (
                AssayType.MPRA,
                AssayType.CRISPR_INTERFERENCE,
                AssayType.CONTACT_ASSAY,
            ),
        )
        by_assay = {option.assay: option for option in options}
        expected_types = {
            AssayType.MPRA: EdgeType.VARIANT_TO_ELEMENT,
            AssayType.CRISPR_INTERFERENCE: EdgeType.ELEMENT_TO_GENE,
            AssayType.CONTACT_ASSAY: EdgeType.CAUSAL_PATH,
        }
        for assay, edge_type in expected_types.items():
            self.assertEqual(
                by_assay[assay].tests_edges,
                tuple(
                    sorted(edge.edge_id for edge in hypothesis.edges if edge.edge_type is edge_type)
                ),
            )

    def test_edge_id_words_cannot_create_routes_and_fallback_is_deterministic(self) -> None:
        edges = (
            _edge(
                "variant_to_element-element_to_gene-causal_path-z",
                EdgeType.GENE_TO_STATE,
            ),
            _edge("opaque-a", EdgeType.GENE_TO_STATE),
        )
        options = ExperimentPlanner().plan(_hypothesis("hyp-fallback", edges))

        self.assertEqual(len(options), 1)
        self.assertEqual(options[0].assay, AssayType.RNA_MEASUREMENT)
        self.assertEqual(options[0].option_id, "hyp-fallback:review")
        self.assertEqual(options[0].tests_edges, tuple(sorted(edge.edge_id for edge in edges)))

    def test_contact_threshold_and_low_uncertainty_fallback_are_explicit(self) -> None:
        edge = _edge("opaque-causal", EdgeType.CAUSAL_PATH)
        below = ExperimentPlanner().plan(_hypothesis("hyp-below", (edge,), uncertainty=0.349999))
        boundary = ExperimentPlanner().plan(_hypothesis("hyp-boundary", (edge,), uncertainty=0.35))

        self.assertEqual(tuple(option.assay for option in below), (AssayType.RNA_MEASUREMENT,))
        self.assertEqual(tuple(option.assay for option in boundary), (AssayType.CONTACT_ASSAY,))
        self.assertEqual(boundary[0].tests_edges, (edge.edge_id,))

    def test_builder_abstention_remains_a_review_route(self) -> None:
        manifest = replace(fixture_manifest(), candidate_elements=())
        hypothesis = HypothesisBuilder().build(
            manifest,
            "run-experiment-abstention",
        ).hypotheses[0]
        self.assertEqual(
            tuple(edge.edge_type for edge in hypothesis.edges),
            (EdgeType.CAUSAL_PATH,),
        )
        self.assertEqual(hypothesis.element_id, "unresolved")
        self.assertEqual(hypothesis.uncertainty, 1.0)

        options = ExperimentPlanner().plan(hypothesis)

        self.assertEqual(tuple(option.assay for option in options), (AssayType.RNA_MEASUREMENT,))
        self.assertEqual(options[0].option_id, f"{hypothesis.hypothesis_id}:review")
        self.assertEqual(options[0].tests_edges, (hypothesis.edges[0].edge_id,))

    def test_partially_unresolved_path_is_not_misclassified_as_an_abstention(self) -> None:
        hypothesis = _hypothesis(
            "hyp-partially-unresolved",
            (_edge("opaque-causal", EdgeType.CAUSAL_PATH),),
        )
        for field_name, value in (
            ("element_id", "unresolved"),
            ("gene_id", "unresolved_gene"),
            ("state_id", "unresolved_state"),
        ):
            with self.subTest(field_name=field_name):
                options = ExperimentPlanner().plan(replace(hypothesis, **{field_name: value}))
                self.assertEqual(
                    tuple(option.assay for option in options),
                    (AssayType.CONTACT_ASSAY,),
                )

    def test_planning_is_stable_across_edge_and_hypothesis_input_order(self) -> None:
        edges = (
            _edge("opaque-v-z", EdgeType.VARIANT_TO_ELEMENT),
            _edge("opaque-eg", EdgeType.ELEMENT_TO_GENE),
            _edge("opaque-v-a", EdgeType.VARIANT_TO_ELEMENT),
            _edge("opaque-path", EdgeType.CAUSAL_PATH),
        )
        first = _hypothesis("hyp-a", edges)
        first_reordered = _hypothesis("hyp-a", tuple(reversed(edges)))
        second = _hypothesis("hyp-b", (_edge("opaque-state", EdgeType.GENE_TO_STATE),))
        planner = ExperimentPlanner()

        self.assertEqual(planner.plan(first), planner.plan(first_reordered))
        self.assertEqual(
            planner.plan_many((first, second)),
            planner.plan_many(iter((second, first_reordered))),
        )

    def test_repeated_context_values_are_normalized_for_realistic_routes(self) -> None:
        edges = (
            _edge("opaque-v", EdgeType.VARIANT_TO_ELEMENT),
            _edge("opaque-eg", EdgeType.ELEMENT_TO_GENE),
            _edge("opaque-path", EdgeType.CAUSAL_PATH),
        )
        hypothesis = _hypothesis("hyp-shared-context", edges)
        shared_context = replace(
            hypothesis.context,
            disease_class=hypothesis.context.cell_state,
            territory=hypothesis.context.cell_state,
        )

        options = ExperimentPlanner().plan(replace(hypothesis, context=shared_context))

        self.assertTrue(options)
        self.assertTrue(
            all(option.required_context == (shared_context.cell_state,) for option in options)
        )

    def test_plan_many_rejects_duplicate_and_colliding_hypothesis_identities(self) -> None:
        hypothesis = _hypothesis(
            "hyp-identity",
            (_edge("opaque-state", EdgeType.GENE_TO_STATE),),
        )
        planner = ExperimentPlanner()

        with self.assertRaisesRegex(ValidationError, "duplicate hypothesis_id"):
            planner.plan_many((hypothesis, hypothesis))
        with self.assertRaisesRegex(ValidationError, "collision has different content"):
            planner.plan_many((hypothesis, replace(hypothesis, mechanism="different mechanism")))

    def test_plan_many_allows_shared_edges_but_rejects_conflicting_edge_identity(self) -> None:
        shared_edge = _edge("opaque-shared", EdgeType.ELEMENT_TO_GENE)
        first = _hypothesis("hyp-shared-a", (shared_edge,))
        second = _hypothesis("hyp-shared-b", (shared_edge,))
        planner = ExperimentPlanner()

        self.assertEqual(len(planner.plan_many((first, second))), 2)
        conflicting = _hypothesis(
            "hyp-shared-conflict",
            (replace(shared_edge, target_id="different-target"),),
        )
        with self.assertRaisesRegex(ValidationError, "edge_id collision has different content"):
            planner.plan_many((first, conflicting))

    def test_invalid_values_fail_with_validation_errors(self) -> None:
        planner = ExperimentPlanner()
        with self.assertRaisesRegex(ValidationError, "hypothesis must be a Hypothesis"):
            planner.plan(cast(Hypothesis, object()))
        for invalid in ("hypothesis", b"hypothesis", {"hypothesis": "value"}, 7):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValidationError):
                    planner.plan_many(cast(Iterable[Hypothesis], invalid))
        with self.assertRaisesRegex(ValidationError, "only Hypothesis"):
            planner.plan_many(cast(Iterable[Hypothesis], (object(),)))
        with self.assertRaisesRegex(ValidationError, "limits must be"):
            ExperimentPlanner(limits=cast(ExperimentPlanningLimits, object()))

    def test_limits_are_downward_only_exact_integers(self) -> None:
        cases = (
            ("max_hypotheses", 0),
            ("max_hypotheses", True),
            ("max_hypotheses", MAX_EXPERIMENT_HYPOTHESES + 1),
            ("max_edges_per_hypothesis", 0),
            ("max_edges_per_hypothesis", False),
            (
                "max_edges_per_hypothesis",
                MAX_EXPERIMENT_EDGES_PER_HYPOTHESIS + 1,
            ),
            ("max_total_edges", 0),
            ("max_total_edges", 1.5),
            ("max_total_edges", MAX_EXPERIMENT_TOTAL_EDGES + 1),
        )
        for field_name, value in cases:
            with self.subTest(field_name=field_name, value=value):
                kwargs = {field_name: value}
                with self.assertRaises(ValidationError):
                    ExperimentPlanningLimits(**kwargs)  # type: ignore[arg-type]

    def test_bounded_iterable_reads_only_one_hypothesis_past_limit(self) -> None:
        planner = ExperimentPlanner(
            limits=ExperimentPlanningLimits(
                max_hypotheses=2,
                max_edges_per_hypothesis=2,
                max_total_edges=3,
            )
        )
        yielded: list[int] = []

        def hypotheses() -> Iterable[Hypothesis]:
            for index in range(10):
                yielded.append(index)
                yield _hypothesis(
                    f"hyp-{index}",
                    (_edge(f"opaque-{index}", EdgeType.GENE_TO_STATE),),
                )

        with self.assertRaisesRegex(ValidationError, "maximum of 2 items"):
            planner.plan_many(hypotheses())
        self.assertEqual(yielded, [0, 1, 2])

    def test_per_hypothesis_and_total_edge_limits_fail_closed(self) -> None:
        two_edges = _hypothesis(
            "hyp-two-edges",
            (
                _edge("opaque-a", EdgeType.GENE_TO_STATE),
                _edge("opaque-b", EdgeType.GENE_TO_STATE),
            ),
        )
        per_hypothesis = ExperimentPlanner(
            limits=ExperimentPlanningLimits(
                max_hypotheses=2,
                max_edges_per_hypothesis=1,
                max_total_edges=2,
            )
        )
        with self.assertRaisesRegex(ValidationError, "edges exceeds"):
            per_hypothesis.plan(two_edges)

        first_one_edge = _hypothesis(
            "hyp-one-edge",
            (_edge("opaque-c", EdgeType.GENE_TO_STATE),),
        )
        second_one_edge = _hypothesis(
            "hyp-another-edge",
            (_edge("opaque-d", EdgeType.GENE_TO_STATE),),
        )
        total = ExperimentPlanner(
            limits=ExperimentPlanningLimits(
                max_hypotheses=2,
                max_edges_per_hypothesis=2,
                max_total_edges=1,
            )
        )
        with self.assertRaisesRegex(ValidationError, "maximum of 1 total edges"):
            total.plan_many((first_one_edge, second_one_edge))


if __name__ == "__main__":
    unittest.main()
