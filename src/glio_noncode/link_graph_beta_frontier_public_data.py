"""Fresh public aggregate fixture for Domain 10 C05-C08 link evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from .errors import ValidationError
from .link_graph import LinkState
from .serialization import content_hash, jsonable, require_non_empty


LINK_GRAPH_BETA_FRONTIER_FIXTURE_VERSION = "2026.08.d10-c05-c08.v1"
LINK_GRAPH_BETA_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|core|unknown"
LINK_GRAPH_BETA_FRONTIER_FOREIGN_CONTEXT_KEY = "GRCh38|glioma|adult|differentiated|core|unknown"
LINK_GRAPH_BETA_FRONTIER_BOUNDARY = "public_aggregate_non_patient"


class LinkGraphBetaFrontierOperation(StrEnum):
    ACTIVITY_CONTACT = "activity_by_contact"
    COACCESSIBILITY = "coaccessibility"
    MOLECULAR_QTL = "molecular_qtl"
    ALLELE_SPECIFIC = "allele_specific"


class LinkGraphBetaFrontierRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierSource:
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
            raise ValidationError("beta frontier sources must be public aggregates")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierRecord:
    record_id: str
    operation: LinkGraphBetaFrontierOperation
    role: LinkGraphBetaFrontierRole
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
            raise ValidationError("beta frontier records need receipts")
        if self.expected_state not in {item.value for item in LinkState}:
            raise ValidationError(f"unknown beta frontier state: {self.expected_state}")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"record_id": self.record_id, "operation": self.operation, "role": self.role, "context_key": self.context_key, "source_ids": self.source_ids, "payload": dict(self.payload), "expected_state": self.expected_state, "expected_issue_codes": self.expected_issue_codes, "expected_measurements": dict(self.expected_measurements)}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierFixture:
    fixture_id: str
    version: str
    context_key: str
    foreign_context_key: str
    boundary: str
    sources: tuple[LinkGraphBetaFrontierSource, ...]
    records: tuple[LinkGraphBetaFrontierRecord, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        for name in ("fixture_id", "version", "context_key", "foreign_context_key", "boundary"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash({"fixture_id": self.fixture_id, "version": self.version, "sources": self.sources, "records": self.records}))

    @property
    def positive_records(self) -> tuple[LinkGraphBetaFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is LinkGraphBetaFrontierRole.POSITIVE)

    @property
    def control_records(self) -> tuple[LinkGraphBetaFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is LinkGraphBetaFrontierRole.CONTROL)

    def operation_records(self, operation: LinkGraphBetaFrontierOperation | str) -> tuple[LinkGraphBetaFrontierRecord, ...]:
        value = LinkGraphBetaFrontierOperation(str(operation))
        return tuple(item for item in self.records if item.operation is value)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "version": self.version, "context_key": self.context_key, "foreign_context_key": self.foreign_context_key, "boundary": self.boundary, "sources": [item.to_dict() for item in self.sources], "records": [item.to_dict() for item in self.records]}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierDataAudit:
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


def _source(source_id: str, kind: str, version: str, uri: str) -> LinkGraphBetaFrontierSource:
    return LinkGraphBetaFrontierSource(source_id, kind, version, uri, content_hash({"source_id": source_id, "version": version, "uri": uri}), LINK_GRAPH_BETA_FRONTIER_CONTEXT_KEY, receipt_fields={"scope": "aggregate", "access": "public", "schema": "locked"})


def _base(context_key: str, evidence_id: str, *, gene_id: str = "GENE1", element_id: str = "enh-1") -> dict[str, Any]:
    return {"evidence_id": evidence_id, "variant_id": "v-1", "element_id": element_id, "gene_id": gene_id, "context_key": context_key, "source_version": "v2"}


def _activity(context_key: str, evidence_id: str = "abc-1", *, activity: float = 0.8, contact: float = 5.0, gene_id: str = "GENE1", replicate_id: str | None = None) -> dict[str, Any]:
    return {**_base(context_key, evidence_id, gene_id=gene_id), "activity_signal": activity, "contact_signal": contact, "contact_scale": 10.0, "confidence": 0.9, **({"replicate_id": replicate_id} if replicate_id else {})}


def _coaccessibility(context_key: str, evidence_id: str = "co-1", *, score: float = 0.75, gene_id: str = "GENE1") -> dict[str, Any]:
    return {**_base(context_key, evidence_id, gene_id=gene_id), "score": score, "confidence": 0.9, "source_id": "coaccess-public"}


def _qtl(context_key: str, evidence_id: str = "qtl-1", *, q_value: float = 0.001, effect_size: float = 0.42) -> dict[str, Any]:
    return {**_base(context_key, evidence_id), "q_value": q_value, "effect_size": effect_size, "confidence": 0.9, "source_id": "qtl-public"}


def _allele(context_key: str, evidence_id: str = "allele-gain", *, direction: str = "gain", support: float = 0.8) -> dict[str, Any]:
    return {**_base(context_key, evidence_id), "direction": direction, "support": support, "confidence": 0.9, "source_id": "allele-public"}


def _records() -> tuple[LinkGraphBetaFrontierRecord, ...]:
    c = LINK_GRAPH_BETA_FRONTIER_CONTEXT_KEY
    f = LINK_GRAPH_BETA_FRONTIER_FOREIGN_CONTEXT_KEY
    return (
        LinkGraphBetaFrontierRecord("D10-C05-P", LinkGraphBetaFrontierOperation.ACTIVITY_CONTACT, LinkGraphBetaFrontierRole.POSITIVE, c, ("activity-public",), {"observations": [_activity(c)]}, "partial", ("single_method",), {"observation_count": 1, "support": 0.4}),
        LinkGraphBetaFrontierRecord("D10-C05-C1", LinkGraphBetaFrontierOperation.ACTIVITY_CONTACT, LinkGraphBetaFrontierRole.CONTROL, c, ("activity-public",), {"observations": [_activity(c, "abc-r1", replicate_id="r1"), _activity(c, "abc-r2", replicate_id="r2")]}, "partial", ("replicate_pair",), {"observation_count": 2, "support": 0.4}),
        LinkGraphBetaFrontierRecord("D10-C05-C2", LinkGraphBetaFrontierOperation.ACTIVITY_CONTACT, LinkGraphBetaFrontierRole.CONTROL, c, ("activity-public",), {"observations": []}, "abstained", ("missing_evidence",), {"observation_count": 0}),
        LinkGraphBetaFrontierRecord("D10-C05-C3", LinkGraphBetaFrontierOperation.ACTIVITY_CONTACT, LinkGraphBetaFrontierRole.CONTROL, f, ("activity-public",), {"observations": [_activity(f, "abc-foreign")]}, "out_of_domain", ("context_mismatch",), {"observation_count": 0}),
        LinkGraphBetaFrontierRecord("D10-C06-P", LinkGraphBetaFrontierOperation.COACCESSIBILITY, LinkGraphBetaFrontierRole.POSITIVE, c, ("coaccess-public",), {"observations": [_coaccessibility(c)]}, "partial", ("single_method",), {"observation_count": 1, "score": 0.75}),
        LinkGraphBetaFrontierRecord("D10-C06-C1", LinkGraphBetaFrontierOperation.COACCESSIBILITY, LinkGraphBetaFrontierRole.CONTROL, c, ("coaccess-public",), {"observations": [_coaccessibility(c, "co-1"), _coaccessibility(c, "co-2", gene_id="GENE2")]}, "partial", ("alternative_gene",), {"observation_count": 2, "gene_count": 2}),
        LinkGraphBetaFrontierRecord("D10-C06-C2", LinkGraphBetaFrontierOperation.COACCESSIBILITY, LinkGraphBetaFrontierRole.CONTROL, c, ("coaccess-public",), {"observations": []}, "abstained", ("missing_evidence",), {"observation_count": 0}),
        LinkGraphBetaFrontierRecord("D10-C06-C3", LinkGraphBetaFrontierOperation.COACCESSIBILITY, LinkGraphBetaFrontierRole.CONTROL, f, ("coaccess-public",), {"observations": [_coaccessibility(f, "co-foreign")]}, "out_of_domain", ("context_mismatch",), {"observation_count": 0}),
        LinkGraphBetaFrontierRecord("D10-C07-P", LinkGraphBetaFrontierOperation.MOLECULAR_QTL, LinkGraphBetaFrontierRole.POSITIVE, c, ("qtl-public",), {"observations": [_qtl(c)]}, "partial", ("single_method",), {"observation_count": 1, "bounded_support": 0.3}),
        LinkGraphBetaFrontierRecord("D10-C07-C1", LinkGraphBetaFrontierOperation.MOLECULAR_QTL, LinkGraphBetaFrontierRole.CONTROL, c, ("qtl-public",), {"observations": [_qtl(c, "qtl-weak", q_value=0.5)]}, "partial", ("weak_q_value",), {"observation_count": 1, "bounded_support": 0.030102999}),
        LinkGraphBetaFrontierRecord("D10-C07-C2", LinkGraphBetaFrontierOperation.MOLECULAR_QTL, LinkGraphBetaFrontierRole.CONTROL, c, ("qtl-public",), {"observations": []}, "abstained", ("missing_evidence",), {"observation_count": 0}),
        LinkGraphBetaFrontierRecord("D10-C07-C3", LinkGraphBetaFrontierOperation.MOLECULAR_QTL, LinkGraphBetaFrontierRole.CONTROL, f, ("qtl-public",), {"observations": [_qtl(f, "qtl-foreign")]}, "out_of_domain", ("context_mismatch",), {"observation_count": 0}),
        LinkGraphBetaFrontierRecord("D10-C08-P", LinkGraphBetaFrontierOperation.ALLELE_SPECIFIC, LinkGraphBetaFrontierRole.POSITIVE, c, ("allele-public",), {"observations": [_allele(c)]}, "partial", ("single_direction",), {"observation_count": 1, "direction_count": 1}),
        LinkGraphBetaFrontierRecord("D10-C08-C1", LinkGraphBetaFrontierOperation.ALLELE_SPECIFIC, LinkGraphBetaFrontierRole.CONTROL, c, ("allele-public",), {"observations": [_allele(c, "allele-gain", direction="gain"), _allele(c, "allele-loss", direction="loss", support=0.7)]}, "contradictory", ("direction_conflict",), {"observation_count": 2, "direction_count": 2}),
        LinkGraphBetaFrontierRecord("D10-C08-C2", LinkGraphBetaFrontierOperation.ALLELE_SPECIFIC, LinkGraphBetaFrontierRole.CONTROL, c, ("allele-public",), {"observations": []}, "abstained", ("missing_evidence",), {"observation_count": 0}),
        LinkGraphBetaFrontierRecord("D10-C08-C3", LinkGraphBetaFrontierOperation.ALLELE_SPECIFIC, LinkGraphBetaFrontierRole.CONTROL, f, ("allele-public",), {"observations": [_allele(f, "allele-foreign")]}, "out_of_domain", ("context_mismatch",), {"observation_count": 0}),
    )


def default_link_graph_beta_frontier_fixture() -> LinkGraphBetaFrontierFixture:
    sources = (_source("activity-public", "activity_by_contact_aggregate", "activity-v2", "https://data.example.org/links/activity-by-contact-v2"), _source("coaccess-public", "coaccessibility_aggregate", "coaccess-v2", "https://data.example.org/links/coaccessibility-v2"), _source("qtl-public", "molecular_qtl_aggregate", "qtl-v2", "https://data.example.org/links/molecular-qtl-v2"), _source("allele-public", "allele_specific_aggregate", "allele-v2", "https://data.example.org/links/allele-specific-v2"))
    return LinkGraphBetaFrontierFixture("link-graph-beta-frontier-fixture", LINK_GRAPH_BETA_FRONTIER_FIXTURE_VERSION, LINK_GRAPH_BETA_FRONTIER_CONTEXT_KEY, LINK_GRAPH_BETA_FRONTIER_FOREIGN_CONTEXT_KEY, LINK_GRAPH_BETA_FRONTIER_BOUNDARY, sources, _records())


def audit_link_graph_beta_frontier_data(fixture: LinkGraphBetaFrontierFixture) -> LinkGraphBetaFrontierDataAudit:
    source_ids = {source.source_id for source in fixture.sources}
    checks = ("record_count" if len(fixture.records) == 16 else "record_count_failed", "source_count" if len(fixture.sources) == 4 else "source_count_failed", "operation_balance" if all(len(fixture.operation_records(item)) == 4 for item in LinkGraphBetaFrontierOperation) else "operation_balance_failed", "positive_balance" if len(fixture.positive_records) == 4 else "positive_balance_failed", "control_balance" if len(fixture.control_records) == 12 else "control_balance_failed", "record_sources" if all(set(record.source_ids) <= source_ids for record in fixture.records) else "record_sources_failed", "aggregate_boundary" if fixture.boundary == LINK_GRAPH_BETA_FRONTIER_BOUNDARY else "aggregate_boundary_failed")
    return LinkGraphBetaFrontierDataAudit(fixture.fixture_id, all(not item.endswith("_failed") for item in checks), checks, len(fixture.records), len(fixture.sources), len(fixture.positive_records), len(fixture.control_records))


def link_graph_beta_frontier_fixture_json(fixture: LinkGraphBetaFrontierFixture | None = None) -> str:
    return json.dumps((fixture or default_link_graph_beta_frontier_fixture()).to_dict(), sort_keys=True, indent=2)


__all__ = ["LINK_GRAPH_BETA_FRONTIER_BOUNDARY", "LINK_GRAPH_BETA_FRONTIER_CONTEXT_KEY", "LINK_GRAPH_BETA_FRONTIER_FIXTURE_VERSION", "LINK_GRAPH_BETA_FRONTIER_FOREIGN_CONTEXT_KEY", "LinkGraphBetaFrontierDataAudit", "LinkGraphBetaFrontierFixture", "LinkGraphBetaFrontierOperation", "LinkGraphBetaFrontierRecord", "LinkGraphBetaFrontierRole", "LinkGraphBetaFrontierSource", "audit_link_graph_beta_frontier_data", "default_link_graph_beta_frontier_fixture", "link_graph_beta_frontier_fixture_json"]
