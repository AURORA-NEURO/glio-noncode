from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

from glio_noncode.errors import ValidationError
from glio_noncode.hypotheses import HypothesisBuilder, HypothesisWorkLimits
from glio_noncode.models import (
    EdgeType,
    EvidenceClaim,
    EvidenceState,
    EvidenceTier,
    ReferenceContext,
)
from glio_noncode.serialization import content_hash

from .helpers import fixture_manifest


def external_claim(
    edge_id: str,
    label: str,
    *,
    context: ReferenceContext | None = None,
) -> EvidenceClaim:
    manifest = fixture_manifest()
    selected_context = manifest.context if context is None else context
    return EvidenceClaim(
        evidence_id=content_hash(
            {"edge_id": edge_id, "label": label},
            prefix="external-evidence",
        ),
        edge_id=edge_id,
        source_id=f"external-source:{label}",
        channel=f"external-channel:{label}",
        state=EvidenceState.SUPPORTED,
        tier=EvidenceTier.REVIEWED,
        score=1.0,
        confidence=1.0,
        context=selected_context,
        summary=f"External observation for {label}.",
        payload={"label": label},
        produced_by="test_external_adapter",
        created_at="2026-09-02T12:00:00+00:00",
    )


class HypothesisExternalClaimTests(unittest.TestCase):
    def test_external_claims_cover_every_built_edge_class_and_affect_aggregation(self) -> None:
        manifest = fixture_manifest()
        builder = HypothesisBuilder()
        baseline = builder.build(manifest, "run-external-claims")
        baseline_edges = {
            edge.edge_id: edge for hypothesis in baseline.hypotheses for edge in hypothesis.edges
        }
        claims = tuple(
            external_claim(edge_id, f"edge-{index}") for index, edge_id in enumerate(baseline_edges)
        )

        built = builder.build(
            manifest,
            "run-external-claims",
            external_claims=claims,
        )
        built_edges = {
            edge.edge_id: edge for hypothesis in built.hypotheses for edge in hypothesis.edges
        }

        self.assertEqual(set(built_edges), set(baseline_edges))
        self.assertEqual(
            {edge.edge_type for edge in built_edges.values()},
            {edge.edge_type for edge in baseline_edges.values()},
        )
        self.assertTrue(
            {claim.evidence_id for claim in claims}.issubset(
                {claim.evidence_id for claim in built.claims}
            )
        )
        for claim in claims:
            with self.subTest(edge_id=claim.edge_id):
                self.assertIn(claim.evidence_id, built_edges[claim.edge_id].claim_ids)
                self.assertGreater(
                    built_edges[claim.edge_id].support,
                    baseline_edges[claim.edge_id].support,
                )

    def test_external_claim_iterable_is_bounded_by_one_sentinel(self) -> None:
        manifest = fixture_manifest()
        edge_id = HypothesisBuilder._edge_id(  # noqa: SLF001 - seam contract
            manifest.variants[0].variant_id,
            manifest.candidate_elements[0].element_id,
            EdgeType.VARIANT_TO_ELEMENT,
        )
        builder = HypothesisBuilder(limits=HypothesisWorkLimits(max_external_claims=2))
        accepted = tuple(external_claim(edge_id, f"accepted-{index}") for index in range(2))
        self.assertEqual(
            len(
                builder.build(
                    manifest,
                    "run-external-boundary",
                    external_claims=accepted,
                ).hypotheses
            ),
            1,
        )

        consumed: list[int] = []

        def unbounded_claims():
            index = 0
            while True:
                consumed.append(index)
                yield object()
                index += 1

        with self.assertRaisesRegex(ValidationError, "maximum of 2 items"):
            builder.build(
                manifest,
                "run-external-over-bound",
                external_claims=unbounded_claims(),
            )
        self.assertEqual(consumed, [0, 1, 2])

    def test_external_claim_limit_requires_a_bounded_positive_integer(self) -> None:
        ceiling = HypothesisWorkLimits().max_external_claims
        for malformed in (True, 1.0, "1"):
            with self.subTest(malformed=malformed):
                with self.assertRaisesRegex(ValidationError, "must be an integer"):
                    HypothesisWorkLimits(max_external_claims=malformed)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValidationError, "must be positive"):
            HypothesisWorkLimits(max_external_claims=0)
        with self.assertRaisesRegex(ValidationError, "safety ceiling"):
            HypothesisWorkLimits(max_external_claims=ceiling + 1)

    def test_external_claims_reject_malformed_containers_and_non_exact_items(self) -> None:
        manifest = fixture_manifest()
        builder = HypothesisBuilder()
        for malformed in ("claim", b"claim", bytearray(b"claim"), {"claim": "value"}):
            with self.subTest(malformed=type(malformed).__name__):
                with self.assertRaisesRegex(ValidationError, "must be an iterable"):
                    builder.build(
                        manifest,
                        "run-malformed-external-container",
                        external_claims=malformed,  # type: ignore[arg-type]
                    )
        with self.assertRaisesRegex(ValidationError, "exact EvidenceClaim"):
            builder.build(
                manifest,
                "run-non-exact-external-item",
                external_claims=(object(),),  # type: ignore[arg-type]
            )

        edge_id = (
            builder.build(
                manifest,
                "run-derived-external-edge",
            )
            .hypotheses[0]
            .edges[0]
            .edge_id
        )
        claim = external_claim(edge_id, "derived")

        class DerivedEvidenceClaim(EvidenceClaim):
            pass

        derived = DerivedEvidenceClaim(
            evidence_id=claim.evidence_id,
            edge_id=claim.edge_id,
            source_id=claim.source_id,
            channel=claim.channel,
            state=claim.state,
            tier=claim.tier,
            score=claim.score,
            confidence=claim.confidence,
            context=claim.context,
            summary=claim.summary,
            payload=claim.payload,
            depends_on=claim.depends_on,
            produced_by=claim.produced_by,
            created_at=claim.created_at,
            supersedes=claim.supersedes,
        )
        with self.assertRaisesRegex(ValidationError, "exact EvidenceClaim"):
            builder.build(
                manifest,
                "run-derived-external-item",
                external_claims=(derived,),
            )

    def test_external_claims_reject_noncanonical_and_duplicate_claim_ids(self) -> None:
        manifest = fixture_manifest()
        edge_id = (
            HypothesisBuilder()
            .build(
                manifest,
                "run-validation-edge",
            )
            .hypotheses[0]
            .edges[0]
            .edge_id
        )
        claim = external_claim(edge_id, "validation")
        invalid = replace(claim, created_at="not-a-utc-timestamp")
        with self.assertRaisesRegex(ValidationError, "ISO-8601 UTC"):
            HypothesisBuilder().build(
                manifest,
                "run-noncanonical-external",
                external_claims=(invalid,),
            )
        with self.assertRaisesRegex(ValidationError, "duplicate evidence ID"):
            HypothesisBuilder().build(
                manifest,
                "run-duplicate-external",
                external_claims=(claim, claim),
            )

    def test_external_claims_reject_context_mismatch_and_unknown_edges(self) -> None:
        manifest = fixture_manifest()
        edge_id = (
            HypothesisBuilder()
            .build(
                manifest,
                "run-context-edge",
            )
            .hypotheses[0]
            .edges[0]
            .edge_id
        )
        mismatched = external_claim(
            edge_id,
            "wrong-context",
            context=replace(manifest.context, cell_state="different-cell-state"),
        )
        with self.assertRaisesRegex(ValidationError, "context does not match"):
            HypothesisBuilder().build(
                manifest,
                "run-context-mismatch",
                external_claims=(mismatched,),
            )

        unknown_edge = HypothesisBuilder._edge_id(  # noqa: SLF001 - seam contract
            "unknown-variant",
            "unknown-element",
            EdgeType.VARIANT_TO_ELEMENT,
        )
        with self.assertRaisesRegex(ValidationError, "unknown or ineligible edge"):
            HypothesisBuilder().build(
                manifest,
                "run-unknown-external-edge",
                external_claims=(external_claim(unknown_edge, "unknown-edge"),),
            )

    def test_external_claim_consumption_is_a_checked_postcondition(self) -> None:
        manifest = fixture_manifest()
        builder = HypothesisBuilder()
        edge_id = (
            builder.build(
                manifest,
                "run-consumption-edge",
            )
            .hypotheses[0]
            .edges[0]
            .edge_id
        )
        claim = external_claim(edge_id, "unconsumed")

        with patch.object(builder, "_consume_external_edge", return_value=None):
            with self.assertRaisesRegex(ValidationError, "were not consumed"):
                builder.build(
                    manifest,
                    "run-unconsumed-external",
                    external_claims=(claim,),
                )


if __name__ == "__main__":
    unittest.main()
