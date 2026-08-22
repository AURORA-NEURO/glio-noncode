"""Typed execution adapters for the Domain 09 C09-C12 fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha import BoundaryMotifOrientationAnalyzer, CTCFCohesinDisruptionModel, IDHInsulatorDysfunctionModel, SVTopologyRewiringSimulator, TopologyAlphaState
from .topology_alpha_frontier_public_data import TOPOLOGY_ALPHA_FRONTIER_CONTEXT_KEY, TopologyAlphaFrontierOperation, TopologyAlphaFrontierRecord


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierAdapterSpec:
    operation: TopologyAlphaFrontierOperation
    adapter_id: str
    primitive: str
    input_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    state_rules: tuple[str, ...]
    limitation: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierAdapterResult:
    record_id: str
    operation: TopologyAlphaFrontierOperation
    state: str
    primitive_state: str
    issue_codes: tuple[str, ...]
    measurements: dict[str, Any]
    source_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierAdapterRegistry:
    specs: tuple[TopologyAlphaFrontierAdapterSpec, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: TopologyAlphaFrontierOperation | str) -> TopologyAlphaFrontierAdapterSpec:
        value = TopologyAlphaFrontierOperation(str(operation))
        for spec in self.specs:
            if spec.operation is value:
                return spec
        raise KeyError(value)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"specs": [item.to_dict() for item in self.specs], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _result(record: TopologyAlphaFrontierRecord, primitive_state: str, state: str | None = None, *, issue_codes: tuple[str, ...] = (), measurements: dict[str, Any] | None = None, evidence_ids: tuple[str, ...] = ()) -> TopologyAlphaFrontierAdapterResult:
    value = state or primitive_state
    return TopologyAlphaFrontierAdapterResult(record.record_id, record.operation, value, primitive_state, issue_codes, measurements or {}, record.source_ids, evidence_ids, content_hash({"record_id": record.record_id, "operation": record.operation, "state": value, "primitive_state": primitive_state, "issues": issue_codes, "measurements": measurements or {}, "evidence_ids": evidence_ids}))


def _motif(record: TopologyAlphaFrontierRecord) -> TopologyAlphaFrontierAdapterResult:
    payload = record.payload
    report = BoundaryMotifOrientationAnalyzer().analyze(payload.get("records", ()), context_key=TOPOLOGY_ALPHA_FRONTIER_CONTEXT_KEY, minimum_score=0.5)
    issues = [item.code for item in report.issues]
    if report.state is TopologyAlphaState.AMBIGUOUS:
        issues.append("orientation_ambiguity")
    return _result(record, report.state.value, issue_codes=tuple(dict.fromkeys(issues)), measurements={"observation_count": len(report.observations), "result_count": len(report.results), "relationship_labels": sorted({label for item in report.results for label in item.relationship_labels}), "median_scores": [item.median_score for item in report.results], "source_ids": sorted({source for item in report.results for source in item.source_ids}), "raw_hash_count": len({raw for item in report.results for raw in item.raw_hashes})}, evidence_ids=tuple(item.observation_id for item in report.observations))


def _ctcf(record: TopologyAlphaFrontierRecord) -> TopologyAlphaFrontierAdapterResult:
    payload = record.payload
    report = CTCFCohesinDisruptionModel().analyze(payload.get("records", ()), context_key=TOPOLOGY_ALPHA_FRONTIER_CONTEXT_KEY, disruption_threshold=0.2)
    issues = [item.code for item in report.issues]
    if report.state is TopologyAlphaState.AMBIGUOUS:
        issues.append("channel_disagreement")
    return _result(record, report.state.value, issue_codes=tuple(dict.fromkeys(issues)), measurements={"result_count": len(report.results), "labels": sorted({item.disruption_label for item in report.results}), "ctcf_deltas": [item.ctcf_delta for item in report.results], "cohesin_deltas": [item.cohesin_delta for item in report.results], "combined_deltas": [item.combined_delta for item in report.results], "source_ids": sorted({source for item in report.results for source in item.source_ids}), "raw_hash_count": len({raw for item in report.results for raw in item.raw_hashes})}, evidence_ids=tuple(item.variant_id for item in report.results))


def _idh(record: TopologyAlphaFrontierRecord) -> TopologyAlphaFrontierAdapterResult:
    payload = record.payload
    report = IDHInsulatorDysfunctionModel().assess(payload.get("records", ()), context_key=TOPOLOGY_ALPHA_FRONTIER_CONTEXT_KEY, dysfunction_threshold=0.2)
    return _result(record, report.state.value, issue_codes=tuple(item.code for item in report.issues), measurements={"result_count": len(report.results), "labels": sorted({item.label for item in report.results}), "insulator_deltas": [item.insulator_delta for item in report.results], "dysfunction_indices": [item.dysfunction_index for item in report.results], "mutant_methylation": [item.mutant_methylation for item in report.results], "wildtype_methylation": [item.wildtype_methylation for item in report.results], "source_ids": sorted({source for item in report.results for source in item.source_ids}), "raw_hash_count": len({raw for item in report.results for raw in item.raw_hashes})}, evidence_ids=tuple(item.region_id for item in report.results))


def _sv(record: TopologyAlphaFrontierRecord) -> TopologyAlphaFrontierAdapterResult:
    payload = record.payload
    report = SVTopologyRewiringSimulator().simulate(payload.get("contacts", ()), payload.get("events", ()), context_key=TOPOLOGY_ALPHA_FRONTIER_CONTEXT_KEY)
    return _result(record, report.state.value, issue_codes=tuple(item.code for item in report.issues), measurements={"contact_count": len(payload.get("contacts", ())), "event_count": len(payload.get("events", ())), "result_count": len(report.results), "lost_edges": [item.lost_edge_ids for item in report.results], "gained_edges": [item.gained_edge_ids for item in report.results], "rewired_edges": [item.rewired_edge_ids for item in report.results], "preserved_edges": [item.preserved_edge_ids for item in report.results], "affected_nodes": [item.affected_node_ids for item in report.results], "source_ids": sorted({source for item in report.results for source in item.source_ids}), "raw_hash_count": len({raw for item in report.results for raw in item.raw_hashes})}, evidence_ids=tuple(item.sv_id for item in report.results))


def execute_topology_alpha_frontier_record(record: TopologyAlphaFrontierRecord) -> TopologyAlphaFrontierAdapterResult:
    if record.operation is TopologyAlphaFrontierOperation.BOUNDARY_MOTIF:
        return _motif(record)
    if record.operation is TopologyAlphaFrontierOperation.CTCF_COHESIN:
        return _ctcf(record)
    if record.operation is TopologyAlphaFrontierOperation.IDH_INSULATOR:
        return _idh(record)
    if record.operation is TopologyAlphaFrontierOperation.SV_REWIRE:
        return _sv(record)
    raise ValueError(f"unsupported topology alpha frontier operation: {record.operation}")


def build_topology_alpha_frontier_adapters() -> TopologyAlphaFrontierAdapterRegistry:
    specs = (
        TopologyAlphaFrontierAdapterSpec(TopologyAlphaFrontierOperation.BOUNDARY_MOTIF, "d09-c09-boundary-motif", "BoundaryMotifOrientationAnalyzer", ("records", "boundary_id", "side", "orientation", "context_key"), ("relationship_labels", "left_orientations", "right_orientations", "median_score"), ("supported", "partial", "ambiguous", "out_of_domain"), "Orientation is a boundary observation, not insulation proof."),
        TopologyAlphaFrontierAdapterSpec(TopologyAlphaFrontierOperation.CTCF_COHESIN, "d09-c10-ctcf-cohesin", "CTCFCohesinDisruptionModel", ("records", "variant_id", "reference_ctcf", "alternate_ctcf", "context_key"), ("ctcf_delta", "cohesin_delta", "combined_delta", "disruption_label"), ("supported", "partial", "ambiguous", "out_of_domain"), "Channel comparison is descriptive and retains missingness."),
        TopologyAlphaFrontierAdapterSpec(TopologyAlphaFrontierOperation.IDH_INSULATOR, "d09-c11-idh-insulator", "IDHInsulatorDysfunctionModel", ("records", "region_id", "molecular_state", "insulator_score", "context_key"), ("insulator_delta", "dysfunction_index", "methylation_channels", "label"), ("supported", "partial", "out_of_domain"), "Methylation remains separate from the insulator score."),
        TopologyAlphaFrontierAdapterSpec(TopologyAlphaFrontierOperation.SV_REWIRE, "d09-c12-sv-rewire", "SVTopologyRewiringSimulator", ("contacts", "events", "deleted_edge_ids", "gained_edge_ids", "rewired_edge_ids", "context_key"), ("preserved_edges", "lost_edges", "gained_edges", "rewired_edges", "affected_nodes"), ("supported", "partial", "out_of_domain"), "Declared edge simulation is not a 3D structure prediction."),
    )
    return TopologyAlphaFrontierAdapterRegistry(specs, len(specs) == 4)


__all__ = ["TopologyAlphaFrontierAdapterRegistry", "TopologyAlphaFrontierAdapterResult", "TopologyAlphaFrontierAdapterSpec", "build_topology_alpha_frontier_adapters", "execute_topology_alpha_frontier_record"]
