from __future__ import annotations

import unittest

from glio_noncode.context import compare_context, context_gate
from glio_noncode.evidence import EvidenceGraph
from glio_noncode.models import (
    EdgeType,
    EvidenceClaim,
    EvidenceState,
    EvidenceTier,
    HypothesisEdge,
    ReferenceContext,
    SupportLevel,
)


def context(**overrides: str) -> ReferenceContext:
    values = {
        "genome_build": "GRCh38",
        "disease_class": "diffuse_glioma",
        "age_group": "adult",
        "cell_state": "malignant",
        "territory": "core",
        "treatment_phase": "pre",
    }
    values.update(overrides)
    return ReferenceContext(**values)


class ContextEvidenceTests(unittest.TestCase):
    def test_exact_context_is_high(self) -> None:
        match = compare_context(context(), context())
        self.assertEqual(match.score, 1.0)
        self.assertEqual(match.support_level, SupportLevel.HIGH)
        self.assertTrue(context_gate(match))

    def test_context_transport_is_visible(self) -> None:
        match = compare_context(context(), context(age_group="pediatric", cell_state="stem_like"))
        self.assertLess(match.score, 0.7)
        self.assertIn("age_group", match.mismatched_dimensions)
        self.assertIn("transport required", match.rationale)

    def test_dependence_grouping_does_not_double_count(self) -> None:
        graph = EvidenceGraph()
        edge = HypothesisEdge(
            edge_id="edge-1",
            edge_type=EdgeType.VARIANT_TO_ELEMENT,
            source_id="v",
            target_id="e",
            support=0.0,
            uncertainty=1.0,
            context_fit=1.0,
            claim_ids=("c1", "c2", "c3"),
            support_level=SupportLevel.UNKNOWN,
        )
        for evidence_id, channel, score in (
            ("c1", "motif_delta", 0.9),
            ("c2", "sequence_model", 0.9),
            ("c3", "accessibility", 0.6),
        ):
            graph.append(
                EvidenceClaim(
                    evidence_id=evidence_id,
                    edge_id="edge-1",
                    source_id="source",
                    channel=channel,
                    state=EvidenceState.SUPPORTED,
                    tier=EvidenceTier.COMPUTED,
                    score=score,
                    confidence=1.0,
                    context=context(),
                    summary="fixture",
                )
            )
        aggregate = graph.aggregate(edge)
        self.assertGreater(aggregate.score, 0.0)
        self.assertLess(aggregate.score, 0.9)
        self.assertEqual(aggregate.channel_groups, ("chromatin", "sequence"))

    def test_measured_negative_remains_distinct(self) -> None:
        graph = EvidenceGraph()
        graph.append(
            EvidenceClaim(
                evidence_id="negative",
                edge_id="edge-negative",
                source_id="source",
                channel="accessibility",
                state=EvidenceState.MEASURED_NEGATIVE,
                tier=EvidenceTier.EXPERIMENTAL,
                score=0.05,
                confidence=0.9,
                context=context(),
                summary="measured low accessibility",
            )
        )
        edge = HypothesisEdge(
            edge_id="edge-negative",
            edge_type=EdgeType.VARIANT_TO_ELEMENT,
            source_id="v",
            target_id="e",
            support=0.0,
            uncertainty=1.0,
            context_fit=1.0,
            claim_ids=("negative",),
            support_level=SupportLevel.UNKNOWN,
        )
        aggregate = graph.aggregate(edge)
        self.assertEqual(aggregate.negative_claim_ids, ("negative",))
        self.assertEqual(aggregate.score, 0.0)
