"""Closed public aggregate fixture for Domain 10 C09-C12 link paths."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .link_graph_alpha import LinkGraphAlphaState
from .serialization import content_hash, jsonable, require_non_empty


LINK_GRAPH_ALPHA_FRONTIER_FIXTURE_VERSION = "2026.08.d10-c09-c12.v1"
LINK_GRAPH_ALPHA_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|core|unknown"
LINK_GRAPH_ALPHA_FRONTIER_FOREIGN_CONTEXT_KEY = "GRCh38|glioma|adult|differentiated|core|unknown"
LINK_GRAPH_ALPHA_FRONTIER_BOUNDARY = "public_aggregate_non_patient"


class LinkGraphAlphaFrontierOperation(StrEnum):
    CRISPR_PERTURBATION = "crispr_perturbation"
    CONTACT_3D = "contact_3d"
    PROMOTER_TETHERING = "promoter_tethering"
    MULTI_GENE_GRAPH = "multi_gene_graph"


class LinkGraphAlphaFrontierRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierSource:
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
            raise ValidationError("link graph alpha frontier sources must be public aggregates")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierRecord:
    record_id: str
    operation: LinkGraphAlphaFrontierOperation
    role: LinkGraphAlphaFrontierRole
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
            raise ValidationError("link graph alpha frontier records need source receipts")
        if self.expected_state not in {item.value for item in LinkGraphAlphaState} | {"contradictory", "out_of_domain"}:
            raise ValidationError(f"unknown link graph alpha frontier state: {self.expected_state}")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"record_id": self.record_id, "operation": self.operation, "role": self.role, "context_key": self.context_key, "source_ids": self.source_ids, "payload": dict(self.payload), "expected_state": self.expected_state, "expected_issue_codes": self.expected_issue_codes, "expected_measurements": dict(self.expected_measurements)}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierFixture:
    fixture_id: str
    version: str
    context_key: str
    foreign_context_key: str
    boundary: str
    sources: tuple[LinkGraphAlphaFrontierSource, ...]
    records: tuple[LinkGraphAlphaFrontierRecord, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        for name in ("fixture_id", "version", "context_key", "foreign_context_key", "boundary"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash({"fixture_id": self.fixture_id, "version": self.version, "sources": self.sources, "records": self.records}))

    @property
    def positive_records(self) -> tuple[LinkGraphAlphaFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is LinkGraphAlphaFrontierRole.POSITIVE)

    @property
    def control_records(self) -> tuple[LinkGraphAlphaFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is LinkGraphAlphaFrontierRole.CONTROL)

    def operation_records(self, operation: LinkGraphAlphaFrontierOperation | str) -> tuple[LinkGraphAlphaFrontierRecord, ...]:
        value = LinkGraphAlphaFrontierOperation(str(operation))
        return tuple(item for item in self.records if item.operation is value)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "version": self.version, "context_key": self.context_key, "foreign_context_key": self.foreign_context_key, "boundary": self.boundary, "sources": [item.to_dict() for item in self.sources], "records": [item.to_dict() for item in self.records]}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierDataAudit:
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


def _source(source_id: str, kind: str, version: str, uri: str) -> LinkGraphAlphaFrontierSource:
    return LinkGraphAlphaFrontierSource(source_id, kind, version, uri, content_hash({"source_id": source_id, "version": version, "uri": uri}), LINK_GRAPH_ALPHA_FRONTIER_CONTEXT_KEY, receipt_fields={"scope": "aggregate", "access": "public", "schema": "locked"})


def _crispr(context_key: str, *, mode: str = "positive") -> dict[str, Any]:
    base = {"variant_id": "v-1", "element_id": "enh-1", "gene_id": "GENE1", "perturbation_mode": "CRISPRi", "effect_scale": 1.0, "context_key": context_key, "source_id": "crispr-aggregate", "source_version": "crispr-v2"}
    if mode == "contradictory":
        return {"observations": [{**base, "evidence_id": "cr-a", "direction": "activating", "effect_size": 0.8}, {**base, "evidence_id": "cr-b", "direction": "repressing", "effect_size": -0.8}]}
    if mode == "weak":
        return {"observations": [{**base, "evidence_id": "cr-weak", "direction": "unknown", "effect_size": 0.1}]}
    return {"observations": [{**base, "evidence_id": "cr-1", "direction": "repressing", "effect_size": -0.8}]}


def _contact(context_key: str, *, mode: str = "positive") -> dict[str, Any]:
    base = {"variant_id": "v-1", "element_id": "enh-1", "contact_scale": 1.0, "resolution_bp": 5000, "assay_kind": "hic", "context_key": context_key, "source_id": "contact-aggregate", "source_version": "contact-v3"}
    if mode == "weak":
        return {"observations": [{**base, "evidence_id": "ct-weak", "gene_id": "GENE1", "contact_signal": 0.2}]}
    if mode == "alternatives":
        return {"observations": [{**base, "evidence_id": "ct-1", "gene_id": "GENE1", "contact_signal": 0.8}, {**base, "evidence_id": "ct-2", "gene_id": "GENE2", "contact_signal": 0.8}]}
    return {"observations": [{**base, "evidence_id": "ct-1", "gene_id": "GENE1", "contact_signal": 0.9}]}


def _tether(context_key: str, *, mode: str = "positive") -> dict[str, Any]:
    base = {"variant_id": "v-1", "element_id": "enh-1", "gene_id": "GENE1", "distance_bp": 1000, "context_key": context_key, "source_id": "tether-aggregate", "source_version": "tether-v2", "observation_id": "th-1"}
    if mode == "missing":
        return {"observations": [base]}
    if mode == "tie":
        return {"observations": [{**base, "observation_id": "th-1", "gene_id": "GENE1", "contact_support": 0.8, "promoter_activity": 0.8}, {**base, "observation_id": "th-2", "gene_id": "GENE2", "contact_support": 0.8, "promoter_activity": 0.8}]}
    return {"observations": [{**base, "contact_support": 0.8, "promoter_activity": 0.8, "element_activity": 0.8, "promoter_overlap": True}]}


def _graph(context_key: str, *, mode: str = "positive") -> dict[str, Any]:
    base = {"variant_id": "v-1", "element_id": "enh-1", "gene_id": "GENE1", "context_key": context_key, "source_version": "graph-v2", "support": 0.8, "confidence": 0.9}
    if mode == "single":
        return {"evidence": [{**base, "evidence_id": "ge-1", "link_type": "contact", "source_id": "graph-contact"}]}
    if mode == "contradictory":
        return {"evidence": [{**base, "evidence_id": "ge-a", "link_type": "contact", "source_id": "graph-contact"}, {**base, "evidence_id": "ge-b", "link_type": "coaccessibility", "source_id": "graph-coaccess", "state": "contradictory"}]}
    return {"evidence": [{**base, "evidence_id": "ge-1", "link_type": "contact", "source_id": "graph-contact"}, {**base, "evidence_id": "ge-2", "link_type": "coaccessibility", "source_id": "graph-coaccess"}]}


def _records() -> tuple[LinkGraphAlphaFrontierRecord, ...]:
    c = LINK_GRAPH_ALPHA_FRONTIER_CONTEXT_KEY
    f = LINK_GRAPH_ALPHA_FRONTIER_FOREIGN_CONTEXT_KEY
    return (
        LinkGraphAlphaFrontierRecord("D10-C09-P", LinkGraphAlphaFrontierOperation.CRISPR_PERTURBATION, LinkGraphAlphaFrontierRole.POSITIVE, c, ("crispr-aggregate",), _crispr(c), "partial", ("single_method",), {"link_count": 1}),
        LinkGraphAlphaFrontierRecord("D10-C09-C1", LinkGraphAlphaFrontierOperation.CRISPR_PERTURBATION, LinkGraphAlphaFrontierRole.CONTROL, c, ("crispr-aggregate",), _crispr(c, mode="weak"), "partial", ("low_support", "single_method"), {"link_count": 1}),
        LinkGraphAlphaFrontierRecord("D10-C09-C2", LinkGraphAlphaFrontierOperation.CRISPR_PERTURBATION, LinkGraphAlphaFrontierRole.CONTROL, c, ("crispr-aggregate",), _crispr(c, mode="contradictory"), "contradictory", ("direction_disagreement",), {"link_count": 1}),
        LinkGraphAlphaFrontierRecord("D10-C09-C3", LinkGraphAlphaFrontierOperation.CRISPR_PERTURBATION, LinkGraphAlphaFrontierRole.CONTROL, f, ("crispr-aggregate",), _crispr(f), "out_of_domain", ("context_mismatch",), {"link_count": 0}),
        LinkGraphAlphaFrontierRecord("D10-C10-P", LinkGraphAlphaFrontierOperation.CONTACT_3D, LinkGraphAlphaFrontierRole.POSITIVE, c, ("contact-aggregate",), _contact(c), "partial", ("single_assay",), {"link_count": 1}),
        LinkGraphAlphaFrontierRecord("D10-C10-C1", LinkGraphAlphaFrontierOperation.CONTACT_3D, LinkGraphAlphaFrontierRole.CONTROL, c, ("contact-aggregate",), _contact(c, mode="weak"), "partial", ("weak_contact", "single_assay"), {"link_count": 1}),
        LinkGraphAlphaFrontierRecord("D10-C10-C2", LinkGraphAlphaFrontierOperation.CONTACT_3D, LinkGraphAlphaFrontierRole.CONTROL, c, ("contact-aggregate",), _contact(c, mode="alternatives"), "partial", ("alternative_gene", "single_assay"), {"link_count": 2}),
        LinkGraphAlphaFrontierRecord("D10-C10-C3", LinkGraphAlphaFrontierOperation.CONTACT_3D, LinkGraphAlphaFrontierRole.CONTROL, f, ("contact-aggregate",), _contact(f), "out_of_domain", ("context_mismatch",), {"link_count": 0}),
        LinkGraphAlphaFrontierRecord("D10-C11-P", LinkGraphAlphaFrontierOperation.PROMOTER_TETHERING, LinkGraphAlphaFrontierRole.POSITIVE, c, ("tether-aggregate",), _tether(c), "supported", expected_measurements={"result_count": 1}),
        LinkGraphAlphaFrontierRecord("D10-C11-C1", LinkGraphAlphaFrontierOperation.PROMOTER_TETHERING, LinkGraphAlphaFrontierRole.CONTROL, c, ("tether-aggregate",), _tether(c, mode="missing"), "abstained", ("missing_components",), {"result_count": 1}),
        LinkGraphAlphaFrontierRecord("D10-C11-C2", LinkGraphAlphaFrontierOperation.PROMOTER_TETHERING, LinkGraphAlphaFrontierRole.CONTROL, c, ("tether-aggregate",), _tether(c, mode="tie"), "ambiguous", ("tethering_ambiguity",), {"result_count": 2}),
        LinkGraphAlphaFrontierRecord("D10-C11-C3", LinkGraphAlphaFrontierOperation.PROMOTER_TETHERING, LinkGraphAlphaFrontierRole.CONTROL, f, ("tether-aggregate",), _tether(f), "out_of_domain", ("context_mismatch",), {"result_count": 0}),
        LinkGraphAlphaFrontierRecord("D10-C12-P", LinkGraphAlphaFrontierOperation.MULTI_GENE_GRAPH, LinkGraphAlphaFrontierRole.POSITIVE, c, ("graph-contact", "graph-coaccess"), _graph(c), "supported", expected_measurements={"edge_count": 1}),
        LinkGraphAlphaFrontierRecord("D10-C12-C1", LinkGraphAlphaFrontierOperation.MULTI_GENE_GRAPH, LinkGraphAlphaFrontierRole.CONTROL, c, ("graph-contact",), _graph(c, mode="single"), "partial", ("single_evidence",), {"edge_count": 1}),
        LinkGraphAlphaFrontierRecord("D10-C12-C2", LinkGraphAlphaFrontierOperation.MULTI_GENE_GRAPH, LinkGraphAlphaFrontierRole.CONTROL, c, ("graph-contact", "graph-coaccess"), _graph(c, mode="contradictory"), "contradictory", ("contradictory_evidence",), {"edge_count": 1}),
        LinkGraphAlphaFrontierRecord("D10-C12-C3", LinkGraphAlphaFrontierOperation.MULTI_GENE_GRAPH, LinkGraphAlphaFrontierRole.CONTROL, f, ("graph-contact",), _graph(f), "out_of_domain", ("context_mismatch",), {"edge_count": 0}),
    )


def default_link_graph_alpha_frontier_fixture() -> LinkGraphAlphaFrontierFixture:
    sources = (_source("crispr-aggregate", "crispr_perturbation_aggregate", "crispr-v2", "https://data.example.org/links/crispr-v2"), _source("contact-aggregate", "contact_3d_aggregate", "contact-v3", "https://data.example.org/links/contact-v3"), _source("tether-aggregate", "promoter_tethering_aggregate", "tether-v2", "https://data.example.org/links/tether-v2"), _source("graph-contact", "graph_contact_aggregate", "graph-v2", "https://data.example.org/links/graph-contact-v2"), _source("graph-coaccess", "graph_coaccessibility_aggregate", "graph-v2", "https://data.example.org/links/graph-coaccess-v2"))
    return LinkGraphAlphaFrontierFixture("link-graph-alpha-frontier-fixture", LINK_GRAPH_ALPHA_FRONTIER_FIXTURE_VERSION, LINK_GRAPH_ALPHA_FRONTIER_CONTEXT_KEY, LINK_GRAPH_ALPHA_FRONTIER_FOREIGN_CONTEXT_KEY, LINK_GRAPH_ALPHA_FRONTIER_BOUNDARY, sources, _records())


def audit_link_graph_alpha_frontier_data(fixture: LinkGraphAlphaFrontierFixture) -> LinkGraphAlphaFrontierDataAudit:
    checks = ("record_count" if len(fixture.records) == 16 else "record_count_failed", "source_count" if len(fixture.sources) == 5 else "source_count_failed", "operation_balance" if all(len(fixture.operation_records(item)) == 4 for item in LinkGraphAlphaFrontierOperation) else "operation_balance_failed", "positive_balance" if len(fixture.positive_records) == 4 else "positive_balance_failed", "control_balance" if len(fixture.control_records) == 12 else "control_balance_failed", "aggregate_boundary" if fixture.boundary == LINK_GRAPH_ALPHA_FRONTIER_BOUNDARY else "aggregate_boundary_failed", "source_receipts" if all(item.public_aggregate for item in fixture.sources) else "source_receipts_failed", "record_sources" if all(set(item.source_ids) <= {source.source_id for source in fixture.sources} for item in fixture.records) else "record_sources_failed")
    return LinkGraphAlphaFrontierDataAudit(fixture.fixture_id, all(not item.endswith("_failed") for item in checks), checks, len(fixture.records), len(fixture.sources), len(fixture.positive_records), len(fixture.control_records))


def fixture_json(fixture: LinkGraphAlphaFrontierFixture | None = None) -> str:
    return json.dumps((fixture or default_link_graph_alpha_frontier_fixture()).to_dict(), sort_keys=True, indent=2)


__all__ = ["LINK_GRAPH_ALPHA_FRONTIER_BOUNDARY", "LINK_GRAPH_ALPHA_FRONTIER_CONTEXT_KEY", "LINK_GRAPH_ALPHA_FRONTIER_FIXTURE_VERSION", "LINK_GRAPH_ALPHA_FRONTIER_FOREIGN_CONTEXT_KEY", "LinkGraphAlphaFrontierDataAudit", "LinkGraphAlphaFrontierFixture", "LinkGraphAlphaFrontierOperation", "LinkGraphAlphaFrontierRecord", "LinkGraphAlphaFrontierRole", "LinkGraphAlphaFrontierSource", "audit_link_graph_alpha_frontier_data", "default_link_graph_alpha_frontier_fixture", "fixture_json"]
