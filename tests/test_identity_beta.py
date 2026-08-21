from __future__ import annotations

import unittest

from glio_noncode.identity_beta import (
    BatchSampleIdentityChecker,
    ChainOfCustodyCapture,
    CustodyEvent,
    CustodyEventKind,
    DuplicateAliasReconciler,
    IdentityBetaState,
    SampleIdentityObservation,
    VariantEquivalenceResolver,
    VariantIdentityRecord,
)
from glio_noncode.models import VariantIdentity, VariantKind, VariantOrigin


class IdentityBetaTests(unittest.TestCase):
    def _variant(
        self,
        variant_id: str,
        *,
        chromosome: str = "7",
        alternate: str = "t",
    ) -> VariantIdentity:
        return VariantIdentity(
            variant_id=variant_id,
            kind=VariantKind.SNV,
            chromosome=chromosome,
            start=100,
            end=100,
            reference="a",
            alternate=alternate,
            genome_build="GRCh38",
            origin=VariantOrigin.SOMATIC,
        )

    def _record(
        self,
        record_id: str,
        variant_id: str,
        *,
        chromosome: str = "7",
        alternate: str = "t",
        aliases: tuple[str, ...] = (),
        source_id: str = "source-1",
    ) -> VariantIdentityRecord:
        return VariantIdentityRecord(
            record_id=record_id,
            variant=self._variant(variant_id, chromosome=chromosome, alternate=alternate),
            source_id=source_id,
            source_version="v1",
            raw_hash=f"sha256:{record_id}",
            aliases=aliases,
        )

    def test_equivalence_resolver_groups_normalized_contig_and_alias(self) -> None:
        records = (
            self._record("r1", "source-id-1", aliases=("legacy-1",)),
            self._record(
                "r2",
                "source-id-2",
                chromosome="chr7",
                alternate="T",
                source_id="source-2",
            ),
        )
        result = VariantEquivalenceResolver().resolve(records, "legacy-1")
        self.assertEqual(result.state, IdentityBetaState.SUPPORTED)
        self.assertEqual(result.record_ids, ("r1",))
        self.assertEqual(result.methods, ("explicit_alias",))

        canonical = VariantEquivalenceResolver().resolve(records, records[0].equivalence_key)
        self.assertEqual(canonical.record_ids, ("r1", "r2"))
        self.assertEqual(canonical.state, IdentityBetaState.SUPPORTED)

    def test_alias_reconciliation_retains_duplicates_and_alias_collisions(self) -> None:
        result = DuplicateAliasReconciler().reconcile(
            (
                self._record("r1", "v1", aliases=("shared",)),
                self._record("r1-dup", "v1-copy", aliases=("shared",), source_id="source-2"),
                self._record("r2", "v2", alternate="g", aliases=("shared",)),
                self._record("r3", "v3", alternate="c", source_id="source-3"),
            )
        )
        self.assertEqual(result.state, IdentityBetaState.AMBIGUOUS)
        self.assertEqual(result.duplicate_record_ids, ("r1", "r1-dup"))
        self.assertIn("shared", result.ambiguous_aliases)
        self.assertGreaterEqual(len(result.groups), 4)

    def test_batch_sample_checker_detects_missing_and_cross_subject_identity(self) -> None:
        result = BatchSampleIdentityChecker().check(
            (
                SampleIdentityObservation(
                    "o1", "batch-1", "sample-1", "subject-1", "src", "v1", "h1"
                ),
                SampleIdentityObservation(
                    "o2", "batch-1", "sample-1", "subject-2", "src", "v1", "h2"
                ),
                SampleIdentityObservation("o3", None, "sample-2", None, "src", "v1", "h3"),
            ),
            require_subject=True,
        )
        self.assertEqual(result.state, IdentityBetaState.CONTRADICTORY)
        self.assertIn("o3", result.missing_observation_ids)
        self.assertTrue(
            any(issue.code == "sample_maps_to_multiple_subjects" for issue in result.issues)
        )

    def test_chain_of_custody_preserves_hash_continuity_and_flags_gaps(self) -> None:
        good = ChainOfCustodyCapture().capture(
            (
                CustodyEvent(
                    "e1",
                    "artifact-1",
                    CustodyEventKind.RECEIVED,
                    "operator-1",
                    "2026-08-21T00:00:00+00:00",
                    (),
                    ("sha256:raw",),
                    "source-1",
                ),
                CustodyEvent(
                    "e2",
                    "artifact-1",
                    CustodyEventKind.TRANSFORMED,
                    "pipeline-1",
                    "2026-08-21T00:01:00+00:00",
                    ("sha256:raw",),
                    ("sha256:normalized",),
                    "source-1",
                    previous_event_id="e1",
                ),
            )
        )
        self.assertEqual(good.state, IdentityBetaState.SUPPORTED)
        self.assertEqual(good.chains[0].event_ids, ("e1", "e2"))

        broken = ChainOfCustodyCapture().capture(
            (
                CustodyEvent(
                    "e3",
                    "artifact-2",
                    CustodyEventKind.RECEIVED,
                    "operator-1",
                    "2026-08-21T00:00:00+00:00",
                    (),
                    ("sha256:raw-2",),
                    "source-1",
                ),
                CustodyEvent(
                    "e4",
                    "artifact-2",
                    CustodyEventKind.VALIDATED,
                    "reviewer-1",
                    "2026-08-21T00:01:00+00:00",
                    ("sha256:wrong",),
                    ("sha256:validated",),
                    "source-1",
                    previous_event_id="missing",
                ),
            )
        )
        self.assertEqual(broken.state, IdentityBetaState.CONTRADICTORY)
        self.assertTrue(any(issue.code == "hash_continuity_gap" for issue in broken.issues))
        self.assertTrue(any(issue.code == "missing_previous_event" for issue in broken.issues))


if __name__ == "__main__":
    unittest.main()
