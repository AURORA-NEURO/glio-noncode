from __future__ import annotations

import unittest

from glio_noncode.methylation_beta import (
    CpGCreationLossAnalyzer,
    IdhHypermethylationContextModel,
    MethylationBetaState,
    MethylationContextRetriever,
    MethylationRecord,
    MethylationRecordParser,
    MethylationSensitiveMotifAnalyzer,
    MethylationSensitiveMotifDefinition,
)

CONTEXT = "GRCh38|glioma|adult|stem_like|tumor|unknown"
OTHER_CONTEXT = "GRCh38|glioma|adult|differentiated|tumor|unknown"


class MethylationBetaTests(unittest.TestCase):
    def test_parser_preserves_one_based_records_and_quarantines_invalid_rows(self) -> None:
        text = (
            "chrom\tposition\tbeta\tcontext\tcoverage\tmolecular_state\n"
            f"7\t100\t0.8\t{CONTEXT}\t50\tIDH-mutant\n"
            f"7\t101\t\t{CONTEXT}\t40\tIDH-mutant\n"
            f"7\tbad\t0.4\t{CONTEXT}\t30\tIDH-mutant\n"
        )
        batch = MethylationRecordParser().parse_text(
            text,
            source_id="methylation-atlas",
            source_version="v1",
        )
        self.assertEqual(len(batch.records), 2)
        self.assertEqual(batch.records[0].chromosome, "chr7")
        self.assertEqual(batch.records[0].position, 100)
        self.assertIsNone(batch.records[1].beta_value)
        self.assertEqual(batch.records[0].coverage, 50)
        self.assertEqual(batch.records[0].molecular_state, "IDH-mutant")
        self.assertEqual(batch.issues[0].code, "invalid_methylation_row")

    def test_bed_parser_and_context_retriever_keep_context_boundaries(self) -> None:
        text = (
            "chrom\tstart\tbeta\tcontext\n"
            f"7\t99\t0.8\t{CONTEXT}\n"
            f"7\t99\t0.2\t{CONTEXT}\n"
            f"7\t99\t0.4\t{OTHER_CONTEXT}\n"
        )
        batch = MethylationRecordParser().parse_text(
            text,
            source_id="methylation-atlas",
            source_version="v1",
            coordinate_system="bed",
        )
        retriever = MethylationContextRetriever(batch.records)
        ambiguous = retriever.query("7", 100, 100, context_key=CONTEXT)
        self.assertEqual(ambiguous.state, MethylationBetaState.AMBIGUOUS)
        self.assertEqual(ambiguous.median_beta, 0.5)
        out_of_domain = retriever.query("7", 100, 100, context_key="missing-context")
        self.assertEqual(out_of_domain.state, MethylationBetaState.OUT_OF_DOMAIN)
        self.assertEqual(out_of_domain.records, ())

    def test_cpg_creation_and_loss_annotate_exact_methylation_context(self) -> None:
        record = MethylationRecord(
            record_id="meth-100",
            chromosome="chr7",
            position=100,
            beta_value=0.8,
            context_key=CONTEXT,
            source_id="methylation-atlas",
            source_version="v1",
            raw_hash="raw-100",
        )
        analyzer = CpGCreationLossAnalyzer()
        created = analyzer.analyze(
            "AAGTT",
            "ACGTT",
            variant_id="var-create",
            window_start=99,
            chromosome="7",
            context_key=CONTEXT,
            methylation_records=(record,),
        )
        self.assertEqual(created.state, MethylationBetaState.SUPPORTED)
        self.assertEqual(created.created[0].genomic_start, 100)
        self.assertEqual(created.created[0].methylation_state, "methylated")
        self.assertEqual(created.methylation_context_state, MethylationBetaState.SUPPORTED)

        lost = analyzer.analyze(
            "ACGTT",
            "AAGTT",
            variant_id="var-loss",
            window_start=99,
            chromosome="7",
            context_key=CONTEXT,
            methylation_records=(record,),
        )
        self.assertEqual(lost.lost[0].reference_dinucleotide, "CG")
        self.assertEqual(lost.lost[0].alternate_dinucleotide, "AG")

    def test_cpg_analyzer_abstains_for_unreplayable_length_change(self) -> None:
        result = CpGCreationLossAnalyzer().analyze(
            "ACGTT",
            "ACGTTT",
            variant_id="var-indel",
        )
        self.assertEqual(result.state, MethylationBetaState.OUT_OF_DOMAIN)
        self.assertEqual(result.issues[0].code, "length_changing_variant_out_of_domain")

    def test_methylation_sensitive_motif_keeps_missing_sites_explicit(self) -> None:
        motif = MethylationSensitiveMotifDefinition(
            motif_id="TF:CG",
            name="CG-sensitive factor",
            consensus="CG",
            source_id="motif-catalog",
            source_version="v1",
            sensitive_positions=(0,),
            strand_aware=False,
        )
        record = MethylationRecord(
            record_id="meth-100",
            chromosome="chr7",
            position=100,
            beta_value=0.8,
            context_key=CONTEXT,
            source_id="methylation-atlas",
            source_version="v1",
            raw_hash="raw-100",
        )
        observed = MethylationSensitiveMotifAnalyzer().analyze(
            "ACGTT",
            sequence_id="window-1",
            motifs=(motif,),
            methylation_records=(record,),
            window_start=99,
            chromosome="7",
            context_key=CONTEXT,
        )
        self.assertEqual(observed.state, MethylationBetaState.SUPPORTED)
        self.assertEqual(observed.hits[0].start, 100)
        self.assertEqual(observed.hits[0].methylation_state, "methylated")
        missing = MethylationSensitiveMotifAnalyzer().analyze(
            "ACGTT",
            sequence_id="window-1",
            motifs=(motif,),
            window_start=99,
            chromosome="7",
            context_key=CONTEXT,
        )
        self.assertEqual(missing.state, MethylationBetaState.PARTIAL)
        self.assertEqual(missing.hits[0].methylation_state, "missing")

    def test_idh_context_model_requires_target_and_comparator_panels(self) -> None:
        target = tuple(
            MethylationRecord(
                record_id=f"target-{index}",
                chromosome="chr7",
                position=100 + index,
                beta_value=value,
                context_key=CONTEXT,
                source_id="methylation-atlas",
                source_version="v1",
                raw_hash=f"target-raw-{index}",
                coverage=100,
                molecular_state="IDH-mutant",
            )
            for index, value in enumerate((0.8, 0.9, 0.7))
        )
        comparator = tuple(
            MethylationRecord(
                record_id=f"comparator-{index}",
                chromosome="chr7",
                position=100 + index,
                beta_value=0.2,
                context_key=CONTEXT,
                source_id="methylation-atlas",
                source_version="v1",
                raw_hash=f"comparator-raw-{index}",
                molecular_state="IDH-wildtype",
            )
            for index in range(3)
        )
        model = IdhHypermethylationContextModel()
        supported = model.assess(
            target,
            context_key=CONTEXT,
            comparator_records=comparator,
            model_id="idh-panel",
            model_version="v1",
        )
        self.assertEqual(supported.state, MethylationBetaState.SUPPORTED)
        self.assertTrue(supported.hypermethylated)
        self.assertEqual(supported.delta_vs_comparator, 0.6)
        partial = model.assess(
            target,
            context_key=CONTEXT,
            comparator_records=comparator[:1],
            model_id="idh-panel",
            model_version="v1",
        )
        self.assertEqual(partial.state, MethylationBetaState.PARTIAL)
        out_of_domain = model.assess(
            target,
            context_key=OTHER_CONTEXT,
            comparator_records=comparator,
            model_id="idh-panel",
            model_version="v1",
        )
        self.assertEqual(out_of_domain.state, MethylationBetaState.OUT_OF_DOMAIN)


if __name__ == "__main__":
    unittest.main()
