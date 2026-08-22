"""Public aggregate fixture for Domain 10 C01-C04 link baselines."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from .errors import ValidationError
from .link_graph import LinkState
from .serialization import content_hash, jsonable, require_non_empty


LINK_GRAPH_FOUNDATION_FRONTIER_FIXTURE_VERSION = "2026.08.d10-c01-c04.v1"
LINK_GRAPH_FOUNDATION_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|core|unknown"
LINK_GRAPH_FOUNDATION_FRONTIER_FOREIGN_CONTEXT_KEY = "GRCh38|glioma|adult|differentiated|core|unknown"
LINK_GRAPH_FOUNDATION_FRONTIER_BOUNDARY = "public_aggregate_non_patient"


class LinkGraphFoundationFrontierOperation(StrEnum):
    COORDINATE_OVERLAP = "coordinate_overlap"
    NEAREST_GENE = "nearest_gene"
    CCRE_ASSIGNMENT = "ccre_assignment"
    CONSENSUS = "enhancer_gene_consensus"


class LinkGraphFoundationFrontierRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierSource:
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
            raise ValidationError("foundation link sources must be public aggregates")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierRecord:
    record_id: str
    operation: LinkGraphFoundationFrontierOperation
    role: LinkGraphFoundationFrontierRole
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
            raise ValidationError("foundation link records need receipts")
        if self.expected_state not in {item.value for item in LinkState}:
            raise ValidationError(f"unknown foundation link state: {self.expected_state}")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"record_id": self.record_id, "operation": self.operation, "role": self.role, "context_key": self.context_key, "source_ids": self.source_ids, "payload": dict(self.payload), "expected_state": self.expected_state, "expected_issue_codes": self.expected_issue_codes, "expected_measurements": dict(self.expected_measurements)}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierFixture:
    fixture_id: str
    version: str
    context_key: str
    foreign_context_key: str
    boundary: str
    sources: tuple[LinkGraphFoundationFrontierSource, ...]
    records: tuple[LinkGraphFoundationFrontierRecord, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        for name in ("fixture_id", "version", "context_key", "foreign_context_key", "boundary"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash({"fixture_id": self.fixture_id, "version": self.version, "sources": self.sources, "records": self.records}))

    @property
    def positive_records(self) -> tuple[LinkGraphFoundationFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is LinkGraphFoundationFrontierRole.POSITIVE)

    @property
    def control_records(self) -> tuple[LinkGraphFoundationFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is LinkGraphFoundationFrontierRole.CONTROL)

    def operation_records(self, operation: LinkGraphFoundationFrontierOperation | str) -> tuple[LinkGraphFoundationFrontierRecord, ...]:
        value = LinkGraphFoundationFrontierOperation(str(operation))
        return tuple(item for item in self.records if item.operation is value)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "version": self.version, "context_key": self.context_key, "foreign_context_key": self.foreign_context_key, "boundary": self.boundary, "sources": [item.to_dict() for item in self.sources], "records": [item.to_dict() for item in self.records]}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierDataAudit:
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


def _source(source_id: str, kind: str, version: str, uri: str) -> LinkGraphFoundationFrontierSource:
    return LinkGraphFoundationFrontierSource(source_id, kind, version, uri, content_hash({"source_id": source_id, "version": version, "uri": uri}), LINK_GRAPH_FOUNDATION_FRONTIER_CONTEXT_KEY, receipt_fields={"scope": "aggregate", "access": "public", "schema": "locked"})


def _variant(context_key: str, *, position: int = 1000) -> dict[str, Any]:
    return {"variant_id": "v-1", "kind": "snv", "chromosome": "7", "start": position, "end": position, "reference": "A", "alternate": "T", "genome_build": "GRCh38", "origin": "somatic", "context_key": context_key}


def _element(context_key: str, *, element_id: str = "enh-1", element_type: str = "enhancer", start: int = 990, end: int = 1010, genes: tuple[str, ...] = ("GENE1",)) -> dict[str, Any]:
    genome, disease, age, cell, territory, treatment = context_key.split("|")
    return {"element_id": element_id, "chromosome": "7", "start": start, "end": end, "element_type": element_type, "source_id": "element-aggregate", "target_genes": genes, "context": {"genome_build": genome, "disease_class": disease, "age_group": age, "cell_state": cell, "territory": territory, "treatment_phase": treatment}, "context_key": context_key}


def _gene(context_key: str, *, gene_id: str = "GENE1", start: int = 800, end: int = 900) -> dict[str, Any]:
    return {"gene_id": gene_id, "symbol": gene_id, "chromosome": "7", "start": start, "end": end, "genome_build": "GRCh38", "context_key": context_key, "source_version": "gene-v2", "raw_hash": content_hash((gene_id, start, end))}


def _evidence(context_key: str, *, mode: str = "positive") -> dict[str, Any]:
    base = {"variant_id": "v-1", "element_id": "enh-1", "gene_id": "GENE1", "variant": "v-1", "context_key": context_key, "source_version": "consensus-v2", "support": 0.8, "confidence": 0.9}
    if mode == "single":
        return {"evidence": [{**base, "evidence_id": "ev-1", "link_type": "contact", "source_id": "consensus-contact"}]}
    if mode == "contradictory":
        return {"evidence": [{**base, "evidence_id": "ev-a", "link_type": "contact", "source_id": "consensus-contact"}, {**base, "evidence_id": "ev-b", "link_type": "coaccessibility", "source_id": "consensus-activity", "state": "contradictory"}]}
    return {"evidence": [{**base, "evidence_id": "ev-1", "link_type": "contact", "source_id": "consensus-contact"}, {**base, "evidence_id": "ev-2", "link_type": "coaccessibility", "source_id": "consensus-activity"}]}


def _records() -> tuple[LinkGraphFoundationFrontierRecord, ...]:
    c = LINK_GRAPH_FOUNDATION_FRONTIER_CONTEXT_KEY
    f = LINK_GRAPH_FOUNDATION_FRONTIER_FOREIGN_CONTEXT_KEY
    element = _element(c)
    return (
        LinkGraphFoundationFrontierRecord("D10-C01-P", LinkGraphFoundationFrontierOperation.COORDINATE_OVERLAP, LinkGraphFoundationFrontierRole.POSITIVE, c, ("element-aggregate",), {"variant": _variant(c), "elements": [element]}, "supported", (), {"link_count": 1}),
        LinkGraphFoundationFrontierRecord("D10-C01-C1", LinkGraphFoundationFrontierOperation.COORDINATE_OVERLAP, LinkGraphFoundationFrontierRole.CONTROL, c, ("element-aggregate",), {"variant": _variant(c), "elements": [element, _element(c, element_id="enh-2", start=995, end=1005)]}, "ambiguous", ("multiple_overlaps",), {"link_count": 2}),
        LinkGraphFoundationFrontierRecord("D10-C01-C2", LinkGraphFoundationFrontierOperation.COORDINATE_OVERLAP, LinkGraphFoundationFrontierRole.CONTROL, c, ("element-aggregate",), {"variant": _variant(c, position=5000), "elements": [element]}, "absent", ("no_overlap",), {"link_count": 0}),
        LinkGraphFoundationFrontierRecord("D10-C01-C3", LinkGraphFoundationFrontierOperation.COORDINATE_OVERLAP, LinkGraphFoundationFrontierRole.CONTROL, f, ("element-aggregate",), {"variant": _variant(f), "elements": [_element(f)]}, "out_of_domain", ("context_mismatch",), {"link_count": 0}),
        LinkGraphFoundationFrontierRecord("D10-C02-P", LinkGraphFoundationFrontierOperation.NEAREST_GENE, LinkGraphFoundationFrontierRole.POSITIVE, c, ("gene-aggregate",), {"variant": _variant(c), "genes": [_gene(c, start=800, end=900)], "max_distance_bp": 1000}, "supported", (), {"link_count": 1}),
        LinkGraphFoundationFrontierRecord("D10-C02-C1", LinkGraphFoundationFrontierOperation.NEAREST_GENE, LinkGraphFoundationFrontierRole.CONTROL, c, ("gene-aggregate",), {"variant": _variant(c), "genes": [_gene(c, gene_id="GENE1", start=800, end=900), _gene(c, gene_id="GENE2", start=800, end=900)], "max_distance_bp": 1000}, "ambiguous", ("distance_tie",), {"link_count": 2}),
        LinkGraphFoundationFrontierRecord("D10-C02-C2", LinkGraphFoundationFrontierOperation.NEAREST_GENE, LinkGraphFoundationFrontierRole.CONTROL, c, ("gene-aggregate",), {"variant": _variant(c), "genes": [_gene(c, start=1, end=10)], "max_distance_bp": 10}, "abstained", ("distance_window",), {"link_count": 0}),
        LinkGraphFoundationFrontierRecord("D10-C02-C3", LinkGraphFoundationFrontierOperation.NEAREST_GENE, LinkGraphFoundationFrontierRole.CONTROL, f, ("gene-aggregate",), {"variant": _variant(f), "genes": [_gene(f, start=800, end=900)], "max_distance_bp": 1000}, "abstained", ("context_mismatch",), {"link_count": 0}),
        LinkGraphFoundationFrontierRecord("D10-C03-P", LinkGraphFoundationFrontierOperation.CCRE_ASSIGNMENT, LinkGraphFoundationFrontierRole.POSITIVE, c, ("ccre-aggregate",), {"variant": _variant(c), "elements": [_element(c, element_type="ccre")]}, "supported", (), {"element_count": 1}),
        LinkGraphFoundationFrontierRecord("D10-C03-C1", LinkGraphFoundationFrontierOperation.CCRE_ASSIGNMENT, LinkGraphFoundationFrontierRole.CONTROL, c, ("ccre-aggregate",), {"variant": _variant(c), "elements": [_element(c, element_id="ccre-1", element_type="ccre"), _element(c, element_id="ccre-2", element_type="ccre")]}, "ambiguous", ("multiple_ccres",), {"element_count": 2}),
        LinkGraphFoundationFrontierRecord("D10-C03-C2", LinkGraphFoundationFrontierOperation.CCRE_ASSIGNMENT, LinkGraphFoundationFrontierRole.CONTROL, c, ("ccre-aggregate",), {"variant": _variant(c), "elements": [_element(c, element_type="enhancer")]}, "absent", ("no_ccre",), {"element_count": 0}),
        LinkGraphFoundationFrontierRecord("D10-C03-C3", LinkGraphFoundationFrontierOperation.CCRE_ASSIGNMENT, LinkGraphFoundationFrontierRole.CONTROL, f, ("ccre-aggregate",), {"variant": _variant(f), "elements": [_element(f, element_type="ccre")]}, "out_of_domain", ("context_mismatch",), {"element_count": 0}),
        LinkGraphFoundationFrontierRecord("D10-C04-P", LinkGraphFoundationFrontierOperation.CONSENSUS, LinkGraphFoundationFrontierRole.POSITIVE, c, ("consensus-contact", "consensus-activity"), {**_evidence(c), "variant_id": "v-1"}, "supported", (), {"link_count": 1}),
        LinkGraphFoundationFrontierRecord("D10-C04-C1", LinkGraphFoundationFrontierOperation.CONSENSUS, LinkGraphFoundationFrontierRole.CONTROL, c, ("consensus-contact",), _evidence(c, mode="single"), "partial", ("single_method",), {"link_count": 1}),
        LinkGraphFoundationFrontierRecord("D10-C04-C2", LinkGraphFoundationFrontierOperation.CONSENSUS, LinkGraphFoundationFrontierRole.CONTROL, c, ("consensus-contact", "consensus-activity"), _evidence(c, mode="contradictory"), "contradictory", ("contradictory_evidence",), {"link_count": 1}),
        LinkGraphFoundationFrontierRecord("D10-C04-C3", LinkGraphFoundationFrontierOperation.CONSENSUS, LinkGraphFoundationFrontierRole.CONTROL, f, ("consensus-contact", "consensus-activity"), _evidence(f), "out_of_domain", ("context_mismatch",), {"link_count": 0}),
    )


def default_link_graph_foundation_frontier_fixture() -> LinkGraphFoundationFrontierFixture:
    sources = (_source("element-aggregate", "regulatory_element_aggregate", "element-v2", "https://data.example.org/links/elements-v2"), _source("gene-aggregate", "gene_interval_aggregate", "gene-v2", "https://data.example.org/links/genes-v2"), _source("ccre-aggregate", "ccre_aggregate", "ccre-v2", "https://data.example.org/links/ccre-v2"), _source("consensus-contact", "contact_aggregate", "consensus-v2", "https://data.example.org/links/consensus-contact-v2"), _source("consensus-activity", "activity_aggregate", "consensus-v2", "https://data.example.org/links/consensus-activity-v2"))
    return LinkGraphFoundationFrontierFixture("link-graph-foundation-frontier-fixture", LINK_GRAPH_FOUNDATION_FRONTIER_FIXTURE_VERSION, LINK_GRAPH_FOUNDATION_FRONTIER_CONTEXT_KEY, LINK_GRAPH_FOUNDATION_FRONTIER_FOREIGN_CONTEXT_KEY, LINK_GRAPH_FOUNDATION_FRONTIER_BOUNDARY, sources, _records())


def audit_link_graph_foundation_frontier_data(fixture: LinkGraphFoundationFrontierFixture) -> LinkGraphFoundationFrontierDataAudit:
    source_ids = {source.source_id for source in fixture.sources}
    checks = ("record_count" if len(fixture.records) == 16 else "record_count_failed", "source_count" if len(fixture.sources) == 5 else "source_count_failed", "operation_balance" if all(len(fixture.operation_records(item)) == 4 for item in LinkGraphFoundationFrontierOperation) else "operation_balance_failed", "positive_balance" if len(fixture.positive_records) == 4 else "positive_balance_failed", "control_balance" if len(fixture.control_records) == 12 else "control_balance_failed", "record_sources" if all(set(record.source_ids) <= source_ids for record in fixture.records) else "record_sources_failed", "aggregate_boundary" if fixture.boundary == LINK_GRAPH_FOUNDATION_FRONTIER_BOUNDARY else "aggregate_boundary_failed")
    return LinkGraphFoundationFrontierDataAudit(fixture.fixture_id, all(not item.endswith("_failed") for item in checks), checks, len(fixture.records), len(fixture.sources), len(fixture.positive_records), len(fixture.control_records))


def link_graph_foundation_frontier_fixture_json(fixture: LinkGraphFoundationFrontierFixture | None = None) -> str:
    return json.dumps((fixture or default_link_graph_foundation_frontier_fixture()).to_dict(), sort_keys=True, indent=2)


__all__ = ["LINK_GRAPH_FOUNDATION_FRONTIER_BOUNDARY", "LINK_GRAPH_FOUNDATION_FRONTIER_CONTEXT_KEY", "LINK_GRAPH_FOUNDATION_FRONTIER_FIXTURE_VERSION", "LINK_GRAPH_FOUNDATION_FRONTIER_FOREIGN_CONTEXT_KEY", "LinkGraphFoundationFrontierDataAudit", "LinkGraphFoundationFrontierFixture", "LinkGraphFoundationFrontierOperation", "LinkGraphFoundationFrontierRecord", "LinkGraphFoundationFrontierRole", "LinkGraphFoundationFrontierSource", "audit_link_graph_foundation_frontier_data", "default_link_graph_foundation_frontier_fixture", "link_graph_foundation_frontier_fixture_json"]
