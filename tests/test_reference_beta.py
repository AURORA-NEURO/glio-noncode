from __future__ import annotations

import json
import unittest

from glio_noncode.reference_beta import (
    DiseaseOntologyMapper,
    GencodeTranscriptAdapter,
    ManeTranscriptAdapter,
    ReferenceBetaState,
    RegulatoryOntologyAdapter,
)


class ReferenceBetaTests(unittest.TestCase):
    def test_gencode_adapter_parses_versioned_gtf_and_preserves_bad_rows(self) -> None:
        text = (
            "##gtf-version 3\n"
            "7\tGENCODE\ttranscript\t100\t500\t.\t+\t.\t"
            'gene_id "ENSG0001.2"; transcript_id "ENST0001.4"; gene_name "GENE1"; '
            'transcript_type "protein_coding";\n'
            "bad\trow\n"
        )
        catalog = GencodeTranscriptAdapter().parse_text(
            text,
            source_id="gencode",
            source_version="v46",
            assembly="GRCh38",
        )
        self.assertEqual(catalog.state, ReferenceBetaState.PARTIAL)
        self.assertEqual(len(catalog.records), 1)
        record = catalog.records[0]
        self.assertEqual(record.transcript_id, "ENST0001")
        self.assertEqual(record.transcript_version, "4")
        self.assertEqual(record.gene_id, "ENSG0001")
        self.assertEqual(record.chromosome, "chr7")
        self.assertEqual(record.versioned_id, "ENST0001.4")
        self.assertEqual(
            GencodeTranscriptAdapter().resolve(catalog, transcript_id="ENST0001.4").state,
            ReferenceBetaState.SUPPORTED,
        )

    def test_gencode_gene_resolution_retains_transcript_ambiguity(self) -> None:
        text = json.dumps(
            {
                "records": [
                    {
                        "transcript_id": "tx-1",
                        "gene_id": "gene-1",
                        "chrom": "7",
                        "start": 100,
                        "end": 200,
                        "strand": "+",
                        "biotype": "lncRNA",
                    },
                    {
                        "transcript_id": "tx-2",
                        "gene_id": "gene-1",
                        "chrom": "7",
                        "start": 300,
                        "end": 400,
                        "strand": "+",
                        "biotype": "lncRNA",
                    },
                ]
            }
        )
        catalog = GencodeTranscriptAdapter().parse_text(text, source_id="gencode")
        result = GencodeTranscriptAdapter().resolve(catalog, gene_id="gene-1")
        self.assertEqual(result.state, ReferenceBetaState.AMBIGUOUS)
        self.assertEqual(len(result.records), 2)

    def test_mane_adapter_preserves_status_and_resolves_exact_transcript(self) -> None:
        text = (
            "ensembl_transcript_id\trefseq_transcript_id\tgene_id\tgene_name\t"
            "mane_status\tassembly\tchrom\tstart\tend\n"
            "ENST0001\tNM_0001.1\tGENE1\tGENE1\tMANE Select\tGRCh38\t7\t100\t500\n"
        )
        catalog = ManeTranscriptAdapter().parse_text(
            text,
            source_id="mane",
            source_version="1.4",
        )
        self.assertEqual(catalog.state, ReferenceBetaState.SUPPORTED)
        result = ManeTranscriptAdapter().resolve(catalog, transcript_id="NM_0001.1")
        self.assertEqual(result.state, ReferenceBetaState.SUPPORTED)
        self.assertEqual(result.records[0].mane_status, "MANE Select")
        self.assertEqual(result.records[0].chromosome, "chr7")

    def test_regulatory_ontology_adapter_matches_declared_alias_and_flags_collision(self) -> None:
        text = json.dumps(
            {
                "terms": [
                    {
                        "term_id": "RO:0001",
                        "label": "enhancer",
                        "definition": "regulatory enhancer",
                        "aliases": ["enh"],
                    },
                    {
                        "term_id": "RO:0002",
                        "label": "silencer",
                        "definition": "regulatory silencer",
                        "aliases": ["enh"],
                    },
                ]
            }
        )
        adapter = RegulatoryOntologyAdapter()
        catalog = adapter.parse_text(text, source_id="reg-ontology", source_version="v1")
        exact = adapter.normalize({"term_id": "RO:0001"}, catalog=catalog)
        self.assertEqual(exact.state, ReferenceBetaState.SUPPORTED)
        self.assertEqual(exact.matches[0].term.label, "enhancer")
        ambiguous = adapter.normalize({"label": "enh"}, catalog=catalog)
        self.assertEqual(ambiguous.state, ReferenceBetaState.AMBIGUOUS)
        unknown = adapter.normalize({"label": "promoter_like"}, catalog=catalog)
        self.assertEqual(unknown.state, ReferenceBetaState.ABSTAINED)

    def test_disease_ontology_mapper_retains_one_to_many_targets(self) -> None:
        text = json.dumps(
            {
                "mappings": [
                    {
                        "source_term_id": "SRC:1",
                        "source_label": "glioma",
                        "target_term_id": "MONDO:001",
                        "target_namespace": "MONDO",
                        "relationship": "exact",
                    },
                    {
                        "source_term_id": "SRC:1",
                        "source_label": "glioma",
                        "target_term_id": "DOID:006",
                        "target_namespace": "DOID",
                        "relationship": "broader",
                    },
                ]
            }
        )
        mapper = DiseaseOntologyMapper()
        catalog = mapper.parse_text(text, source_id="disease-map", source_version="v1")
        ambiguous = mapper.map({"source_term_id": "SRC:1"}, catalog=catalog)
        self.assertEqual(ambiguous.state, ReferenceBetaState.AMBIGUOUS)
        self.assertEqual(len(ambiguous.mappings), 2)
        exact = mapper.map({"source_term_id": "SRC:missing"}, catalog=catalog)
        self.assertEqual(exact.state, ReferenceBetaState.ABSTAINED)
