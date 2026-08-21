from __future__ import annotations

import unittest

from glio_noncode.structural_haplotype import (
    AlleleAwareSvRepresenter,
    PangenomeGraphProjector,
    PhasedHaplotypeAssembler,
    RepeatMobileElementAnnotator,
    StructuralAlphaState,
)

CONTEXT = "GRCh38|glioma|adult|stem_like|unknown|unknown"


class StructuralHaplotypeTests(unittest.TestCase):
    def test_assembler_keeps_two_explicit_paths_and_unphased_rows(self) -> None:
        result = PhasedHaplotypeAssembler().assemble(
            [
                {
                    "observation_id": "v1",
                    "sample_id": "S1",
                    "chrom": "chr7",
                    "pos": 100,
                    "ref": "A",
                    "alt": "T",
                    "GT": "1|0",
                    "PS": "phase-1",
                    "context_key": CONTEXT,
                },
                {
                    "observation_id": "v2",
                    "sample_id": "S1",
                    "chrom": "7",
                    "pos": 200,
                    "ref": "G",
                    "alt": "C",
                    "GT": "0|1",
                    "PS": "phase-1",
                    "context_key": CONTEXT,
                },
                {
                    "observation_id": "v3",
                    "sample_id": "S1",
                    "chrom": "7",
                    "pos": 300,
                    "ref": "C",
                    "alt": "A",
                    "GT": "0/1",
                    "context_key": CONTEXT,
                },
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(result.state, StructuralAlphaState.PARTIAL)
        self.assertEqual(len(result.haplotypes), 2)
        self.assertEqual(len(result.unphased_observations), 1)
        self.assertEqual([call.allele_index for call in result.haplotypes[0].calls], [1, 0])
        self.assertEqual([call.allele_index for call in result.haplotypes[1].calls], [0, 1])

    def test_assembler_with_only_wrong_context_is_out_of_domain(self) -> None:
        result = PhasedHaplotypeAssembler().assemble(
            [
                {
                    "observation_id": "v1",
                    "sample_id": "S1",
                    "chrom": "7",
                    "pos": 100,
                    "ref": "A",
                    "alt": "T",
                    "GT": "1|0",
                    "PS": "phase-1",
                    "context_key": "GRCh37|other",
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(result.state, StructuralAlphaState.OUT_OF_DOMAIN)
        self.assertEqual(result.haplotypes, ())
        self.assertEqual(result.issues[0].code, "context_mismatch")

    def test_allele_aware_representation_retains_dosage_and_zygosity(self) -> None:
        result = AlleleAwareSvRepresenter().represent(
            [
                {
                    "event_id": "sv-1",
                    "sample_id": "S1",
                    "chrom": "7",
                    "start": 100,
                    "end": 200,
                    "kind": "deletion",
                    "alternate": "<DEL>",
                    "GT": "1|0",
                    "allele_index": 1,
                    "copy_number": 1,
                    "support": 0.9,
                }
            ]
        )
        self.assertEqual(result.state, StructuralAlphaState.SUPPORTED)
        self.assertEqual(result.events[0].dosage, 1)
        self.assertEqual(result.events[0].zygosity, "heterozygous")
        self.assertEqual(result.events[0].allele_state, "alternate")

    def test_allele_aware_conflicting_coordinates_are_not_merged_silently(self) -> None:
        result = AlleleAwareSvRepresenter().represent(
            [
                {
                    "event_id": "sv-1",
                    "sample_id": "S1",
                    "chrom": "7",
                    "start": 100,
                    "end": 200,
                    "kind": "deletion",
                    "alternate": "<DEL>",
                    "GT": "1|0",
                    "allele_index": 1,
                },
                {
                    "event_id": "sv-1",
                    "sample_id": "S1",
                    "chrom": "7",
                    "start": 101,
                    "end": 200,
                    "kind": "deletion",
                    "alternate": "<DEL>",
                    "GT": "1|0",
                    "allele_index": 1,
                },
            ]
        )
        self.assertEqual(result.state, StructuralAlphaState.CONTRADICTORY)
        self.assertEqual(result.issues[0].code, "conflicting_allele_observation")

    def test_graph_projection_keeps_multiple_paths_and_unmapped_queries(self) -> None:
        result = PangenomeGraphProjector().project(
            [
                {"query_id": "q1", "chrom": "7", "start": 110, "end": 120},
                {"query_id": "q2", "chrom": "7", "start": 900, "end": 910},
            ],
            [
                {"node_id": "n1", "path_id": "p1", "chrom": "7", "start": 100, "end": 150},
                {"node_id": "n2", "path_id": "p2", "chrom": "7", "start": 100, "end": 150},
            ],
        )
        self.assertEqual(result.state, StructuralAlphaState.AMBIGUOUS)
        self.assertEqual(len(result.matches), 2)
        self.assertEqual(result.unmapped_query_ids, ("q2",))

    def test_graph_projection_finds_nested_prior_interval(self) -> None:
        result = PangenomeGraphProjector().project(
            [{"query_id": "q1", "chrom": "7", "start": 120, "end": 125}],
            [
                {"node_id": "outer", "path_id": "p1", "chrom": "7", "start": 1, "end": 1000},
                {"node_id": "inner", "path_id": "p1", "chrom": "7", "start": 110, "end": 130},
            ],
        )
        self.assertEqual({match.node_id for match in result.matches}, {"outer", "inner"})

    def test_repeat_annotation_indexes_mobile_and_static_features(self) -> None:
        result = RepeatMobileElementAnnotator().annotate(
            [{"query_id": "sv-1", "chrom": "7", "start": 100, "end": 150}],
            [
                {
                    "annotation_id": "r1",
                    "chrom": "7",
                    "start": 110,
                    "end": 125,
                    "family": "L1",
                    "class": "LINE",
                    "subfamily": "L1HS",
                    "strand": "+",
                },
                {
                    "annotation_id": "r2",
                    "chrom": "7",
                    "start": 130,
                    "end": 140,
                    "family": "Alu",
                    "class": "SINE",
                    "subfamily": "AluY",
                    "strand": "-",
                },
            ],
        )
        self.assertEqual(result.state, StructuralAlphaState.AMBIGUOUS)
        self.assertEqual(len(result.hits), 2)
        self.assertTrue(all(hit.is_mobile for hit in result.hits))

    def test_repeat_annotation_retains_no_hit_and_context_issue(self) -> None:
        result = RepeatMobileElementAnnotator().annotate(
            [{"query_id": "q1", "chrom": "7", "start": 500, "end": 510}],
            [
                {
                    "annotation_id": "r1",
                    "chrom": "7",
                    "start": 100,
                    "end": 120,
                    "family": "satellite",
                    "class": "satellite",
                    "context_key": "other",
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(result.state, StructuralAlphaState.PARTIAL)
        self.assertEqual(result.unannotated_query_ids, ("q1",))
        self.assertEqual(result.issues[0].code, "annotation_context_mismatch")


if __name__ == "__main__":
    unittest.main()
