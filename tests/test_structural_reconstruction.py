from __future__ import annotations

import unittest

from glio_noncode.errors import ValidationError
from glio_noncode.intake import RawVariantRecord, VariantIntake
from glio_noncode.models import ReferenceContext
from glio_noncode.structural_reconstruction import StructuralReconstructor
from glio_noncode.variation import (
    Breakend,
    HaplotypeSegment,
    StructuralEvent,
    StructuralEventKind,
)


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


class StructuralDataModelContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = ReferenceContext("GRCh38", "glioma", "adult", "stem_like")

    def _paired_breakends(self) -> tuple[Breakend, Breakend]:
        return (
            Breakend("b1", "7", 100, "forward", "b2"),
            Breakend("b2", "8", 200, "reverse", "b1"),
        )

    def _event(self, **overrides: object) -> StructuralEvent:
        values: dict[str, object] = {
            "event_id": "event-1",
            "kind": StructuralEventKind.BREAKEND_PAIR,
            "breakends": self._paired_breakends(),
            "haplotype_segments": (),
            "context": self.context,
            "source_id": "fixture-vcf",
            "reconstruction_support": 1.0,
            "uncertainty": 0.0,
        }
        values.update(overrides)
        return StructuralEvent(**values)  # type: ignore[arg-type]

    def test_breakend_rejects_invalid_coordinates_and_copy_number(self) -> None:
        for overrides in (
            {"position": True},
            {"position": 100.0},
            {"orientation": []},
            {"copy_number": True},
            {"copy_number": float("nan")},
            {"copy_number": float("inf")},
            {"copy_number": -0.25},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ValidationError):
                values: dict[str, object] = {
                    "breakend_id": "b1",
                    "chromosome": "7",
                    "position": 100,
                    "orientation": "forward",
                    "mate_id": "b2",
                }
                values.update(overrides)
                Breakend(**values)  # type: ignore[arg-type]

    def test_haplotype_segment_validates_and_detaches_source_ids(self) -> None:
        source_ids = ["v1"]
        segment = HaplotypeSegment("s1", "7", 10, 20, "PS42", "T", source_ids)
        source_ids.append("later-mutation")
        self.assertEqual(segment.source_variant_ids, ("v1",))

        for start, end, variant_ids in (
            (True, 20, ("v1",)),
            (21, 20, ("v1",)),
            (10, 20, ()),
            (10, 20, ("v1", "v1")),
        ):
            with self.subTest(start=start, end=end, variant_ids=variant_ids):
                with self.assertRaises(ValidationError):
                    HaplotypeSegment("s1", "7", start, end, "PS42", "T", variant_ids)  # type: ignore[arg-type]

    def test_breakend_pair_requires_two_unique_reciprocal_mates(self) -> None:
        malformed_pairs = (
            (Breakend("b1", "7", 100, "forward", "missing"),),
            (
                Breakend("b1", "7", 100, "forward", "b2"),
                Breakend("b2", "8", 200, "reverse", "b2"),
            ),
            (
                Breakend("b1", "7", 100, "forward", "b2"),
                Breakend("b1", "8", 200, "reverse", "b1"),
            ),
            (
                Breakend("b1", "7", 100, "forward", "b2"),
                Breakend("b2", "8", 200, "reverse", "b1"),
                Breakend("b3", "9", 300, "forward", "b4"),
                Breakend("b4", "10", 400, "reverse", "b3"),
            ),
        )
        for breakends in malformed_pairs:
            with self.subTest(breakends=breakends), self.assertRaises(ValidationError):
                self._event(breakends=breakends)

    def test_event_rejects_bad_scores_types_and_context(self) -> None:
        for field, value in (
            ("reconstruction_support", True),
            ("reconstruction_support", float("nan")),
            ("reconstruction_support", 1.01),
            ("uncertainty", -0.01),
            ("kind", "breakend_pair"),
            ("context", object()),
            ("annotations", []),
        ):
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                self._event(**{field: value})

    def test_event_copies_sequences_and_freezes_content_address_metadata(self) -> None:
        breakends = list(self._paired_breakends())
        annotations = {"source": {"notes": ["original"]}}
        event = self._event(breakends=breakends, annotations=annotations)
        original_address = event.content_address

        breakends.clear()
        annotations["source"]["notes"].append("mutated")
        self.assertEqual(len(event.breakends), 2)
        self.assertEqual(event.content_address, original_address)
        with self.assertRaises(TypeError):
            event.annotations["source"]["notes"].append("blocked")
        self.assertEqual(event.to_dict()["content_address"], original_address)

    def test_haplotype_event_requires_a_phased_segment(self) -> None:
        with self.assertRaises(ValidationError):
            self._event(
                kind=StructuralEventKind.HAPLOTYPE,
                breakends=(),
                haplotype_segments=(),
            )

        segment = HaplotypeSegment("s1", "7", 10, 10, "PS42", "T", ("v1",))
        valid = self._event(
            kind=StructuralEventKind.HAPLOTYPE,
            breakends=(),
            haplotype_segments=[segment],
        )
        self.assertEqual(valid.haplotype_segments, (segment,))


if __name__ == "__main__":
    unittest.main()
