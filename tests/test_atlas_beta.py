from __future__ import annotations

import json
import unittest

from glio_noncode.atlas_beta import (
    AtlasBetaState,
    HistoneMarkTrackHarmonizer,
    MolecularAtlasState,
    MolecularStateAtlasAdapter,
)
from glio_noncode.models import ReferenceContext

CONTEXT = "GRCh38|glioma|adult|stem_like|unknown|unknown"


class AtlasBetaTests(unittest.TestCase):
    def test_state_atlas_keeps_idh_states_separate_and_context_gated(self) -> None:
        batch = MolecularStateAtlasAdapter().parse_text(
            json.dumps(
                {
                    "records": [
                        {
                            "element_id": "enh-1",
                            "chrom": "7",
                            "start": 99,
                            "end": 120,
                            "molecular_state": "IDH-mutant",
                            "context_key": CONTEXT,
                            "assay": "ATAC",
                            "activity_score": 0.8,
                        },
                        {
                            "element_id": "enh-2",
                            "chrom": "7",
                            "start": 99,
                            "end": 120,
                            "molecular_state": "IDH-wildtype",
                            "context_key": CONTEXT,
                            "assay": "ATAC",
                            "activity_score": 0.7,
                        },
                    ]
                }
            ),
            source_id="state-atlas",
            source_version="v1",
        )
        context = ReferenceContext("GRCh38", "glioma", "adult", "stem_like")
        adapter = MolecularStateAtlasAdapter()
        mutant = adapter.query(
            batch.records,
            molecular_state=MolecularAtlasState.IDH_MUTANT,
            chromosome="7",
            start=100,
            end=120,
            context=context,
        )
        self.assertEqual(mutant.state, AtlasBetaState.SUPPORTED)
        self.assertEqual(mutant.matches[0].element_id, "enh-1")
        wildtype = adapter.query(
            batch.records,
            molecular_state=MolecularAtlasState.IDH_WILDTYPE,
            chromosome="7",
            start=100,
            end=120,
            context=context,
        )
        self.assertEqual(wildtype.state, AtlasBetaState.SUPPORTED)
        self.assertEqual(wildtype.matches[0].element_id, "enh-2")

    def test_state_atlas_reports_out_of_domain_without_transport(self) -> None:
        record = MolecularStateAtlasAdapter().parse_text(
            json.dumps(
                {
                    "records": [
                        {
                            "element_id": "enh-1",
                            "chrom": "7",
                            "start": 99,
                            "end": 120,
                            "molecular_state": "H3K27-altered",
                            "context_key": "GRCh38|glioma|pediatric|stem_like|unknown|unknown",
                            "assay": "ATAC",
                        }
                    ]
                }
            ),
            source_id="state-atlas",
        )
        result = MolecularStateAtlasAdapter().query(
            record.records,
            molecular_state=MolecularAtlasState.H3K27_ALTERED,
            chromosome="7",
            start=100,
            end=120,
            context=ReferenceContext("GRCh38", "glioma", "adult", "stem_like"),
        )
        self.assertEqual(result.state, AtlasBetaState.OUT_OF_DOMAIN)
        self.assertEqual(result.matches, ())

    def test_histone_harmonizer_splits_boundaries_and_retains_replicate_spread(self) -> None:
        text = (
            "chrom\tstart\tend\tmark\tsignal\treplicate_id\tcontext_key\n"
            f"7\t99\t120\tH3K27ac\t4\trep-1\t{CONTEXT}\n"
            f"7\t99\t120\tH3K27ac\t5\trep-2\t{CONTEXT}\n"
            f"7\t109\t130\tH3K27ac\t6\trep-3\t{CONTEXT}\n"
        )
        result = HistoneMarkTrackHarmonizer().parse_text(
            text,
            source_id="histone",
            source_version="v2",
            spread_tolerance=2,
        )
        self.assertEqual(result.state, AtlasBetaState.PARTIAL)
        self.assertEqual(len(result.intervals), 3)
        first = result.intervals[0]
        self.assertEqual((first.start, first.end), (100, 109))
        self.assertEqual(first.replicate_ids, ("rep-1", "rep-2"))
        self.assertEqual(first.median_signal, 4.5)
        self.assertEqual(result.intervals[-1].state, AtlasBetaState.PARTIAL)

    def test_histone_harmonizer_marks_large_signal_disagreement_ambiguous(self) -> None:
        observations = HistoneMarkTrackHarmonizer().parse_text(
            "chrom\tstart\tend\tmark\tsignal\treplicate_id\tcontext_key\n"
            f"7\t99\t120\tH3K27ac\t2\trep-1\t{CONTEXT}\n"
            f"7\t99\t120\tH3K27ac\t8\trep-2\t{CONTEXT}\n",
            source_id="histone",
            spread_tolerance=1,
        )
        self.assertEqual(observations.state, AtlasBetaState.AMBIGUOUS)
        self.assertEqual(observations.intervals[0].signal_spread, 6.0)
