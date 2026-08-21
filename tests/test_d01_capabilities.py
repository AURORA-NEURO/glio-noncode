from __future__ import annotations

import unittest

from glio_noncode.intake import IntakeFormat, VariantIntake
from glio_noncode.models import ReferenceContext
from glio_noncode.regulatory_tracks import RegulatoryTrackFormat, RegulatoryTrackParser
from glio_noncode.variant_normalization import NormalizationState, VRSNormalizer


class D01CapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = ReferenceContext(
            genome_build="GRCh38",
            disease_class="glioma",
            age_group="adult",
            cell_state="tumor",
        )

    def test_bed_coordinate_conversion_and_quarantine(self) -> None:
        batch = RegulatoryTrackParser().parse_text(
            "# track name=fixture\n7\t99\t120\treg-1\t800\t+\n7\tbad\t140\tbad\n",
            source_id="fixture-bed",
            genome_build="GRCh38",
            input_format=RegulatoryTrackFormat.BED,
        )
        self.assertEqual(len(batch.features), 1)
        self.assertEqual((batch.features[0].start, batch.features[0].end), (100, 120))
        self.assertEqual(batch.features[0].score, 0.8)
        self.assertEqual(len(batch.errors), 1)
        self.assertEqual(batch.errors[0].line_number, 3)
        elements = batch.to_candidate_elements(self.context)
        self.assertEqual(elements[0].state_ids, ("unresolved_state",))
        self.assertEqual(elements[0].annotations["track_coordinate_system"], "0-based-half-open")

    def test_gff3_attributes_and_json_are_preserved(self) -> None:
        gff = (
            "##gff-version 3\n"
            "7\tENCODE\tenhancer\t100\t120\t.\t+\t.\t"
            "ID=enh-1;gene_id=EGFR;cell_state=stem_like\n"
        )
        batch = RegulatoryTrackParser().parse_text(
            gff,
            source_id="fixture-gff",
            genome_build="GRCh38",
        )
        self.assertEqual(batch.input_format, RegulatoryTrackFormat.GFF3)
        self.assertEqual(batch.features[0].attributes["gene_id"], "EGFR")
        element = batch.to_candidate_elements(self.context)[0]
        self.assertEqual(element.target_genes, ("EGFR",))
        self.assertEqual(element.state_ids, ("stem_like",))

        json_batch = RegulatoryTrackParser().parse_text(
            '{"features":[{"id":"enh-2","chrom":"7","start":200,"end":220,"attributes":{"gene":"TP53"}}]}',
            source_id="fixture-json",
            genome_build="GRCh38",
            input_format="json",
        )
        self.assertEqual(json_batch.features[0].feature_id, "enh-2")
        self.assertEqual(json_batch.to_candidate_elements(self.context)[0].target_genes, ("TP53",))

    def test_vrs_normalization_emits_provenance_and_abstains_on_breakends(self) -> None:
        normalizer = VRSNormalizer()
        supported = normalizer.normalize(
            {
                "variant_id": "v1",
                "chromosome": "7",
                "start": 100,
                "reference": "AA",
                "alternate": "AT",
            },
            genome_build="GRCh38",
        )
        self.assertEqual(supported.state, NormalizationState.SUPPORTED)
        self.assertEqual(len(supported.candidates), 1)
        self.assertEqual(supported.candidates[0].vrs_allele["location"]["interval"]["start"], 100)
        self.assertTrue(any("left alignment" in warning for warning in supported.warnings))

        breakend = normalizer.normalize("7:100:BND:8:200", genome_build="GRCh38")
        self.assertEqual(breakend.state, NormalizationState.ABSTAINED)
        self.assertEqual(breakend.candidates, ())

    def test_repeat_context_reports_ambiguity_without_selecting_a_placement(self) -> None:
        result = VRSNormalizer().normalize(
            {
                "variant_id": "repeat",
                "chromosome": "7",
                "start": 103,
                "reference": "A",
                "alternate": "AA",
            },
            genome_build="GRCh38",
            reference_sequence="AAAAAA",
            sequence_digest="SQ.fixture",
            reference_start=100,
        )
        self.assertEqual(result.state, NormalizationState.AMBIGUOUS)
        self.assertIsNone(result.selected_candidate_id)
        self.assertGreater(len(result.candidates), 1)
        self.assertTrue(result.ambiguities)

    def test_gvcf_preserves_deferred_reference_block(self) -> None:
        text = (
            "##fileformat=VCFv4.3\n"
            "##contig=<ID=7>\n"
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\n"
            "7\t100\t.\tA\t<NON_REF>\t.\tPASS\tEND=200\tGT\t0/0\n"
        )
        batch = VariantIntake().parse_text(
            text,
            source_id="fixture-gvcf",
            input_format=IntakeFormat.GVCF,
        )
        self.assertEqual(batch.input_format, IntakeFormat.GVCF)
        self.assertEqual(batch.variants, ())
        self.assertEqual(len(batch.deferred_records), 1)
        self.assertTrue(any(issue.code == "unsupported_symbolic_allele" for issue in batch.issues))


if __name__ == "__main__":
    unittest.main()
