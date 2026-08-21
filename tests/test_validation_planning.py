from __future__ import annotations

import unittest

from glio_noncode.causal_reasoning import CausalState, RegulatoryCausalHypothesis
from glio_noncode.models import ReferenceContext
from glio_noncode.validation_planning import (
    AssayCapability,
    AssayConstraints,
    AssayEligibilityRouter,
    EvidenceGapAnalyzer,
    MPRAPlanner,
    PlanState,
    STARRSeqPlanner,
    ValidationAssay,
    ValidationPlanBuilder,
    ValidationTarget,
)


class ValidationPlanningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = ReferenceContext(
            "GRCh38", "glioma", "adult", "stem_like", territory="core"
        )
        self.hypothesis = RegulatoryCausalHypothesis(
            hypothesis_id="h1",
            variant_id="v1",
            element_id="enh1",
            gene_id="GENE1",
            state_id="stem_like",
            mechanism="regulatory_link",
            context_key=self.context.key,
            state=CausalState.PARTIAL,
            support_proxy=0.4,
            uncertainty=0.8,
            factor_graph_id="graph1",
            factor_ids=("f1",),
            prior_profile_id="prior1",
            measurement_edge_id="edge1",
            missing_evidence=("measurement_likelihood",),
            contradictory_edges=(),
            limitations=("research",),
            content_address="sha256:h1",
        )
        self.constraints = AssayConstraints(
            "c1",
            self.context.key,
            "neural_model",
            4,
            12,
            4,
            ("negative_control", "positive_control"),
            ("barcode", "rna"),
        )
        self.target = ValidationTarget(
            "target1",
            "v1",
            "enh1",
            "ACGTACGT",
            2,
            "G",
            "T",
            self.context,
            "sequence-source",
        )

    def test_gap_analyzer_ranks_missing_uncertainty_and_available_channels(self) -> None:
        result = EvidenceGapAnalyzer().analyze(
            self.hypothesis, available_channels=("sequence", "chromatin")
        )
        self.assertEqual(result.state, PlanState.PARTIAL)
        self.assertIn("h1:missing:1", result.priority_order)
        self.assertIn("h1:uncertainty", result.priority_order)
        self.assertEqual(result.available_channels, ("chromatin", "sequence"))

    def test_assay_router_exposes_ready_and_blocked_routes(self) -> None:
        inventory = (
            AssayCapability(
                ValidationAssay.MPRA,
                ("neural_model",),
                4,
                12,
                ("negative_control", "positive_control"),
                ("barcode", "rna"),
                "assay-inventory",
                0.8,
            ),
            AssayCapability(
                ValidationAssay.MPRA,
                ("other_model",),
                4,
                12,
                ("negative_control",),
                ("barcode",),
                "assay-inventory",
                0.5,
            ),
        )
        routes = AssayEligibilityRouter().route(
            self.constraints, inventory, assay=ValidationAssay.MPRA
        )
        self.assertEqual(routes[0].state, PlanState.READY_FOR_REVIEW)
        self.assertEqual(routes[0].model_system, "neural_model")
        self.assertEqual(routes[1].state, PlanState.BLOCKED)
        self.assertTrue(routes[1].blockers)
        self.assertTrue(routes[1].sensitivity)

    def test_mpra_planner_generates_reference_and_alternate_constructs(self) -> None:
        package = MPRAPlanner().plan((self.target,), self.constraints)
        self.assertEqual(package.state, PlanState.READY_FOR_REVIEW)
        self.assertEqual(len(package.constructs), 2)
        self.assertEqual(
            {construct.allele for construct in package.constructs}, {"reference", "alternate"}
        )
        alternate = next(item for item in package.constructs if item.allele == "alternate")
        self.assertEqual(alternate.sequence, "ACTTACGT")
        self.assertEqual(package.controls, ("negative_control", "positive_control"))

    def test_starr_seq_planner_blocks_context_mismatch_and_budget_overflow(self) -> None:
        other = ValidationTarget(
            "target2",
            "v2",
            "enh2",
            "ACGTACGT",
            2,
            "G",
            "A",
            ReferenceContext("GRCh38", "glioma", "pediatric", "stem_like", territory="core"),
            "sequence-source",
        )
        package = STARRSeqPlanner().plan((self.target, other), self.constraints)
        self.assertEqual(package.state, PlanState.BLOCKED)
        self.assertIn("target2:context_mismatch", package.blockers)

        budget = AssayConstraints(
            "small", self.context.key, "neural_model", 4, 12, 1,
            ("negative_control",), ("barcode",)
        )
        blocked = STARRSeqPlanner().plan((self.target,), budget)
        self.assertEqual(blocked.state, PlanState.BLOCKED)
        self.assertIn("max_constructs_exceeded", blocked.blockers)

    def test_validation_plan_builder_propagates_blocked_route(self) -> None:
        gap = EvidenceGapAnalyzer().analyze(self.hypothesis)
        routes = AssayEligibilityRouter().route(
            self.constraints,
            (),
            assay=ValidationAssay.MPRA,
        )
        package = MPRAPlanner().plan((self.target,), self.constraints)
        plan = ValidationPlanBuilder().build("plan1", gap, routes, (package,))
        self.assertEqual(plan.state, PlanState.ABSTAINED)
        self.assertEqual(plan.context_key, self.context.key)
        self.assertTrue(plan.content_address.startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()
