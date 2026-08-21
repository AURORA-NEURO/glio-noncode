from __future__ import annotations

import json
import unittest

from glio_noncode.cohort_beta import (
    CohortBetaState,
    FunctionalConvergenceParser,
    FunctionalConvergenceTester,
    FunctionalDirection,
    PathwayRegulonConvergenceTester,
    PathwayRegulonObservation,
    PathwayRegulonParser,
    RegionalBurdenRegion,
    RegionalBurdenTester,
    RegulatoryRecurrenceParser,
    RegulatoryRecurrenceTester,
    SetDirection,
    SetKind,
)

CONTEXT = "GRCh38|glioma|adult|stem_like|core|unknown"
OTHER_CONTEXT = "GRCh38|glioma|adult|differentiated|core|unknown"


def recurrence(
    record_id: str,
    variant_id: str,
    sample_id: str,
    position: int,
    *,
    context_key: str = CONTEXT,
    source_id: str = "cohort-a",
    callable: bool = True,
    region_id: str | None = "reg-1",
) -> dict[str, object]:
    return {
        "record_id": record_id,
        "variant_id": variant_id,
        "sample_id": sample_id,
        "chromosome": "chr7",
        "position": position,
        "context_key": context_key,
        "source_id": source_id,
        "source_version": "v1",
        "callable": callable,
        "region_id": region_id,
    }


class CohortBetaTests(unittest.TestCase):
    def test_recurrence_parser_quarantines_bad_rows_and_hotspot_deduplicates_samples(self) -> None:
        batch = RegulatoryRecurrenceParser().parse_text(
            json.dumps(
                {
                    "records": [
                        recurrence("r1", "v1", "s1", 100),
                        recurrence("r2", "v1", "s2", 100),
                        recurrence("r3", "v2", "s2", 110),
                        {"record_id": "bad", "position": "not-an-int"},
                    ]
                }
            ),
            source_id="cohort-parser",
        )
        self.assertEqual(len(batch.records), 3)
        self.assertEqual(batch.issues[0].code, "invalid_recurrence_row")
        result = RegulatoryRecurrenceTester().test(
            batch.records,
            context_key=CONTEXT,
            minimum_recurrent_samples=2,
            hotspot_window_bp=20,
            minimum_hotspot_variants=2,
            minimum_hotspot_samples=2,
        )
        self.assertEqual(result.state, CohortBetaState.SUPPORTED)
        self.assertEqual(result.recurrent_variant_ids, ("v1",))
        self.assertEqual(len(result.hotspots), 1)
        self.assertEqual(result.hotspots[0].variant_ids, ("v1", "v2"))
        self.assertEqual(result.observed_sample_count, 2)

    def test_recurrence_context_and_callable_gates_are_explicit(self) -> None:
        wrong_context = RegulatoryRecurrenceTester().test(
            (recurrence("other", "v1", "s1", 100, context_key=OTHER_CONTEXT),),
            context_key=CONTEXT,
        )
        self.assertEqual(wrong_context.state, CohortBetaState.OUT_OF_DOMAIN)
        non_callable = RegulatoryRecurrenceTester().test(
            (recurrence("uncallable", "v1", "s1", 100, callable=False),),
            context_key=CONTEXT,
        )
        self.assertEqual(non_callable.state, CohortBetaState.PARTIAL)

    def test_regional_burden_uses_callable_bases_and_comparator(self) -> None:
        region = RegionalBurdenRegion(
            "reg-1",
            "chr7",
            100,
            200,
            1000,
            CONTEXT,
            "regions",
            "v1",
            "raw-region",
        )
        result = RegionalBurdenTester().test(
            (region,),
            (
                recurrence("r1", "v1", "s1", 120),
                recurrence("r2", "v2", "s2", 150),
                recurrence("duplicate", "v1", "s3", 120),
            ),
            region_id="reg-1",
            context_key=CONTEXT,
            background_rate=0.001,
        )
        self.assertEqual(result.state, CohortBetaState.SUPPORTED)
        self.assertEqual(result.observed_variant_count, 2)
        self.assertEqual(result.observed_sample_count, 3)
        self.assertAlmostEqual(result.burden_per_kb, 2.0)
        self.assertAlmostEqual(result.expected_count, 1.0)
        self.assertAlmostEqual(result.excess_ratio, 2.0)

    def test_functional_convergence_contrasts_features_and_tracks_sample_count(self) -> None:
        observations = (
            {
                "observation_id": "f1-a",
                "variant_id": "v1",
                "sample_id": "s1",
                "feature_id": "motif-loss",
                "feature_class": "sequence",
                "support": 0.9,
                "direction": "loss",
                "context_key": CONTEXT,
                "source_id": "sequence-a",
                "source_version": "v1",
            },
            {
                "observation_id": "f1-b",
                "variant_id": "v2",
                "sample_id": "s2",
                "feature_id": "motif-loss",
                "feature_class": "sequence",
                "support": 0.8,
                "direction": "loss",
                "context_key": CONTEXT,
                "source_id": "sequence-b",
                "source_version": "v1",
            },
            {
                "observation_id": "f2-a",
                "variant_id": "v1",
                "sample_id": "s1",
                "feature_id": "accessibility",
                "feature_class": "chromatin",
                "support": 0.3,
                "direction": "gain",
                "context_key": CONTEXT,
                "source_id": "chromatin-a",
                "source_version": "v1",
            },
            {
                "observation_id": "ctrl-1",
                "variant_id": "c1",
                "sample_id": "cs1",
                "feature_id": "motif-loss",
                "feature_class": "sequence",
                "support": 0.2,
                "direction": "loss",
                "context_key": CONTEXT,
                "source_id": "sequence-control",
                "source_version": "v1",
                "is_control": True,
            },
            {
                "observation_id": "ctrl-2",
                "variant_id": "c2",
                "sample_id": "cs2",
                "feature_id": "motif-loss",
                "feature_class": "sequence",
                "support": 0.3,
                "direction": "loss",
                "context_key": CONTEXT,
                "source_id": "sequence-control",
                "source_version": "v1",
                "is_control": True,
            },
        )
        result = FunctionalConvergenceTester().test(
            observations,
            context_key=CONTEXT,
            minimum_observed_variants=2,
            ambiguity_margin=0.01,
        )
        self.assertEqual(result.state, CohortBetaState.SUPPORTED)
        self.assertEqual(result.leading_feature_ids, ("motif-loss",))
        self.assertAlmostEqual(result.convergence_score, 0.6)
        self.assertEqual(result.observed_variant_count, 2)
        self.assertEqual(result.observed_sample_count, 2)
        self.assertIsNone(result.features[1].control_support)

    def test_functional_parser_preserves_direction_and_out_of_domain_state(self) -> None:
        batch = FunctionalConvergenceParser().parse_text(
            "observation_id\tvariant_id\tsample_id\tfeature_id\tfeature_class\tsupport\tdirection\tcontext_key\n"
            f"f1\tv1\ts1\tmotif\tsequence\t0.7\tloss\t{CONTEXT}\n",
            source_id="functional-tsv",
            input_format="tsv",
        )
        self.assertEqual(batch.observations[0].direction, FunctionalDirection.LOSS)
        out_of_domain = FunctionalConvergenceTester().test(
            batch.observations,
            context_key=OTHER_CONTEXT,
        )
        self.assertEqual(out_of_domain.state, CohortBetaState.OUT_OF_DOMAIN)

    def test_pathway_regulon_convergence_reports_leading_set_and_direction_conflict(self) -> None:
        rows = (
            PathwayRegulonObservation(
                "p1",
                "v1",
                "s1",
                "GENE1",
                "path-a",
                SetKind.PATHWAY,
                0.8,
                SetDirection.ACTIVATED,
                CONTEXT,
                "path-a",
                "v1",
                "raw-p1",
            ),
            PathwayRegulonObservation(
                "p2",
                "v2",
                "s2",
                "GENE2",
                "path-a",
                SetKind.PATHWAY,
                0.7,
                SetDirection.ACTIVATED,
                CONTEXT,
                "path-b",
                "v1",
                "raw-p2",
            ),
            PathwayRegulonObservation(
                "p3",
                "v1",
                "s1",
                "GENE3",
                "path-a",
                SetKind.PATHWAY,
                0.6,
                SetDirection.REPRESSED,
                CONTEXT,
                "path-a",
                "v1",
                "raw-p3",
            ),
            PathwayRegulonObservation(
                "c1",
                "c1",
                "cs1",
                "GENE1",
                "path-a",
                SetKind.PATHWAY,
                0.2,
                SetDirection.ACTIVATED,
                CONTEXT,
                "path-control",
                "v1",
                "raw-c1",
                True,
            ),
            PathwayRegulonObservation(
                "c2",
                "c2",
                "cs2",
                "GENE2",
                "path-a",
                SetKind.PATHWAY,
                0.3,
                SetDirection.ACTIVATED,
                CONTEXT,
                "path-control",
                "v1",
                "raw-c2",
                True,
            ),
        )
        result = PathwayRegulonConvergenceTester().test(
            rows,
            context_key=CONTEXT,
            set_kind=SetKind.PATHWAY,
            minimum_genes=2,
            ambiguity_margin=0.01,
        )
        self.assertEqual(result.state, CohortBetaState.CONTRADICTORY)
        self.assertEqual(result.leading_set_ids, ("path-a",))
        self.assertTrue(result.sets[0].directional_conflict)
        self.assertEqual(result.observed_gene_count, 3)

    def test_pathway_parser_accepts_regulon_namespace(self) -> None:
        batch = PathwayRegulonParser().parse_text(
            json.dumps(
                {
                    "observations": [
                        {
                            "observation_id": "r1",
                            "variant_id": "v1",
                            "sample_id": "s1",
                            "gene_id": "GENE1",
                            "set_id": "reg-1",
                            "set_kind": "regulon",
                            "support": 0.8,
                            "direction": "activated",
                            "context_key": CONTEXT,
                        }
                    ]
                }
            ),
            source_id="regulon-json",
        )
        self.assertEqual(batch.observations[0].set_kind, SetKind.REGULON)
        self.assertTrue(batch.content_address)


if __name__ == "__main__":
    unittest.main()
