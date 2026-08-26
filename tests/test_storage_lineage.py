"""Deep tests for storage lineage graphs, projections, packets, and surfaces."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.batch_runtime import BatchRuntime
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.runtime import CaseRuntime
from glio_noncode.storage_lineage import (
    build_storage_lineage,
    diff_storage_lineage,
    query_storage_lineage,
    storage_lineage_edges_csv,
    storage_lineage_json,
    storage_lineage_markdown,
    storage_lineage_nodes_csv,
    storage_lineage_capabilities,
    storage_lineage_schema,
)
from glio_noncode.storage_lineage_contracts import (
    StorageLineageEdgeKind,
    StorageLineageGraph,
    StorageLineageNodeKind,
)
from glio_noncode.storage_lineage_observability import (
    build_storage_lineage_observability,
    query_storage_lineage_events,
    storage_lineage_events_csv,
    storage_lineage_metrics_csv,
    storage_lineage_observability_capabilities,
    storage_lineage_observability_json,
    storage_lineage_observability_schema,
)
from glio_noncode.storage_lineage_review import (
    build_storage_lineage_review_queue,
    query_storage_lineage_review,
    storage_lineage_review_capabilities,
    storage_lineage_review_csv,
    storage_lineage_review_json,
    storage_lineage_review_markdown,
    storage_lineage_review_schema,
)
from glio_noncode.storage_lineage_packet import (
    build_storage_lineage_packet,
    load_storage_lineage_packet,
    storage_lineage_packet_capabilities,
    storage_lineage_packet_json,
    storage_lineage_packet_schema,
    verify_storage_lineage_packet,
    write_storage_lineage_packet,
)

from .helpers import fixture_manifest


class StorageLineageTests(unittest.TestCase):
    """Exercise the complete read-only provenance boundary."""

    def _runtime(self, directory: str) -> tuple[CaseRuntime, object]:
        runtime = CaseRuntime(directory)
        return runtime, runtime.evaluate(fixture_manifest())

    def _get(self, connection: HTTPConnection, path: str) -> tuple[int, object]:
        connection.request("GET", path)
        response = connection.getresponse()
        return response.status, json.loads(response.read())

    def _post(
        self,
        connection: HTTPConnection,
        path: str,
        payload: dict[str, object],
    ) -> tuple[int, object]:
        body = json.dumps(payload).encode("utf-8")
        connection.request(
            "POST",
            path,
            body=body,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(body)),
            },
        )
        response = connection.getresponse()
        return response.status, json.loads(response.read())

    def test_empty_graph_is_accepted_deterministic_and_roundtrippable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            first = build_storage_lineage(runtime)
            second = build_storage_lineage(runtime)
            self.assertEqual(first, second)
            self.assertTrue(first.accepted)
            self.assertEqual(first.node_count, 0)
            self.assertEqual(first.edge_count, 0)
            self.assertEqual(first.root_count, 0)
            self.assertTrue(first.connected)
            self.assertEqual(first.max_depth, 0)
            self.assertEqual(first.missing_addresses, ())
            self.assertEqual(first.orphan_addresses, ())
            self.assertEqual(first, StorageLineageGraph.from_mapping(first.to_dict()))
            self.assertEqual(storage_lineage_json(first), storage_lineage_json(second))
            self.assertIn("storage_lineage_version", first.to_dict())
            serialized = json.dumps(first.to_dict(), sort_keys=True).lower()
            for forbidden in (
                "agent_id",
                "assistant_name",
                "author_email",
                "language_name",
                "model_version",
                "patient_id",
                "subject_id",
            ):
                self.assertNotIn(forbidden, serialized)

    def test_populated_run_projects_root_and_reference_edges(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier = self._runtime(directory)
            graph = build_storage_lineage(runtime)
            self.assertTrue(graph.accepted)
            self.assertEqual(graph.root_count, 1)
            self.assertEqual(graph.node_count, 4)
            self.assertEqual(graph.edge_count, 5)
            self.assertEqual(graph.root_node_ids, (f"run:{dossier.run_id}",))
            self.assertEqual(
                sum(item.kind is StorageLineageEdgeKind.ROOT for item in graph.edges),
                3,
            )
            self.assertEqual(
                sum(item.kind is StorageLineageEdgeKind.REFERENCE for item in graph.edges),
                2,
            )
            self.assertEqual(graph.missing_node_count, 0)
            self.assertEqual(graph.orphan_node_count, 0)
            self.assertTrue(all(item.accepted for item in graph.nodes))
            self.assertTrue(all(item.accepted for item in graph.edges))
            self.assertEqual(
                tuple(item.node_id for item in graph.nodes),
                tuple(sorted(item.node_id for item in graph.nodes)),
            )
            self.assertEqual(
                tuple(item.edge_id for item in graph.edges),
                tuple(sorted(item.edge_id for item in graph.edges)),
            )
            run = next(item for item in graph.nodes if item.kind is StorageLineageNodeKind.RUN)
            self.assertTrue(run.root)
            self.assertEqual(run.depth, 0)
            self.assertEqual(run.out_degree, 3)
            self.assertEqual(run.in_degree, 0)
            objects = tuple(item for item in graph.nodes if item.kind is StorageLineageNodeKind.OBJECT)
            self.assertEqual(len(objects), 3)
            self.assertEqual(tuple(item.depth for item in objects), (1, 1, 1))

    def test_batch_projects_two_roots_and_preserves_object_addresses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _ = self._runtime(directory)
            batch = BatchRuntime(runtime=runtime).evaluate(
                [
                    fixture_manifest().to_dict(),
                    fixture_manifest().to_dict(),
                ]
            )
            graph = build_storage_lineage(runtime)
            self.assertTrue(graph.accepted)
            self.assertEqual(graph.root_count, 2)
            self.assertEqual(graph.batch_count if hasattr(graph, "batch_count") else sum(item.kind is StorageLineageNodeKind.BATCH for item in graph.nodes), 1)
            self.assertTrue(any(item.kind is StorageLineageNodeKind.BATCH for item in graph.nodes))
            batch_nodes = tuple(item for item in graph.nodes if item.kind is StorageLineageNodeKind.BATCH)
            self.assertEqual(len(batch_nodes), 1)
            batch_node = batch_nodes[0]
            self.assertEqual(batch_node.out_degree, 2)
            self.assertTrue(
                all(
                    item.kind is StorageLineageEdgeKind.ROOT
                    for item in graph.edges
                    if item.source_id == batch_node.node_id
                )
            )
            self.assertGreaterEqual(graph.object_node_count, 3)
            self.assertEqual(
                len({item.address for item in graph.nodes if item.address is not None}),
                graph.object_node_count,
            )
            self.assertTrue(batch.batch_id)

    def test_missing_reference_is_explicit_and_unresolved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier = self._runtime(directory)
            run_record = runtime.get_run(dossier.run_id)
            missing_address = str(run_record["dossier_address"])
            digest = missing_address.split(":", 1)[1]
            (runtime.store.store.objects / f"{digest}.json").unlink()
            graph = build_storage_lineage(runtime)
            self.assertFalse(graph.accepted)
            self.assertIn(missing_address, graph.missing_addresses)
            self.assertEqual(graph.missing_node_count, 1)
            missing = next(item for item in graph.nodes if item.kind is StorageLineageNodeKind.MISSING)
            self.assertEqual(missing.address, missing_address)
            self.assertFalse(missing.accepted)
            self.assertTrue(missing.referenced)
            self.assertIsNone(missing.path if not missing_address.startswith("sha256:") else None)
            edges = tuple(item for item in graph.edges if item.target_id == missing.node_id)
            self.assertTrue(edges)
            self.assertTrue(all(item.kind in (StorageLineageEdgeKind.ROOT, StorageLineageEdgeKind.MISSING_REFERENCE) for item in edges))
            self.assertTrue(all(not item.accepted for item in edges))

    def test_orphan_object_is_kept_in_graph_and_has_review_item(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _ = self._runtime(directory)
            orphan_address = runtime.store.store.put({"orphan": True})
            graph = build_storage_lineage(runtime)
            self.assertFalse(graph.accepted)
            self.assertIn(orphan_address, graph.orphan_addresses)
            orphan = next(item for item in graph.nodes if item.address == orphan_address)
            self.assertEqual(orphan.kind, StorageLineageNodeKind.ORPHAN)
            self.assertEqual(orphan.in_degree, 0)
            self.assertEqual(orphan.out_degree, 0)
            self.assertEqual(orphan.depth, 0)
            queue = build_storage_lineage_review_queue(graph)
            self.assertTrue(queue.accepted is False)
            item = next(item for item in queue.items if item.target_id == orphan.node_id)
            self.assertEqual(item.issue.value, "orphan-object")
            self.assertEqual(item.severity.value, "high")
            self.assertEqual(item.disposition.value, "inspect")
            self.assertIn(orphan_address, item.evidence)

    def test_object_payloads_never_enter_graph_projection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _ = self._runtime(directory)
            graph = build_storage_lineage(runtime)
            payload = json.dumps(graph.to_dict(), sort_keys=True)
            self.assertNotIn('"payload"', payload)
            self.assertNotIn('"events"', payload)
            self.assertNotIn('"records"', payload)
            for node in graph.nodes:
                self.assertIsInstance(node.to_dict(), dict)
                self.assertNotIn("content", node.to_dict())
                self.assertNotIn("value", node.to_dict())
            for edge in graph.edges:
                self.assertNotIn("content", edge.to_dict())
                self.assertNotIn("payload", edge.to_dict())

    def test_graph_filters_are_bounded_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _ = self._runtime(directory)
            graph = build_storage_lineage(runtime)
            nodes = query_storage_lineage(graph, resource="nodes", limit=2)
            self.assertEqual(nodes.total, graph.node_count)
            self.assertEqual(len(nodes.items), 2)
            self.assertTrue(nodes.has_more)
            self.assertEqual(nodes.items, query_storage_lineage(graph, resource="nodes", limit=2).items)
            roots = query_storage_lineage(graph, root_only=True)
            self.assertEqual(roots.total, graph.root_count)
            self.assertTrue(all(item["root"] for item in roots.items))
            objects = query_storage_lineage(graph, node_kind="object")
            self.assertEqual(objects.total, graph.object_node_count)
            edges = query_storage_lineage(graph, resource="edges", edge_kind="reference")
            self.assertEqual(edges.total, 2)
            self.assertTrue(all(item["kind"] == "reference" for item in edges.items))
            searched = query_storage_lineage(graph, text="run:")
            self.assertEqual(searched.total, 1)
            self.assertEqual(searched.items[0]["kind"], "run")
            for kwargs in (
                {"resource": "unknown"},
                {"node_kind": "unknown"},
                {"edge_kind": "unknown"},
                {"limit": 501},
                {"offset": -1},
            ):
                with self.assertRaises(ValidationError):
                    query_storage_lineage(graph, **kwargs)

    def test_graph_query_filters_missing_and_orphan_edges(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier = self._runtime(directory)
            runtime.store.store.put({"orphan": True})
            digest = str(runtime.get_run(dossier.run_id)["dossier_address"]).split(":", 1)[1]
            (runtime.store.store.objects / f"{digest}.json").unlink()
            graph = build_storage_lineage(runtime)
            missing_nodes = query_storage_lineage(graph, missing_only=True)
            orphan_nodes = query_storage_lineage(graph, orphan_only=True)
            self.assertEqual(missing_nodes.total, 1)
            self.assertEqual(orphan_nodes.total, 1)
            missing_edges = query_storage_lineage(graph, resource="edges", missing_only=True)
            self.assertGreaterEqual(missing_edges.total, 1)
            self.assertTrue(all(item["target_id"].startswith("missing:") for item in missing_edges.items))
            self.assertEqual(query_storage_lineage(graph, root_only=True, orphan_only=True).total, 0)
            self.assertEqual(query_storage_lineage(graph, root_only=True, missing_only=True).total, 0)

    def test_graph_diff_tracks_structural_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _ = self._runtime(directory)
            baseline = build_storage_lineage(runtime)
            runtime.store.store.put({"orphan": True})
            candidate = build_storage_lineage(runtime)
            result = diff_storage_lineage(baseline, candidate)
            self.assertTrue(result.accepted)
            self.assertNotEqual(baseline.content_address, candidate.content_address)
            self.assertTrue(result.added_node_ids)
            self.assertFalse(result.removed_node_ids)
            self.assertTrue(result.root_set_changed is False)
            self.assertTrue(result.missing_set_changed is False)
            self.assertTrue(result.orphan_set_changed)
            self.assertEqual(result, diff_storage_lineage(baseline.to_dict(), candidate.to_dict()))
            self.assertEqual(result, type(result).from_mapping(result.to_dict()))

    def test_export_formats_have_closed_headers_and_no_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _ = self._runtime(directory)
            graph = build_storage_lineage(runtime)
            nodes_csv = storage_lineage_nodes_csv(graph)
            edges_csv = storage_lineage_edges_csv(graph)
            markdown = storage_lineage_markdown(graph)
            self.assertIn("node_id", nodes_csv.splitlines()[0])
            self.assertIn("edge_id", edges_csv.splitlines()[0])
            self.assertIn("# Storage lineage graph", markdown)
            self.assertIn("Graph:", markdown)
            self.assertIn(graph.content_address, storage_lineage_json(graph))
            self.assertNotIn("payload", nodes_csv.lower())
            self.assertNotIn("payload", edges_csv.lower())
            self.assertEqual(nodes_csv, storage_lineage_nodes_csv(graph))
            self.assertEqual(edges_csv, storage_lineage_edges_csv(graph))
            self.assertEqual(markdown, storage_lineage_markdown(graph))

    def test_graph_contract_rejects_unknown_fields_and_bad_addresses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _ = self._runtime(directory)
            graph = build_storage_lineage(runtime)
            body = graph.to_dict()
            unknown = dict(body)
            unknown["unexpected"] = True
            with self.assertRaises(ValidationError):
                StorageLineageGraph.from_mapping(unknown)
            bad_address = dict(body)
            bad_address["content_address"] = "storage-lineage:tampered"
            with self.assertRaises(ValidationError):
                StorageLineageGraph.from_mapping(bad_address)
            bad_nodes = dict(body)
            bad_nodes["nodes"] = list(body["nodes"]) + [dict(body["nodes"][0])] if body["nodes"] else [{"node_id": "bad"}]
            with self.assertRaises(ValidationError):
                StorageLineageGraph.from_mapping(bad_nodes)

    def test_observability_is_addressed_timestamp_free_and_replayable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _ = self._runtime(directory)
            graph = build_storage_lineage(runtime)
            first = build_storage_lineage_observability(graph)
            second = build_storage_lineage_observability(graph)
            self.assertEqual(first, second)
            self.assertTrue(first.accepted)
            self.assertEqual(first.graph_address, graph.content_address)
            self.assertEqual(len(first.events), graph.node_count + graph.edge_count)
            self.assertEqual(len(first.metrics), 16)
            self.assertEqual(first, type(first).from_mapping(first.to_dict()))
            self.assertTrue(all(item.graph_address == graph.content_address for item in first.events))
            self.assertTrue(all(item.graph_address == graph.content_address for item in first.metrics))
            self.assertEqual(
                len(query_storage_lineage_events(first, event_type="node-seen")),
                graph.node_count,
            )
            self.assertEqual(
                len(query_storage_lineage_events(first, state="accepted")),
                graph.node_count + graph.edge_count,
            )
            self.assertEqual(
                query_storage_lineage_events(first, kind="reference")[0].kind,
                "reference",
            )
            self.assertIn("sequence", storage_lineage_events_csv(first).splitlines()[0])
            self.assertIn("name", storage_lineage_metrics_csv(first).splitlines()[0])
            self.assertIn(first.content_address, storage_lineage_observability_json(first))
            with self.assertRaises(ValidationError):
                query_storage_lineage_events(first, event_type="unknown")
            with self.assertRaises(ValidationError):
                query_storage_lineage_events(first, state="unknown")
            with self.assertRaises(ValidationError):
                query_storage_lineage_events(first, limit=501)

    def test_observability_reports_unresolved_and_orphan_states(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier = self._runtime(directory)
            runtime.store.store.put({"orphan": True})
            digest = str(runtime.get_run(dossier.run_id)["dossier_address"]).split(":", 1)[1]
            (runtime.store.store.objects / f"{digest}.json").unlink()
            graph = build_storage_lineage(runtime)
            observation = build_storage_lineage_observability(graph)
            self.assertFalse(observation.accepted)
            unresolved = query_storage_lineage_events(observation, state="unresolved")
            rejected = query_storage_lineage_events(observation, event_type="orphan-object")
            self.assertGreaterEqual(len(unresolved), 1)
            self.assertGreaterEqual(len(rejected), 1)
            metrics = {item.name: item.value for item in observation.metrics}
            self.assertGreaterEqual(metrics["missing_node_count"], 1)
            self.assertGreaterEqual(metrics["orphan_node_count"], 1)
            self.assertGreaterEqual(metrics["rejected_node_count"], 1)
            self.assertGreaterEqual(metrics["connected_component_count"], 2)

    def test_review_queue_is_priority_ordered_and_filterable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier = self._runtime(directory)
            runtime.store.store.put({"orphan": True})
            digest = str(runtime.get_run(dossier.run_id)["dossier_address"]).split(":", 1)[1]
            (runtime.store.store.objects / f"{digest}.json").unlink()
            graph = build_storage_lineage(runtime)
            queue = build_storage_lineage_review_queue(graph)
            self.assertFalse(queue.accepted)
            self.assertGreaterEqual(queue.item_count, 2)
            self.assertEqual(
                tuple(item.priority for item in queue.items),
                tuple(sorted((item.priority for item in queue.items), reverse=True)),
            )
            self.assertEqual(queue, type(queue).from_mapping(queue.to_dict()))
            critical = query_storage_lineage_review(queue, severity="critical")
            high = query_storage_lineage_review(queue, severity="high")
            self.assertTrue(all(item.severity.value == "critical" for item in critical))
            self.assertTrue(all(item.severity.value == "high" for item in high))
            self.assertGreaterEqual(len(critical), 1)
            self.assertGreaterEqual(len(high), 1)
            reconciliation = query_storage_lineage_review(queue, disposition="reconcile")
            self.assertTrue(all(item.disposition.value == "reconcile" for item in reconciliation))
            self.assertEqual(query_storage_lineage_review(queue, priority_min=101). __len__(), 0)
            self.assertIn("review_id", storage_lineage_review_csv(queue).splitlines()[0])
            self.assertIn("# Storage lineage review queue", storage_lineage_review_markdown(queue))
            self.assertIn(queue.content_address, storage_lineage_review_json(queue))
            with self.assertRaises(ValidationError):
                query_storage_lineage_review(queue, issue="unknown")
            with self.assertRaises(ValidationError):
                query_storage_lineage_review(queue, disposition="unknown")
            with self.assertRaises(ValidationError):
                query_storage_lineage_review(queue, limit=501)

    def test_empty_queue_contains_non_mutating_monitor_item(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            graph = build_storage_lineage(CaseRuntime(directory))
            queue = build_storage_lineage_review_queue(graph)
            self.assertTrue(queue.accepted)
            self.assertEqual(queue.item_count, 1)
            self.assertTrue(queue.requires_attention)
            item = queue.items[0]
            self.assertEqual(item.issue.value, "empty-graph")
            self.assertEqual(item.disposition.value, "monitor")
            self.assertEqual(item.severity.value, "info")
            self.assertEqual(query_storage_lineage_review(queue, issue="empty-graph")[0], item)

    def test_packet_has_fixed_artifact_set_and_exact_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _ = self._runtime(directory)
            graph = build_storage_lineage(runtime)
            packet = build_storage_lineage_packet(graph)
            self.assertTrue(packet.accepted)
            self.assertEqual(len(packet.artifacts), 10)
            self.assertEqual(
                tuple(item.artifact_id for item in packet.artifacts),
                (
                    "graph-json", "nodes-csv", "edges-csv", "summary-json", "schema-json",
                    "capabilities-json", "observability-json", "events-csv", "review-queue-json", "review-csv",
                ),
            )
            self.assertEqual(packet, type(packet).from_mapping(packet.to_dict()) if hasattr(type(packet), "from_mapping") else packet)
            self.assertEqual(packet.to_dict(), packet.to_dict())
            payloads = {item.artifact_id: item.content for item in packet.artifacts}
            self.assertIn(b"audit_address", payloads["graph-json"])
            self.assertNotIn(b"payload", payloads["graph-json"].lower())
            self.assertNotIn(b"agent", payloads["graph-json"].lower())
            self.assertEqual(storage_lineage_packet_json(packet), storage_lineage_packet_json(packet))
            destination = Path(directory) / "packet"
            self.assertEqual(write_storage_lineage_packet(packet, destination), destination)
            verification = verify_storage_lineage_packet(destination)
            self.assertTrue(verification.accepted, verification.to_dict())
            self.assertEqual(verification.checked_artifact_count, 10)
            self.assertEqual(verification.missing_paths, ())
            self.assertEqual(verification.unexpected_paths, ())
            self.assertEqual(verification.tampered_paths, ())
            self.assertEqual(verification.boundary_violations, ())
            offline = load_storage_lineage_packet(destination)
            self.assertEqual(offline.graph.content_address, graph.content_address)
            self.assertEqual(offline.observability.graph_address, graph.content_address)
            self.assertEqual(offline.review_queue.graph_address, graph.content_address)
            self.assertEqual(offline.verification, verification)

    def test_packet_refuses_nonempty_destination_unless_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            graph = build_storage_lineage(CaseRuntime(directory))
            packet = build_storage_lineage_packet(graph)
            destination = Path(directory) / "packet"
            destination.mkdir()
            (destination / "unrelated.txt").write_text("x", encoding="utf-8")
            with self.assertRaises(ValidationError):
                write_storage_lineage_packet(packet, destination)
            write_storage_lineage_packet(packet, destination, allow_existing=True)
            result = verify_storage_lineage_packet(destination)
            self.assertFalse(result.accepted)
            self.assertIn("unrelated.txt", result.unexpected_paths)

    def test_packet_detects_tamper_and_unknown_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            graph = build_storage_lineage(CaseRuntime(directory))
            packet = build_storage_lineage_packet(graph)
            destination = Path(directory) / "packet"
            write_storage_lineage_packet(packet, destination)
            graph_path = destination / "lineage" / "graph.json"
            graph_path.write_bytes(graph_path.read_bytes() + b" ")
            (destination / "lineage" / "extra.txt").write_text("extra", encoding="utf-8")
            result = verify_storage_lineage_packet(destination)
            self.assertFalse(result.accepted)
            self.assertIn("lineage/graph.json", result.tampered_paths)
            self.assertIn("lineage/extra.txt", result.unexpected_paths)
            with self.assertRaises(ValidationError):
                load_storage_lineage_packet(destination)

    def test_packet_detects_manifest_drift_and_boundary_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            graph = build_storage_lineage(CaseRuntime(directory))
            packet = build_storage_lineage_packet(graph)
            destination = Path(directory) / "packet"
            write_storage_lineage_packet(packet, destination)
            manifest_path = destination / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["packet_id"] = "changed"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = verify_storage_lineage_packet(destination)
            self.assertFalse(result.accepted)
            self.assertIn("manifest.content_address", result.manifest_drift)
            self.assertIn("manifest.contract", result.manifest_drift)

            destination2 = Path(directory) / "packet2"
            write_storage_lineage_packet(packet, destination2)
            csv_path = destination2 / "lineage" / "nodes.csv"
            csv_path.write_bytes(csv_path.read_bytes() + b"assistant")
            result2 = verify_storage_lineage_packet(destination2)
            self.assertFalse(result2.accepted)
            self.assertTrue(result2.boundary_violations)
            self.assertTrue(any("assistant" in value for value in result2.boundary_violations))

    def test_packet_capabilities_and_schemas_are_closed(self) -> None:
        graph_schema = storage_lineage_schema()
        graph_caps = storage_lineage_capabilities()
        observation_schema = storage_lineage_observability_schema()
        observation_caps = storage_lineage_observability_capabilities()
        review_schema = storage_lineage_review_schema()
        review_caps = storage_lineage_review_capabilities()
        packet_schema = storage_lineage_packet_schema()
        packet_caps = storage_lineage_packet_capabilities()
        self.assertEqual(graph_schema["version"], "storage-lineage-schema-v1")
        self.assertTrue(graph_caps["address_only"])
        self.assertFalse(graph_caps["payload_exposure"])
        self.assertEqual(observation_schema["version"], "storage-lineage-observability-schema-v1")
        self.assertTrue(observation_caps["deterministic_events"])
        self.assertFalse(observation_caps["payload_exposure"])
        self.assertEqual(review_schema["version"], "storage-lineage-review-schema-v1")
        self.assertTrue(review_caps["priority_ordering"])
        self.assertFalse(review_caps["payload_exposure"])
        self.assertEqual(packet_schema["payload_count"], 10)
        self.assertEqual(packet_schema["artifact_count"], 11)
        self.assertEqual(packet_caps["payload_ids"], tuple(packet_schema["payload_ids"]))
        self.assertTrue(packet_caps["exact_byte_verification"])
        self.assertFalse(packet_caps["source_payloads"])
        serialized = json.dumps(
            {
                "graph_schema": graph_schema,
                "graph_caps": graph_caps,
                "observation_schema": observation_schema,
                "observation_caps": observation_caps,
                "review_schema": review_schema,
                "review_caps": review_caps,
                "packet_schema": packet_schema,
                "packet_caps": packet_caps,
            },
            sort_keys=True,
        ).lower()
        self.assertNotIn("agent_id", serialized)
        self.assertNotIn("language_name", serialized)
        self.assertNotIn("model_name", serialized)

    def test_cli_graph_and_projection_commands_write_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _ = self._runtime(directory)
            commands = (
                ("storage-lineage", "lineage.json", []),
                ("storage-lineage", "nodes.csv", ["--format", "nodes-csv"]),
                ("storage-lineage", "edges.csv", ["--format", "edges-csv"]),
                ("storage-lineage", "lineage.md", ["--format", "markdown"]),
                ("storage-lineage-observability", "observability.json", []),
                ("storage-lineage-observability", "events.csv", ["--format", "events-csv"]),
                ("storage-lineage-observability", "metrics.csv", ["--format", "metrics-csv"]),
                ("storage-lineage-review", "review.json", []),
                ("storage-lineage-review", "review.csv", ["--format", "csv"]),
                ("storage-lineage-review", "review.md", ["--format", "markdown"]),
                ("storage-lineage-schema", "graph-schema.json", []),
                ("storage-lineage-capabilities", "graph-caps.json", []),
                ("storage-lineage-observability-schema", "obs-schema.json", []),
                ("storage-lineage-observability-capabilities", "obs-caps.json", []),
                ("storage-lineage-review-schema", "review-schema.json", []),
                ("storage-lineage-review-capabilities", "review-caps.json", []),
                ("storage-lineage-packet-schema", "packet-schema.json", []),
                ("storage-lineage-packet-capabilities", "packet-caps.json", []),
            )
            for command, filename, extra in commands:
                output = Path(directory) / filename
                args = [command, "--data-root", directory, *extra, "--output", str(output)]
                if command.endswith("-schema") or command.endswith("-capabilities"):
                    args = [command, "--output", str(output)]
                self.assertEqual(main(args), 0, command)
                self.assertTrue(output.is_file(), filename)
                self.assertGreater(output.stat().st_size, 0, filename)
            self.assertIn("node_id", (Path(directory) / "nodes.csv").read_text(encoding="utf-8"))
            self.assertIn("# Storage lineage graph", (Path(directory) / "lineage.md").read_text(encoding="utf-8"))
            self.assertIn("event_type", (Path(directory) / "events.csv").read_text(encoding="utf-8"))
            self.assertIn("review_id", (Path(directory) / "review.csv").read_text(encoding="utf-8"))
            graph_payload = json.loads((Path(directory) / "lineage.json").read_text(encoding="utf-8"))
            self.assertEqual(graph_payload["node_count"], 4)
            self.assertTrue(runtime.store.store.objects.exists())

    def test_cli_packet_verify_and_load_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            packet_directory = Path(directory) / "packet"
            output = Path(directory) / "packet.json"
            self.assertEqual(
                main(
                    [
                        "storage-lineage-packet",
                        "--data-root",
                        directory,
                        "--destination",
                        str(packet_directory),
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            packet_payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(packet_payload["destination"], str(packet_directory))
            verification_output = Path(directory) / "verify.json"
            self.assertEqual(
                main(
                    [
                        "storage-lineage-packet-verify",
                        str(packet_directory),
                        "--output",
                        str(verification_output),
                    ]
                ),
                0,
            )
            verification = json.loads(verification_output.read_text(encoding="utf-8"))
            self.assertTrue(verification["accepted"])
            load_output = Path(directory) / "load.json"
            self.assertEqual(
                main(
                    [
                        "storage-lineage-packet-load",
                        str(packet_directory),
                        "--output",
                        str(load_output),
                    ]
                ),
                0,
            )
            loaded = json.loads(load_output.read_text(encoding="utf-8"))
            self.assertEqual(loaded["verification"]["content_address"], verification["content_address"])
            self.assertEqual(loaded["graph"]["content_address"], packet_payload["graph_address"])

    def test_http_get_surfaces_match_local_addresses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _ = self._runtime(directory)
            graph = build_storage_lineage(runtime)
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                status, graph_payload = self._get(connection, "/v1/storage/lineage")
                self.assertEqual(status, 200)
                self.assertEqual(graph_payload["graph"]["content_address"], graph.content_address)
                status, query_payload = self._get(connection, "/v1/storage/lineage?resource=edges&edge_kind=reference")
                self.assertEqual(status, 200)
                self.assertEqual(query_payload["query"]["total"], 2)
                status, schema = self._get(connection, "/v1/storage/lineage/schema")
                self.assertEqual(status, 200)
                self.assertEqual(schema["version"], "storage-lineage-schema-v1")
                status, caps = self._get(connection, "/v1/storage/lineage/capabilities")
                self.assertEqual(status, 200)
                self.assertTrue(caps["address_only"])
                status, obs = self._get(connection, "/v1/storage/lineage/observability")
                self.assertEqual(status, 200)
                self.assertEqual(obs["graph_address"], graph.content_address)
                status, obs_query = self._get(connection, "/v1/storage/lineage/observability?event_type=node-seen")
                self.assertEqual(status, 200)
                self.assertEqual(len(obs_query["events"]), graph.node_count)
                status, review = self._get(connection, "/v1/storage/lineage/review")
                self.assertEqual(status, 200)
                self.assertEqual(review["queue"]["graph_address"], graph.content_address)
                status, packet = self._get(connection, "/v1/storage/lineage/packet")
                self.assertEqual(status, 200)
                self.assertEqual(packet["graph_address"], graph.content_address)
                status, packet_schema = self._get(connection, "/v1/storage/lineage/packet/schema")
                self.assertEqual(status, 200)
                self.assertEqual(packet_schema["payload_count"], 10)
                status, packet_caps = self._get(connection, "/v1/storage/lineage/packet/capabilities")
                self.assertEqual(status, 200)
                self.assertTrue(packet_caps["exact_byte_verification"])
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_http_csv_get_surfaces_and_post_graph_operations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _ = self._runtime(directory)
            graph = build_storage_lineage(runtime)
            observation = build_storage_lineage_observability(graph)
            queue = build_storage_lineage_review_queue(graph)
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                for path, marker in (
                    ("/v1/storage/lineage/nodes.csv", "node_id"),
                    ("/v1/storage/lineage/edges.csv", "edge_id"),
                    ("/v1/storage/lineage/observability/events.csv", "event_type"),
                    ("/v1/storage/lineage/observability/metrics.csv", "name"),
                ):
                    connection.request("GET", path)
                    response = connection.getresponse()
                    body = response.read().decode("utf-8")
                    self.assertEqual(response.status, 200, path)
                    self.assertIn(marker, body)
                status, verified = self._post(connection, "/v1/storage/lineage/verify", {"graph": graph.to_dict()})
                self.assertEqual(status, 200)
                self.assertEqual(verified["content_address"], graph.content_address)
                status, queried = self._post(
                    connection,
                    "/v1/storage/lineage/query",
                    {"graph": graph.to_dict(), "query": {"resource": "nodes", "node_kind": "run"}},
                )
                self.assertEqual(status, 200)
                self.assertEqual(queried["total"], 1)
                status, diff = self._post(
                    connection,
                    "/v1/storage/lineage/diff",
                    {"baseline": graph.to_dict(), "candidate": graph.to_dict()},
                )
                self.assertEqual(status, 200)
                self.assertFalse(diff["added_node_ids"])
                status, event_query = self._post(
                    connection,
                    "/v1/storage/lineage/observability/query",
                    {"observability": observation.to_dict(), "query": {"event_type": "edge-seen"}},
                )
                self.assertEqual(status, 200)
                self.assertEqual(event_query["count"], graph.edge_count)
                status, review_query = self._post(
                    connection,
                    "/v1/storage/lineage/review/query",
                    {"queue": queue.to_dict(), "query": {"disposition": "accepted"}},
                )
                self.assertEqual(status, 200)
                self.assertEqual(review_query["count"], 0)
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_http_rejects_invalid_graph_and_packet_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                status, payload = self._post(connection, "/v1/storage/lineage/verify", {"graph": {"bad": True}})
                self.assertIn(status, (400, 422))
                self.assertIn("error", payload)
                status, payload = self._post(connection, "/v1/storage/lineage/query", {"graph": {}, "query": {}})
                self.assertIn(status, (400, 422))
                self.assertIn("error", payload)
                status, payload = self._post(connection, "/v1/storage/lineage/packet/verify", {})
                self.assertEqual(status, 400)
                self.assertIn("error", payload)
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
