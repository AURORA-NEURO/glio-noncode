from __future__ import annotations

import unittest
from math import nan

from glio_noncode.causal import CausalLattice, compare_paths
from glio_noncode.cohort import CohortObservation, RecurrenceModel
from glio_noncode.errors import ValidationError
from glio_noncode.models import EdgeType, HypothesisEdge, SupportLevel
from glio_noncode.variation import (
    MAX_ALTERNATE_EVENT_GRAPH_HOPS,
    AlternateEventGraph,
)
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
        self.assertEqual(graph.node_count(), 4)
        self.assertEqual(graph.edge_count(), 4)

    def test_alternate_event_graph_fails_closed_when_path_budget_is_exceeded(self) -> None:
        graph = AlternateEventGraph()
        for layer in range(8):
            for branch in range(2):
                graph.add_edge(
                    f"layer-{layer}-{branch}",
                    f"layer-{layer + 1}-0",
                    0.9,
                    f"edge-{layer}-{branch}-0",
                )
                graph.add_edge(
                    f"layer-{layer}-{branch}",
                    f"layer-{layer + 1}-1",
                    0.9,
                    f"edge-{layer}-{branch}-1",
                )
        graph.add_edge("source", "layer-0-0", 0.9, "source-0")
        graph.add_edge("source", "layer-0-1", 0.9, "source-1")
        graph.add_edge("layer-8-0", "target", 0.9, "target-0")
        graph.add_edge("layer-8-1", "target", 0.9, "target-1")

        with self.assertRaisesRegex(ValidationError, "exceeds the 100-path limit"):
            graph.paths("source", "target", max_hops=10, max_paths=100)
        with self.assertRaisesRegex(ValidationError, "exceeds the 10-expansion limit"):
            graph.paths("source", "target", max_hops=10, max_expansions=10)

    def test_alternate_event_graph_validates_limits_edges_and_finite_support(self) -> None:
        graph = AlternateEventGraph()
        graph.add_edge("a", "b", 1, "edge-1")
        self.assertEqual(graph.paths("a", "b", max_hops=1), graph.paths("a", "b"))
        self.assertEqual(graph.paths("a", "a"), ())

        for kwargs in (
            {"max_hops": 0},
            {"max_hops": MAX_ALTERNATE_EVENT_GRAPH_HOPS + 1},
            {"max_hops": True},
            {"max_paths": 0},
            {"max_expansions": -1},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                graph.paths("a", "b", **kwargs)
        for support in (float("nan"), float("inf"), True, "0.5"):
            with self.subTest(support=support), self.assertRaises(ValidationError):
                graph.add_edge("a", "b", support, f"bad-{support}")  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValidationError, "must be unique"):
            graph.add_edge("b", "c", 0.5, "edge-1")
        for invalid_identifier in ("x" * 257, "line\nbreak", "line\u0085break"):
            with self.subTest(invalid_identifier=invalid_identifier), self.assertRaisesRegex(
                ValidationError, "control-free text"
            ):
                graph.add_edge(invalid_identifier, "c", 0.5, "invalid-id")
        with self.assertRaisesRegex(ValidationError, "control-free text"):
            graph.paths("x" * 257, "b")

    def test_alternate_event_graph_aggregates_support_in_the_log_domain(self) -> None:
        graph = AlternateEventGraph()
        for index in range(64):
            support = 1e-82 if index < 4 else 1.0
            graph.add_edge(f"node-{index}", f"node-{index + 1}", support, f"edge-{index}")

        (path,) = graph.paths("node-0", "node-64", max_hops=64)

        self.assertEqual(path.support, 0.000007)
        self.assertEqual(path.uncertainty, 1.0)

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
        with self.assertRaisesRegex(ValidationError, "workflow cycle includes"):
            WorkflowCompiler().compile("cycle", steps)

    def test_workflow_contracts_reject_malformed_steps_and_empty_graphs(self) -> None:
        malformed = (
            {"step_id": "x", "kind": StepKind.INGEST, "input_contract": 7},
            {"step_id": "x", "kind": StepKind.INGEST, "depends_on": []},
        )
        for value in malformed:
            with self.assertRaises(ValidationError):
                WorkflowStep(**value)  # type: ignore[arg-type]
        with self.assertRaises(ValidationError):
            WorkflowStep("x", StepKind.INGEST, depends_on=("x",))
        with self.assertRaises(ValidationError):
            WorkflowStep("x", "ingest")  # type: ignore[arg-type]
        with self.assertRaises(ValidationError):
            WorkflowStep("x", StepKind.INGEST, optional="false")  # type: ignore[arg-type]
        with self.assertRaises(ValidationError):
            WorkflowCompiler().compile("empty", ())
        with self.assertRaises(ValidationError):
            WorkflowCompiler().compile("bad", (object(),))  # type: ignore[arg-type]

    def test_resource_envelope_rejects_non_finite_and_wrong_scalar_types(self) -> None:
        for kwargs in (
            {"cpu": nan},
            {"memory_gb": "2"},
            {"gpu_count": True},
            {"max_seconds": 1.5},
            {"network_egress": 1},
        ):
            with self.assertRaises(ValidationError):
                ResourceEnvelope(**kwargs)

    def test_causal_lattice_identifies_weakest_edge(self) -> None:
        edges = (
            HypothesisEdge(
                "e1",
                EdgeType.VARIANT_TO_ELEMENT,
                "v",
                "e",
                0.8,
                0.2,
                1.0,
                ("c1",),
                SupportLevel.HIGH,
            ),
            HypothesisEdge(
                "e2", EdgeType.ELEMENT_TO_GENE, "e", "g", 0.25, 0.7, 0.8, ("c2",), SupportLevel.LOW
            ),
            HypothesisEdge(
                "e3",
                EdgeType.GENE_TO_STATE,
                "g",
                "s",
                0.7,
                0.3,
                0.9,
                ("c3",),
                SupportLevel.MODERATE,
            ),
        )
        summary = CausalLattice().summarize("path-1", edges, alternatives=("alternative-gene",))
        self.assertEqual(summary.weakest_edge_id, "e2")
        self.assertEqual(len(summary.sensitivity), 3)
        self.assertIn("alternative-gene", summary.alternatives)
        self.assertEqual(summary.bottleneck_support, 0.25)
        self.assertTrue(summary.all_edges_have_nonzero_support)
        self.assertEqual(
            summary.to_dict()["support_semantics"],
            "heuristic aggregate proxy; not a calibrated probability",
        )

    def test_zeroed_required_edge_marks_serial_path_incomplete(self) -> None:
        edges = tuple(
            HypothesisEdge(
                f"edge-{index}",
                EdgeType.CAUSAL_PATH,
                f"node-{index}",
                f"node-{index + 1}",
                0.1,
                0.2,
                1.0,
                (f"claim-{index}",),
                SupportLevel.LOW,
            )
            for index in range(3)
        )
        summary = CausalLattice().summarize("weak-path", edges)
        challenged = summary.sensitivity[0]

        self.assertEqual(challenged.aggregate_sensitivity, "low")
        self.assertGreater(challenged.challenged_support, 0.0)
        self.assertEqual(challenged.challenged_bottleneck_support, 0.0)
        self.assertFalse(challenged.all_edges_have_nonzero_support_after_challenge)
        self.assertIn("path incomplete", challenged.conclusion)

        zero_edge_path = CausalLattice().summarize(
            "preexisting-zero-edge",
            (
                HypothesisEdge(
                    "zero-edge",
                    EdgeType.CAUSAL_PATH,
                    "node-0",
                    "node-1",
                    0.0,
                    0.9,
                    1.0,
                    ("claim-zero",),
                    SupportLevel.LOW,
                ),
                *edges[1:],
            ),
        )
        self.assertGreater(zero_edge_path.support, 0.0)
        self.assertEqual(zero_edge_path.bottleneck_support, 0.0)
        self.assertFalse(zero_edge_path.all_edges_have_nonzero_support)

    def test_path_validation_rejects_disconnected_and_duplicate_edges(self) -> None:
        first = HypothesisEdge(
            "edge-a",
            EdgeType.CAUSAL_PATH,
            "node-a",
            "node-b",
            0.8,
            0.2,
            1.0,
            ("claim-a",),
            SupportLevel.HIGH,
        )
        disconnected = HypothesisEdge(
            "edge-b",
            EdgeType.CAUSAL_PATH,
            "node-x",
            "node-y",
            0.7,
            0.3,
            1.0,
            ("claim-b",),
            SupportLevel.MODERATE,
        )
        duplicate = HypothesisEdge(
            "edge-a",
            EdgeType.CAUSAL_PATH,
            "node-b",
            "node-c",
            0.7,
            0.3,
            1.0,
            ("claim-c",),
            SupportLevel.MODERATE,
        )

        with self.assertRaisesRegex(ValidationError, "contiguous"):
            CausalLattice().summarize("disconnected", (first, disconnected))
        with self.assertRaisesRegex(ValidationError, "edge IDs must be unique"):
            CausalLattice().summarize("duplicate", (first, duplicate))

    def test_path_ranking_prioritizes_the_weakest_required_edge(self) -> None:
        weak_link_path = CausalLattice().summarize(
            "a-weak-link",
            (
                HypothesisEdge(
                    "a1",
                    EdgeType.CAUSAL_PATH,
                    "a",
                    "b",
                    0.95,
                    0.1,
                    1.0,
                    ("ca1",),
                    SupportLevel.HIGH,
                ),
                HypothesisEdge(
                    "a2", EdgeType.CAUSAL_PATH, "b", "c", 0.1, 0.1, 1.0, ("ca2",), SupportLevel.LOW
                ),
                HypothesisEdge(
                    "a3",
                    EdgeType.CAUSAL_PATH,
                    "c",
                    "d",
                    0.95,
                    0.1,
                    1.0,
                    ("ca3",),
                    SupportLevel.HIGH,
                ),
            ),
        )
        balanced_path = CausalLattice().summarize(
            "b-balanced",
            tuple(
                HypothesisEdge(
                    f"b{index}",
                    EdgeType.CAUSAL_PATH,
                    f"m{index}",
                    f"m{index + 1}",
                    0.5,
                    0.1,
                    1.0,
                    (f"cb{index}",),
                    SupportLevel.MODERATE,
                )
                for index in range(3)
            ),
        )

        self.assertGreater(weak_link_path.support, balanced_path.support)
        self.assertEqual(compare_paths((weak_link_path, balanced_path))[0].path_id, "b-balanced")

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
