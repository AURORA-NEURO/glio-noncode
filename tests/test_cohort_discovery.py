from __future__ import annotations

import unittest

from glio_noncode.cohort_discovery import (
    CallableInterval,
    ChromatinContextControlMatcher,
    CohortDiscoveryEvidenceBuilder,
    CohortQuery,
    CohortQueryBuilder,
    CohortState,
    CohortVariantRecord,
    LocalBackgroundMutationModel,
    SequenceContextControlMatcher,
)
from glio_noncode.models import ReferenceContext, VariantIdentity, VariantKind, VariantOrigin


class CohortDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = ReferenceContext(
            "GRCh38", "glioma", "adult", "stem_like", territory="core"
        )
        self.other_context = ReferenceContext(
            "GRCh38", "glioma", "pediatric", "stem_like", territory="core"
        )

    def _record(
        self,
        record_id: str,
        position: int,
        *,
        context: ReferenceContext | None = None,
        callable: bool = True,
        sequence: str | None = None,
        chromatin: dict[str, float] | None = None,
        origin: VariantOrigin = VariantOrigin.SOMATIC,
    ) -> CohortVariantRecord:
        return CohortVariantRecord(
            record_id=record_id,
            variant=VariantIdentity(
                record_id,
                VariantKind.SNV,
                "chr7",
                position,
                position,
                "A",
                "T",
                "GRCh38",
                origin=origin,
            ),
            context_key=(context or self.context).key,
            source_id="cohort-1",
            sample_id=f"sample-{record_id}",
            callable=callable,
            sequence_context=sequence,
            chromatin_features=chromatin or {},
        )

    def test_query_builder_preserves_exclusion_reasons_and_context(self) -> None:
        records = (
            self._record("r1", 100),
            self._record("r2", 200, callable=False),
            self._record("r3", 300, context=self.other_context),
        )
        query = CohortQuery(
            "q1", self.context.key, variant_kinds=("snv",), origins=("somatic",)
        )
        result = CohortQueryBuilder().build(query, records)
        self.assertEqual(result.state, CohortState.PARTIAL)
        self.assertEqual(result.variant_ids, ("r1",))
        self.assertEqual(result.excluded_reasons, {"not_callable": 1})
        self.assertEqual(result.excluded_count, 1)

        out_of_domain = CohortQueryBuilder().build(
            CohortQuery("q2", self.other_context.key), (self._record("r4", 400),)
        )
        self.assertEqual(out_of_domain.state, CohortState.OUT_OF_DOMAIN)

    def test_local_background_model_uses_callable_space_and_no_p_value(self) -> None:
        intervals = (
            CallableInterval("i1", "7", 1, 1000, 1000, self.context.key, "callable", "v1", "h1"),
            CallableInterval(
                "i2", "7", 1, 1000, 1000, self.other_context.key, "callable", "v1", "h2"
            ),
        )
        estimate = LocalBackgroundMutationModel().estimate(
            self.context,
            (self._record("r1", 100), self._record("r2", 200)),
            intervals,
            target_callable_bases=500,
        )
        self.assertEqual(estimate.state, CohortState.SUPPORTED)
        self.assertEqual(estimate.observed_count, 2)
        self.assertEqual(estimate.callable_bases, 1000)
        self.assertEqual(estimate.background_rate, 0.002)
        self.assertEqual(estimate.expected_count, 1.0)
        self.assertFalse(any("p-value" in item for item in estimate.limitations))

    def test_sequence_controls_use_exact_context_and_hamming_cutoff(self) -> None:
        target = self._record("target", 100, sequence="ACGT")
        candidates = (
            self._record("same", 200, sequence="ACGT"),
            self._record("near", 300, sequence="ACGA"),
            self._record("far", 400, sequence="TTTT"),
            self._record("wrong", 500, context=self.other_context, sequence="ACGT"),
        )
        result = SequenceContextControlMatcher().match(
            target, candidates, self.context, max_controls=2, max_distance=0.25
        )
        self.assertEqual(result.state, CohortState.SUPPORTED)
        self.assertEqual([item.candidate_id for item in result.controls], ["same", "near"])
        self.assertEqual(result.controls[1].distance, 0.25)

        wrong = SequenceContextControlMatcher().match(
            target, (candidates[-1],), self.context, max_controls=1, max_distance=0.0
        )
        self.assertEqual(wrong.state, CohortState.OUT_OF_DOMAIN)

    def test_chromatin_controls_use_declared_feature_ranges(self) -> None:
        target = self._record(
            "target", 100, chromatin={"accessibility": 0.5, "h3k27ac": 0.7}
        )
        candidates = (
            self._record("same", 200, chromatin={"accessibility": 0.5, "h3k27ac": 0.7}),
            self._record("near", 300, chromatin={"accessibility": 0.55, "h3k27ac": 0.75}),
            self._record("missing", 400, chromatin={"accessibility": 0.5}),
        )
        result = ChromatinContextControlMatcher().match(
            target,
            candidates,
            self.context,
            feature_ranges={"accessibility": (0.0, 1.0), "h3k27ac": (0.0, 1.0)},
            max_controls=2,
            max_distance=0.1,
        )
        self.assertEqual(result.state, CohortState.SUPPORTED)
        self.assertEqual([item.candidate_id for item in result.controls], ["same", "near"])

    def test_discovery_evidence_propagates_partial_control_state(self) -> None:
        query = CohortQueryBuilder().build(
            CohortQuery("q1", self.context.key), (self._record("r1", 100),)
        )
        target = self._record("target", 200, sequence="ACGT")
        controls = SequenceContextControlMatcher().match(
            target, (), self.context, max_controls=1, max_distance=0.0
        )
        evidence = CohortDiscoveryEvidenceBuilder().build(
            "cohort-e1", query, sequence_controls=(controls,)
        )
        self.assertEqual(evidence.state, CohortState.ABSTAINED)
        self.assertEqual(evidence.context_key, self.context.key)
        self.assertTrue(evidence.content_address.startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()
