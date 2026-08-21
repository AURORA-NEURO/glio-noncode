from __future__ import annotations

import unittest

from glio_noncode.topology_alpha import (
    BoundaryMotifOrientationAnalyzer,
    CTCFCohesinDisruptionModel,
    IDHInsulatorDysfunctionModel,
    SVTopologyRewiringSimulator,
    TopologyAlphaState,
)

CONTEXT = "GRCh38|glioma|adult|stem_like|tumor|unknown"


class TopologyAlphaTests(unittest.TestCase):
    def test_boundary_motif_orientation_reports_convergent_pair(self) -> None:
        result = BoundaryMotifOrientationAnalyzer().analyze(
            [
                {
                    "boundary_id": "b1",
                    "chrom": "7",
                    "boundary_position": 1000,
                    "side": "left",
                    "motif_id": "ctcf-left",
                    "orientation": "+",
                    "score": 0.9,
                    "context_key": CONTEXT,
                },
                {
                    "boundary_id": "b1",
                    "chrom": "7",
                    "boundary_position": 1000,
                    "side": "right",
                    "motif_id": "ctcf-right",
                    "orientation": "-",
                    "score": 0.8,
                    "context_key": CONTEXT,
                },
            ],
            context_key=CONTEXT,
        )
        boundary = result.results[0]
        self.assertEqual(result.state, TopologyAlphaState.SUPPORTED)
        self.assertEqual(boundary.relationship_labels, ("convergent",))
        self.assertAlmostEqual(boundary.median_score, 0.85)

    def test_boundary_motif_orientation_preserves_mixed_alternatives(self) -> None:
        result = BoundaryMotifOrientationAnalyzer().analyze(
            [
                {
                    "boundary_id": "b2",
                    "chrom": "7",
                    "boundary_position": 2000,
                    "side": "left",
                    "motif_id": "m1",
                    "orientation": "+",
                    "score": 0.9,
                    "context_key": CONTEXT,
                },
                {
                    "boundary_id": "b2",
                    "chrom": "7",
                    "boundary_position": 2000,
                    "side": "left",
                    "motif_id": "m1-alt",
                    "orientation": "-",
                    "score": 0.9,
                    "context_key": CONTEXT,
                },
                {
                    "boundary_id": "b2",
                    "chrom": "7",
                    "boundary_position": 2000,
                    "side": "right",
                    "motif_id": "m2",
                    "orientation": "+",
                    "score": 0.9,
                    "context_key": CONTEXT,
                },
                {
                    "boundary_id": "b2",
                    "chrom": "7",
                    "boundary_position": 2000,
                    "side": "right",
                    "motif_id": "m3",
                    "orientation": "-",
                    "score": 0.9,
                    "context_key": CONTEXT,
                },
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(result.state, TopologyAlphaState.AMBIGUOUS)
        self.assertEqual(
            result.results[0].relationship_labels,
            ("convergent", "divergent", "tandem"),
        )

    def test_ctcf_cohesin_model_reports_disruption(self) -> None:
        result = CTCFCohesinDisruptionModel().analyze(
            [
                {
                    "variant_id": "v1",
                    "reference_ctcf": 0.9,
                    "alternate_ctcf": 0.4,
                    "reference_cohesin": 0.8,
                    "alternate_cohesin": 0.5,
                    "context_key": CONTEXT,
                }
            ],
            context_key=CONTEXT,
            disruption_threshold=0.2,
        )
        model = result.results[0]
        self.assertEqual(result.state, TopologyAlphaState.SUPPORTED)
        self.assertEqual(model.disruption_label, "disrupted")
        self.assertAlmostEqual(model.combined_delta, -0.4)

    def test_ctcf_cohesin_model_marks_missing_channel_partial(self) -> None:
        result = CTCFCohesinDisruptionModel().analyze(
            [
                {
                    "variant_id": "v2",
                    "reference_ctcf": 0.9,
                    "alternate_ctcf": 0.4,
                    "context_key": CONTEXT,
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(result.state, TopologyAlphaState.PARTIAL)
        self.assertEqual(result.results[0].disruption_label, "disrupted")

    def test_idh_insulator_model_compares_state_channels(self) -> None:
        result = IDHInsulatorDysfunctionModel().assess(
            [
                {
                    "region_id": "ins-1",
                    "molecular_state": "IDH-mutant",
                    "insulator_score": 0.3,
                    "methylation_fraction": 0.8,
                    "context_key": CONTEXT,
                },
                {
                    "region_id": "ins-1",
                    "molecular_state": "IDH-wildtype",
                    "insulator_score": 0.8,
                    "methylation_fraction": 0.2,
                    "context_key": CONTEXT,
                },
            ],
            context_key=CONTEXT,
            dysfunction_threshold=0.2,
        )
        model = result.results[0]
        self.assertEqual(result.state, TopologyAlphaState.SUPPORTED)
        self.assertEqual(model.label, "dysfunction_candidate")
        self.assertAlmostEqual(model.insulator_delta, -0.5)
        self.assertAlmostEqual(model.mutant_methylation, 0.8)

    def test_idh_insulator_model_requires_both_state_references(self) -> None:
        result = IDHInsulatorDysfunctionModel().assess(
            [
                {
                    "region_id": "ins-2",
                    "molecular_state": "IDH-mutant",
                    "insulator_score": 0.3,
                    "context_key": CONTEXT,
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(result.state, TopologyAlphaState.PARTIAL)
        self.assertIsNone(result.results[0].dysfunction_index)

    def test_sv_topology_simulator_reports_lost_gained_and_rewired_edges(self) -> None:
        result = SVTopologyRewiringSimulator().simulate(
            [
                {"edge_id": "e1", "source_node": "n1", "target_node": "n2", "context_key": CONTEXT},
                {"edge_id": "e2", "source_node": "n2", "target_node": "n3", "context_key": CONTEXT},
            ],
            [
                {
                    "sv_id": "sv-1",
                    "sv_kind": "deletion",
                    "deleted_edge_ids": ["e1"],
                    "gained_edge_ids": ["e3"],
                    "rewired_edge_ids": ["e2"],
                    "affected_node_ids": ["n1", "n2", "n3"],
                    "context_key": CONTEXT,
                }
            ],
            context_key=CONTEXT,
        )
        simulation = result.results[0]
        self.assertEqual(result.state, TopologyAlphaState.SUPPORTED)
        self.assertEqual(simulation.lost_edge_ids, ("e1",))
        self.assertEqual(simulation.gained_edge_ids, ("e3",))
        self.assertEqual(simulation.rewired_edge_ids, ("e2",))
        self.assertEqual(simulation.preserved_edge_ids, ())

    def test_sv_topology_simulator_context_gates_events(self) -> None:
        result = SVTopologyRewiringSimulator().simulate(
            [{"edge_id": "e1", "source_node": "n1", "target_node": "n2", "context_key": CONTEXT}],
            [
                {
                    "sv_id": "sv-wrong",
                    "deleted_edge_ids": ["e1"],
                    "context_key": "GRCh38|glioma|pediatric|stem_like|tumor|unknown",
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(result.state, TopologyAlphaState.OUT_OF_DOMAIN)
        self.assertEqual(result.results, ())


if __name__ == "__main__":
    unittest.main()
