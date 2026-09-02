from __future__ import annotations

import math
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from typing import Any, cast
from unittest.mock import patch

from glio_noncode.errors import ValidationError
from glio_noncode.evidence import (
    MAX_EVIDENCE_CLAIM_BYTES,
    MAX_EVIDENCE_CLAIMS,
    MAX_EVIDENCE_CLAIMS_PER_EDGE,
    MAX_EVIDENCE_DEPENDENCIES_PER_CLAIM,
    MAX_EVIDENCE_GRAPH_BYTES,
    AggregateSupport,
    EvidenceGraph,
    EvidenceGraphLimits,
)
from glio_noncode.models import (
    EdgeType,
    EvidenceClaim,
    EvidenceState,
    EvidenceTier,
    HypothesisEdge,
    ReferenceContext,
    SupportLevel,
)
from glio_noncode.serialization import canonical_bytes

CREATED_AT = "2026-09-02T12:00:00+00:00"
CONTEXT = ReferenceContext(
    genome_build="GRCh38",
    disease_class="diffuse_glioma",
    age_group="adult",
    cell_state="stem_like",
    territory="infiltrating_edge",
    treatment_phase="pre_treatment",
)


def evidence_claim(
    evidence_id: str,
    *,
    edge_id: str = "edge-1",
    channel: str = "accessibility",
    state: EvidenceState = EvidenceState.SUPPORTED,
    tier: EvidenceTier = EvidenceTier.COMPUTED,
    score: float | None = 0.8,
    confidence: float = 0.9,
    context: ReferenceContext = CONTEXT,
    payload: object | None = None,
    depends_on: tuple[str, ...] = (),
    supersedes: str | None = None,
) -> EvidenceClaim:
    return EvidenceClaim(
        evidence_id=evidence_id,
        edge_id=edge_id,
        source_id=f"source-{evidence_id}",
        channel=channel,
        state=state,
        tier=tier,
        score=score,
        confidence=confidence,
        context=context,
        summary=f"claim {evidence_id}",
        payload={} if payload is None else cast(dict[str, object], payload),
        depends_on=depends_on,
        produced_by="test-evidence",
        created_at=CREATED_AT,
        supersedes=supersedes,
    )


def hypothesis_edge(
    *claim_ids: str,
    edge_id: str = "edge-1",
    edge_type: EdgeType = EdgeType.VARIANT_TO_ELEMENT,
    source_id: str = "variant-1",
    target_id: str = "element-1",
) -> HypothesisEdge:
    return HypothesisEdge(
        edge_id=edge_id,
        edge_type=edge_type,
        source_id=source_id,
        target_id=target_id,
        support=0.0,
        uncertainty=1.0,
        context_fit=1.0,
        claim_ids=claim_ids,
        support_level=SupportLevel.UNKNOWN,
    )


class EvidenceGraphLimitTests(unittest.TestCase):
    def test_limit_configuration_is_exact_positive_and_below_hard_ceilings(self) -> None:
        ceilings = {
            "max_claims": MAX_EVIDENCE_CLAIMS,
            "max_claims_per_edge": MAX_EVIDENCE_CLAIMS_PER_EDGE,
            "max_dependencies_per_claim": MAX_EVIDENCE_DEPENDENCIES_PER_CLAIM,
            "max_claim_bytes": MAX_EVIDENCE_CLAIM_BYTES,
            "max_graph_bytes": MAX_EVIDENCE_GRAPH_BYTES,
        }
        for field_name, ceiling in ceilings.items():
            for malformed in (True, 1.0, "1"):
                with self.subTest(field_name=field_name, malformed=malformed):
                    with self.assertRaisesRegex(ValidationError, "must be an integer"):
                        EvidenceGraphLimits(**{field_name: malformed})  # type: ignore[arg-type]
            with self.subTest(field_name=field_name, malformed=0):
                with self.assertRaisesRegex(ValidationError, "must be positive"):
                    EvidenceGraphLimits(**{field_name: 0})
            with self.subTest(field_name=field_name, malformed=ceiling + 1):
                with self.assertRaisesRegex(ValidationError, "safety ceiling"):
                    EvidenceGraphLimits(**{field_name: ceiling + 1})

        with self.assertRaisesRegex(ValidationError, "limits must be EvidenceGraphLimits"):
            EvidenceGraph(limits=cast(EvidenceGraphLimits, {}))

    def test_extend_consumes_only_one_over_limit_sentinel_and_is_atomic(self) -> None:
        graph = EvidenceGraph(limits=EvidenceGraphLimits(max_claims=2))
        consumed: list[int] = []

        def claims():
            for index in range(10):
                consumed.append(index)
                yield evidence_claim(f"claim-{index}")

        with self.assertRaisesRegex(ValidationError, "maximum of 2 claims"):
            graph.extend(claims())

        self.assertEqual(consumed, [0, 1, 2])
        self.assertEqual(graph.all_claims(), ())

    def test_per_edge_dependency_and_byte_limits_fail_without_partial_mutation(self) -> None:
        edge_limited = EvidenceGraph(
            limits=EvidenceGraphLimits(max_claims=3, max_claims_per_edge=1)
        )
        first = evidence_claim("first")
        edge_limited.append(first)
        with self.assertRaisesRegex(ValidationError, "edge edge-1.*maximum of 1"):
            edge_limited.extend((evidence_claim("second"),))
        self.assertEqual(edge_limited.all_claims(), (first,))

        external = "source:" + "a" * 64
        dependency_limited = EvidenceGraph(
            limits=EvidenceGraphLimits(max_dependencies_per_claim=1)
        )
        with self.assertRaisesRegex(ValidationError, "dependencies.*maximum of 1"):
            dependency_limited.append(
                evidence_claim("many-dependencies", depends_on=(external, external[:-1] + "b"))
            )
        self.assertEqual(dependency_limited.all_claims(), ())

        oversized = evidence_claim("oversized", payload={"value": "large-payload"})
        size = len(canonical_bytes(oversized.to_dict()))
        claim_limited = EvidenceGraph(
            limits=EvidenceGraphLimits(max_claim_bytes=size - 1)
        )
        with self.assertRaisesRegex(ValidationError, "maximum canonical size"):
            claim_limited.append(oversized)
        self.assertEqual(claim_limited.all_claims(), ())

        graph_limited = EvidenceGraph(
            limits=EvidenceGraphLimits(max_claim_bytes=size, max_graph_bytes=size)
        )
        graph_limited.append(oversized)
        before = graph_limited.all_claims()
        with self.assertRaisesRegex(ValidationError, "graph.*maximum canonical size"):
            graph_limited.append(
                evidence_claim("oversize2", payload={"value": "large-payload"})
            )
        self.assertEqual(graph_limited.all_claims(), before)


class EvidenceGraphValidationTests(unittest.TestCase):
    def test_append_rejects_non_claims_and_invalid_direct_runtime_types(self) -> None:
        valid = evidence_claim("valid")
        invalid = (
            object(),
            replace(valid, evidence_id="bad-state", state=cast(EvidenceState, "supported")),
            replace(valid, evidence_id="bad-tier", tier=cast(EvidenceTier, "computed")),
            replace(valid, evidence_id="bad-score", score=cast(float, True)),
            replace(valid, evidence_id="bad-confidence", confidence=cast(float, True)),
            replace(
                valid,
                evidence_id="bad-context",
                context=cast(ReferenceContext, object()),
            ),
        )
        for value in invalid:
            with self.subTest(value=type(value).__name__):
                graph = EvidenceGraph()
                with self.assertRaises(ValidationError):
                    graph.append(cast(EvidenceClaim, value))
                self.assertEqual(graph.all_claims(), ())

    def test_retained_alias_mutation_is_detected_before_read_or_aggregation(self) -> None:
        claim = evidence_claim("mutable")
        graph = EvidenceGraph()
        graph.append(claim)
        object.__setattr__(claim, "confidence", math.nan)

        with self.assertRaisesRegex(ValidationError, "finite"):
            graph.get("mutable")
        with self.assertRaisesRegex(ValidationError, "finite"):
            graph.aggregate(hypothesis_edge("mutable"))
        with self.assertRaisesRegex(ValidationError, "finite"):
            graph.all_claims()

    def test_payload_input_and_aggregate_exports_do_not_alias_mutable_values(self) -> None:
        source: dict[str, Any] = {"rows": [{"score": 0.8}], "labels": ["a"]}
        claim = evidence_claim("immutable", payload=source)
        graph = EvidenceGraph()
        graph.append(claim)
        before = claim.to_dict()

        source["rows"][0]["score"] = 0.0
        source["labels"].append("changed")
        self.assertEqual(claim.to_dict(), before)

        aggregate = graph.aggregate(hypothesis_edge("immutable"))
        exported = aggregate.to_dict()
        cast(list[str], exported["supported_claim_ids"]).append("forged")
        self.assertEqual(aggregate.supported_claim_ids, ("immutable",))

    def test_aggregate_support_validates_metrics_order_and_disjoint_classes(self) -> None:
        valid = {
            "score": 0.5,
            "uncertainty": 0.5,
            "context_support": 0.5,
            "supported_claim_ids": ("a",),
            "negative_claim_ids": ("b",),
            "missing_claim_ids": ("c",),
            "channel_groups": ("chromatin",),
            "rationale": "bounded aggregate",
        }
        for changes in (
            {"score": math.nan},
            {"uncertainty": math.inf},
            {"context_support": -0.1},
            {"supported_claim_ids": cast(tuple[str, ...], ["a"])},
            {"supported_claim_ids": ("z", "a")},
            {"negative_claim_ids": ("a",)},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(ValidationError):
                    AggregateSupport(**(valid | changes))  # type: ignore[arg-type]

    def test_get_and_for_edge_validate_identifier_types_but_keep_missing_key_error(self) -> None:
        graph = EvidenceGraph()
        with self.assertRaises(ValidationError):
            graph.get(cast(str, 1))
        with self.assertRaises(ValidationError):
            graph.for_edge(cast(str, True))
        with self.assertRaises(KeyError):
            graph.get("missing")
        self.assertEqual(graph.for_edge("missing"), ())


class EvidenceGraphClosureTests(unittest.TestCase):
    def test_plain_forward_dependencies_are_rejected_but_external_addresses_are_allowed(
        self,
    ) -> None:
        graph = EvidenceGraph()
        with self.assertRaisesRegex(ValidationError, "canonical content address"):
            graph.append(evidence_claim("dangling", depends_on=("missing-claim",)))
        self.assertEqual(graph.all_claims(), ())

        with self.assertRaisesRegex(ValidationError, "canonical content address"):
            graph.extend(
                (
                    evidence_claim("dependent", depends_on=("future",)),
                    evidence_claim("future"),
                )
            )
        self.assertEqual(graph.all_claims(), ())

        external = "source:" + "b" * 64
        externally_derived = evidence_claim("external", depends_on=(external,))
        graph.append(externally_derived)
        self.assertEqual(graph.get("external"), externally_derived)
        with self.assertRaisesRegex(ValidationError, "collides.*external dependency"):
            graph.append(evidence_claim(external))
        self.assertEqual(graph.all_claims(), (externally_derived,))

    def test_duplicate_and_colliding_batch_identities_are_atomic(self) -> None:
        claim = evidence_claim("same-id")
        graph = EvidenceGraph()
        with self.assertRaisesRegex(ValidationError, "duplicate evidence ID"):
            graph.extend((claim, claim))
        self.assertEqual(graph.all_claims(), ())

        graph.append(claim)
        before = graph.all_claims()
        with self.assertRaisesRegex(ValidationError, "collision has different content"):
            graph.extend((evidence_claim("new"), replace(claim, summary="changed")))
        self.assertEqual(graph.all_claims(), before)

    def test_extend_detects_claim_mutation_by_its_producer_before_commit(self) -> None:
        first = evidence_claim("first")

        def mutating_producer():
            yield first
            object.__setattr__(first, "summary", "changed after yield")
            yield evidence_claim("second")

        graph = EvidenceGraph()
        with self.assertRaisesRegex(ValidationError, "mutated during extension"):
            graph.extend(mutating_producer())
        self.assertEqual(graph.all_claims(), ())

    def test_supersession_requires_an_earlier_claim_on_the_same_edge(self) -> None:
        graph = EvidenceGraph()
        original = evidence_claim("original", edge_id="edge-original")
        graph.append(original)
        with self.assertRaisesRegex(ValidationError, "another edge"):
            graph.append(
                evidence_claim(
                    "replacement",
                    edge_id="edge-other",
                    supersedes=original.evidence_id,
                )
            )
        with self.assertRaisesRegex(ValidationError, "not present"):
            graph.append(evidence_claim("missing", supersedes="unknown"))
        self.assertEqual(graph.all_claims(), (original,))

    def test_all_claims_is_canonical_while_preserving_dependency_order(self) -> None:
        root = evidence_claim("z-root")
        dependent = evidence_claim("a-dependent", depends_on=(root.evidence_id,))
        independent = evidence_claim("m-independent")
        graph = EvidenceGraph()
        graph.extend((root, dependent, independent))

        self.assertEqual(
            tuple(claim.evidence_id for claim in graph.all_claims()),
            ("m-independent", "z-root", "a-dependent"),
        )

    def test_graph_rejects_mixed_case_contexts_atomically(self) -> None:
        graph = EvidenceGraph()
        first = evidence_claim("first-context")
        graph.append(first)
        source_specific_context = replace(
            CONTEXT,
            assay_support=("ATAC-seq",),
            source_version="2026-09",
        )
        graph.append(
            evidence_claim("source-context", context=source_specific_context)
        )
        other_context = replace(CONTEXT, age_group="pediatric")
        with self.assertRaisesRegex(ValidationError, "share the graph context"):
            graph.append(evidence_claim("other-context", context=other_context))
        self.assertEqual(
            tuple(claim.evidence_id for claim in graph.all_claims()),
            ("first-context", "source-context"),
        )

    def test_graph_requires_a_canonical_claim_timestamp(self) -> None:
        claim = replace(evidence_claim("invalid-time"), created_at="not-a-timestamp")

        with self.assertRaisesRegex(ValidationError, "UTC timestamp"):
            EvidenceGraph().append(claim)


class EvidenceGraphAggregationTests(unittest.TestCase):
    def test_declared_claims_are_reported_missing_or_must_belong_to_the_edge(self) -> None:
        graph = EvidenceGraph()
        actual = evidence_claim("actual")
        foreign = evidence_claim("foreign", edge_id="edge-foreign")
        graph.extend((actual, foreign))

        unresolved = graph.aggregate(hypothesis_edge("declared"))
        self.assertEqual(unresolved.supported_claim_ids, ("actual",))
        self.assertEqual(unresolved.missing_claim_ids, ("declared",))
        with self.assertRaisesRegex(ValidationError, "bound to edge-foreign"):
            graph.aggregate(hypothesis_edge("foreign"))

        empty = EvidenceGraph()
        empty_result = empty.aggregate(hypothesis_edge("declared-a", "declared-b"))
        self.assertEqual(empty_result.score, 0.0)
        self.assertEqual(empty_result.uncertainty, 1.0)
        self.assertEqual(
            empty_result.missing_claim_ids,
            ("declared-a", "declared-b"),
        )

    def test_declared_claims_are_a_floor_and_same_edge_extras_remain_included(self) -> None:
        graph = EvidenceGraph()
        declared = evidence_claim("declared", channel="motif_delta")
        staged_extra = evidence_claim("staged-extra", channel="accessibility")
        graph.extend((declared, staged_extra))

        aggregate = graph.aggregate(hypothesis_edge("declared"))

        self.assertEqual(
            aggregate.supported_claim_ids,
            ("declared", "staged-extra"),
        )
        self.assertEqual(aggregate.channel_groups, ("chromatin", "sequence"))

    def test_edge_id_reuse_requires_one_structural_typed_identity(self) -> None:
        graph = EvidenceGraph()
        graph.append(evidence_claim("claim"))
        edge = hypothesis_edge("claim")
        graph.aggregate(edge)
        with self.assertRaisesRegex(ValidationError, "edge ID collision"):
            graph.aggregate(replace(edge, target_id="different-target"))

    def test_superseded_history_is_retained_but_only_active_heads_are_aggregated(self) -> None:
        old = evidence_claim(
            "old",
            channel="motif_delta",
            score=1.0,
            confidence=1.0,
        )
        replacement = evidence_claim(
            "replacement",
            channel="motif_delta",
            state=EvidenceState.MEASURED_NEGATIVE,
            tier=EvidenceTier.REVIEWED,
            score=1.0,
            confidence=1.0,
            supersedes=old.evidence_id,
        )
        graph = EvidenceGraph()
        graph.extend((old, replacement))

        aggregate = graph.aggregate(hypothesis_edge("old", "replacement"))

        self.assertEqual(aggregate.score, 0.0)
        self.assertEqual(aggregate.supported_claim_ids, ())
        self.assertEqual(aggregate.negative_claim_ids, ("replacement",))
        self.assertEqual(
            tuple(claim.evidence_id for claim in graph.for_edge("edge-1")),
            ("old", "replacement"),
        )
        self.assertEqual(
            tuple(claim.evidence_id for claim in graph.all_claims()),
            ("old", "replacement"),
        )

    def test_correlated_negative_claims_do_not_multiply_the_penalty(self) -> None:
        positive = evidence_claim(
            "positive",
            channel="motif_delta",
            score=1.0,
            confidence=1.0,
        )
        negatives = tuple(
            evidence_claim(
                f"negative-{index}",
                channel="accessibility" if index % 2 == 0 else "histone_activity",
                state=EvidenceState.MEASURED_NEGATIVE,
                tier=EvidenceTier.REVIEWED,
                score=1.0,
                confidence=1.0,
            )
            for index in range(3)
        )
        one = EvidenceGraph()
        one.extend((positive, negatives[0]))
        many = EvidenceGraph()
        many.extend((positive, *negatives))

        one_result = one.aggregate(hypothesis_edge("positive", negatives[0].evidence_id))
        many_result = many.aggregate(
            hypothesis_edge("positive", *(claim.evidence_id for claim in negatives))
        )

        self.assertEqual(many_result.score, one_result.score)

    def test_abstentions_do_not_create_false_context_support(self) -> None:
        abstentions = tuple(
            evidence_claim(
                f"abstained-{index}",
                channel=f"attempted-channel-{index}",
                state=EvidenceState.ABSTAINED,
                score=None,
                confidence=1.0,
            )
            for index in range(3)
        )
        graph = EvidenceGraph()
        graph.extend(abstentions)

        aggregate = graph.aggregate(
            hypothesis_edge(*(claim.evidence_id for claim in abstentions))
        )

        self.assertEqual(aggregate.score, 0.0)
        self.assertEqual(aggregate.context_support, 0.0)
        self.assertEqual(aggregate.uncertainty, 1.0)
        self.assertEqual(
            aggregate.channel_groups,
            tuple(f"attempted-channel-{index}" for index in range(3)),
        )

    def test_equivalent_orders_are_canonical_finite_and_idempotent(self) -> None:
        claims = (
            evidence_claim("z-supported", channel="motif_delta"),
            evidence_claim(
                "a-negative",
                channel="contact",
                state=EvidenceState.CONTRADICTORY,
                score=0.2,
            ),
            evidence_claim(
                "m-missing",
                channel="accessibility",
                state=EvidenceState.ABSTAINED,
                score=None,
                confidence=0.1,
            ),
        )
        first = EvidenceGraph()
        first.extend(claims)
        second = EvidenceGraph()
        second.extend(reversed(claims))
        edge = hypothesis_edge(*(claim.evidence_id for claim in claims))
        reversed_edge = hypothesis_edge(*(claim.evidence_id for claim in reversed(claims)))

        first_result = first.aggregate(edge)
        second_result = second.aggregate(reversed_edge)

        self.assertEqual(first_result, first.aggregate(edge))
        self.assertEqual(first_result.to_dict(), second_result.to_dict())
        self.assertEqual(first.all_claims(), second.all_claims())
        self.assertEqual(first.for_edge("edge-1"), second.for_edge("edge-1"))
        self.assertTrue(math.isfinite(first_result.score))
        self.assertTrue(math.isfinite(first_result.uncertainty))
        self.assertTrue(math.isfinite(first_result.context_support))

    def test_unique_channel_aggregation_performs_linear_grouping_work(self) -> None:
        claims = tuple(
            evidence_claim(f"claim-{index:03}", channel=f"unique-{index:03}")
            for index in range(64)
        )
        graph = EvidenceGraph()
        graph.extend(reversed(claims))
        edge = hypothesis_edge(*(claim.evidence_id for claim in claims))
        original = EvidenceGraph._channel_group

        with patch.object(EvidenceGraph, "_channel_group", side_effect=original) as grouped:
            aggregate = graph.aggregate(edge)

        self.assertEqual(grouped.call_count, len(claims))
        self.assertEqual(len(aggregate.channel_groups), len(claims))

    def test_numeric_helpers_reject_nonfinite_overflow_and_malformed_inputs(self) -> None:
        for values in (
            [math.nan],
            [math.inf],
            [cast(float, True)],
            [cast(float, 10**400)],
        ):
            with self.subTest(values=values):
                with self.assertRaises(ValidationError):
                    EvidenceGraph._dependence_adjusted_mean(values)
        with self.assertRaisesRegex(ValidationError, "list or tuple"):
            EvidenceGraph._dependence_adjusted_mean(cast(list[float], iter((0.5,))))

    def test_concurrent_appends_remain_complete_and_canonical(self) -> None:
        graph = EvidenceGraph()

        def append(index: int) -> None:
            graph.append(evidence_claim(f"claim-{index:03}"))

        with ThreadPoolExecutor(max_workers=8) as pool:
            tuple(pool.map(append, range(64)))

        self.assertEqual(
            tuple(claim.evidence_id for claim in graph.all_claims()),
            tuple(f"claim-{index:03}" for index in range(64)),
        )


if __name__ == "__main__":
    unittest.main()
