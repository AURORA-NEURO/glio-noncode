"""Public aggregate fixture for Domain 11 C09-C12 controls.

The fixture is intentionally small enough to audit by hand while exercising
all four external-alpha operations: source-omission sensitivity, confounder
checklists, dependence correction, and negative-evidence integration.  Every
row carries source receipts, an exact context, an expected bounded state, and
an address derived from the row envelope.  The data is aggregate and
non-patient; it is not a clinical or causal-effect dataset.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from .causal_reasoning import CausalState
from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty


CAUSAL_ALPHA_FRONTIER_FIXTURE_VERSION = "2026.08.d11-c09-c12.v1"
CAUSAL_ALPHA_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|core|unknown"
CAUSAL_ALPHA_FRONTIER_FOREIGN_CONTEXT_KEY = "GRCh38|glioma|adult|differentiated|core|unknown"
CAUSAL_ALPHA_FRONTIER_BOUNDARY = "public_aggregate_non_patient"


class CausalAlphaFrontierOperation(StrEnum):
    """Closed set of operations delivered by this frontier package."""

    MEDIATION_SENSITIVITY = "mediation_sensitivity"
    CONFOUNDING_CHECKLIST = "confounding_checklist"
    DEPENDENCE_CORRECTION = "dependence_correction"
    NEGATIVE_EVIDENCE = "negative_evidence"


class CausalAlphaFrontierRole(StrEnum):
    """Fixture role used to distinguish positive paths from controls."""

    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierSource:
    """A public source receipt attached to one or more fixture rows."""

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
            raise ValidationError("causal alpha source URI must use HTTPS")
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
class CausalAlphaFrontierRecord:
    """One closed fixture case and the payload consumed by an adapter."""

    record_id: str
    operation: CausalAlphaFrontierOperation
    role: CausalAlphaFrontierRole
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
        if not self.source_ids or not self.payload:
            raise ValidationError("causal alpha record requires receipts and payload")
        if not isinstance(self.operation, CausalAlphaFrontierOperation):
            raise ValidationError("causal alpha operation is not declared")
        if not isinstance(self.role, CausalAlphaFrontierRole):
            raise ValidationError("causal alpha role is not declared")
        if not isinstance(self.expected_state, CausalState):
            raise ValidationError("causal alpha expected state is not declared")
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
class CausalAlphaFrontierFixture:
    """Versioned aggregate fixture with a closed source and record set."""

    fixture_id: str
    version: str
    context_key: str
    foreign_context_key: str
    boundary: str
    sources: tuple[CausalAlphaFrontierSource, ...]
    records: tuple[CausalAlphaFrontierRecord, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        for name in ("fixture_id", "version", "context_key", "foreign_context_key", "boundary"):
            require_non_empty(str(getattr(self, name)), name)
        if self.boundary != CAUSAL_ALPHA_FRONTIER_BOUNDARY:
            raise ValidationError("unsupported causal alpha evidence boundary")
        if not self.sources or not self.records:
            raise ValidationError("causal alpha fixture requires sources and records")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def positive_records(self) -> tuple[CausalAlphaFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is CausalAlphaFrontierRole.POSITIVE)

    @property
    def control_records(self) -> tuple[CausalAlphaFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is CausalAlphaFrontierRole.CONTROL)

    def source_map(self) -> dict[str, CausalAlphaFrontierSource]:
        return {item.source_id: item for item in self.sources}

    def record_map(self) -> dict[str, CausalAlphaFrontierRecord]:
        return {item.record_id: item for item in self.records}

    def operation_records(self, operation: CausalAlphaFrontierOperation | str) -> tuple[CausalAlphaFrontierRecord, ...]:
        value = CausalAlphaFrontierOperation(str(operation))
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
class CausalAlphaFrontierDataAudit:
    """Receipt and closure checks for the public fixture."""

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


def _source(source_id: str, title: str, uri: str, source_kind: str, release: str, scope: str) -> CausalAlphaFrontierSource:
    return CausalAlphaFrontierSource(source_id, title, uri, source_kind, release, scope)


def _mediator(evidence_id: str, source_id: str, context_key: str, *, support: float = 0.82, uncertainty: float = 0.12, source_node: str = "variant:v1", target_node: str = "element:enh-1", direction: str = "supports") -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "mediator_kind": "sequence_to_element",
        "source_node": source_node,
        "target_node": target_node,
        "context_key": context_key,
        "support": support,
        "uncertainty": uncertainty,
        "source_id": source_id,
        "source_version": "public-alpha-2025.1",
        "raw_hash": content_hash({"evidence_id": evidence_id, "source_id": source_id, "context_key": context_key}),
        "direction": direction,
    }


def _confounder(observation_id: str, confounder_id: str, context_key: str, source_id: str, *, status: str = "addressed", addressed: bool | None = True, severity: float = 0.3, adjustment_method: str = "stratification") -> dict[str, Any]:
    return {
        "observation_id": observation_id,
        "confounder_id": confounder_id,
        "label": confounder_id.replace("_", " "),
        "status": status,
        "addressed": addressed,
        "severity": severity,
        "adjustment_method": adjustment_method,
        "context_key": context_key,
        "source_id": source_id,
        "source_version": "public-alpha-2025.1",
        "raw_hash": content_hash({"observation_id": observation_id, "confounder_id": confounder_id, "context_key": context_key}),
    }


def _dependence(evidence_id: str, group: str, context_key: str, source_id: str, *, support: float = 0.8, uncertainty: float = 0.1, state: str = "supported", method_family: str = "functional") -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "edge_id": "edge:variant-to-state",
        "method_family": method_family,
        "dependence_group": group,
        "support": support,
        "uncertainty": uncertainty,
        "context_key": context_key,
        "source_id": source_id,
        "source_version": "public-alpha-2025.1",
        "raw_hash": content_hash({"evidence_id": evidence_id, "group": group}),
        "state": state,
    }


def _negative(evidence_id: str, context_key: str, source_id: str, *, polarity: str = "positive", strength: float = 0.8, negative_control: bool = False, assay_label: str = "aggregate_assay") -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "edge_id": "edge:variant-to-state",
        "polarity": polarity,
        "strength": strength,
        "context_key": context_key,
        "source_id": source_id,
        "source_version": "public-alpha-2025.1",
        "raw_hash": content_hash({"evidence_id": evidence_id, "source_id": source_id}),
        "negative_control": negative_control,
        "assay_label": assay_label,
    }


def _record(record_id: str, operation: CausalAlphaFrontierOperation, role: CausalAlphaFrontierRole, context_key: str, source_ids: tuple[str, ...], payload: Mapping[str, Any], state: CausalState, issues: tuple[str, ...], description: str) -> CausalAlphaFrontierRecord:
    return CausalAlphaFrontierRecord(record_id, operation, role, context_key, source_ids, dict(payload), state, issues, description)


def default_causal_alpha_frontier_fixture() -> CausalAlphaFrontierFixture:
    context = CAUSAL_ALPHA_FRONTIER_CONTEXT_KEY
    foreign = CAUSAL_ALPHA_FRONTIER_FOREIGN_CONTEXT_KEY
    sources = (
        _source("encode", "ENCODE public functional genomics portal", "https://www.encodeproject.org/", "public_assay_archive", "2025-01", "aggregate functional and control evidence"),
        _source("geo", "NCBI Gene Expression Omnibus", "https://www.ncbi.nlm.nih.gov/geo/", "public_archive", "2025-01", "aggregate expression and perturbation references"),
        _source("gtex", "GTEx public portal", "https://gtexportal.org/home/", "public_expression_archive", "v8", "aggregate tissue and state references"),
        _source("pubmed", "PubMed public literature index", "https://pubmed.ncbi.nlm.nih.gov/", "public_literature_index", "2025-01", "method and evidence vocabulary"),
        _source("4dn", "4D Nucleome public data portal", "https://data.4dnucleome.org/", "public_topology_archive", "2025-01", "aggregate topology and replicate metadata"),
    )
    records = (
        _record("D11-C09-P", CausalAlphaFrontierOperation.MEDIATION_SENSITIVITY, CausalAlphaFrontierRole.POSITIVE, context, ("encode", "pubmed"), {"mediator_kind": "sequence_to_element", "source_node": "variant:v1", "target_node": "element:enh-1", "evidence": [_mediator("c09-p-a", "encode", context), _mediator("c09-p-b", "pubmed", context, support=0.74)]}, CausalState.SUPPORTED, (), "two public source paths remain supported under leave-one-source-out checks"),
        _record("D11-C09-C1", CausalAlphaFrontierOperation.MEDIATION_SENSITIVITY, CausalAlphaFrontierRole.CONTROL, context, ("encode",), {"mediator_kind": "sequence_to_element", "source_node": "variant:v1", "target_node": "element:enh-1", "evidence": [_mediator("c09-c1-a", "encode", context)]}, CausalState.PARTIAL, (), "a single mediator source cannot establish source-omission robustness"),
        _record("D11-C09-C2", CausalAlphaFrontierOperation.MEDIATION_SENSITIVITY, CausalAlphaFrontierRole.CONTROL, context, ("encode", "pubmed"), {"mediator_kind": "sequence_to_element", "source_node": "variant:v1", "target_node": "element:enh-1", "evidence": [_mediator("c09-c2-a", "encode", context, support=0.98), _mediator("c09-c2-b", "pubmed", context, support=0.2)]}, CausalState.PARTIAL, (), "source omission shifts support beyond the declared robustness tolerance"),
        _record("D11-C09-C3", CausalAlphaFrontierOperation.MEDIATION_SENSITIVITY, CausalAlphaFrontierRole.CONTROL, foreign, ("encode",), {"mediator_kind": "sequence_to_element", "source_node": "variant:v1", "target_node": "element:enh-1", "evidence": [_mediator("c09-c3-a", "encode", foreign)]}, CausalState.OUT_OF_DOMAIN, ("context_mismatch",), "foreign state context is quarantined"),
        _record("D11-C10-P", CausalAlphaFrontierOperation.CONFOUNDING_CHECKLIST, CausalAlphaFrontierRole.POSITIVE, context, ("geo", "gtex"), {"required_confounder_ids": ["batch", "purity", "sex"], "observations": [_confounder("c10-p-batch", "batch", context, "geo"), _confounder("c10-p-purity", "purity", context, "gtex"), _confounder("c10-p-sex", "sex", context, "geo", status="not_applicable", addressed=None, adjustment_method="design_scope")]}, CausalState.SUPPORTED, (), "all declared confounder checks are addressed or explicitly not applicable"),
        _record("D11-C10-C1", CausalAlphaFrontierOperation.CONFOUNDING_CHECKLIST, CausalAlphaFrontierRole.CONTROL, context, ("geo",), {"required_confounder_ids": ["batch", "purity", "sex"], "observations": [_confounder("c10-c1-batch", "batch", context, "geo")]}, CausalState.PARTIAL, (), "required purity and sex checks are missing"),
        _record("D11-C10-C2", CausalAlphaFrontierOperation.CONFOUNDING_CHECKLIST, CausalAlphaFrontierRole.CONTROL, context, ("geo", "gtex"), {"required_confounder_ids": ["batch", "purity"], "observations": [_confounder("c10-c2-batch", "batch", context, "geo"), _confounder("c10-c2-purity", "purity", context, "gtex", status="unresolved", addressed=False, severity=0.9, adjustment_method="not_yet_selected")]}, CausalState.PARTIAL, (), "an unresolved purity confounder keeps the checklist partial"),
        _record("D11-C10-C3", CausalAlphaFrontierOperation.CONFOUNDING_CHECKLIST, CausalAlphaFrontierRole.CONTROL, foreign, ("geo",), {"required_confounder_ids": ["batch"], "observations": [_confounder("c10-c3-batch", "batch", foreign, "geo")]}, CausalState.OUT_OF_DOMAIN, ("context_mismatch",), "foreign checklist context is not transported"),
        _record("D11-C11-P", CausalAlphaFrontierOperation.DEPENDENCE_CORRECTION, CausalAlphaFrontierRole.POSITIVE, context, ("encode", "geo", "4dn"), {"observations": [_dependence("c11-p-a", "functional-replicates", context, "encode", support=0.72), _dependence("c11-p-b", "expression-replicates", context, "geo", support=0.84, method_family="expression"), _dependence("c11-p-c", "topology-replicates", context, "4dn", support=0.78, method_family="topology")]}, CausalState.SUPPORTED, (), "three declared dependence groups retain one representative per group"),
        _record("D11-C11-C1", CausalAlphaFrontierOperation.DEPENDENCE_CORRECTION, CausalAlphaFrontierRole.CONTROL, context, ("encode", "geo"), {"observations": [_dependence("c11-c1-a", "functional-replicates", context, "encode"), _dependence("c11-c1-b", "functional-replicates", context, "geo", support=0.7)]}, CausalState.PARTIAL, (), "duplicate paths collapse to one independent group"),
        _record("D11-C11-C2", CausalAlphaFrontierOperation.DEPENDENCE_CORRECTION, CausalAlphaFrontierRole.CONTROL, context, ("encode", "geo"), {"observations": [_dependence("c11-c2-a", "functional-replicates", context, "encode"), _dependence("c11-c2-b", "expression-replicates", context, "geo", state="contradictory")]}, CausalState.CONTRADICTORY, (), "a declared contradictory path blocks corrected support"),
        _record("D11-C11-C3", CausalAlphaFrontierOperation.DEPENDENCE_CORRECTION, CausalAlphaFrontierRole.CONTROL, foreign, ("encode",), {"observations": [_dependence("c11-c3-a", "functional-replicates", foreign, "encode")]}, CausalState.OUT_OF_DOMAIN, ("context_mismatch",), "foreign dependence groups are excluded"),
        _record("D11-C12-P", CausalAlphaFrontierOperation.NEGATIVE_EVIDENCE, CausalAlphaFrontierRole.POSITIVE, context, ("geo",), {"observations": [_negative("c12-p-a", context, "geo", polarity="positive", strength=0.84)]}, CausalState.PARTIAL, (), "positive evidence remains partial until a negative-control path is declared"),
        _record("D11-C12-C1", CausalAlphaFrontierOperation.NEGATIVE_EVIDENCE, CausalAlphaFrontierRole.CONTROL, context, ("encode",), {"observations": [_negative("c12-c1-a", context, "encode", polarity="negative", strength=0.9)]}, CausalState.MEASURED_NEGATIVE, (), "negative-only observation is retained as measured negative"),
        _record("D11-C12-C2", CausalAlphaFrontierOperation.NEGATIVE_EVIDENCE, CausalAlphaFrontierRole.CONTROL, context, ("geo", "encode"), {"observations": [_negative("c12-c2-a", context, "geo", polarity="positive", strength=0.8), _negative("c12-c2-b", context, "encode", polarity="negative_control", strength=0.88, negative_control=True)]}, CausalState.CONTRADICTORY, (), "positive and negative-control paths remain explicitly contradictory"),
        _record("D11-C12-C3", CausalAlphaFrontierOperation.NEGATIVE_EVIDENCE, CausalAlphaFrontierRole.CONTROL, foreign, ("encode",), {"observations": [_negative("c12-c3-a", foreign, "encode", polarity="negative_control", strength=0.8, negative_control=True)]}, CausalState.OUT_OF_DOMAIN, ("context_mismatch",), "foreign negative evidence is quarantined"),
    )
    return CausalAlphaFrontierFixture("causal-alpha-frontier-public-aggregate", CAUSAL_ALPHA_FRONTIER_FIXTURE_VERSION, context, foreign, CAUSAL_ALPHA_FRONTIER_BOUNDARY, sources, records)


def audit_causal_alpha_frontier_data(fixture: CausalAlphaFrontierFixture | None = None) -> CausalAlphaFrontierDataAudit:
    value = fixture or default_causal_alpha_frontier_fixture()
    source_ids = set(value.source_map())
    checks = (
        {"check_id": "boundary", "passed": value.boundary == CAUSAL_ALPHA_FRONTIER_BOUNDARY, "detail": "aggregate non-patient boundary"},
        {"check_id": "version", "passed": value.version == CAUSAL_ALPHA_FRONTIER_FIXTURE_VERSION, "detail": "fixture version pinned"},
        {"check_id": "sources", "passed": len(value.sources) == 5, "detail": "five public receipts"},
        {"check_id": "records", "passed": len(value.records) == 16, "detail": "sixteen alpha control rows"},
        {"check_id": "positives", "passed": len(value.positive_records) == 4, "detail": "one positive per operation"},
        {"check_id": "controls", "passed": len(value.control_records) == 12, "detail": "three controls per operation"},
        {"check_id": "operations", "passed": {item.operation for item in value.records} == set(CausalAlphaFrontierOperation), "detail": "four operations closed"},
        {"check_id": "source_references", "passed": all(set(item.source_ids) <= source_ids for item in value.records), "detail": "source IDs resolve"},
        {"check_id": "unique_records", "passed": len(value.record_map()) == len(value.records), "detail": "record IDs unique"},
        {"check_id": "addresses", "passed": all(item.content_address.startswith("sha256:") for item in value.records), "detail": "record addresses present"},
        {"check_id": "foreign_controls", "passed": sum(item.context_key == value.foreign_context_key for item in value.records) == 4, "detail": "one foreign control per operation"},
        {"check_id": "payloads", "passed": all(item.payload for item in value.records), "detail": "payloads present"},
    )
    checks = tuple({**item, "content_address": content_hash(item)} for item in checks)
    return CausalAlphaFrontierDataAudit(value.fixture_id, len(value.records), len(value.sources), len(value.positive_records), len(value.control_records), sum(item.context_key == value.foreign_context_key for item in value.records), checks, all(item["passed"] for item in checks))


__all__ = [
    "CAUSAL_ALPHA_FRONTIER_BOUNDARY",
    "CAUSAL_ALPHA_FRONTIER_CONTEXT_KEY",
    "CAUSAL_ALPHA_FRONTIER_FIXTURE_VERSION",
    "CAUSAL_ALPHA_FRONTIER_FOREIGN_CONTEXT_KEY",
    "CausalAlphaFrontierDataAudit",
    "CausalAlphaFrontierFixture",
    "CausalAlphaFrontierOperation",
    "CausalAlphaFrontierRecord",
    "CausalAlphaFrontierRole",
    "CausalAlphaFrontierSource",
    "audit_causal_alpha_frontier_data",
    "default_causal_alpha_frontier_fixture",
]
