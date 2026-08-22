"""Public aggregate fixture for Domain 11 C01-C04 causal foundations.

The fixture is intentionally compact but structurally complete. Each row keeps
the exact context, public source receipts, factor or measurement payload,
expected state, issue floor, and a content address. It is an aggregate research
fixture; it does not contain subject-level records or clinical conclusions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from .causal_reasoning import CausalState, FactorType
from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty


CAUSAL_FOUNDATION_FRONTIER_FIXTURE_VERSION = "2026.08.d11-c01-c04.v1"
CAUSAL_FOUNDATION_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|core|unknown"
CAUSAL_FOUNDATION_FRONTIER_FOREIGN_CONTEXT_KEY = "GRCh38|glioma|adult|differentiated|core|unknown"
CAUSAL_FOUNDATION_FRONTIER_BOUNDARY = "public_aggregate_non_patient"


class CausalFoundationFrontierOperation(StrEnum):
    HYPOTHESIS_OBJECT = "typed_hypothesis_object"
    FACTOR_GRAPH = "factor_graph_constructor"
    CONTEXT_PRIOR = "context_conditioned_prior"
    MEASUREMENT_LIKELIHOOD = "measurement_likelihood"


class CausalFoundationFrontierRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierSource:
    source_id: str
    title: str
    uri: str
    source_kind: str
    release: str
    scope: str
    content_address: str = ""

    def __post_init__(self) -> None:
        for name in ("source_id", "title", "uri", "source_kind", "release", "scope"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.uri.startswith("https://"):
            raise ValidationError("causal foundation source URI must use HTTPS")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "source_id": self.source_id,
            "title": self.title,
            "uri": self.uri,
            "source_kind": self.source_kind,
            "release": self.release,
            "scope": self.scope,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierRecord:
    record_id: str
    operation: CausalFoundationFrontierOperation
    role: CausalFoundationFrontierRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    expected_state: CausalState
    expected_issue_codes: tuple[str, ...]
    description: str
    content_address: str = ""

    def __post_init__(self) -> None:
        for name in ("record_id", "context_key", "description"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.source_ids:
            raise ValidationError("causal foundation records require source receipts")
        if not self.payload:
            raise ValidationError("causal foundation records require payload")
        if not isinstance(self.operation, CausalFoundationFrontierOperation):
            raise ValidationError("causal foundation operation is not declared")
        if not isinstance(self.role, CausalFoundationFrontierRole):
            raise ValidationError("causal foundation role is not declared")
        if not isinstance(self.expected_state, CausalState):
            raise ValidationError("causal foundation state is not declared")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "record_id": self.record_id,
            "operation": self.operation,
            "role": self.role,
            "context_key": self.context_key,
            "source_ids": self.source_ids,
            "payload": dict(self.payload),
            "expected_state": self.expected_state,
            "expected_issue_codes": self.expected_issue_codes,
            "description": self.description,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierFixture:
    fixture_id: str
    version: str
    context_key: str
    foreign_context_key: str
    boundary: str
    sources: tuple[CausalFoundationFrontierSource, ...]
    records: tuple[CausalFoundationFrontierRecord, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        for name in ("fixture_id", "version", "context_key", "foreign_context_key", "boundary"):
            require_non_empty(str(getattr(self, name)), name)
        if self.boundary != CAUSAL_FOUNDATION_FRONTIER_BOUNDARY:
            raise ValidationError("unsupported causal foundation boundary")
        if not self.sources or not self.records:
            raise ValidationError("causal foundation fixture requires sources and records")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def positive_records(self) -> tuple[CausalFoundationFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is CausalFoundationFrontierRole.POSITIVE)

    @property
    def control_records(self) -> tuple[CausalFoundationFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is CausalFoundationFrontierRole.CONTROL)

    def source_map(self) -> dict[str, CausalFoundationFrontierSource]:
        return {item.source_id: item for item in self.sources}

    def record_map(self) -> dict[str, CausalFoundationFrontierRecord]:
        return {item.record_id: item for item in self.records}

    def operation_records(self, operation: CausalFoundationFrontierOperation | str) -> tuple[CausalFoundationFrontierRecord, ...]:
        value = CausalFoundationFrontierOperation(str(operation))
        return tuple(item for item in self.records if item.operation is value)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "fixture_id": self.fixture_id,
            "version": self.version,
            "context_key": self.context_key,
            "foreign_context_key": self.foreign_context_key,
            "boundary": self.boundary,
            "sources": [item.to_dict() for item in self.sources],
            "records": [item.to_dict() for item in self.records],
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierDataAudit:
    fixture_id: str
    record_count: int
    source_count: int
    positive_count: int
    control_count: int
    foreign_context_count: int
    checks: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_checks(self) -> tuple[str, ...]:
        return tuple(item["check_id"] for item in self.checks if not item["passed"])

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "fixture_id": self.fixture_id,
            "record_count": self.record_count,
            "source_count": self.source_count,
            "positive_count": self.positive_count,
            "control_count": self.control_count,
            "foreign_context_count": self.foreign_context_count,
            "checks": self.checks,
            "failed_checks": self.failed_checks,
            "accepted": self.accepted,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


def _source(source_id: str, title: str, uri: str, source_kind: str, release: str, scope: str) -> CausalFoundationFrontierSource:
    return CausalFoundationFrontierSource(source_id, title, uri, source_kind, release, scope)


def _factor(
    factor_id: str,
    edge_id: str,
    context_key: str,
    source_id: str,
    *,
    state: str = CausalState.SUPPORTED.value,
    factor_type: str = FactorType.LINK.value,
    support: float | None = 0.82,
    uncertainty: float = 0.2,
    parent_factor_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "factor_id": factor_id,
        "edge_id": edge_id,
        "factor_type": factor_type,
        "context_key": context_key,
        "source_id": source_id,
        "source_version": "public-aggregate-2025.1",
        "raw_hash": content_hash({"factor_id": factor_id, "edge_id": edge_id, "state": state}),
        "state": state,
        "support": support,
        "uncertainty": uncertainty,
        "parent_factor_ids": parent_factor_ids,
        "claim_ids": (f"claim:{edge_id}",),
    }


def _profile(profile_id: str, context_key: str) -> dict[str, Any]:
    return {
        "profile_id": profile_id,
        "context_key": context_key,
        "base_score": 0.45,
        "feature_weights": {"stem_signal": 0.22, "chromatin_score": 0.18},
        "feature_ranges": {"stem_signal": (0.0, 1.0), "chromatin_score": (0.0, 1.0)},
        "source_version": "context-profile-2025.1",
        "raw_hash": content_hash({"profile_id": profile_id, "context_key": context_key}),
    }


def _measurement(
    measurement_id: str,
    edge_id: str,
    context_key: str,
    channel: str,
    source_id: str,
    *,
    state: str = CausalState.SUPPORTED.value,
    score: float | None = 0.84,
    confidence: float = 0.9,
) -> dict[str, Any]:
    return {
        "measurement_id": measurement_id,
        "edge_id": edge_id,
        "channel": channel,
        "context_key": context_key,
        "source_id": source_id,
        "source_version": "public-measurement-2025.1",
        "raw_hash": content_hash({"measurement_id": measurement_id, "channel": channel}),
        "state": state,
        "score": score,
        "confidence": confidence,
    }


def _record(
    record_id: str,
    operation: CausalFoundationFrontierOperation,
    role: CausalFoundationFrontierRole,
    context_key: str,
    source_ids: tuple[str, ...],
    payload: Mapping[str, Any],
    state: CausalState,
    issues: tuple[str, ...],
    description: str,
) -> CausalFoundationFrontierRecord:
    return CausalFoundationFrontierRecord(record_id, operation, role, context_key, source_ids, dict(payload), state, issues, description)


def default_causal_foundation_frontier_fixture() -> CausalFoundationFrontierFixture:
    context = CAUSAL_FOUNDATION_FRONTIER_CONTEXT_KEY
    foreign = CAUSAL_FOUNDATION_FRONTIER_FOREIGN_CONTEXT_KEY
    sources = (
        _source("encode", "ENCODE public functional genomics portal", "https://www.encodeproject.org/", "public_assay_archive", "2025-01", "aggregate chromatin and regulatory measurements"),
        _source("four-d", "4D Nucleome public data portal", "https://data.4dnucleome.org/", "public_topology_archive", "2025-01", "aggregate genome-organization observations"),
        _source("geo", "NCBI Gene Expression Omnibus", "https://www.ncbi.nlm.nih.gov/geo/", "public_archive", "2025-01", "aggregate molecular measurements"),
        _source("gtex", "GTEx public portal", "https://gtexportal.org/home/", "public_expression_archive", "v8", "aggregate tissue and context expression references"),
        _source("pubmed", "PubMed public literature index", "https://pubmed.ncbi.nlm.nih.gov/", "public_literature_index", "2025-01", "method and provenance vocabulary"),
    )
    records = (
        _record("D11-C01-P", CausalFoundationFrontierOperation.HYPOTHESIS_OBJECT, CausalFoundationFrontierRole.POSITIVE, context, ("encode", "geo", "gtex"), {"hypothesis_id": "h-c01-p", "variant_id": "v-1", "element_id": "enh-1", "gene_id": "GENE1", "state_id": "stem_like", "mechanism": "regulatory_link", "factors": [_factor("c01-f1", "edge-c01", context, "encode")], "profile": _profile("prior-c01-p", context), "features": {"stem_signal": 0.8, "chromatin_score": 0.75}, "measurements": [_measurement("c01-m1", "edge-c01", context, "accessibility", "encode"), _measurement("c01-m2", "edge-c01", context, "contact", "four-d")]}, CausalState.SUPPORTED, (), "complete typed hypothesis retains graph, prior, and likelihood proxies"),
        _record("D11-C01-C1", CausalFoundationFrontierOperation.HYPOTHESIS_OBJECT, CausalFoundationFrontierRole.CONTROL, context, ("encode", "geo"), {"hypothesis_id": "h-c01-c1", "variant_id": "v-1", "element_id": "enh-1", "gene_id": "GENE1", "state_id": "stem_like", "mechanism": "regulatory_link", "factors": [_factor("c01-c1-f1", "edge-c01-c1", context, "encode")], "profile": _profile("prior-c01-c1", context), "features": {"stem_signal": 0.8}, "measurements": [_measurement("c01-c1-m1", "edge-c01-c1", context, "contact", "four-d")]}, CausalState.ABSTAINED, ("missing_prior_feature",), "missing context feature prevents hypothesis completion"),
        _record("D11-C01-C2", CausalFoundationFrontierOperation.HYPOTHESIS_OBJECT, CausalFoundationFrontierRole.CONTROL, context, ("encode", "geo", "pubmed"), {"hypothesis_id": "h-c01-c2", "variant_id": "v-1", "element_id": "enh-1", "gene_id": "GENE1", "state_id": "stem_like", "mechanism": "regulatory_link", "factors": [_factor("c01-c2-f1", "edge-c01-c2", context, "encode"), _factor("c01-c2-f2", "edge-c01-c2", context, "geo", state=CausalState.MEASURED_NEGATIVE.value, support=0.1)], "profile": _profile("prior-c01-c2", context), "features": {"stem_signal": 0.8, "chromatin_score": 0.75}, "measurements": [_measurement("c01-c2-m1", "edge-c01-c2", context, "accessibility", "encode"), _measurement("c01-c2-m2", "edge-c01-c2", context, "contact", "four-d")]}, CausalState.CONTRADICTORY, ("contradictory_factor_edge",), "contradictory factor states remain visible in the hypothesis"),
        _record("D11-C01-C3", CausalFoundationFrontierOperation.HYPOTHESIS_OBJECT, CausalFoundationFrontierRole.CONTROL, foreign, ("encode", "geo"), {"hypothesis_id": "h-c01-c3", "variant_id": "v-1", "element_id": "enh-1", "gene_id": "GENE1", "state_id": "differentiated", "mechanism": "regulatory_link", "factors": [_factor("c01-c3-f1", "edge-c01-c3", foreign, "encode")], "profile": _profile("prior-c01-c3", foreign), "features": {"stem_signal": 0.8, "chromatin_score": 0.75}, "measurements": [_measurement("c01-c3-m1", "edge-c01-c3", foreign, "contact", "four-d")]}, CausalState.OUT_OF_DOMAIN, ("context_mismatch",), "foreign context is quarantined before hypothesis construction"),
        _record("D11-C02-P", CausalFoundationFrontierOperation.FACTOR_GRAPH, CausalFoundationFrontierRole.POSITIVE, context, ("encode", "four-d"), {"factors": [_factor("c02-f1", "edge-c02", context, "encode"), _factor("c02-f2", "edge-c02", context, "four-d", factor_type=FactorType.TOPOLOGY.value, support=0.76)]}, CausalState.SUPPORTED, (), "supported factor graph retains two public evidence factors"),
        _record("D11-C02-C1", CausalFoundationFrontierOperation.FACTOR_GRAPH, CausalFoundationFrontierRole.CONTROL, context, ("encode",), {"factors": [_factor("c02-c1-f1", "edge-c02-c1", context, "encode", parent_factor_ids=("missing-parent",))]}, CausalState.PARTIAL, ("orphan_factor_lineage",), "orphan lineage is retained and graph state becomes partial"),
        _record("D11-C02-C2", CausalFoundationFrontierOperation.FACTOR_GRAPH, CausalFoundationFrontierRole.CONTROL, context, ("encode", "four-d"), {"factors": [_factor("c02-c2-f1", "edge-c02-c2", context, "encode"), _factor("c02-c2-f2", "edge-c02-c2", context, "four-d", state=CausalState.MEASURED_NEGATIVE.value, support=0.1)]}, CausalState.CONTRADICTORY, ("contradictory_factor_edge",), "supported and measured-negative factors share one edge"),
        _record("D11-C02-C3", CausalFoundationFrontierOperation.FACTOR_GRAPH, CausalFoundationFrontierRole.CONTROL, foreign, ("encode",), {"factors": [_factor("c02-c3-f1", "edge-c02-c3", foreign, "encode")]}, CausalState.OUT_OF_DOMAIN, ("context_mismatch",), "foreign graph context is not transported"),
        _record("D11-C03-P", CausalFoundationFrontierOperation.CONTEXT_PRIOR, CausalFoundationFrontierRole.POSITIVE, context, ("gtex", "geo"), {"profile": _profile("prior-c03-p", context), "features": {"stem_signal": 0.8, "chromatin_score": 0.75}}, CausalState.SUPPORTED, (), "bounded prior evaluates all declared features"),
        _record("D11-C03-C1", CausalFoundationFrontierOperation.CONTEXT_PRIOR, CausalFoundationFrontierRole.CONTROL, context, ("gtex",), {"profile": _profile("prior-c03-c1", context), "features": {"stem_signal": 0.8}}, CausalState.ABSTAINED, ("missing_prior_feature",), "missing feature produces prior abstention"),
        _record("D11-C03-C2", CausalFoundationFrontierOperation.CONTEXT_PRIOR, CausalFoundationFrontierRole.CONTROL, context, ("gtex",), {"profile": _profile("prior-c03-c2", context), "features": {"stem_signal": 1.4, "chromatin_score": 0.75}}, CausalState.OUT_OF_DOMAIN, ("prior_feature_out_of_range",), "out-of-support feature is quarantined"),
        _record("D11-C03-C3", CausalFoundationFrontierOperation.CONTEXT_PRIOR, CausalFoundationFrontierRole.CONTROL, foreign, ("gtex",), {"profile": _profile("prior-c03-c3", context), "features": {"stem_signal": 0.8, "chromatin_score": 0.75}}, CausalState.OUT_OF_DOMAIN, ("context_mismatch",), "prior profile context mismatch is explicit"),
        _record("D11-C04-P", CausalFoundationFrontierOperation.MEASUREMENT_LIKELIHOOD, CausalFoundationFrontierRole.POSITIVE, context, ("encode", "four-d", "geo"), {"edge_id": "edge-c04-p", "measurements": [_measurement("c04-m1", "edge-c04-p", context, "accessibility", "encode"), _measurement("c04-m2", "edge-c04-p", context, "contact", "four-d"), _measurement("c04-m3", "edge-c04-p", context, "qtl", "geo")]}, CausalState.SUPPORTED, (), "dependent channels collapse into independent measurement groups"),
        _record("D11-C04-C1", CausalFoundationFrontierOperation.MEASUREMENT_LIKELIHOOD, CausalFoundationFrontierRole.CONTROL, context, ("four-d",), {"edge_id": "edge-c04-c1", "measurements": [_measurement("c04-c1-m1", "edge-c04-c1", context, "contact", "four-d")]}, CausalState.PARTIAL, ("single_measurement_group",), "one usable group remains partial"),
        _record("D11-C04-C2", CausalFoundationFrontierOperation.MEASUREMENT_LIKELIHOOD, CausalFoundationFrontierRole.CONTROL, context, ("encode", "four-d"), {"edge_id": "edge-c04-c2", "measurements": [_measurement("c04-c2-m1", "edge-c04-c2", context, "accessibility", "encode", state=CausalState.CONTRADICTORY.value, score=None), _measurement("c04-c2-m2", "edge-c04-c2", context, "contact", "four-d")]}, CausalState.CONTRADICTORY, ("contradictory_measurement",), "contradictory measurement state is not averaged away"),
        _record("D11-C04-C3", CausalFoundationFrontierOperation.MEASUREMENT_LIKELIHOOD, CausalFoundationFrontierRole.CONTROL, foreign, ("four-d",), {"edge_id": "edge-c04-c3", "measurements": [_measurement("c04-c3-m1", "edge-c04-c3", foreign, "contact", "four-d")]}, CausalState.OUT_OF_DOMAIN, ("context_mismatch",), "foreign measurement context is quarantined"),
    )
    return CausalFoundationFrontierFixture(
        "causal-foundation-frontier-public-aggregate",
        CAUSAL_FOUNDATION_FRONTIER_FIXTURE_VERSION,
        context,
        foreign,
        CAUSAL_FOUNDATION_FRONTIER_BOUNDARY,
        sources,
        records,
    )


def audit_causal_foundation_frontier_data(
    fixture: CausalFoundationFrontierFixture | None = None,
) -> CausalFoundationFrontierDataAudit:
    value = fixture or default_causal_foundation_frontier_fixture()
    source_ids = set(value.source_map())
    checks = (
        {"check_id": "boundary", "passed": value.boundary == CAUSAL_FOUNDATION_FRONTIER_BOUNDARY, "detail": "aggregate non-patient boundary"},
        {"check_id": "version", "passed": value.version == CAUSAL_FOUNDATION_FRONTIER_FIXTURE_VERSION, "detail": "fixture version pinned"},
        {"check_id": "sources", "passed": len(value.sources) == 5, "detail": "five public source receipts"},
        {"check_id": "records", "passed": len(value.records) == 16, "detail": "sixteen operation rows"},
        {"check_id": "positive", "passed": len(value.positive_records) == 4, "detail": "one positive per operation"},
        {"check_id": "controls", "passed": len(value.control_records) == 12, "detail": "three controls per operation"},
        {"check_id": "operations", "passed": {item.operation for item in value.records} == set(CausalFoundationFrontierOperation), "detail": "four operations closed"},
        {"check_id": "source_references", "passed": all(set(item.source_ids) <= source_ids for item in value.records), "detail": "source IDs resolve"},
        {"check_id": "unique_records", "passed": len(value.record_map()) == len(value.records), "detail": "record IDs unique"},
        {"check_id": "content_addresses", "passed": all(item.content_address.startswith("sha256:") for item in value.records), "detail": "record receipts addressed"},
        {"check_id": "context_controls", "passed": sum(item.context_key == value.foreign_context_key for item in value.records) == 4, "detail": "foreign context controls retained"},
        {"check_id": "payloads", "passed": all(item.payload for item in value.records), "detail": "payloads are non-empty"},
    )
    checks = tuple({**item, "content_address": content_hash(item)} for item in checks)
    return CausalFoundationFrontierDataAudit(value.fixture_id, len(value.records), len(value.sources), len(value.positive_records), len(value.control_records), sum(item.context_key == value.foreign_context_key for item in value.records), checks, all(item["passed"] for item in checks))


def causal_foundation_frontier_fixture_json(
    fixture: CausalFoundationFrontierFixture | None = None,
) -> str:
    import json

    return json.dumps((fixture or default_causal_foundation_frontier_fixture()).to_dict(), sort_keys=True, default=str)


__all__ = [
    "CAUSAL_FOUNDATION_FRONTIER_BOUNDARY",
    "CAUSAL_FOUNDATION_FRONTIER_CONTEXT_KEY",
    "CAUSAL_FOUNDATION_FRONTIER_FIXTURE_VERSION",
    "CAUSAL_FOUNDATION_FRONTIER_FOREIGN_CONTEXT_KEY",
    "CausalFoundationFrontierDataAudit",
    "CausalFoundationFrontierFixture",
    "CausalFoundationFrontierOperation",
    "CausalFoundationFrontierRecord",
    "CausalFoundationFrontierRole",
    "CausalFoundationFrontierSource",
    "audit_causal_foundation_frontier_data",
    "causal_foundation_frontier_fixture_json",
    "default_causal_foundation_frontier_fixture",
]
