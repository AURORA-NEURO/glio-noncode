"""Typed source-to-result lineage graph for Domain 03 C13-C16."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .specimen_preanalytic_fixture_eval import evaluate_specimen_preanalytic_fixture
from .specimen_preanalytic_public_data import SpecimenPreanalyticFixtureCatalog


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticLineageNode:
    node_id: str
    kind: str
    address: str
    context_key: str
    state: str
    public: bool

    def __post_init__(self) -> None:
        for field in ("node_id", "kind", "address", "context_key", "state"):
            require_non_empty(str(getattr(self, field)), f"lineage {field}")
        if not self.address.startswith("sha256:"):
            raise ValueError("lineage node address must be sha256-prefixed")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticLineageEdge:
    source_node_id: str
    target_node_id: str
    relation: str

    def __post_init__(self) -> None:
        for field in ("source_node_id", "target_node_id", "relation"):
            require_non_empty(str(getattr(self, field)), f"lineage edge {field}")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticLineageGraph:
    graph_id: str
    fixture_id: str
    context_key: str
    nodes: tuple[SpecimenPreanalyticLineageNode, ...]
    edges: tuple[SpecimenPreanalyticLineageEdge, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.graph_id, "lineage graph ID")
        require_non_empty(self.fixture_id, "lineage fixture ID")
        if not self.nodes or not self.edges:
            raise ValueError("lineage graph requires nodes and edges")
        if not self.content_address.startswith("sha256:"):
            raise ValueError("lineage graph must be addressed")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
        }


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticLineageCheck:
    check_id: str
    passed: bool
    observed: Any
    expected: Any
    message: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticLineageAudit:
    graph_id: str
    state: str
    checks: tuple[SpecimenPreanalyticLineageCheck, ...]
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == "accepted" and all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed": self.passed, "failed_check_ids": self.failed_check_ids}


def build_specimen_preanalytic_lineage(
    catalog: SpecimenPreanalyticFixtureCatalog,
    *,
    graph_id: str = "specimen-preanalytic-c13-c16-lineage",
) -> SpecimenPreanalyticLineageGraph:
    evaluation = evaluate_specimen_preanalytic_fixture(catalog)
    nodes: list[SpecimenPreanalyticLineageNode] = []
    edges: list[SpecimenPreanalyticLineageEdge] = []
    fixture_node = f"fixture:{catalog.fixture_id}"
    for receipt in catalog.source_receipts:
        source_node = f"source:{receipt.source_id}"
        nodes.append(
            SpecimenPreanalyticLineageNode(
                source_node,
                "public_source",
                receipt.content_address,
                catalog.context_key,
                "declared",
                True,
            )
        )
        edges.append(SpecimenPreanalyticLineageEdge(source_node, fixture_node, "declares"))
    nodes.append(
        SpecimenPreanalyticLineageNode(
            fixture_node, "fixture", catalog.content_address, catalog.context_key, "accepted", True
        )
    )
    for record, receipt in zip(catalog.records, evaluation.receipts, strict=True):
        record_node = f"record:{record.record_id}"
        result_node = f"result:{record.record_id}"
        nodes.append(
            SpecimenPreanalyticLineageNode(
                record_node,
                "fixture_record",
                record.content_address,
                record.context_key,
                record.expected_state.value,
                True,
            )
        )
        nodes.append(
            SpecimenPreanalyticLineageNode(
                result_node,
                "sanitized_result",
                receipt.output_address,
                receipt.context_key,
                receipt.observed_state,
                True,
            )
        )
        edges.append(SpecimenPreanalyticLineageEdge(fixture_node, record_node, "contains"))
        edges.append(SpecimenPreanalyticLineageEdge(record_node, result_node, "produces"))
    body = {
        "graph_id": graph_id,
        "fixture_id": catalog.fixture_id,
        "context_key": catalog.context_key,
        "nodes": nodes,
        "edges": edges,
    }
    return SpecimenPreanalyticLineageGraph(
        graph_id,
        catalog.fixture_id,
        catalog.context_key,
        tuple(nodes),
        tuple(edges),
        content_hash(body),
    )


def audit_specimen_preanalytic_lineage(
    graph: SpecimenPreanalyticLineageGraph,
) -> SpecimenPreanalyticLineageAudit:
    nodes = {node.node_id: node for node in graph.nodes}
    checks: list[SpecimenPreanalyticLineageCheck] = []

    def add(check_id: str, passed: bool, observed: Any, expected: Any, message: str) -> None:
        checks.append(
            SpecimenPreanalyticLineageCheck(check_id, bool(passed), observed, expected, message)
        )

    source_nodes = tuple(node for node in graph.nodes if node.kind == "public_source")
    record_nodes = tuple(node for node in graph.nodes if node.kind == "fixture_record")
    result_nodes = tuple(node for node in graph.nodes if node.kind == "sanitized_result")
    add(
        "fixture-root",
        f"fixture:{graph.fixture_id}" in nodes,
        tuple(nodes),
        f"fixture:{graph.fixture_id}",
        "fixture root exists",
    )
    add(
        "source-floor",
        len(source_nodes) == 4,
        len(source_nodes),
        4,
        "four public sources are rooted",
    )
    add("record-floor", len(record_nodes) == 12, len(record_nodes), 12, "twelve records are rooted")
    add("result-floor", len(result_nodes) == 12, len(result_nodes), 12, "twelve results are rooted")
    add(
        "node-identity",
        len(nodes) == len(graph.nodes),
        len(nodes),
        len(graph.nodes),
        "node IDs are unique",
    )
    add(
        "edge-endpoints",
        all(edge.source_node_id in nodes and edge.target_node_id in nodes for edge in graph.edges),
        True,
        True,
        "all edges resolve",
    )
    add(
        "relation-vocabulary",
        {edge.relation for edge in graph.edges} == {"declares", "contains", "produces"},
        {edge.relation for edge in graph.edges},
        {"declares", "contains", "produces"},
        "relations are typed",
    )
    add(
        "source-roots",
        all(
            edge.relation == "declares" and edge.source_node_id.startswith("source:")
            for edge in graph.edges
            if edge.relation == "declares"
        ),
        True,
        True,
        "source edges are rooted",
    )
    add(
        "record-containment",
        sum(edge.relation == "contains" for edge in graph.edges) == 12,
        sum(edge.relation == "contains" for edge in graph.edges),
        12,
        "fixture contains twelve records",
    )
    add(
        "result-production",
        sum(edge.relation == "produces" for edge in graph.edges) == 12,
        sum(edge.relation == "produces" for edge in graph.edges),
        12,
        "records produce twelve results",
    )
    add(
        "context-consistency",
        all(node.context_key == graph.context_key for node in graph.nodes),
        True,
        True,
        "all nodes use exact context",
    )
    add(
        "address-floor",
        all(node.address.startswith("sha256:") for node in graph.nodes),
        True,
        True,
        "all nodes are addressed",
    )
    add(
        "public-boundary",
        all(node.public for node in graph.nodes),
        True,
        True,
        "graph nodes are public projections",
    )
    add(
        "graph-address",
        graph.content_address
        == content_hash(
            {
                "graph_id": graph.graph_id,
                "fixture_id": graph.fixture_id,
                "context_key": graph.context_key,
                "nodes": graph.nodes,
                "edges": graph.edges,
            }
        ),
        graph.content_address,
        "sha256:<recomputed>",
        "graph address is deterministic",
    )
    add(
        "sanitized-projection",
        not _forbidden_keys(graph.to_dict()),
        True,
        True,
        "graph omits raw payload fields",
    )
    state = "accepted" if all(check.passed for check in checks) else "review"
    body = {"graph_id": graph.graph_id, "state": state, "checks": checks}
    return SpecimenPreanalyticLineageAudit(graph.graph_id, state, tuple(checks), content_hash(body))


def _forbidden_keys(value: Any) -> tuple[str, ...]:
    forbidden = {
        "records",
        "raw_records",
        "payload",
        "patient_id",
        "subject_id",
        "medical_record_number",
        "sample_patient_id",
        "participant_id",
        "case_uuid",
        "individual_id",
        "person_id",
    }
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key).lower() in forbidden:
                found.add(str(key).lower())
            found.update(_forbidden_keys(nested))
    elif isinstance(value, (list, tuple)):
        for nested in value:
            found.update(_forbidden_keys(nested))
    return tuple(sorted(found))


__all__ = [
    "SpecimenPreanalyticLineageAudit",
    "SpecimenPreanalyticLineageCheck",
    "SpecimenPreanalyticLineageEdge",
    "SpecimenPreanalyticLineageGraph",
    "SpecimenPreanalyticLineageNode",
    "audit_specimen_preanalytic_lineage",
    "build_specimen_preanalytic_lineage",
]
