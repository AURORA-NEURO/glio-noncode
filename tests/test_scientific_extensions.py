from __future__ import annotations

import unittest

from glio_noncode.causal import CausalLattice
from glio_noncode.cohort import CohortObservation, RecurrenceModel
from glio_noncode.models import EdgeType, HypothesisEdge, SupportLevel
from glio_noncode.variation import AlternateEventGraph
from glio_noncode.workflow import ResourceEnvelope, StepKind, WorkflowCompiler, WorkflowStep

from .helpers import fixture_manifest


class ScientificExtensionTests(unittest.TestCase):
    def test_alternate_event_graph_retains_multiple_paths(self) -> None:
        graph = AlternateEventGraph()
        graph.add_edge("variant", "element-a", 0.8, "edge-a")
        graph.add_edge("variant", "element-b", 0.7, "edge-b")
        graph.add_edge("element-a", "gene", 0.6, "edge-c")
        graph.add_edge("element-b", "gene", 0.9, "edge-d")
        paths = graph.paths("variant", "gene")
        self.assertEqual(len(paths), 2)
        self.assertGreater(paths[0].support, paths[1].support)

    def test_workflow_compiler_orders_dependencies(self) -> None:
        compiled = WorkflowCompiler().compile_initial_slice()
        self.assertEqual(compiled.steps[0].step_id, "ingest")
        self.assertEqual(compiled.steps[-1].step_id, "export")
        self.assertGreater(compiled.max_seconds, 0)
        self.assertTrue(all(step.resource.cpu > 0 for step in compiled.steps))

    def test_workflow_compiler_rejects_cycle(self) -> None:
        steps = (
            WorkflowStep("a", StepKind.INGEST, ("b",)),
            WorkflowStep("b", StepKind.NORMALIZE, ("a",)),
        )
        with self.assertRaises(Exception):
            WorkflowCompiler().compile("cycle", steps)

    def test_causal_lattice_identifies_weakest_edge(self) -> None:
        edges = (
            HypothesisEdge("e1", EdgeType.VARIANT_TO_ELEMENT, "v", "e", 0.8, 0.2, 1.0, ("c1",), SupportLevel.HIGH),
            HypothesisEdge("e2", EdgeType.ELEMENT_TO_GENE, "e", "g", 0.25, 0.7, 0.8, ("c2",), SupportLevel.LOW),
            HypothesisEdge("e3", EdgeType.GENE_TO_STATE, "g", "s", 0.7, 0.3, 0.9, ("c3",), SupportLevel.MODERATE),
        )
        summary = CausalLattice().summarize("path-1", edges, alternatives=("alternative-gene",))
        self.assertEqual(summary.weakest_edge_id, "e2")
        self.assertEqual(len(summary.sensitivity), 3)
        self.assertIn("alternative-gene", summary.alternatives)

    def test_matched_recurrence_exposes_control_warnings(self) -> None:
        manifest = fixture_manifest()
        rows = [
            CohortObservation(
                observation_id=f"obs-{index}",
                subject_id=f"subject-{index}",
                locus_id="locus-a" if index < 2 else f"locus-{index}",
                mutated=index < 2,
                callable=True,
                mutability_score=0.4 + index * 0.01,
                chromatin_score=0.6,
                ancestry_group="group-a",
                disease_class="diffuse_glioma",
                context=manifest.context,
            )
            for index in range(6)
        ]
        result = RecurrenceModel().evaluate(rows, "locus-a")
        self.assertEqual(result.observed_count, 2)
        self.assertGreaterEqual(result.uncertainty, 0.0)
        self.assertTrue(result.limitations)

    def test_resource_envelope_capacity_check(self) -> None:
        request = ResourceEnvelope(cpu=2, memory_gb=4, gpu_count=0, storage_gb=3)
        capacity = ResourceEnvelope(cpu=4, memory_gb=8, gpu_count=1, storage_gb=5)
        self.assertTrue(request.fits(capacity))
        self.assertFalse(ResourceEnvelope(cpu=5).fits(capacity))
