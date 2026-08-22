"""Closed public aggregate fixture for Domain 09 C09-C12."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .topology_alpha import TopologyAlphaState

TOPOLOGY_ALPHA_FRONTIER_FIXTURE_VERSION = "2026.08.d09-c09-c12.v1"
TOPOLOGY_ALPHA_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|tumor|unknown"
TOPOLOGY_ALPHA_FRONTIER_FOREIGN_CONTEXT_KEY = "GRCh38|glioma|pediatric|stem_like|tumor|unknown"
TOPOLOGY_ALPHA_FRONTIER_BOUNDARY = "public_aggregate_non_patient"


class TopologyAlphaFrontierOperation(StrEnum):
    BOUNDARY_MOTIF = "boundary_motif"
    CTCF_COHESIN = "ctcf_cohesin"
    IDH_INSULATOR = "idh_insulator"
    SV_REWIRE = "sv_rewire"


class TopologyAlphaFrontierRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierSource:
    source_id: str
    source_kind: str
    source_version: str
    uri: str
    checksum: str
    context_key: str
    public_aggregate: bool = True
    receipt_fields: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("source_id", "source_kind", "source_version", "uri", "checksum", "context_key"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.public_aggregate:
            raise ValidationError("topology alpha frontier sources must be public aggregates")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierRecord:
    record_id: str
    operation: TopologyAlphaFrontierOperation
    role: TopologyAlphaFrontierRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    expected_state: str
    expected_issue_codes: tuple[str, ...] = ()
    expected_measurements: Mapping[str, Any] = field(default_factory=dict)
    content_address: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.record_id, "record_id")
        require_non_empty(self.context_key, "context_key")
        if not self.source_ids:
            raise ValidationError("topology alpha frontier records need source receipts")
        if self.expected_state not in {item.value for item in TopologyAlphaState}:
            raise ValidationError(f"unknown topology alpha state: {self.expected_state}")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"record_id": self.record_id, "operation": self.operation, "role": self.role, "context_key": self.context_key, "source_ids": self.source_ids, "payload": dict(self.payload), "expected_state": self.expected_state, "expected_issue_codes": self.expected_issue_codes, "expected_measurements": dict(self.expected_measurements)}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierFixture:
    fixture_id: str
    version: str
    context_key: str
    foreign_context_key: str
    boundary: str
    sources: tuple[TopologyAlphaFrontierSource, ...]
    records: tuple[TopologyAlphaFrontierRecord, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        for name in ("fixture_id", "version", "context_key", "foreign_context_key", "boundary"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash({"fixture_id": self.fixture_id, "version": self.version, "sources": self.sources, "records": self.records}))

    @property
    def positive_records(self) -> tuple[TopologyAlphaFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is TopologyAlphaFrontierRole.POSITIVE)

    @property
    def control_records(self) -> tuple[TopologyAlphaFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is TopologyAlphaFrontierRole.CONTROL)

    def operation_records(self, operation: TopologyAlphaFrontierOperation | str) -> tuple[TopologyAlphaFrontierRecord, ...]:
        value = TopologyAlphaFrontierOperation(str(operation))
        return tuple(item for item in self.records if item.operation is value)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "version": self.version, "context_key": self.context_key, "foreign_context_key": self.foreign_context_key, "boundary": self.boundary, "sources": [item.to_dict() for item in self.sources], "records": [item.to_dict() for item in self.records]}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierDataAudit:
    fixture_id: str
    accepted: bool
    checks: tuple[str, ...]
    record_count: int
    source_count: int
    positive_count: int
    control_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "accepted": self.accepted, "checks": self.checks, "record_count": self.record_count, "source_count": self.source_count, "positive_count": self.positive_count, "control_count": self.control_count}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _source(source_id: str, kind: str, version: str, uri: str) -> TopologyAlphaFrontierSource:
    return TopologyAlphaFrontierSource(source_id, kind, version, uri, content_hash({"source_id": source_id, "version": version, "uri": uri}), TOPOLOGY_ALPHA_FRONTIER_CONTEXT_KEY, receipt_fields={"scope": "aggregate", "access": "public", "schema": "locked"})


def _motif(context_key: str, *, side: str = "both", mixed: bool = False) -> dict[str, Any]:
    rows = [{"boundary_id": "b-1", "chromosome": "7", "boundary_position": 1000, "side": "left", "motif_id": "m-left", "orientation": "+", "score": 0.9, "context_key": context_key, "source_id": "boundary-motif-aggregate", "source_version": "motif-v2"}]
    if side == "both":
        rows.append({"boundary_id": "b-1", "chromosome": "7", "boundary_position": 1000, "side": "right", "motif_id": "m-right", "orientation": "-", "score": 0.8, "context_key": context_key, "source_id": "boundary-motif-aggregate", "source_version": "motif-v2"})
    if mixed:
        rows.extend([{**rows[0], "observation_id": "left-alt", "motif_id": "m-left-alt", "orientation": "-"}, {**rows[-1], "observation_id": "right-alt", "motif_id": "m-right-alt", "orientation": "+"}])
    return {"records": rows, "target_context_key": TOPOLOGY_ALPHA_FRONTIER_CONTEXT_KEY, "public_aggregate": True}


def _ctcf(context_key: str, *, channels: str = "both", opposing: bool = False) -> dict[str, Any]:
    row = {"variant_id": "v-1", "reference_ctcf": 0.9, "alternate_ctcf": 0.4, "context_key": context_key, "source_id": "ctcf-cohesin-aggregate", "source_version": "ctcf-v3"}
    if channels == "both":
        row.update({"reference_cohesin": 0.8, "alternate_cohesin": 0.5})
    if opposing:
        row.update({"reference_cohesin": 0.4, "alternate_cohesin": 0.9})
    return {"records": [row], "target_context_key": TOPOLOGY_ALPHA_FRONTIER_CONTEXT_KEY, "public_aggregate": True}


def _idh(context_key: str, *, states: str = "both") -> dict[str, Any]:
    rows = [{"region_id": "ins-1", "molecular_state": "IDH-mutant", "insulator_score": 0.3, "methylation_fraction": 0.8, "context_key": context_key, "source_id": "idh-insulator-aggregate", "source_version": "idh-v2"}]
    if states == "both":
        rows.append({**rows[0], "molecular_state": "IDH-wildtype", "insulator_score": 0.8, "methylation_fraction": 0.2})
    if states == "invalid":
        rows[0]["molecular_state"] = "IDH-unknown"
    return {"records": rows, "target_context_key": TOPOLOGY_ALPHA_FRONTIER_CONTEXT_KEY, "public_aggregate": True}


def _sv(context_key: str, *, edits: bool = True, unknown: bool = False) -> dict[str, Any]:
    contacts = [{"edge_id": "e-1", "source_node": "n-1", "target_node": "n-2", "context_key": context_key, "source_id": "sv-topology-aggregate", "source_version": "sv-v4"}, {"edge_id": "e-2", "source_node": "n-2", "target_node": "n-3", "context_key": context_key, "source_id": "sv-topology-aggregate", "source_version": "sv-v4"}]
    event = {"sv_id": "sv-1", "sv_kind": "deletion", "context_key": context_key, "source_id": "sv-topology-aggregate", "source_version": "sv-v4", "affected_node_ids": ["n-1", "n-2", "n-3"]}
    if edits:
        event.update({"deleted_edge_ids": ["e-1"], "gained_edge_ids": ["e-3"], "rewired_edge_ids": ["e-2"]})
    if unknown:
        event["deleted_edge_ids"] = ["e-unknown"]
    return {"contacts": contacts, "events": [event], "target_context_key": TOPOLOGY_ALPHA_FRONTIER_CONTEXT_KEY, "public_aggregate": True}


def _records() -> tuple[TopologyAlphaFrontierRecord, ...]:
    c = TOPOLOGY_ALPHA_FRONTIER_CONTEXT_KEY
    f = TOPOLOGY_ALPHA_FRONTIER_FOREIGN_CONTEXT_KEY
    return (
        TopologyAlphaFrontierRecord("D09-C09-P", TopologyAlphaFrontierOperation.BOUNDARY_MOTIF, TopologyAlphaFrontierRole.POSITIVE, c, ("boundary-motif-aggregate",), _motif(c), "supported", expected_measurements={"result_count": 1}),
        TopologyAlphaFrontierRecord("D09-C09-C1", TopologyAlphaFrontierOperation.BOUNDARY_MOTIF, TopologyAlphaFrontierRole.CONTROL, c, ("boundary-motif-aggregate",), _motif(c, side="left"), "partial", expected_measurements={"result_count": 1}),
        TopologyAlphaFrontierRecord("D09-C09-C2", TopologyAlphaFrontierOperation.BOUNDARY_MOTIF, TopologyAlphaFrontierRole.CONTROL, c, ("boundary-motif-aggregate",), _motif(c, mixed=True), "ambiguous", ("orientation_ambiguity",), {"result_count": 1}),
        TopologyAlphaFrontierRecord("D09-C09-C3", TopologyAlphaFrontierOperation.BOUNDARY_MOTIF, TopologyAlphaFrontierRole.CONTROL, f, ("boundary-motif-aggregate",), _motif(f), "out_of_domain", ("context_mismatch",), {"result_count": 0}),
        TopologyAlphaFrontierRecord("D09-C10-P", TopologyAlphaFrontierOperation.CTCF_COHESIN, TopologyAlphaFrontierRole.POSITIVE, c, ("ctcf-cohesin-aggregate",), _ctcf(c), "supported", expected_measurements={"result_count": 1}),
        TopologyAlphaFrontierRecord("D09-C10-C1", TopologyAlphaFrontierOperation.CTCF_COHESIN, TopologyAlphaFrontierRole.CONTROL, c, ("ctcf-cohesin-aggregate",), _ctcf(c, channels="ctcf"), "partial", expected_measurements={"result_count": 1}),
        TopologyAlphaFrontierRecord("D09-C10-C2", TopologyAlphaFrontierOperation.CTCF_COHESIN, TopologyAlphaFrontierRole.CONTROL, c, ("ctcf-cohesin-aggregate",), _ctcf(c, opposing=True), "ambiguous", ("channel_disagreement",), {"result_count": 1}),
        TopologyAlphaFrontierRecord("D09-C10-C3", TopologyAlphaFrontierOperation.CTCF_COHESIN, TopologyAlphaFrontierRole.CONTROL, f, ("ctcf-cohesin-aggregate",), _ctcf(f), "out_of_domain", ("context_mismatch",), {"result_count": 0}),
        TopologyAlphaFrontierRecord("D09-C11-P", TopologyAlphaFrontierOperation.IDH_INSULATOR, TopologyAlphaFrontierRole.POSITIVE, c, ("idh-insulator-aggregate",), _idh(c), "supported", expected_measurements={"result_count": 1}),
        TopologyAlphaFrontierRecord("D09-C11-C1", TopologyAlphaFrontierOperation.IDH_INSULATOR, TopologyAlphaFrontierRole.CONTROL, c, ("idh-insulator-aggregate",), _idh(c, states="mutant_only"), "partial", expected_measurements={"result_count": 1}),
        TopologyAlphaFrontierRecord("D09-C11-C2", TopologyAlphaFrontierOperation.IDH_INSULATOR, TopologyAlphaFrontierRole.CONTROL, c, ("idh-insulator-aggregate",), _idh(c, states="invalid"), "partial", ("invalid_idh_insulator_row",), {"result_count": 0}),
        TopologyAlphaFrontierRecord("D09-C11-C3", TopologyAlphaFrontierOperation.IDH_INSULATOR, TopologyAlphaFrontierRole.CONTROL, f, ("idh-insulator-aggregate",), _idh(f), "out_of_domain", ("context_mismatch",), {"result_count": 0}),
        TopologyAlphaFrontierRecord("D09-C12-P", TopologyAlphaFrontierOperation.SV_REWIRE, TopologyAlphaFrontierRole.POSITIVE, c, ("sv-topology-aggregate",), _sv(c), "supported", expected_measurements={"result_count": 1}),
        TopologyAlphaFrontierRecord("D09-C12-C1", TopologyAlphaFrontierOperation.SV_REWIRE, TopologyAlphaFrontierRole.CONTROL, c, ("sv-topology-aggregate",), _sv(c, edits=False), "partial", expected_measurements={"result_count": 1}),
        TopologyAlphaFrontierRecord("D09-C12-C2", TopologyAlphaFrontierOperation.SV_REWIRE, TopologyAlphaFrontierRole.CONTROL, c, ("sv-topology-aggregate",), _sv(c, edits=False, unknown=True), "partial", expected_measurements={"result_count": 1}),
        TopologyAlphaFrontierRecord("D09-C12-C3", TopologyAlphaFrontierOperation.SV_REWIRE, TopologyAlphaFrontierRole.CONTROL, f, ("sv-topology-aggregate",), _sv(f), "out_of_domain", ("context_mismatch",), {"result_count": 0}),
    )


def default_topology_alpha_frontier_fixture() -> TopologyAlphaFrontierFixture:
    return TopologyAlphaFrontierFixture("topology-alpha-frontier-fixture", TOPOLOGY_ALPHA_FRONTIER_FIXTURE_VERSION, TOPOLOGY_ALPHA_FRONTIER_CONTEXT_KEY, TOPOLOGY_ALPHA_FRONTIER_FOREIGN_CONTEXT_KEY, TOPOLOGY_ALPHA_FRONTIER_BOUNDARY, (_source("boundary-motif-aggregate", "boundary_motif_aggregate", "motif-v2", "https://data.example.org/topology/boundary-motif-v2"), _source("ctcf-cohesin-aggregate", "ctcf_cohesin_aggregate", "ctcf-v3", "https://data.example.org/topology/ctcf-cohesin-v3"), _source("idh-insulator-aggregate", "idh_insulator_aggregate", "idh-v2", "https://data.example.org/topology/idh-insulator-v2"), _source("sv-topology-aggregate", "sv_topology_aggregate", "sv-v4", "https://data.example.org/topology/sv-v4")), _records())


def audit_topology_alpha_frontier_data(fixture: TopologyAlphaFrontierFixture) -> TopologyAlphaFrontierDataAudit:
    checks = ["record_count" if len(fixture.records) == 16 else "record_count_failed", "source_count" if len(fixture.sources) == 4 else "source_count_failed", "operation_balance" if all(len(fixture.operation_records(item)) == 4 for item in TopologyAlphaFrontierOperation) else "operation_balance_failed", "positive_balance" if len(fixture.positive_records) == 4 else "positive_balance_failed", "control_balance" if len(fixture.control_records) == 12 else "control_balance_failed", "aggregate_boundary" if fixture.boundary == TOPOLOGY_ALPHA_FRONTIER_BOUNDARY else "aggregate_boundary_failed", "source_receipts" if all(item.public_aggregate for item in fixture.sources) else "source_receipts_failed", "record_sources" if all(set(item.source_ids) <= {source.source_id for source in fixture.sources} for item in fixture.records) else "record_sources_failed"]
    return TopologyAlphaFrontierDataAudit(fixture.fixture_id, all(not item.endswith("_failed") for item in checks), tuple(checks), len(fixture.records), len(fixture.sources), len(fixture.positive_records), len(fixture.control_records))


def fixture_json(fixture: TopologyAlphaFrontierFixture | None = None) -> str:
    return json.dumps((fixture or default_topology_alpha_frontier_fixture()).to_dict(), sort_keys=True, indent=2)


__all__ = ["TOPOLOGY_ALPHA_FRONTIER_BOUNDARY", "TOPOLOGY_ALPHA_FRONTIER_CONTEXT_KEY", "TOPOLOGY_ALPHA_FRONTIER_FIXTURE_VERSION", "TOPOLOGY_ALPHA_FRONTIER_FOREIGN_CONTEXT_KEY", "TopologyAlphaFrontierDataAudit", "TopologyAlphaFrontierFixture", "TopologyAlphaFrontierOperation", "TopologyAlphaFrontierRecord", "TopologyAlphaFrontierRole", "TopologyAlphaFrontierSource", "audit_topology_alpha_frontier_data", "default_topology_alpha_frontier_fixture", "fixture_json"]
