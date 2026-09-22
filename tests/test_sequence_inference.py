from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

import glio_noncode
from glio_noncode.data_sources import FetchReceipt, FetchStatus, SequenceSlice
from glio_noncode.errors import ValidationError
from glio_noncode.identity import parse_variant
from glio_noncode.models import ReferenceContext
from glio_noncode.sequence_inference import (
    HaplotypeMotifChange,
    MotifDefinition,
    MotifScanner,
    PhasedVariantIdentity,
    SequenceAnalysisState,
    SequenceInference,
)
from glio_noncode.serialization import content_hash


def _sequence(sequence: str = "AACCGGTTAACC", *, assembly: str = "GRCh38") -> SequenceSlice:
    receipt = FetchReceipt(
        source_id="SRC-UCSC-REST",
        source_version="fixture-1",
        url="https://api.example/sequence",
        request_hash=content_hash({"request": "sequence-fixture"}),
        response_hash=content_hash({"response": sequence}),
        status=FetchStatus.FETCHED,
        http_status=200,
        attempts=1,
        retrieved_at="2026-08-20T00:00:00+00:00",
        elapsed_seconds=0.01,
        cache_expires_at=None,
    )
    return SequenceSlice(
        assembly, "chr7", 100, 100 + len(sequence) - 1, sequence, "SRC-UCSC-REST", receipt
    )


def _phased(
    notation: str,
    variant_id: str,
    *,
    phase_set: str = "phase-1",
    haplotype_index: int = 1,
    sample_id: str = "sample-1",
) -> PhasedVariantIdentity:
    variant = parse_variant(notation, genome_build="GRCh38", variant_id=variant_id)
    return PhasedVariantIdentity(
        replace(variant, sample_id=sample_id),
        phase_set=phase_set,
        haplotype_index=haplotype_index,
    )


class SequenceInferenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = ReferenceContext("GRCh38", "glioma", "adult", "stem_like")

    def test_scanner_matches_iupac_on_both_strands(self) -> None:
        hits = MotifScanner().scan(
            "ACGTAC",
            genomic_start=100,
            motifs=(MotifDefinition("m1", "sequence-motif", "ACG"),),
        )
        self.assertTrue(any(hit.strand == "+" for hit in hits))
        self.assertTrue(all(hit.start >= 100 for hit in hits))

    def test_snv_disrupts_motif_without_creating_a_probability(self) -> None:
        variant = parse_variant("7:104:G>A", genome_build="GRCh38", variant_id="v1")
        result = SequenceInference().analyze(
            variant,
            _sequence(),
            motifs=(MotifDefinition("m-cgg", "CGG motif", "CGG"),),
        )
        self.assertEqual(result.state, SequenceAnalysisState.SUPPORTED)
        self.assertGreaterEqual(len(result.disrupted_hits), 1)
        self.assertIsNone(result.to_claim(context=self.context, edge_id="edge-1").score)

    def test_motif_generator_is_reused_for_reference_and_alternate_scans(self) -> None:
        variant = parse_variant("7:104:G>A", genome_build="GRCh38", variant_id="generator")
        motif = MotifDefinition("created", "created-on-alternate", "CCA")
        result = SequenceInference().analyze(
            variant,
            _sequence(),
            motifs=(candidate for candidate in (motif,)),
        )
        self.assertEqual(result.state, SequenceAnalysisState.SUPPORTED)
        self.assertEqual(tuple(hit.motif_id for hit in result.created_hits), ("created",))

    def test_reference_mismatch_abstains(self) -> None:
        variant = parse_variant("7:104:C>A", genome_build="GRCh38", variant_id="mismatch")
        result = SequenceInference().analyze(variant, _sequence())
        self.assertEqual(result.state, SequenceAnalysisState.REFERENCE_MISMATCH)
        self.assertEqual(result.alternate_sequence_hash, None)

    def test_genome_build_mismatch_abstains_before_allele_comparison(self) -> None:
        variant = parse_variant("7:104:G>A", genome_build="GRCh38", variant_id="build-check")
        result = SequenceInference().analyze(variant, _sequence(assembly="GRCh37"))
        self.assertEqual(result.state, SequenceAnalysisState.ABSTAINED)
        self.assertIn("genome builds do not match", result.limitations[0])

    def test_known_ucsc_assembly_alias_is_accepted(self) -> None:
        variant = parse_variant("7:104:G>A", genome_build="GRCh38", variant_id="build-alias")
        result = SequenceInference().analyze(variant, _sequence(assembly="hg38"))
        self.assertEqual(result.state, SequenceAnalysisState.SUPPORTED)

    def test_structural_allele_abstains_in_literal_sequence_engine(self) -> None:
        variant = parse_variant("7:104:BND:chr8:200", genome_build="GRCh38")
        result = SequenceInference().analyze(variant, _sequence())
        self.assertEqual(result.state, SequenceAnalysisState.ABSTAINED)
        self.assertIn("only literal SNV and indel", result.limitations[0])

    def test_length_changing_indel_abstains_until_haplotype_coordinates_are_mapped(self) -> None:
        variant = parse_variant("7:102:CC>C", genome_build="GRCh38")
        result = SequenceInference().analyze(variant, _sequence())
        self.assertEqual(result.state, SequenceAnalysisState.ABSTAINED)
        self.assertIn("alternate-haplotype coordinate mapping", result.limitations[0])

    def test_phased_snvs_jointly_create_motif_and_are_order_independent(self) -> None:
        first = _phased("7:103:C>T", "snv-1")
        second = _phased("7:104:G>A", "snv-2")
        motif = MotifDefinition("joint", "jointly-created motif", "CTAG")

        forward = SequenceInference().analyze_haplotype(
            (first, second), _sequence(), motifs=(motif,)
        )
        reverse = SequenceInference().analyze_haplotype(
            (second, first), _sequence(), motifs=(motif,)
        )

        self.assertEqual(forward.state, SequenceAnalysisState.SUPPORTED)
        self.assertEqual(forward.variant_ids, ("snv-1", "snv-2"))
        self.assertEqual(forward.content_address, reverse.content_address)
        self.assertEqual(len(forward.created_hits), 1)
        created = forward.created_hits[0]
        self.assertEqual(created.change, HaplotypeMotifChange.CREATED)
        self.assertEqual(created.matched_sequence, "CTAG")
        self.assertEqual(created.reference_interval, ("chr7", 102, 105))
        self.assertEqual(created.variant_ids, ("snv-1", "snv-2"))

    def test_insertion_maps_retained_anchor_and_unaffected_downstream_motifs(self) -> None:
        insertion = _phased("7:102:C>CT", "insert-t")
        motifs = (
            MotifDefinition("anchor", "unchanged anchor motif", "AAC"),
            MotifDefinition("junction", "insertion-spanning motif", "CTC"),
            MotifDefinition("downstream", "unchanged downstream motif", "TTAA"),
        )

        result = SequenceInference().analyze_haplotype((insertion,), _sequence(), motifs=motifs)

        self.assertEqual(result.state, SequenceAnalysisState.SUPPORTED)
        self.assertEqual(result.alternate_length_delta, 1)
        created = {hit.motif_id: hit for hit in result.created_hits}
        self.assertIn("junction", created)
        self.assertIsNone(created["junction"].reference_interval)
        self.assertIsNotNone(created["junction"].haplotype_interval)
        self.assertEqual(created["junction"].variant_ids, ("insert-t",))
        self.assertNotIn("anchor", created)
        self.assertNotIn("downstream", created)
        disrupted_ids = {hit.motif_id for hit in result.disrupted_hits}
        self.assertNotIn("anchor", disrupted_ids)
        self.assertNotIn("downstream", disrupted_ids)

    def test_indel_shared_suffix_keeps_unchanged_reference_coordinates(self) -> None:
        insertion = _phased("7:102:CC>TCC", "insert-before-shared-suffix")
        motif = MotifDefinition("suffix", "motif across retained suffix", "CCG")

        result = SequenceInference().analyze_haplotype((insertion,), _sequence(), motifs=(motif,))

        self.assertEqual(result.state, SequenceAnalysisState.SUPPORTED)
        self.assertNotIn("suffix", {hit.motif_id for hit in result.created_hits})
        self.assertNotIn("suffix", {hit.motif_id for hit in result.disrupted_hits})

    def test_deletion_maps_downstream_hits_and_attributes_junction_motifs(self) -> None:
        deletion = _phased("7:102:CC>C", "delete-c")
        motifs = (
            MotifDefinition("junction", "deletion-junction motif", "CGG"),
            MotifDefinition("downstream", "unchanged downstream motif", "TTAA"),
        )

        result = SequenceInference().analyze_haplotype((deletion,), _sequence(), motifs=motifs)

        self.assertEqual(result.state, SequenceAnalysisState.SUPPORTED)
        self.assertEqual(result.alternate_length_delta, -1)
        created = next(hit for hit in result.created_hits if hit.motif_id == "junction")
        self.assertIsNone(created.reference_interval)
        self.assertEqual(created.variant_ids, ("delete-c",))
        disrupted = next(hit for hit in result.disrupted_hits if hit.motif_id == "junction")
        self.assertEqual(disrupted.reference_interval, ("chr7", 103, 105))
        self.assertEqual(disrupted.variant_ids, ("delete-c",))
        created_ids = {hit.motif_id for hit in result.created_hits}
        disrupted_ids = {hit.motif_id for hit in result.disrupted_hits}
        self.assertNotIn("downstream", created_ids)
        self.assertNotIn("downstream", disrupted_ids)

    def test_haplotype_abstains_for_overlapping_variants(self) -> None:
        result = SequenceInference().analyze_haplotype(
            (_phased("7:103:C>T", "first"), _phased("7:103:C>A", "second")),
            _sequence(),
        )
        self.assertEqual(result.state, SequenceAnalysisState.ABSTAINED)
        self.assertIn("overlapping variants", result.limitations[0])

    def test_haplotype_requires_one_phase_set_haplotype_and_sample(self) -> None:
        first = _phased("7:103:C>T", "first")
        with self.assertRaisesRegex(ValidationError, "one phase set and haplotype"):
            SequenceInference().analyze_haplotype(
                (first, _phased("7:104:G>A", "second", phase_set="phase-2")),
                _sequence(),
            )
        with self.assertRaisesRegex(ValidationError, "one phase set and haplotype"):
            SequenceInference().analyze_haplotype(
                (first, _phased("7:104:G>A", "second", haplotype_index=2)),
                _sequence(),
            )
        with self.assertRaisesRegex(ValidationError, "one sample"):
            SequenceInference().analyze_haplotype(
                (first, _phased("7:104:G>A", "second", sample_id="sample-2")),
                _sequence(),
            )

    def test_haplotype_rejects_unknown_phase_labels(self) -> None:
        with self.assertRaisesRegex(ValidationError, "resolved phase block"):
            _phased("7:103:C>T", "unphased", phase_set="unphased")
        variant_without_sample = parse_variant("7:103:C>T", variant_id="no-sample")
        with self.assertRaisesRegex(ValidationError, "explicit sample_id"):
            PhasedVariantIdentity(variant_without_sample, "phase-1", 1)

    def test_vcf_call_factory_requires_explicit_phase_and_maps_each_alt_copy(self) -> None:
        variant = parse_variant("7:103:C>T", variant_id="vcf-alt")
        variant = replace(variant, sample_id="sample-1")

        heterozygous = PhasedVariantIdentity.from_vcf_call(
            variant,
            genotype="0|1",
            phase_set="17",
            alternate_count=1,
            alternate_index=1,
        )
        homozygous = PhasedVariantIdentity.from_vcf_call(
            variant,
            genotype="1|1",
            phase_set="17",
            alternate_count=1,
            alternate_index=1,
        )
        not_carried = PhasedVariantIdentity.from_vcf_call(
            variant,
            genotype="0|2",
            phase_set="17",
            alternate_count=2,
            alternate_index=1,
        )

        self.assertEqual(tuple(item.haplotype_index for item in heterozygous), (2,))
        self.assertEqual(tuple(item.haplotype_index for item in homozygous), (1, 2))
        self.assertEqual(not_carried, ())
        self.assertTrue(all(item.variant.sample_id == "sample-1" for item in heterozygous))

    def test_vcf_call_factory_rejects_unphased_incomplete_or_missing_phase(self) -> None:
        variant = replace(
            parse_variant("7:103:C>T", variant_id="vcf-alt"),
            sample_id="sample-1",
        )
        for genotype in ("0/1", "0|.", "1"):
            with self.subTest(genotype=genotype):
                with self.assertRaisesRegex(ValidationError, "fully called and explicitly phased"):
                    PhasedVariantIdentity.from_vcf_call(
                        variant,
                        genotype=genotype,
                        phase_set="17",
                        alternate_count=1,
                        alternate_index=1,
                    )
        with self.assertRaisesRegex(ValidationError, "resolved phase block"):
            PhasedVariantIdentity.from_vcf_call(
                variant,
                genotype="0|1",
                phase_set=".",
                alternate_count=1,
                alternate_index=1,
            )

    def test_haplotype_preserves_reference_mismatch_and_window_abstentions(self) -> None:
        mismatch = _phased("7:104:C>A", "mismatch")
        outside = _phased("7:120:G>A", "outside")

        mismatch_result = SequenceInference().analyze_haplotype((mismatch,), _sequence())
        outside_result = SequenceInference().analyze_haplotype((outside,), _sequence())

        self.assertEqual(mismatch_result.state, SequenceAnalysisState.REFERENCE_MISMATCH)
        self.assertEqual(outside_result.state, SequenceAnalysisState.OUT_OF_WINDOW)

    def test_haplotype_bounds_consumed_variant_iterable(self) -> None:
        consumed = 0
        first = _phased("7:103:C>T", "first")

        def unbounded_variants():
            nonlocal consumed
            while True:
                consumed += 1
                yield first

        with patch("glio_noncode.sequence_inference.MAX_HAPLOTYPE_VARIANTS", 2):
            with self.assertRaisesRegex(ValidationError, "2-variant limit"):
                SequenceInference().analyze_haplotype(unbounded_variants(), _sequence())
        self.assertEqual(consumed, 3)

    def test_haplotype_bounds_combined_motif_deltas(self) -> None:
        deletion = _phased("7:102:CC>C", "delete-c")
        with patch("glio_noncode.sequence_inference.MAX_HAPLOTYPE_MOTIF_DELTAS", 0):
            with self.assertRaisesRegex(ValidationError, "0-delta output limit"):
                SequenceInference().analyze_haplotype(
                    (deletion,),
                    _sequence(),
                    motifs=(MotifDefinition("junction", "deletion-junction motif", "CGG"),),
                )

    def test_haplotype_bounds_constructed_alternate_sequence(self) -> None:
        insertion = _phased("7:102:C>CT", "insert-t")
        with patch("glio_noncode.sequence_inference.MAX_MOTIF_SCAN_SEQUENCE_BP", 12):
            with self.assertRaisesRegex(ValidationError, "constructed haplotype exceeds"):
                SequenceInference().analyze_haplotype((insertion,), _sequence())

    def test_haplotype_types_are_available_from_the_package_surface(self) -> None:
        self.assertIs(glio_noncode.HaplotypeMotifChange, HaplotypeMotifChange)
        self.assertIs(glio_noncode.PhasedVariantIdentity, PhasedVariantIdentity)
        self.assertIsNotNone(glio_noncode.HaplotypeMotifDelta)
        self.assertIsNotNone(glio_noncode.HaplotypeSequenceAnalysisResult)
        self.assertIs(glio_noncode.SequenceAnalysisState, SequenceAnalysisState)

    def test_ambiguous_allele_abstains(self) -> None:
        variant = parse_variant("7:104:N>A", genome_build="GRCh38")
        result = SequenceInference().analyze(variant, _sequence())
        self.assertEqual(result.state, SequenceAnalysisState.ABSTAINED)
        self.assertIn("unambiguous literal", result.limitations[0])

    def test_inconsistent_variant_interval_abstains(self) -> None:
        variant = parse_variant("7:104:G>A", genome_build="GRCh38")
        malformed = replace(variant, end=variant.end + 1)
        result = SequenceInference().analyze(malformed, _sequence())
        self.assertEqual(result.state, SequenceAnalysisState.ABSTAINED)
        self.assertIn("interval length does not match", result.limitations[0])

    def test_no_op_allele_abstains(self) -> None:
        variant = parse_variant("7:104:G>G", genome_build="GRCh38")
        result = SequenceInference().analyze(variant, _sequence())
        self.assertEqual(result.state, SequenceAnalysisState.ABSTAINED)
        self.assertIn("alleles are identical", result.limitations[0])

    def test_out_of_window_is_not_a_negative(self) -> None:
        variant = parse_variant("7:120:G>A", genome_build="GRCh38", variant_id="outside")
        result = SequenceInference().analyze(variant, _sequence())
        self.assertEqual(result.state, SequenceAnalysisState.OUT_OF_WINDOW)
        self.assertIn("not fully contained", result.limitations[0])

    def test_sequence_boundary_rejects_malformed_motifs_and_types(self) -> None:
        with self.assertRaises(ValidationError):
            MotifDefinition(7, "motif", "ACG")  # type: ignore[arg-type]
        with self.assertRaises(ValidationError):
            MotifDefinition("motif", "motif", "ACG", source_id=7)  # type: ignore[arg-type]
        with self.assertRaises(ValidationError):
            MotifScanner().scan("ACGT", genomic_start=True, motifs=())  # type: ignore[arg-type]
        with self.assertRaises(ValidationError):
            MotifScanner().scan("ACGT", genomic_start=1, motifs=(object(),))  # type: ignore[arg-type]
        with self.assertRaises(ValidationError):
            SequenceInference().analyze(object(), _sequence())  # type: ignore[arg-type]

    def test_motif_scan_rejects_excessive_comparison_work_before_scanning(self) -> None:
        motif = MotifDefinition("long", "long-pattern", "A" * 8)
        with patch("glio_noncode.sequence_inference.MAX_MOTIF_SCAN_BASE_COMPARISONS", 20):
            with self.assertRaisesRegex(ValidationError, "base-comparison limit"):
                MotifScanner().scan("A" * 20, genomic_start=1, motifs=(motif,))

    def test_motif_scan_rejects_excessive_hit_count_without_partial_result(self) -> None:
        motif = MotifDefinition("a", "adenine", "A")
        with patch("glio_noncode.sequence_inference.MAX_MOTIF_HITS", 2):
            with self.assertRaisesRegex(ValidationError, "2-hit limit"):
                MotifScanner().scan("AAAA", genomic_start=1, motifs=(motif,))

    def test_motif_scan_bounds_copied_hit_sequence_payload(self) -> None:
        motif = MotifDefinition("aa", "two adenines", "AA")
        with patch("glio_noncode.sequence_inference.MAX_MOTIF_HIT_SEQUENCE_BASES", 3):
            with self.assertRaisesRegex(ValidationError, "output limit"):
                MotifScanner().scan("AAAA", genomic_start=1, motifs=(motif,))

    def test_motif_scan_bounds_sequence_length_before_normalization(self) -> None:
        with patch("glio_noncode.sequence_inference.MAX_MOTIF_SCAN_SEQUENCE_BP", 4):
            with self.assertRaisesRegex(ValidationError, "4-base limit"):
                MotifScanner().scan("AAAAA", genomic_start=1, motifs=())

    def test_motif_iterable_consumption_is_bounded(self) -> None:
        consumed = 0
        motif = MotifDefinition("a", "adenine", "A")

        def unbounded_motifs():
            nonlocal consumed
            while True:
                consumed += 1
                yield motif

        with patch("glio_noncode.sequence_inference.MAX_MOTIF_DEFINITIONS", 3):
            with self.assertRaisesRegex(ValidationError, "motif count exceeds"):
                MotifScanner().scan("A", genomic_start=1, motifs=unbounded_motifs())
        self.assertEqual(consumed, 4)


if __name__ == "__main__":
    unittest.main()
