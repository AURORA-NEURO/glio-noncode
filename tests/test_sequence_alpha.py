from __future__ import annotations

import unittest

from glio_noncode.sequence_alpha import (
    NucleosomeSequencePropensityModel,
    PromoterCoreGrammarModel,
    PromoterGrammarRule,
    PromoterMotifDefinition,
    SequenceAlphaState,
    SpliceMotifDefinition,
    SpliceRegulatoryNoncodingScanner,
    UtrMotifDefinition,
    UtrRegulatoryScanner,
)

CONTEXT = "GRCh38|glioma|adult|stem_like|unknown|unknown"


class SequenceAlphaTests(unittest.TestCase):
    def test_nucleosome_propensity_is_deterministic_and_length_gated(self) -> None:
        result = NucleosomeSequencePropensityModel().predict(
            [
                {
                    "sequence_id": "nuc-1",
                    "chrom": "7",
                    "start": 100,
                    "sequence": "AA" * 74,
                    "context_key": CONTEXT,
                    "source_id": "sequence-fixture",
                    "source_version": "v1",
                },
                {
                    "sequence_id": "nuc-short",
                    "chrom": "7",
                    "start": 300,
                    "sequence": "ACGT" * 10,
                    "context_key": CONTEXT,
                },
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(result.state, SequenceAlphaState.PARTIAL)
        self.assertEqual(result.windows[0].sequence_length, 148)
        self.assertEqual(result.windows[0].positioning_label, "favored")
        self.assertEqual(result.windows[0].state, SequenceAlphaState.SUPPORTED)
        self.assertEqual(result.windows[1].state, SequenceAlphaState.PARTIAL)
        self.assertTrue(result.windows[0].content_address.startswith("sha256:"))

    def test_nucleosome_propensity_rejects_context_transport(self) -> None:
        result = NucleosomeSequencePropensityModel().predict(
            [
                {
                    "sequence_id": "wrong-context",
                    "sequence": "ACGT" * 40,
                    "context_key": "GRCh38|glioma|pediatric|stem_like|unknown|unknown",
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(result.state, SequenceAlphaState.OUT_OF_DOMAIN)
        self.assertEqual(result.windows, ())

    def test_splice_scanner_reports_disrupted_non_coding_motif(self) -> None:
        result = SpliceRegulatoryNoncodingScanner().scan(
            [
                {
                    "sequence_id": "splice-1",
                    "chrom": "7",
                    "start": 100,
                    "reference_sequence": "AACGTAA",
                    "alternate_sequence": "AACATAA",
                    "context_key": CONTEXT,
                }
            ],
            [
                SpliceMotifDefinition(
                    motif_id="donor",
                    name="declared donor",
                    consensus="GT",
                    role="donor",
                    source_id="splice-fixture",
                    source_version="v1",
                    strand_aware=False,
                )
            ],
            context_key=CONTEXT,
        )
        window = result.windows[0]
        self.assertEqual(result.state, SequenceAlphaState.SUPPORTED)
        self.assertEqual(len(window.reference_hits), 1)
        self.assertEqual(len(window.alternate_hits), 0)
        self.assertEqual(len(window.disrupted_hits), 1)
        self.assertEqual(window.disrupted_hits[0].role, "donor")

    def test_splice_scanner_marks_ambiguous_created_and_disrupted_sets(self) -> None:
        result = SpliceRegulatoryNoncodingScanner().scan(
            [
                {
                    "sequence_id": "splice-ambiguous",
                    "start": 1,
                    "reference_sequence": "GTAA",
                    "alternate_sequence": "AAGT",
                    "context_key": CONTEXT,
                }
            ],
            [
                SpliceMotifDefinition(
                    motif_id="donor",
                    name="donor",
                    consensus="GT",
                    role="donor",
                    source_id="splice-fixture",
                    source_version="v1",
                    strand_aware=False,
                )
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(result.state, SequenceAlphaState.AMBIGUOUS)
        self.assertEqual(result.windows[0].state, SequenceAlphaState.AMBIGUOUS)

    def test_utr_scanner_separates_region_and_reports_bounded_uorf(self) -> None:
        result = UtrRegulatoryScanner().scan(
            [
                {
                    "utr_id": "utr-5",
                    "region": "5utr",
                    "start": 100,
                    "sequence": "CCCATGAAATAACCC",
                    "context_key": CONTEXT,
                },
                {
                    "utr_id": "utr-3",
                    "region": "3utr",
                    "start": 300,
                    "sequence": "CCCTGTAACCC",
                    "context_key": CONTEXT,
                },
            ],
            [
                UtrMotifDefinition(
                    motif_id="uorf-start",
                    name="uORF start",
                    consensus="ATG",
                    element_kind="uorf_start",
                    region="5utr",
                    source_id="utr-fixture",
                    source_version="v1",
                    strand_aware=False,
                ),
                UtrMotifDefinition(
                    motif_id="mirna-seed",
                    name="miRNA seed",
                    consensus="TGTA",
                    element_kind="mirna_seed",
                    region="3utr",
                    source_id="utr-fixture",
                    source_version="v1",
                    strand_aware=False,
                ),
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(result.state, SequenceAlphaState.SUPPORTED)
        five_prime, three_prime = result.windows
        self.assertEqual(five_prime.region, "5utr")
        self.assertEqual(len(five_prime.upstream_orfs), 1)
        self.assertEqual(five_prime.upstream_orfs[0].stop_codon, "TAA")
        self.assertEqual(three_prime.region, "3utr")
        self.assertEqual(three_prime.reference_hits[0].element_kind, "mirna_seed")
        self.assertEqual(three_prime.upstream_orfs, ())

    def test_utr_scanner_preserves_ambiguous_bases_as_partial(self) -> None:
        result = UtrRegulatoryScanner().scan(
            [
                {
                    "utr_id": "utr-ambiguous",
                    "region": "3utr",
                    "sequence": "TTNAAA",
                    "context_key": CONTEXT,
                }
            ],
            [
                UtrMotifDefinition(
                    motif_id="rbp",
                    name="RBP motif",
                    consensus="TTA",
                    element_kind="rbp",
                    region="3utr",
                    source_id="utr-fixture",
                    source_version="v1",
                )
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(result.state, SequenceAlphaState.PARTIAL)
        self.assertEqual(result.windows[0].state, SequenceAlphaState.PARTIAL)

    def test_promoter_grammar_reports_spacing_and_weighted_coverage(self) -> None:
        result = PromoterCoreGrammarModel().evaluate(
            [
                {
                    "promoter_id": "prom-1",
                    "chrom": "7",
                    "start": 100,
                    "sequence": "AAAATATAAAACAGG",
                    "context_key": CONTEXT,
                }
            ],
            [
                PromoterMotifDefinition(
                    motif_id="tata",
                    name="TATA box",
                    consensus="TATA",
                    element_kind="tata",
                    source_id="promoter-fixture",
                    source_version="v1",
                    strand_aware=False,
                ),
                PromoterMotifDefinition(
                    motif_id="inr",
                    name="initiator",
                    consensus="CA",
                    element_kind="initiator",
                    source_id="promoter-fixture",
                    source_version="v1",
                    strand_aware=False,
                ),
            ],
            [
                PromoterGrammarRule(
                    rule_id="tata-to-inr",
                    motif_a="tata",
                    motif_b="inr",
                    minimum_spacing=2,
                    maximum_spacing=4,
                    allowed_orientations=("same",),
                    source_id="promoter-grammar-fixture",
                    source_version="v1",
                )
            ],
            context_key=CONTEXT,
        )
        evaluation = result.evaluations[0]
        self.assertEqual(result.state, SequenceAlphaState.SUPPORTED)
        self.assertEqual(evaluation.matched_rule_ids, ("tata-to-inr",))
        self.assertEqual(evaluation.unmatched_rule_ids, ())
        self.assertEqual(evaluation.weighted_coverage, 1.0)
        self.assertEqual(evaluation.compatible_pairs[0].spacing, 3)

    def test_promoter_grammar_preserves_unmatched_rules_as_partial(self) -> None:
        result = PromoterCoreGrammarModel().evaluate(
            [{"promoter_id": "prom-empty", "sequence": "CCCCCCCC", "context_key": CONTEXT}],
            [
                PromoterMotifDefinition(
                    motif_id="tata",
                    name="TATA",
                    consensus="TATA",
                    element_kind="tata",
                    source_id="promoter-fixture",
                    source_version="v1",
                    strand_aware=False,
                )
            ],
            [
                PromoterGrammarRule(
                    rule_id="required-tata",
                    motif_a="tata",
                    motif_b="tata",
                    minimum_spacing=0,
                    maximum_spacing=5,
                )
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(result.state, SequenceAlphaState.ABSTAINED)
        self.assertEqual(result.evaluations[0].unmatched_rule_ids, ("required-tata",))


if __name__ == "__main__":
    unittest.main()
