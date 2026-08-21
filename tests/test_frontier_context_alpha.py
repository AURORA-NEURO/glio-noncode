from __future__ import annotations

import unittest

from glio_noncode.frontier_context_alpha import (
    AlleleSaturationSimulator,
    AssaySupportCoverageGate,
    AtlasEvidenceTierAdjudicator,
    AtlasSnapshotPublisher,
    CellStateAbundanceUncertaintyModel,
    CellStateContextPublisher,
    CellStateOODDetector,
    ChromatinEvidencePublisher,
    ContextImputationWithConfidence,
    CrossAssayConcordanceAdjudicator,
    EnhancerGrammarModel,
    EnsembleDisagreementQuantifier,
    InsulatorBoundaryAtlas,
    RegulatoryHotspotAtlas,
    SequenceEvidencePublisher,
    SingleCellReferenceMapper,
)
from glio_noncode.frontier_data_alpha import FrontierState

CONTEXT = "GRCh38|glioma|adult|stem_like|core|untreated"


class FrontierContextAlphaTests(unittest.TestCase):
    def test_atlas_boundary_hotspot_tier_and_snapshot(self) -> None:
        boundary = InsulatorBoundaryAtlas().build(
            [
                {
                    "boundary_id": "b-1",
                    "chromosome": "chr7",
                    "start": 100,
                    "end": 120,
                    "insulation_score": 0.8,
                    "boundary_support": 0.9,
                    "orientation": "convergent",
                }
            ],
            context_key=CONTEXT,
            source_id="hic-1",
        )
        self.assertEqual(boundary.strong_boundary_ids, ("b-1",))
        hotspot = RegulatoryHotspotAtlas().build(
            [
                {
                    "hotspot_id": "h-1",
                    "evidence_type": "accessibility",
                    "source_id": "s-1",
                    "direction": "gain",
                },
                {
                    "hotspot_id": "h-1",
                    "evidence_type": "expression",
                    "source_id": "s-2",
                    "direction": "gain",
                },
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(hotspot.supported_ids, ("h-1",))
        tier = AtlasEvidenceTierAdjudicator().adjudicate(
            [{"atlas_id": "h-1", "source_count": 3, "consistency": 0.9, "reproducibility": 0.9}],
            context_key=CONTEXT,
        )
        self.assertEqual(tier.high_confidence_ids, ("h-1",))
        snapshot = AtlasSnapshotPublisher().publish(
            [{"id": "h-1", "context_key": CONTEXT}],
            snapshot_id="atlas-snapshot",
            atlas_type="regulatory-hotspot",
            version="v1",
            context_key=CONTEXT,
        )
        self.assertEqual(snapshot.state, FrontierState.PUBLISHED)

    def test_sequence_grammar_saturation_disagreement_and_publisher(self) -> None:
        grammar = EnhancerGrammarModel().evaluate(
            [
                {
                    "grammar_id": "g-1",
                    "motif_hits": [
                        {"motif_id": "A", "start": 10, "end": 13},
                        {"motif_id": "B", "start": 20, "end": 23},
                    ],
                    "rules": [{"left_motif": "A", "right_motif": "B", "min_gap": 7, "max_gap": 10}],
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(grammar.supported_ids, ("g-1",))
        saturation = AlleleSaturationSimulator().simulate(
            [
                {
                    "variant_id": "v-1",
                    "reference_score": 0.2,
                    "alternate_alleles": ["A", "T"],
                    "alternate_scores": {"A": 0.8, "T": 0.25},
                    "uncertainty": 0.05,
                }
            ],
            context_key=CONTEXT,
        )
        self.assertIn("v-1", saturation.positive_effect_ids)
        disagreement = EnsembleDisagreementQuantifier().quantify(
            [{"prediction_id": "p-1", "predictions": [0.4, 0.42, 0.41]}],
            context_key=CONTEXT,
        )
        self.assertEqual(disagreement.stable_ids, ("p-1",))
        evidence = SequenceEvidencePublisher().publish(
            [{"sequence_id": "seq-1", "context_key": CONTEXT, "effect": 0.4}],
            bundle_id="seq-bundle",
            context_key=CONTEXT,
            model_ids=("model-1",),
        )
        self.assertEqual(evidence.state, FrontierState.PUBLISHED)

    def test_chromatin_imputation_coverage_and_concordance(self) -> None:
        imputed = ContextImputationWithConfidence().impute(
            [{"feature_id": "f-1", "value": None}, {"feature_id": "f-2", "value": 0.4}],
            context_key=CONTEXT,
            prior_values={"f-1": 0.8},
            prior_confidence={"f-1": 0.9},
        )
        self.assertEqual(imputed.imputed_ids, ("f-1",))
        coverage = AssaySupportCoverageGate().evaluate(
            [{"feature_id": "f-1", "observed_assays": ["ATAC", "H3K27ac"]}],
            context_key=CONTEXT,
            required_assays=("ATAC", "H3K27ac"),
        )
        self.assertEqual(coverage.supported_ids, ("f-1",))
        concordance = CrossAssayConcordanceAdjudicator().adjudicate(
            [
                {
                    "feature_id": "f-1",
                    "observations": {"ATAC": "gain", "H3K27ac": "gain", "RNA": "loss"},
                }
            ],
            context_key=CONTEXT,
            minimum_concordance=0.6,
        )
        self.assertEqual(concordance.concordant_ids, ("f-1",))
        bundle = ChromatinEvidencePublisher().publish(
            [{"feature_id": "f-1", "context_key": CONTEXT, "signal": 0.9}],
            bundle_id="chromatin-bundle",
            context_key=CONTEXT,
            assay_ids=("ATAC",),
        )
        self.assertEqual(bundle.state, FrontierState.PUBLISHED)

    def test_cell_abundance_mapping_ood_and_context_publisher(self) -> None:
        abundance = CellStateAbundanceUncertaintyModel().estimate(
            [{"sample_id": "sample-1", "state_id": "stem_like", "count": 40, "total_cells": 100}],
            context_key=CONTEXT,
        )
        self.assertEqual(abundance.stable_ids, ("sample-1:stem_like",))
        mapping = SingleCellReferenceMapper().map(
            [{"cell_id": "cell-1", "reference_scores": {"stem_like": 0.9, "differentiated": 0.2}}],
            context_key=CONTEXT,
        )
        self.assertEqual(mapping.mapped_ids, ("cell-1",))
        ood = CellStateOODDetector().detect(
            [{"cell_id": "cell-1", "distance": 0.5, "support_score": 0.9}],
            context_key=CONTEXT,
        )
        self.assertEqual(ood.in_domain_ids, ("cell-1",))
        envelope = CellStateContextPublisher().publish(
            envelope_id="cell-context-1",
            context_key=CONTEXT,
            cell_ids=("cell-1",),
            mapping_address=mapping.content_address,
            abundance_address=abundance.content_address,
            ood_address=ood.content_address,
        )
        self.assertEqual(envelope.state, FrontierState.PUBLISHED)


if __name__ == "__main__":
    unittest.main()
