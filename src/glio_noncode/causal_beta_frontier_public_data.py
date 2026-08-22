"""Public aggregate fixture for Domain 11 C05-C08 mediator controls."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from .causal_beta import CausalBetaState, CausalEvidenceDirection, MediatorKind
from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty


CAUSAL_BETA_FRONTIER_FIXTURE_VERSION = "2026.08.d11-c05-c08.v1"
CAUSAL_BETA_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|core|unknown"
CAUSAL_BETA_FRONTIER_FOREIGN_CONTEXT_KEY = "GRCh38|glioma|adult|differentiated|core|unknown"
CAUSAL_BETA_FRONTIER_BOUNDARY = "public_aggregate_non_patient"


class CausalBetaFrontierOperation(StrEnum):
    SEQUENCE_TO_ELEMENT = "sequence_to_element"
    ELEMENT_TO_GENE = "element_to_gene"
    GENE_TO_STATE = "gene_to_state"
    COUNTERFACTUAL_ALLELE_STATE = "counterfactual_allele_state"


class CausalBetaFrontierRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierSource:
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
            raise ValidationError("causal beta source URI must use HTTPS")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"source_id": self.source_id, "title": self.title, "uri": self.uri, "source_kind": self.source_kind, "release": self.release, "scope": self.scope}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierRecord:
    record_id: str
    operation: CausalBetaFrontierOperation
    role: CausalBetaFrontierRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    expected_state: CausalBetaState
    expected_issue_codes: tuple[str, ...]
    description: str
    content_address: str = ""

    def __post_init__(self) -> None:
        for name in ("record_id", "context_key", "description"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.source_ids or not self.payload:
            raise ValidationError("causal beta record requires source receipts and payload")
        if not isinstance(self.operation, CausalBetaFrontierOperation):
            raise ValidationError("causal beta operation is not declared")
        if not isinstance(self.role, CausalBetaFrontierRole):
            raise ValidationError("causal beta role is not declared")
        if not isinstance(self.expected_state, CausalBetaState):
            raise ValidationError("causal beta state is not declared")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"record_id": self.record_id, "operation": self.operation, "role": self.role, "context_key": self.context_key, "source_ids": self.source_ids, "payload": dict(self.payload), "expected_state": self.expected_state, "expected_issue_codes": self.expected_issue_codes, "description": self.description}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierFixture:
    fixture_id: str
    version: str
    context_key: str
    foreign_context_key: str
    boundary: str
    sources: tuple[CausalBetaFrontierSource, ...]
    records: tuple[CausalBetaFrontierRecord, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        for name in ("fixture_id", "version", "context_key", "foreign_context_key", "boundary"):
            require_non_empty(str(getattr(self, name)), name)
        if self.boundary != CAUSAL_BETA_FRONTIER_BOUNDARY:
            raise ValidationError("unsupported causal beta evidence boundary")
        if not self.sources or not self.records:
            raise ValidationError("causal beta fixture requires sources and records")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def positive_records(self) -> tuple[CausalBetaFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is CausalBetaFrontierRole.POSITIVE)

    @property
    def control_records(self) -> tuple[CausalBetaFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is CausalBetaFrontierRole.CONTROL)

    def source_map(self) -> dict[str, CausalBetaFrontierSource]:
        return {item.source_id: item for item in self.sources}

    def record_map(self) -> dict[str, CausalBetaFrontierRecord]:
        return {item.record_id: item for item in self.records}

    def operation_records(self, operation: CausalBetaFrontierOperation | str) -> tuple[CausalBetaFrontierRecord, ...]:
        value = CausalBetaFrontierOperation(str(operation))
        return tuple(item for item in self.records if item.operation is value)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "version": self.version, "context_key": self.context_key, "foreign_context_key": self.foreign_context_key, "boundary": self.boundary, "sources": [item.to_dict() for item in self.sources], "records": [item.to_dict() for item in self.records]}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierDataAudit:
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
        value = {"fixture_id": self.fixture_id, "record_count": self.record_count, "source_count": self.source_count, "positive_count": self.positive_count, "control_count": self.control_count, "foreign_context_count": self.foreign_context_count, "checks": self.checks, "failed_checks": self.failed_checks, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _source(source_id: str, title: str, uri: str, source_kind: str, release: str, scope: str) -> CausalBetaFrontierSource:
    return CausalBetaFrontierSource(source_id, title, uri, source_kind, release, scope)


def _evidence(evidence_id: str, source_id: str, kind: str, source_node: str, target_node: str, context_key: str, *, support: float = 0.82, uncertainty: float = 0.12, direction: str = CausalEvidenceDirection.SUPPORTS.value, sensitivity: float = 0.72, negative_control: bool = False) -> dict[str, Any]:
    return {"evidence_id": evidence_id, "mediator_kind": kind, "source_node": source_node, "target_node": target_node, "context_key": context_key, "support": support, "uncertainty": uncertainty, "source_id": source_id, "source_version": "public-beta-2025.1", "raw_hash": content_hash({"evidence_id": evidence_id, "source_id": source_id, "context_key": context_key}), "direction": direction, "sensitivity": sensitivity, "negative_control": negative_control}


def _observation(observation_id: str, allele: str, state_id: str, value: float, context_key: str, source_id: str) -> dict[str, Any]:
    return {"observation_id": observation_id, "allele": allele, "state_id": state_id, "value": value, "uncertainty": 0.1, "context_key": context_key, "source_id": source_id, "source_version": "public-allele-2025.1", "raw_hash": content_hash({"observation_id": observation_id, "allele": allele, "value": value})}


def _record(record_id: str, operation: CausalBetaFrontierOperation, role: CausalBetaFrontierRole, context_key: str, source_ids: tuple[str, ...], payload: Mapping[str, Any], state: CausalBetaState, issues: tuple[str, ...], description: str) -> CausalBetaFrontierRecord:
    return CausalBetaFrontierRecord(record_id, operation, role, context_key, source_ids, dict(payload), state, issues, description)


def default_causal_beta_frontier_fixture() -> CausalBetaFrontierFixture:
    context = CAUSAL_BETA_FRONTIER_CONTEXT_KEY
    foreign = CAUSAL_BETA_FRONTIER_FOREIGN_CONTEXT_KEY
    sources = (
        _source("encode", "ENCODE public functional genomics portal", "https://www.encodeproject.org/", "public_assay_archive", "2025-01", "aggregate regulatory and accessibility evidence"),
        _source("four-d", "4D Nucleome public data portal", "https://data.4dnucleome.org/", "public_topology_archive", "2025-01", "aggregate contact and topology evidence"),
        _source("geo", "NCBI Gene Expression Omnibus", "https://www.ncbi.nlm.nih.gov/geo/", "public_archive", "2025-01", "aggregate expression and perturbation references"),
        _source("gtex", "GTEx public portal", "https://gtexportal.org/home/", "public_expression_archive", "v8", "aggregate tissue and state references"),
        _source("pubmed", "PubMed public literature index", "https://pubmed.ncbi.nlm.nih.gov/", "public_literature_index", "2025-01", "method and evidence vocabulary"),
    )
    records = (
        _record("D11-C05-P", CausalBetaFrontierOperation.SEQUENCE_TO_ELEMENT, CausalBetaFrontierRole.POSITIVE, context, ("encode", "pubmed"), {"source_node": "variant:v1", "target_node": "element:enh-1", "evidence": [_evidence("c05-p-a", "encode", "sequence_to_element", "variant:v1", "element:enh-1", context), _evidence("c05-p-b", "pubmed", "sequence_to_element", "variant:v1", "element:enh-1", context, support=0.74)]}, CausalBetaState.SUPPORTED, (), "two independent public paths support the sequence-to-element mediator"),
        _record("D11-C05-C1", CausalBetaFrontierOperation.SEQUENCE_TO_ELEMENT, CausalBetaFrontierRole.CONTROL, context, ("encode",), {"source_node": "variant:v1", "target_node": "element:enh-1", "evidence": [_evidence("c05-c1-a", "encode", "sequence_to_element", "variant:v1", "element:enh-1", context)]}, CausalBetaState.PARTIAL, ("minimum_independent_sources",), "one source path remains below the independent-source minimum"),
        _record("D11-C05-C2", CausalBetaFrontierOperation.SEQUENCE_TO_ELEMENT, CausalBetaFrontierRole.CONTROL, context, ("encode", "pubmed"), {"source_node": "variant:v1", "target_node": "element:enh-1", "evidence": [_evidence("c05-c2-a", "encode", "sequence_to_element", "variant:v1", "element:enh-1", context), _evidence("c05-c2-b", "pubmed", "sequence_to_element", "variant:v1", "element:enh-1", context, direction=CausalEvidenceDirection.AGAINST.value, support=0.2)]}, CausalBetaState.CONTRADICTORY, ("contradictory_direction",), "supporting and against-direction paths coexist"),
        _record("D11-C05-C3", CausalBetaFrontierOperation.SEQUENCE_TO_ELEMENT, CausalBetaFrontierRole.CONTROL, foreign, ("encode",), {"source_node": "variant:v1", "target_node": "element:enh-1", "evidence": [_evidence("c05-c3-a", "encode", "sequence_to_element", "variant:v1", "element:enh-1", foreign)]}, CausalBetaState.OUT_OF_DOMAIN, ("context_mismatch",), "foreign cell-state context is quarantined"),
        _record("D11-C06-P", CausalBetaFrontierOperation.ELEMENT_TO_GENE, CausalBetaFrontierRole.POSITIVE, context, ("four-d", "geo"), {"source_node": "element:enh-1", "target_node": "gene:GENE1", "evidence": [_evidence("c06-p-a", "four-d", "element_to_gene", "element:enh-1", "gene:GENE1", context), _evidence("c06-p-b", "geo", "element_to_gene", "element:enh-1", "gene:GENE1", context, support=0.76)]}, CausalBetaState.SUPPORTED, (), "independent topology and expression paths support the element-to-gene mediator"),
        _record("D11-C06-C1", CausalBetaFrontierOperation.ELEMENT_TO_GENE, CausalBetaFrontierRole.CONTROL, context, ("four-d",), {"source_node": "element:enh-1", "target_node": "gene:GENE1", "evidence": [_evidence("c06-c1-a", "four-d", "element_to_gene", "element:enh-1", "gene:GENE1", context)]}, CausalBetaState.PARTIAL, ("minimum_independent_sources",), "one topology path is insufficient for the edge"),
        _record("D11-C06-C2", CausalBetaFrontierOperation.ELEMENT_TO_GENE, CausalBetaFrontierRole.CONTROL, context, ("four-d", "geo"), {"source_node": "element:enh-1", "target_node": "gene:GENE1", "evidence": [_evidence("c06-c2-a", "four-d", "element_to_gene", "element:enh-1", "gene:GENE1", context), _evidence("c06-c2-b", "geo", "element_to_gene", "element:enh-1", "gene:GENE1", context, direction=CausalEvidenceDirection.AGAINST.value)]}, CausalBetaState.CONTRADICTORY, ("contradictory_direction",), "directional disagreement is retained"),
        _record("D11-C06-C3", CausalBetaFrontierOperation.ELEMENT_TO_GENE, CausalBetaFrontierRole.CONTROL, foreign, ("four-d",), {"source_node": "element:enh-1", "target_node": "gene:GENE1", "evidence": [_evidence("c06-c3-a", "four-d", "element_to_gene", "element:enh-1", "gene:GENE1", foreign)]}, CausalBetaState.OUT_OF_DOMAIN, ("context_mismatch",), "foreign context is not transported to the gene edge"),
        _record("D11-C07-P", CausalBetaFrontierOperation.GENE_TO_STATE, CausalBetaFrontierRole.POSITIVE, context, ("geo", "gtex"), {"source_node": "gene:GENE1", "target_node": "state:stem_like", "evidence": [_evidence("c07-p-a", "geo", "gene_to_state", "gene:GENE1", "state:stem_like", context), _evidence("c07-p-b", "gtex", "gene_to_state", "gene:GENE1", "state:stem_like", context, support=0.78)]}, CausalBetaState.SUPPORTED, (), "independent expression paths support the gene-to-state mediator"),
        _record("D11-C07-C1", CausalBetaFrontierOperation.GENE_TO_STATE, CausalBetaFrontierRole.CONTROL, context, ("geo",), {"source_node": "gene:GENE1", "target_node": "state:stem_like", "evidence": [_evidence("c07-c1-a", "geo", "gene_to_state", "gene:GENE1", "state:stem_like", context)]}, CausalBetaState.PARTIAL, ("minimum_independent_sources",), "one expression path remains partial"),
        _record("D11-C07-C2", CausalBetaFrontierOperation.GENE_TO_STATE, CausalBetaFrontierRole.CONTROL, context, ("geo", "gtex"), {"source_node": "gene:GENE1", "target_node": "state:stem_like", "evidence": [_evidence("c07-c2-a", "geo", "gene_to_state", "gene:GENE1", "state:stem_like", context), _evidence("c07-c2-b", "gtex", "gene_to_state", "gene:GENE1", "state:stem_like", context, negative_control=True)]}, CausalBetaState.CONTRADICTORY, ("negative_control_conflict",), "positive path conflicts with a declared negative control"),
        _record("D11-C07-C3", CausalBetaFrontierOperation.GENE_TO_STATE, CausalBetaFrontierRole.CONTROL, foreign, ("geo",), {"source_node": "gene:GENE1", "target_node": "state:stem_like", "evidence": [_evidence("c07-c3-a", "geo", "gene_to_state", "gene:GENE1", "state:stem_like", foreign)]}, CausalBetaState.OUT_OF_DOMAIN, ("context_mismatch",), "state-specific context mismatch is quarantined"),
        _record("D11-C08-P", CausalBetaFrontierOperation.COUNTERFACTUAL_ALLELE_STATE, CausalBetaFrontierRole.POSITIVE, context, ("encode", "geo"), {"state_id": "state:open", "observations": [_observation("c08-p-ref", "reference", "state:open", 0.22, context, "encode"), _observation("c08-p-alt", "alternate", "state:open", 0.81, context, "geo")]}, CausalBetaState.SUPPORTED, (), "reference and alternate aggregate observations yield a descriptive delta"),
        _record("D11-C08-C1", CausalBetaFrontierOperation.COUNTERFACTUAL_ALLELE_STATE, CausalBetaFrontierRole.CONTROL, context, ("encode",), {"state_id": "state:open", "observations": [_observation("c08-c1-ref", "reference", "state:open", 0.22, context, "encode")]}, CausalBetaState.PARTIAL, ("missing_alternate_allele",), "reference-only observation cannot form a delta"),
        _record("D11-C08-C2", CausalBetaFrontierOperation.COUNTERFACTUAL_ALLELE_STATE, CausalBetaFrontierRole.CONTROL, context, ("encode", "geo"), {"state_id": "state:open", "observations": [_observation("c08-c2-ref-a", "reference", "state:open", 0.1, context, "encode"), _observation("c08-c2-ref-b", "reference", "state:open", 0.82, context, "geo"), _observation("c08-c2-alt", "alternate", "state:open", 0.9, context, "geo")]}, CausalBetaState.AMBIGUOUS, ("replicate_ambiguity",), "replicate spread exceeds the declared ambiguity tolerance"),
        _record("D11-C08-C3", CausalBetaFrontierOperation.COUNTERFACTUAL_ALLELE_STATE, CausalBetaFrontierRole.CONTROL, foreign, ("geo",), {"state_id": "state:open", "observations": [_observation("c08-c3-ref", "reference", "state:open", 0.2, foreign, "geo"), _observation("c08-c3-alt", "alternate", "state:open", 0.8, foreign, "geo")]}, CausalBetaState.OUT_OF_DOMAIN, ("context_mismatch",), "foreign context is not transported into allele comparison"),
    )
    return CausalBetaFrontierFixture("causal-beta-frontier-public-aggregate", CAUSAL_BETA_FRONTIER_FIXTURE_VERSION, context, foreign, CAUSAL_BETA_FRONTIER_BOUNDARY, sources, records)


def audit_causal_beta_frontier_data(fixture: CausalBetaFrontierFixture | None = None) -> CausalBetaFrontierDataAudit:
    value = fixture or default_causal_beta_frontier_fixture()
    source_ids = set(value.source_map())
    checks = (
        {"check_id": "boundary", "passed": value.boundary == CAUSAL_BETA_FRONTIER_BOUNDARY, "detail": "aggregate non-patient boundary"},
        {"check_id": "version", "passed": value.version == CAUSAL_BETA_FRONTIER_FIXTURE_VERSION, "detail": "fixture version pinned"},
        {"check_id": "sources", "passed": len(value.sources) == 5, "detail": "five public receipts"},
        {"check_id": "records", "passed": len(value.records) == 16, "detail": "sixteen mediator and counterfactual rows"},
        {"check_id": "positives", "passed": len(value.positive_records) == 4, "detail": "one positive per operation"},
        {"check_id": "controls", "passed": len(value.control_records) == 12, "detail": "three controls per operation"},
        {"check_id": "operations", "passed": {item.operation for item in value.records} == set(CausalBetaFrontierOperation), "detail": "four operations closed"},
        {"check_id": "source_references", "passed": all(set(item.source_ids) <= source_ids for item in value.records), "detail": "source IDs resolve"},
        {"check_id": "unique_records", "passed": len(value.record_map()) == len(value.records), "detail": "record IDs unique"},
        {"check_id": "addresses", "passed": all(item.content_address.startswith("sha256:") for item in value.records), "detail": "record addresses present"},
        {"check_id": "foreign_controls", "passed": sum(item.context_key == value.foreign_context_key for item in value.records) == 4, "detail": "one foreign control per operation"},
        {"check_id": "payloads", "passed": all(item.payload for item in value.records), "detail": "payloads present"},
    )
    checks = tuple({**item, "content_address": content_hash(item)} for item in checks)
    return CausalBetaFrontierDataAudit(value.fixture_id, len(value.records), len(value.sources), len(value.positive_records), len(value.control_records), sum(item.context_key == value.foreign_context_key for item in value.records), checks, all(item["passed"] for item in checks))


def causal_beta_frontier_fixture_json(fixture: CausalBetaFrontierFixture | None = None) -> str:
    import json

    return json.dumps((fixture or default_causal_beta_frontier_fixture()).to_dict(), sort_keys=True, default=str)


__all__ = ["CAUSAL_BETA_FRONTIER_BOUNDARY", "CAUSAL_BETA_FRONTIER_CONTEXT_KEY", "CAUSAL_BETA_FRONTIER_FIXTURE_VERSION", "CAUSAL_BETA_FRONTIER_FOREIGN_CONTEXT_KEY", "CausalBetaFrontierDataAudit", "CausalBetaFrontierFixture", "CausalBetaFrontierOperation", "CausalBetaFrontierRecord", "CausalBetaFrontierRole", "CausalBetaFrontierSource", "audit_causal_beta_frontier_data", "causal_beta_frontier_fixture_json", "default_causal_beta_frontier_fixture"]
