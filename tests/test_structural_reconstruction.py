from __future__ import annotations

import unittest

from glio_noncode.intake import RawVariantRecord, VariantIntake
from glio_noncode.models import ReferenceContext
from glio_noncode.structural_reconstruction import StructuralReconstructor
from glio_noncode.variation import StructuralEventKind


def _record(
    record_id: str,
    chromosome: str,
    position: int,
    alternate: str,
    *,
    info: dict[str, object] | None = None,
    sample: dict[str, object] | None = None,
    reference: str = "N",
) -> RawVariantRecord:
    return RawVariantRecord(
        record_id=record_id,
        chromosome=chromosome,
        position=position,
        reference=reference,
        alternate=alternate,
        source_line=1,
        raw_hash=f"sha256:{record_id}",
        info=info or {},
        sample=sample or {},
    )


class StructuralReconstructionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = ReferenceContext("GRCh38", "glioma", "adult", "stem_like")

    def test_reciprocal_breakends_form_a_paired_event(self) -> None:
        records = (
            _record("bnd1", "7", 100, "N]8:200]", info={"MATEID": "bnd2"}),
            _record("bnd2", "8", 200, "]7:100]N", info={"MATEID": "bnd1"}),
        )
        result = StructuralReconstructor().reconstruct(
            records, context=self.context, source_id="fixture-vcf"
        )
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].kind, StructuralEventKind.BREAKEND_PAIR)
        self.assertEqual(
            {item.breakend_id for item in result.events[0].breakends}, {"bnd1", "bnd2"}
        )
        self.assertFalse(result.has_errors)

    def test_symbolic_deletion_requires_end_and_retains_coordinates(self) -> None:
        record = _record("del1", "7", 100, "<DEL>", info={"END": "150", "SVTYPE": "DEL"})
        result = StructuralReconstructor().reconstruct(
            (record,), context=self.context, source_id="fixture-vcf"
        )
        self.assertEqual(result.events[0].kind, StructuralEventKind.DELETION)
        self.assertEqual({item.position for item in result.events[0].breakends}, {100, 150})

    def test_unpaired_breakend_is_an_error_not_a_guessed_event(self) -> None:
        result = StructuralReconstructor().reconstruct(
            (_record("bnd1", "7", 100, "N]8:200]"),),
            context=self.context,
            source_id="fixture-vcf",
        )
        self.assertEqual(result.events, ())
        self.assertEqual(result.issues[0].code, "missing_mate_id")
        self.assertTrue(result.has_errors)

    def test_phased_records_form_segments_without_flattening(self) -> None:
        records = (
            _record("v1", "7", 10, "T", reference="A", sample={"sample_id": "S1", "PS": "42"}),
            _record("v2", "7", 20, "C", reference="G", sample={"sample_id": "S1", "PS": "42"}),
        )
        result = StructuralReconstructor().reconstruct(
            records, context=self.context, source_id="fixture-vcf"
        )
        haplotypes = [
            event for event in result.events if event.kind == StructuralEventKind.HAPLOTYPE
        ]
        self.assertEqual(len(haplotypes), 1)
        self.assertEqual(len(haplotypes[0].haplotype_segments), 2)
        self.assertEqual(
            {segment.source_variant_ids[0] for segment in haplotypes[0].haplotype_segments},
            {"v1", "v2"},
        )
        self.assertEqual(result.issues, ())

    def test_intake_defers_symbolic_record_for_reconstruction(self) -> None:
        text = "\n".join(
            (
                "##fileformat=VCFv4.3",
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1",
                "7\t100\tdel1\tN\t<DEL>\t.\tPASS\tEND=150;SVTYPE=DEL\tGT\t0/1",
            )
        )
        batch = VariantIntake().parse_text(text, source_id="fixture-vcf")
        result = StructuralReconstructor().reconstruct_batch(batch, context=self.context)
        self.assertEqual(len(batch.deferred_records), 1)
        self.assertEqual(result.events[0].kind, StructuralEventKind.DELETION)


if __name__ == "__main__":
    unittest.main()
