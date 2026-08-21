from __future__ import annotations

import json
import unittest

from glio_noncode.models import ReferenceContext
from glio_noncode.topology_beta import (
    ActivityByContactScorer,
    EnhancerActivityObservation,
    EnhancerPromoterContactEvidence,
    EnhancerPromoterContactScorer,
    LoopStripeAdapter,
    PromoterCaptureContactAdapter,
    TopologyBetaKind,
)
from glio_noncode.topology_context import TopologyState

CONTEXT = ReferenceContext("GRCh38", "glioma", "adult", "stem_like", territory="core").key
OTHER_CONTEXT = ReferenceContext(
    "GRCh38", "glioma", "adult", "differentiated", territory="core"
).key


class TopologyBetaTests(unittest.TestCase):
    def test_loop_stripe_adapter_preserves_feature_kind_coordinates_and_issues(self) -> None:
        text = (
            "feature_id\tfeature_kind\tchrom1\tstart1\tend1\tchrom2\tstart2\tend2\t"
            "signal\tcontext\tversion\tcaller\n"
            f"loop-1\tloop\t7\t99\t120\t7\t299\t320\t12\t{CONTEXT}\tv1\tcaller-a\n"
            f"stripe-1\tstripe\t7\tbad\t120\t7\t299\t320\t8\t{CONTEXT}\tv1\tcaller-a\n"
        )
        batch = LoopStripeAdapter().parse_text(text, source_id="loop-atlas")
        self.assertEqual(len(batch.observations), 1)
        self.assertEqual(batch.observations[0].feature_kind, TopologyBetaKind.LOOP)
        self.assertEqual(batch.observations[0].start_a, 100)
        self.assertEqual(batch.observations[0].end_b, 320)
        self.assertEqual(batch.observations[0].caller, "caller-a")
        self.assertEqual(batch.issues[0].code, "invalid_loop_stripe_row")

    def test_promoter_capture_adapter_preserves_bait_and_target_identity(self) -> None:
        payload = {
            "contacts": [
                {
                    "contact_id": "pc-1",
                    "promoter_id": "GENE1",
                    "target_element_id": "enh-1",
                    "promoter_chromosome": "7",
                    "promoter_start": 100,
                    "promoter_end": 120,
                    "target_chromosome": "7",
                    "target_start": 300,
                    "target_end": 320,
                    "signal": 6.0,
                    "context_key": CONTEXT,
                    "bait_id": "bait-1",
                }
            ]
        }
        batch = PromoterCaptureContactAdapter().parse_text(
            json.dumps(payload),
            source_id="pc-atlas",
            source_version="v2",
            input_format="json",
            coordinate_system="one_based",
        )
        self.assertEqual(len(batch.contacts), 1)
        self.assertEqual(batch.contacts[0].promoter_id, "GENE1")
        self.assertEqual(batch.contacts[0].target_element_id, "enh-1")
        self.assertEqual(batch.contacts[0].bait_id, "bait-1")
        self.assertEqual(batch.contacts[0].promoter_start, 100)

    def test_contact_scorer_keeps_context_and_replicate_disagreement(self) -> None:
        observations = (
            EnhancerPromoterContactEvidence(
                "enh-1",
                "GENE1",
                8.0,
                CONTEXT,
                "pc-atlas",
                "v1",
                "raw-1",
                "pc-1",
            ),
            EnhancerPromoterContactEvidence(
                "enh-1",
                "GENE1",
                2.0,
                CONTEXT,
                "pc-atlas",
                "v1",
                "raw-2",
                "pc-2",
            ),
        )
        score = EnhancerPromoterContactScorer().score(
            observations,
            enhancer_id="enh-1",
            promoter_id="GENE1",
            context_key=CONTEXT,
            signal_scale=10,
            ambiguity_tolerance=1,
        )
        self.assertEqual(score.state, TopologyState.AMBIGUOUS)
        self.assertEqual(score.median_signal, 5.0)
        self.assertEqual(score.normalized_contact_score, 0.5)
        other = EnhancerPromoterContactScorer().score(
            observations,
            enhancer_id="enh-1",
            promoter_id="GENE1",
            context_key=OTHER_CONTEXT,
        )
        self.assertEqual(other.state, TopologyState.OUT_OF_DOMAIN)
        self.assertEqual(other.observations, ())

    def test_activity_by_contact_combines_components_without_probability_claim(self) -> None:
        contacts = (
            EnhancerPromoterContactEvidence(
                "enh-1",
                "GENE1",
                5.0,
                CONTEXT,
                "pc-atlas",
                "v1",
                "raw-contact",
            ),
        )
        activities = (
            EnhancerActivityObservation(
                "enh-1",
                0.8,
                CONTEXT,
                "activity-atlas",
                "v3",
                "raw-activity",
            ),
        )
        result = ActivityByContactScorer().score(
            contacts,
            activities,
            enhancer_id="enh-1",
            promoter_id="GENE1",
            context_key=CONTEXT,
            model_id="abc-model",
            model_version="v1",
            contact_scale=10,
            activity_scale=1,
        )
        self.assertEqual(result.state, TopologyState.SUPPORTED)
        self.assertEqual(result.contact_component, 0.5)
        self.assertEqual(result.activity_component, 0.8)
        self.assertEqual(result.activity_by_contact_score, 0.4)
        self.assertIn("not a probability", " ".join(result.warnings))

        missing_activity = ActivityByContactScorer().score(
            contacts,
            (),
            enhancer_id="enh-1",
            promoter_id="GENE1",
            context_key=CONTEXT,
            model_id="abc-model",
            model_version="v1",
        )
        self.assertEqual(missing_activity.state, TopologyState.ABSTAINED)
        self.assertIsNone(missing_activity.activity_by_contact_score)


if __name__ == "__main__":
    unittest.main()
