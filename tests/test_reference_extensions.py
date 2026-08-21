from __future__ import annotations

import unittest

from glio_noncode.identity import parse_variant
from glio_noncode.reference_extensions import (
    LiftoverAmbiguityScorer,
    LiftoverChainManager,
    PangenomeCoordinateMapper,
    PangenomePath,
    ReferenceExtensionState,
)
from glio_noncode.reference_registry import default_reference_registry


class ReferenceExtensionTests(unittest.TestCase):
    def test_chain_manager_parses_segments_and_projects_variant(self) -> None:
        manager = LiftoverChainManager(default_reference_registry())
        batch = manager.parse_text(
            "mapping_id\tsource_chrom\tsource_start\tsource_end\ttarget_chrom\t"
            "target_start\ttarget_end\tstrand\tversion\n"
            "chain-1\t7\t100\t109\t7\t200\t209\t+\tfixture-1\n"
            "bad\t7\t100\t108\t7\t300\t309\t+\tfixture-2\n",
            source_id="chain-fixture",
            source_assembly="GRCh38",
            target_assembly="GRCh37",
        )
        self.assertEqual(len(batch.segments), 1)
        self.assertEqual(len(batch.issues), 1)
        result = manager.project(parse_variant("7:102:A>T", genome_build="GRCh38"), "hg19")
        self.assertEqual(result.projected_variant.start, 202)

    def test_ambiguity_scorer_does_not_choose_competing_segments(self) -> None:
        manager = LiftoverChainManager(default_reference_registry())
        batch = manager.parse_text(
            "mapping_id\tsource_chrom\tsource_start\tsource_end\ttarget_chrom\t"
            "target_start\ttarget_end\tstrand\tversion\n"
            "chain-1\t7\t100\t109\t7\t200\t209\t+\tv1\n"
            "chain-2\t7\t100\t109\t7\t300\t309\t+\tv2\n",
            source_id="chain-ambiguous",
            source_assembly="GRCh38",
            target_assembly="GRCh37",
        )
        result = LiftoverAmbiguityScorer().score(batch.segments)
        self.assertEqual(result.state, ReferenceExtensionState.AMBIGUOUS)
        self.assertEqual(result.score, 0.5)
        self.assertEqual(len(result.candidate_mapping_ids), 2)

    def test_pangenome_mapper_reports_unique_and_multi_path_results(self) -> None:
        paths = (
            PangenomePath(
                "path-1",
                "reference",
                "7",
                1,
                1000,
                "+",
                "SQ.ref",
                "pangenome-fixture",
                "v1",
            ),
            PangenomePath(
                "path-2",
                "haplotype-1",
                "7",
                1,
                1000,
                "+",
                "SQ.hap1",
                "pangenome-fixture",
                "v1",
            ),
        )
        mapper = PangenomeCoordinateMapper(paths)
        ambiguous = mapper.map_interval("chr7", 100, 120)
        self.assertEqual(ambiguous.state, ReferenceExtensionState.AMBIGUOUS)
        unique = PangenomeCoordinateMapper(paths[:1]).map_interval("7", 100, 120)
        self.assertEqual(unique.state, ReferenceExtensionState.SUPPORTED)
        missing = mapper.map_interval("8", 100, 120)
        self.assertEqual(missing.state, ReferenceExtensionState.ABSTAINED)


if __name__ == "__main__":
    unittest.main()
