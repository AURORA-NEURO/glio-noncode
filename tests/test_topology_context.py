from __future__ import annotations

import unittest

from glio_noncode.models import ReferenceContext
from glio_noncode.topology_context import (
    ContactMatrixNormalizer,
    ContactMatrixParser,
    ContactMatrixQcEvaluator,
    InsulationScoreDeltaEstimator,
    InsulationScoreMeasurement,
    TadBoundaryEnsembleBuilder,
    TadBoundaryParser,
    TopologyAssay,
    TopologyContactRetriever,
    TopologyEvidenceBuilder,
    TopologyState,
)


class TopologyContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = ReferenceContext(
            "GRCh38", "glioma", "adult", "stem_like", territory="core"
        )
        self.other_context = ReferenceContext(
            "GRCh38", "glioma", "adult", "differentiated", territory="core"
        )

    def test_contact_parser_converts_coordinates_and_quarantines_bad_rows(self) -> None:
        text = (
            "chrom1\tstart1\tend1\tchrom2\tstart2\tend2\tcount\tcontext\tversion\n"
            f"7\t99\t120\t7\t299\t320\t10\t{self.context.key}\tv1\n"
            f"7\t299\t320\t7\t99\t120\t5\t{self.context.key}\tv1\n"
            "7\tbad\t400\t7\t500\t520\t1\tunknown\tv1\n"
        )
        batch = ContactMatrixParser().parse_text(
            text, source_id="hic-atlas", assay=TopologyAssay.HI_C
        )
        self.assertEqual(len(batch.records), 2)
        self.assertEqual(batch.records[0].start_a, 100)
        self.assertEqual(batch.records[0].end_b, 320)
        self.assertEqual(batch.records[0].assay, TopologyAssay.HI_C)
        self.assertEqual(len(batch.issues), 1)
        self.assertTrue(batch.records[0].raw_hash.startswith("sha256:"))

    def test_qc_and_normalization_keep_duplicates_and_zeroes_visible(self) -> None:
        text = (
            "chrom1\tstart1\tend1\tchrom2\tstart2\tend2\tcount\tcontext\n"
            f"7\t99\t120\t7\t299\t320\t10\t{self.context.key}\n"
            f"7\t299\t320\t7\t99\t120\t5\t{self.context.key}\n"
            f"7\t500\t520\t7\t700\t720\t0\t{self.context.key}\n"
        )
        records = ContactMatrixParser().parse_text(
            text, source_id="hic-atlas", assay="hi-c"
        ).records
        qc = ContactMatrixQcEvaluator().evaluate(records, normalization_method="mean")
        normalized = ContactMatrixNormalizer().normalize(records, method="mean")
        self.assertEqual(qc.duplicate_count, 1)
        self.assertEqual(qc.zero_signal_count, 1)
        self.assertEqual(qc.state, TopologyState.PARTIAL)
        self.assertEqual(normalized.records[0].normalized_signal, 2.0)
        self.assertEqual(normalized.state, TopologyState.PARTIAL)
        self.assertIn("ICE", normalized.limitations[0])

    def test_contact_retriever_is_assay_and_context_gated(self) -> None:
        text = (
            "chrom1\tstart1\tend1\tchrom2\tstart2\tend2\tcount\tcontext\n"
            f"7\t99\t120\t7\t299\t320\t10\t{self.context.key}\n"
            f"7\t99\t120\t7\t299\t320\t3\t{self.other_context.key}\n"
        )
        records = ContactMatrixParser().parse_text(
            text, source_id="micro-atlas", assay=TopologyAssay.MICRO_C
        ).records
        retriever = TopologyContactRetriever(records)
        supported = retriever.query(
            "micro-c", "7", 100, 110, "chr7", 300, 310, self.context
        )
        out_of_domain = retriever.query(
            "micro-c", "7", 100, 110, "chr7", 300, 310, self.other_context
        )
        self.assertEqual(supported.state, TopologyState.SUPPORTED)
        self.assertEqual(supported.median_signal, 10.0)
        self.assertEqual(out_of_domain.state, TopologyState.SUPPORTED)
        self.assertEqual(out_of_domain.median_signal, 3.0)

        absent = retriever.query(
            "micro-c", "7", 100, 110, "chr7", 900, 910, self.context
        )
        self.assertEqual(absent.state, TopologyState.ABSENT)

    def test_boundary_parser_ensemble_and_context_transport(self) -> None:
        text = (
            "boundary_id\tassay\tchromosome\tposition\tscore\tcontext\tcaller\n"
            f"b1\thi-c\t7\t1000\t0.8\t{self.context.key}\tc1\n"
            f"b2\tmicro-c\t7\t1020\t0.9\t{self.context.key}\tc2\n"
            f"b3\thi-c\t7\t1010\t0.7\t{self.other_context.key}\tc3\n"
            "bad\thi-c\t7\tbad\t0.7\tunknown\tc4\n"
        )
        batch = TadBoundaryParser().parse_text(
            text, source_id="boundary-atlas", assay=TopologyAssay.HI_C
        )
        self.assertEqual(len(batch.observations), 3)
        self.assertEqual(len(batch.issues), 1)
        result = TadBoundaryEnsembleBuilder().build(
            batch.observations,
            chromosome="7",
            region_start=900,
            region_end=1100,
            context=self.context,
            tolerance=50,
        )
        self.assertEqual(result.state, TopologyState.SUPPORTED)
        self.assertEqual(result.representative_position, 1010)
        self.assertEqual(result.agreement, 1.0)
        self.assertEqual(result.source_ids, ("boundary-atlas",))

    def test_equal_boundary_clusters_remain_ambiguous(self) -> None:
        text = (
            "boundary_id\tassay\tchromosome\tposition\tscore\tcontext\n"
            f"b1\thi-c\t7\t1000\t0.8\t{self.context.key}\n"
            f"b2\tmicro-c\t7\t3000\t0.9\t{self.context.key}\n"
        )
        rows = TadBoundaryParser().parse_text(
            text, source_id="boundary-atlas", assay=TopologyAssay.HI_C
        ).observations
        result = TadBoundaryEnsembleBuilder().build(
            rows,
            chromosome="7",
            region_start=900,
            region_end=3100,
            context=self.context,
            tolerance=50,
        )
        self.assertEqual(result.state, TopologyState.AMBIGUOUS)
        self.assertIsNone(result.representative_position)
        self.assertEqual(len(result.clusters), 2)

    def test_insulation_delta_has_missing_and_zero_guards(self) -> None:
        estimator = InsulationScoreDeltaEstimator()
        measured = estimator.estimate(
            InsulationScoreMeasurement(
                "m1", "v1", self.context.key, 0.4, 0.2, "hic", "h1"
            )
        )
        missing = estimator.estimate(
            InsulationScoreMeasurement(
                "m2", "v2", self.context.key, None, 0.2, "hic", "h2"
            )
        )
        zero = estimator.estimate(
            InsulationScoreMeasurement(
                "m3", "v3", self.context.key, 0.0, 0.2, "hic", "h3"
            )
        )
        self.assertEqual(measured.state, TopologyState.SUPPORTED)
        self.assertEqual(measured.delta, -0.2)
        self.assertEqual(measured.direction, "decrease")
        self.assertEqual(missing.state, TopologyState.ABSTAINED)
        self.assertIsNone(zero.relative_delta)

    def test_topology_evidence_builder_propagates_weakest_component(self) -> None:
        text = (
            "chrom1\tstart1\tend1\tchrom2\tstart2\tend2\tcount\tcontext\n"
            f"7\t99\t120\t7\t299\t320\t10\t{self.context.key}\n"
        )
        records = ContactMatrixParser().parse_text(
            text, source_id="hic", assay="hi-c"
        ).records
        query = TopologyContactRetriever(records).query(
            "hi-c", "7", 100, 110, "7", 300, 310, self.context
        )
        delta = InsulationScoreDeltaEstimator().estimate(
            InsulationScoreMeasurement(
                "m1", "v1", self.context.key, None, 0.2, "hic", "h1"
            )
        )
        evidence = TopologyEvidenceBuilder().build(
            "topo-1", self.context, contact_query=query, insulation_delta=delta
        )
        self.assertEqual(evidence.state, TopologyState.ABSTAINED)
        self.assertEqual(evidence.source_ids, ("hic",))
        self.assertTrue(evidence.content_address.startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()
