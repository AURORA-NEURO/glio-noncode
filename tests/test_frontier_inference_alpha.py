from __future__ import annotations

import unittest

from glio_noncode.frontier_data_alpha import FrontierState
from glio_noncode.frontier_inference_alpha import (
    CausalDossierPublisher,
    CohortDiscoveryPublisher,
    CompartmentSwitchEstimator,
    EcDNARegulatoryContactModel,
    FederatedSummaryAnalyzer,
    LinkCalibrationAndAbstention,
    LinkEvidenceDependenceCorrector,
    PosteriorDecompositionEngine,
    RegulatoryDriverHypothesisPosterior,
    SelectivePredictionAndAbstention,
    SubgroupFairnessStratifier,
    TargetGeneRanker,
    TopologyUncertaintyTransportModel,
    TransportabilityEstimator,
)

CONTEXT = "GRCh38|glioma|adult|stem_like|core|untreated"


class FrontierInferenceAlphaTests(unittest.TestCase):
    def test_topology_ecdna_compartment_transport_and_publisher(self) -> None:
        ecdna = EcDNARegulatoryContactModel().evaluate(
            [
                {
                    "amplicon_id": "amp-1",
                    "element_id": "enh-1",
                    "gene_id": "EGFR",
                    "contact_score": 0.8,
                    "source_ids": ["hic-1", "circle-1"],
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(ecdna.supported_ids, ("amp-1",))
        switch = CompartmentSwitchEstimator().estimate(
            [{"region_id": "r-1", "previous_score": -0.4, "current_score": 0.5}],
            context_key=CONTEXT,
        )
        self.assertEqual(switch.switched_ids, ("r-1",))
        transport = TopologyUncertaintyTransportModel().transport(
            [
                {
                    "path_id": "path-1",
                    "node_ids": ["a", "b"],
                    "edges": [{"uncertainty": 0.1}],
                    "signal": 0.9,
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(transport.supported_ids, ("path-1",))

    def test_link_dependence_ranking_calibration_and_causal_receipts(self) -> None:
        dependence = LinkEvidenceDependenceCorrector().correct(
            [
                {"link_id": "l-1", "dependence_group": "assay-a", "support": 0.8},
                {"link_id": "l-2", "dependence_group": "assay-a", "support": 0.8},
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(dependence.links[0].group_size, 2)
        ranked = TargetGeneRanker().rank(
            [
                {
                    "link_id": "l-1",
                    "variant_id": "v-1",
                    "element_id": "e-1",
                    "gene_id": "EGFR",
                    "component_scores": {"contact": 0.9, "activity": 0.8},
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(ranked.top_gene_by_variant["v-1"], "EGFR")
        calibration = LinkCalibrationAndAbstention().evaluate(
            [
                {
                    "link_id": "l-1",
                    "predicted_score": 0.8,
                    "observed_score": 0.75,
                    "uncertainty": 0.05,
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(calibration.accepted_ids, ("l-1",))
        posterior = PosteriorDecompositionEngine().decompose(
            [
                {
                    "hypothesis_id": "h-1",
                    "prior": 0.5,
                    "likelihood": 0.9,
                    "measurement": 0.8,
                    "dependency_penalty": 0.1,
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(posterior.top_hypothesis_id, "h-1")
        driver = RegulatoryDriverHypothesisPosterior().infer(
            [{"driver_id": "d-1", "evidence_ids": ["e-1"], "evidence_support": 0.8, "prior": 0.5}],
            context_key=CONTEXT,
        )
        self.assertEqual(driver.top_driver_id, "d-1")
        selective = SelectivePredictionAndAbstention().evaluate(
            [{"prediction_id": "p-1", "score": 0.9, "uncertainty": 0.05}],
            context_key=CONTEXT,
        )
        self.assertEqual(selective.accepted_ids, ("p-1",))
        dossier = CausalDossierPublisher().publish(
            dossier_id="dossier-1",
            context_key=CONTEXT,
            hypothesis_ids=("h-1",),
            evidence_addresses=(posterior.content_address,),
            top_hypothesis_id="h-1",
        )
        self.assertEqual(dossier.state, FrontierState.PUBLISHED)

    def test_cohort_fairness_transport_federated_and_publisher(self) -> None:
        fairness = SubgroupFairnessStratifier().stratify(
            [
                {"group": "A", "positive": 1},
                {"group": "A", "positive": 1},
                {"group": "B", "positive": 0},
                {"group": "B", "positive": 1},
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(fairness.maximum_parity_gap, 0.5)
        transport = TransportabilityEstimator().estimate(
            [
                {
                    "analysis_id": "analysis-1",
                    "source_features": ["age", "state"],
                    "target_features": ["age", "state"],
                    "shift_score": 0.1,
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(transport.transportable_ids, ("analysis-1",))
        federated = FederatedSummaryAnalyzer().analyze(
            [
                {"feature_id": "f-1", "site_id": "site-a", "count": 10, "mean": 0.4},
                {"feature_id": "f-1", "site_id": "site-b", "count": 12, "mean": 0.6},
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(federated.supported_ids, ("f-1",))
        bundle = CohortDiscoveryPublisher().publish(
            [{"feature_id": "f-1", "context_key": CONTEXT, "weighted_mean": 0.5}],
            bundle_id="cohort-1",
            context_key=CONTEXT,
            analysis_ids=("analysis-1",),
        )
        self.assertEqual(bundle.state, FrontierState.PUBLISHED)


if __name__ == "__main__":
    unittest.main()
