from __future__ import annotations

import unittest

from glio_noncode.causal_reasoning import (
    CausalState,
    ContextConditionedPriorModel,
    ContextPriorProfile,
    FactorGraphConstructor,
    FactorObservation,
    FactorType,
    MeasurementLikelihoodModel,
    MeasurementObservation,
    TypedHypothesisObjectBuilder,
)
from glio_noncode.errors import ValidationError
from glio_noncode.models import ReferenceContext


class CausalReasoningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = ReferenceContext(
            "GRCh38", "glioma", "adult", "stem_like", territory="core"
        )

    def _factor(
        self,
        factor_id: str,
        *,
        edge_id: str = "edge-1",
        state: CausalState = CausalState.SUPPORTED,
        support: float | None = 0.8,
        parent_factor_ids: tuple[str, ...] = (),
        supersedes: str | None = None,
    ) -> FactorObservation:
        return FactorObservation(
            factor_id=factor_id,
            edge_id=edge_id,
            factor_type=FactorType.LINK,
            context_key=self.context.key,
            source_id="source-1",
            source_version="v1",
            raw_hash=f"hash-{factor_id}",
            state=state,
            support=support,
            uncertainty=0.2,
            parent_factor_ids=parent_factor_ids,
            claim_ids=(f"claim-{factor_id}",),
            supersedes=supersedes,
        )

    def test_factor_graph_preserves_lineage_orphans_supersession_and_replay(self) -> None:
        graph = FactorGraphConstructor().construct(
            (
                self._factor("f1"),
                self._factor("f2", parent_factor_ids=("f1",), supersedes="f1"),
                self._factor("f3", edge_id="edge-2", parent_factor_ids=("missing",)),
            ),
            context_key=self.context.key,
            graph_id="graph-1",
        )
        self.assertEqual(graph.state, CausalState.PARTIAL)
        self.assertEqual(graph.superseded_factor_ids, ("f1",))
        self.assertEqual(graph.active_factor_ids, ("f2", "f3"))
        self.assertEqual(graph.orphan_factor_ids, ("f3",))
        self.assertEqual(graph.replay().content_address, graph.content_address)
        with self.assertRaises(ValidationError):
            graph.append(
                FactorObservation(
                    "f4", "edge-3", FactorType.LINK, "wrong-context", "s", "v", "h",
                    CausalState.SUPPORTED, 0.5, 0.2,
                )
            )

    def test_factor_graph_detects_supported_and_negative_contradiction(self) -> None:
        graph = FactorGraphConstructor().construct(
            (
                self._factor("positive"),
                self._factor(
                    "negative", state=CausalState.MEASURED_NEGATIVE, support=0.0
                ),
            ),
            context_key=self.context.key,
        )
        self.assertEqual(graph.state, CausalState.CONTRADICTORY)
        self.assertEqual(graph.contradictory_edge_ids, ("edge-1",))

    def test_empty_factor_graph_abstains(self) -> None:
        graph = FactorGraphConstructor().construct((), context_key=self.context.key)
        self.assertEqual(graph.state, CausalState.ABSTAINED)
        self.assertEqual(graph.active_factors(), ())

    def test_context_prior_model_is_bounded_and_context_conditioned(self) -> None:
        profile = ContextPriorProfile(
            "prior-1",
            self.context.key,
            0.4,
            {"accessibility": 0.2},
            {"accessibility": (0.0, 1.0)},
            "v1",
            "prior-hash",
        )
        model = ContextConditionedPriorModel()
        estimate = model.estimate(self.context, {"accessibility": 0.8}, profile)
        missing = model.estimate(self.context, {}, profile)
        ood = model.estimate(
            ReferenceContext("GRCh38", "glioma", "pediatric", "stem_like", territory="core"),
            {"accessibility": 0.8},
            profile,
        )
        self.assertEqual(estimate.state, CausalState.SUPPORTED)
        self.assertEqual(estimate.prior_score, 0.52)
        self.assertEqual(missing.state, CausalState.ABSTAINED)
        self.assertEqual(ood.state, CausalState.OUT_OF_DOMAIN)
        self.assertIsNone(ood.prior_score)

    def test_measurement_likelihood_groups_dependent_channels(self) -> None:
        observations = (
            MeasurementObservation(
                "m1", "edge-1", "accessibility", self.context.key, "atac", "v1", "h1",
                CausalState.SUPPORTED, 0.8, 0.9,
            ),
            MeasurementObservation(
                "m2", "edge-1", "contact", self.context.key, "hic", "v1", "h2",
                CausalState.SUPPORTED, 0.6, 0.8,
            ),
            MeasurementObservation(
                "m3", "edge-1", "histone_activity", self.context.key, "h3", "v1", "h3",
                CausalState.SUPPORTED, None, 0.7,
            ),
        )
        estimate = MeasurementLikelihoodModel().estimate(
            self.context, observations, edge_id="edge-1"
        )
        self.assertEqual(estimate.state, CausalState.SUPPORTED)
        self.assertEqual(estimate.likelihood_proxy, 0.64)
        self.assertEqual(estimate.channel_groups, ("chromatin", "topology"))
        self.assertEqual(estimate.missing_measurement_ids, ("m3",))

    def test_measurement_likelihood_abstains_or_preserves_contradiction(self) -> None:
        model = MeasurementLikelihoodModel()
        none = model.estimate(self.context, (), edge_id="edge-1")
        wrong = model.estimate(
            self.context,
            (
                MeasurementObservation(
                    "m1", "edge-1", "contact", "wrong", "hic", "v1", "h1",
                    CausalState.SUPPORTED, 0.64, 1.0,
                ),
            ),
            edge_id="edge-1",
        )
        contradiction = model.estimate(
            self.context,
            (
                MeasurementObservation(
                    "m2", "edge-1", "contact", self.context.key, "hic", "v1", "h2",
                    CausalState.CONTRADICTORY, None, 0.9,
                ),
            ),
            edge_id="edge-1",
        )
        self.assertEqual(none.state, CausalState.ABSTAINED)
        self.assertEqual(wrong.state, CausalState.OUT_OF_DOMAIN)
        self.assertEqual(contradiction.state, CausalState.CONTRADICTORY)
        self.assertIsNone(contradiction.likelihood_proxy)

    def test_hypothesis_builder_requires_complete_evidence_and_keeps_proxy_name(self) -> None:
        graph = FactorGraphConstructor().construct(
            (self._factor("f1"),), context_key=self.context.key, graph_id="graph-1"
        )
        profile = ContextPriorProfile(
            "prior-1", self.context.key, 0.4, {"x": 0.2}, {"x": (0.0, 1.0)}, "v1", "h"
        )
        prior = ContextConditionedPriorModel().estimate(self.context, {"x": 0.8}, profile)
        likelihood = MeasurementLikelihoodModel().estimate(
            self.context,
            (
                MeasurementObservation(
                    "m1", "edge-1", "contact", self.context.key, "hic", "v1", "h1",
                    CausalState.SUPPORTED, 0.64, 1.0,
                ),
                MeasurementObservation(
                    "m2", "edge-1", "qtl", self.context.key, "qtl", "v1", "h2",
                    CausalState.SUPPORTED, 0.64, 1.0,
                ),
            ),
            edge_id="edge-1",
        )
        hypothesis = TypedHypothesisObjectBuilder().build(
            hypothesis_id="h-1",
            variant_id="v1",
            element_id="enh-1",
            gene_id="GENE1",
            state_id="stem_like",
            mechanism="regulatory_link",
            context=self.context,
            factor_graph=graph,
            prior=prior,
            likelihood=likelihood,
        )
        self.assertEqual(hypothesis.state, CausalState.SUPPORTED)
        self.assertEqual(hypothesis.support_proxy, 0.3328)
        self.assertEqual(hypothesis.factor_ids, ("f1",))
        self.assertIn("proxy", hypothesis.to_dict().get("limitations", ())[0])


if __name__ == "__main__":
    unittest.main()
