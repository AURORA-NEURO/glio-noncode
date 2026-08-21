from __future__ import annotations

import unittest

from glio_noncode.atlas_extensions import (
    CcreAtlasAdapter,
    CcreAtlasProfile,
    CcreQueryState,
    CcreTrackParser,
)
from glio_noncode.models import ReferenceContext


class AtlasExtensionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = ReferenceContext("GRCh38", "glioma", "adult", "stem_like")

    def test_encode_ccre_parser_converts_bed_coordinates_and_quarantines_rows(self) -> None:
        text = (
            "chrom\tstart\tend\tccre_id\tregistry_class\tscore\tcell_state\t"
            "disease_class\tage_group\tversion\n"
            "chr7\t99\t120\tEH38E123\tenhancer\t80\tstem_like\tglioma\tadult\tv1\n"
            "chr7\tbad\t130\tbad\tenhancer\t0.2\tstem_like\tglioma\tadult\tv1\n"
        )
        batch = CcreTrackParser().parse_text(text, source_id="encode-fixture")
        self.assertEqual(len(batch.records), 1)
        self.assertEqual((batch.records[0].start, batch.records[0].end), (100, 120))
        self.assertEqual(batch.records[0].score, 0.8)
        self.assertEqual(len(batch.issues), 1)

    def test_adult_atlas_returns_context_matched_record(self) -> None:
        batch = CcreTrackParser().parse_text(
            '{"records":[{"chrom":"7","start":99,"end":120,"id":"adult-1",'
            '"profile":"adult_glioma_regulatory","cell_state":"stem_like",'
            '"disease_class":"glioma","age_group":"adult","version":"v1"}]}',
            source_id="adult-fixture",
            profile=CcreAtlasProfile.ADULT_GLIO,
        )
        result = CcreAtlasAdapter(
            batch.records,
            profile=CcreAtlasProfile.ADULT_GLIO,
        ).query("chr7", 100, 120, self.context)
        self.assertEqual(result.state, CcreQueryState.SUPPORTED)
        self.assertEqual(result.matches[0].ccre_id, "adult-1")

    def test_brain_and_pediatric_profiles_preserve_out_of_domain(self) -> None:
        batch = CcreTrackParser().parse_text(
            "chrom\tstart\tend\tccre_id\tprofile\tcell_state\tdisease_class\tage_group\n"
            "7\t99\t120\tbrain-1\tbrain_cell_type_ccre\tastrocyte\tbrain\tadult\n"
            "7\t99\t120\tped-1\tpediatric_glioma_regulatory\tstem_like\tglioma\tpediatric\n",
            source_id="multi-atlas-fixture",
            profile=CcreAtlasProfile.ENCODE_SCREEN,
        )
        brain_context = ReferenceContext("GRCh38", "brain", "adult", "astrocyte")
        brain_result = CcreAtlasAdapter(
            batch.records,
            profile=CcreAtlasProfile.BRAIN_CELL,
        ).query("7", 100, 120, brain_context)
        self.assertEqual(brain_result.state, CcreQueryState.SUPPORTED)
        ped_result = CcreAtlasAdapter(
            batch.records,
            profile=CcreAtlasProfile.PEDIATRIC_GLIO,
        ).query("7", 100, 120, self.context)
        self.assertEqual(ped_result.state, CcreQueryState.OUT_OF_DOMAIN)

    def test_atlas_absence_is_not_a_negative_measurement(self) -> None:
        batch = CcreTrackParser().parse_text(
            "chrom\tstart\tend\tccre_id\tprofile\tcell_state\tdisease_class\tage_group\n"
            "7\t99\t120\tadult-1\tadult_glioma_regulatory\tstem_like\tglioma\tadult\n",
            source_id="absence-fixture",
            profile=CcreAtlasProfile.ADULT_GLIO,
        )
        result = CcreAtlasAdapter(
            batch.records,
            profile=CcreAtlasProfile.ADULT_GLIO,
        ).query("8", 100, 120, self.context)
        self.assertEqual(result.state, CcreQueryState.ABSENT)
        self.assertEqual(result.matches, ())


if __name__ == "__main__":
    unittest.main()
