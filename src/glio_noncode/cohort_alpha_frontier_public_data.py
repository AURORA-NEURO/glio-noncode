"""Public aggregate fixture for Domain 12 C09-C12."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .cohort_alpha import CohortAlphaState
from .serialization import content_hash, jsonable, require_non_empty

C09_C12_CONTEXT = "GRCh38|glioma|adult|stem_like|tumor_core|pre_treatment"
C09_C12_FOREIGN_CONTEXT = "GRCh38|glioma|adult|stem_like|tumor_margin|post_treatment"
C09_C12_FIXTURE_VERSION = "2026.08.d12-c09-c12.v1"
C09_C12_BOUNDARY = "descriptive_public_longitudinal_aggregate_evidence"


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierSource:
    source_id: str
    label: str
    url: str
    version: str
    retrieval_note: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("source_id", "label", "url", "version", "retrieval_note"):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierRecord:
    operation: str
    record_id: str
    payload: Mapping[str, Any]
    expected_state: CohortAlphaState
    control_class: str
    source_ids: tuple[str, ...]
    rationale: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierFixture:
    fixture_id: str
    fixture_version: str
    context_key: str
    foreign_context_key: str
    boundary: str
    sources: tuple[CohortAlphaFrontierSource, ...]
    records: tuple[CohortAlphaFrontierRecord, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    content_address: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.fixture_id, "fixture_id")
        require_non_empty(self.fixture_version, "fixture_version")
        require_non_empty(self.context_key, "context_key")
        if len(self.records) != 16:
            raise ValueError("C09-C12 fixture requires sixteen operation paths")
        if {item.operation for item in self.records} != {"C09", "C10", "C11", "C12"}:
            raise ValueError("C09-C12 fixture must cover all four operations")

    @property
    def operations(self) -> tuple[str, ...]:
        return tuple(sorted({item.operation for item in self.records}))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierDataAudit:
    fixture_id: str
    source_count: int
    record_count: int
    operation_counts: Mapping[str, int]
    control_counts: Mapping[str, int]
    foreign_context_count: int
    accepted: bool
    findings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _source(source_id: str, label: str, url: str, note: str) -> CohortAlphaFrontierSource:
    body = {"source_id": source_id, "label": label, "url": url, "version": "public-aggregate-2026", "retrieval_note": note}
    return CohortAlphaFrontierSource(**body, content_address=content_hash(body, prefix="alpha-source"))


def _record(operation: str, record_id: str, payload: Mapping[str, Any], state: CohortAlphaState, control_class: str, source_ids: tuple[str, ...], rationale: str) -> CohortAlphaFrontierRecord:
    body = {"operation": operation, "record_id": record_id, "payload": payload, "expected_state": state, "control_class": control_class, "source_ids": source_ids, "rationale": rationale}
    return CohortAlphaFrontierRecord(**body, content_address=content_hash(body, prefix="alpha-record"))


def _clonality_payload(context: str, prefix: str, mode: str) -> dict[str, Any]:
    rows = [{"observation_id": f"{prefix}-c1", "variant_id": f"{prefix}-v1", "sample_id": f"{prefix}-primary", "cancer_cell_fraction": 0.90, "phase": "primary", "timepoint": 1, "context_key": context, "source_id": "gdc-longitudinal", "source_version": C09_C12_FIXTURE_VERSION}, {"observation_id": f"{prefix}-c2", "variant_id": f"{prefix}-v1", "sample_id": f"{prefix}-recurrence", "cancer_cell_fraction": 0.88, "phase": "recurrence", "timepoint": 2, "context_key": context, "source_id": "icgc-longitudinal", "source_version": C09_C12_FIXTURE_VERSION}]
    if mode == "partial":
        rows = [{"observation_id": f"{prefix}-partial", "variant_id": f"{prefix}-v1", "sample_id": f"{prefix}-sample", "phase": "primary", "timepoint": 1, "context_key": context, "source_id": "gdc-longitudinal", "source_version": C09_C12_FIXTURE_VERSION}]
    elif mode == "foreign":
        rows = [dict(rows[0], context_key=C09_C12_FOREIGN_CONTEXT)]
    elif mode == "abstained":
        rows = []
    return {"observations": rows, "clonal_threshold": 0.85, "subclonal_threshold": 0.25}


def _recurrence_payload(context: str, prefix: str, mode: str) -> dict[str, Any]:
    rows = [{"observation_id": f"{prefix}-p", "variant_id": f"{prefix}-v1", "locus_id": f"{prefix}-l1", "sample_id": f"{prefix}-primary", "phase": "primary", "frequency": 0.20, "context_key": context, "source_id": "gdc-longitudinal", "source_version": C09_C12_FIXTURE_VERSION}, {"observation_id": f"{prefix}-r", "variant_id": f"{prefix}-v1", "locus_id": f"{prefix}-l1", "sample_id": f"{prefix}-recurrence", "phase": "recurrence", "frequency": 0.60, "context_key": context, "source_id": "icgc-longitudinal", "source_version": C09_C12_FIXTURE_VERSION}]
    if mode == "partial":
        rows = [rows[0]]
    elif mode == "foreign":
        rows = [dict(rows[0], context_key=C09_C12_FOREIGN_CONTEXT)]
    elif mode == "abstained":
        rows = []
    return {"observations": rows, "change_threshold": 0.20}


def _treatment_payload(context: str, prefix: str, mode: str) -> dict[str, Any]:
    rows = [{"observation_id": f"{prefix}-pre", "variant_id": f"{prefix}-v1", "sample_id": f"{prefix}-pre", "treatment_id": "drug-a", "selection_phase": "pre_treatment", "frequency": 0.20, "context_key": context, "source_id": "gdc-treatment", "source_version": C09_C12_FIXTURE_VERSION}, {"observation_id": f"{prefix}-post", "variant_id": f"{prefix}-v1", "sample_id": f"{prefix}-post", "treatment_id": "drug-a", "selection_phase": "post_treatment", "frequency": 0.60, "response_label": "progression", "context_key": context, "source_id": "icgc-treatment", "source_version": C09_C12_FIXTURE_VERSION}]
    if mode == "partial":
        rows = [rows[0]]
    elif mode == "foreign":
        rows = [dict(rows[1], context_key=C09_C12_FOREIGN_CONTEXT)]
    elif mode == "abstained":
        rows = []
    return {"observations": rows, "change_threshold": 0.20}


def _replication_payload(context: str, prefix: str, mode: str) -> dict[str, Any]:
    rows = [{"observation_id": f"{prefix}-a", "feature_id": f"{prefix}-v1", "cohort_id": "cohort-a", "effect": 0.40, "support": 0.80, "sample_count": 10, "context_key": context, "source_id": "study-a", "source_version": C09_C12_FIXTURE_VERSION}, {"observation_id": f"{prefix}-b", "feature_id": f"{prefix}-v1", "cohort_id": "cohort-b", "effect": 0.30, "support": 0.70, "sample_count": 12, "context_key": context, "source_id": "study-b", "source_version": C09_C12_FIXTURE_VERSION}]
    if mode == "ambiguous":
        rows[1] = dict(rows[1], effect=-0.30)
    elif mode == "foreign":
        rows = [dict(rows[0], context_key=C09_C12_FOREIGN_CONTEXT)]
    elif mode == "abstained":
        rows = []
    return {"observations": rows, "minimum_cohorts": 2, "minimum_concordance": 0.75}


def default_cohort_alpha_frontier_fixture() -> CohortAlphaFrontierFixture:
    sources = (_source("gdc-longitudinal", "GDC public aggregate longitudinal portal", "https://gdc.cancer.gov/", "Public aggregate receipt for phase and frequency context."), _source("icgc-longitudinal", "ICGC public aggregate portal", "https://dcc.icgc.org/", "Public aggregate receipt for recurrence observations."), _source("gdc-treatment", "GDC treatment metadata aggregate", "https://gdc.cancer.gov/", "Public aggregate treatment-phase receipt."), _source("icgc-treatment", "ICGC treatment-phase aggregate", "https://dcc.icgc.org/", "Public aggregate treatment and response receipt."), _source("study-a", "Public cohort study A aggregate", "https://dcc.icgc.org/", "Public cohort-level replication receipt."), _source("study-b", "Public cohort study B aggregate", "https://gdc.cancer.gov/", "Public cohort-level replication receipt."))
    records = (
        _record("C09", "c09-positive", _clonality_payload(C09_C12_CONTEXT, "c09p", "positive"), CohortAlphaState.SUPPORTED, "positive", ("gdc-longitudinal", "icgc-longitudinal"), "high CCF observations span primary and recurrence phases"),
        _record("C09", "c09-partial", _clonality_payload(C09_C12_CONTEXT, "c09x", "partial"), CohortAlphaState.PARTIAL, "incomplete_control", ("gdc-longitudinal",), "missing CCF remains partial"),
        _record("C09", "c09-foreign", _clonality_payload(C09_C12_FOREIGN_CONTEXT, "c09f", "foreign"), CohortAlphaState.OUT_OF_DOMAIN, "foreign_context", ("gdc-longitudinal",), "foreign context is not transported"),
        _record("C09", "c09-abstained", _clonality_payload(C09_C12_CONTEXT, "c09a", "abstained"), CohortAlphaState.ABSTAINED, "empty_control", ("gdc-longitudinal",), "empty input produces explicit abstention"),
        _record("C10", "c10-positive", _recurrence_payload(C09_C12_CONTEXT, "c10p", "positive"), CohortAlphaState.SUPPORTED, "positive", ("gdc-longitudinal", "icgc-longitudinal"), "primary and recurrence frequencies produce a bounded delta"),
        _record("C10", "c10-partial", _recurrence_payload(C09_C12_CONTEXT, "c10x", "partial"), CohortAlphaState.PARTIAL, "incomplete_control", ("gdc-longitudinal",), "one phase cannot support comparison"),
        _record("C10", "c10-foreign", _recurrence_payload(C09_C12_FOREIGN_CONTEXT, "c10f", "foreign"), CohortAlphaState.OUT_OF_DOMAIN, "foreign_context", ("gdc-longitudinal",), "foreign phase rows are isolated"),
        _record("C10", "c10-abstained", _recurrence_payload(C09_C12_CONTEXT, "c10a", "abstained"), CohortAlphaState.ABSTAINED, "empty_control", ("gdc-longitudinal",), "empty input produces explicit abstention"),
        _record("C11", "c11-positive", _treatment_payload(C09_C12_CONTEXT, "c11p", "positive"), CohortAlphaState.SUPPORTED, "positive", ("gdc-treatment", "icgc-treatment"), "pre and post frequencies produce a descriptive selection signal"),
        _record("C11", "c11-partial", _treatment_payload(C09_C12_CONTEXT, "c11x", "partial"), CohortAlphaState.PARTIAL, "incomplete_control", ("gdc-treatment",), "one treatment phase cannot support comparison"),
        _record("C11", "c11-foreign", _treatment_payload(C09_C12_FOREIGN_CONTEXT, "c11f", "foreign"), CohortAlphaState.OUT_OF_DOMAIN, "foreign_context", ("icgc-treatment",), "foreign treatment rows are isolated"),
        _record("C11", "c11-abstained", _treatment_payload(C09_C12_CONTEXT, "c11a", "abstained"), CohortAlphaState.ABSTAINED, "empty_control", ("gdc-treatment",), "empty input produces explicit abstention"),
        _record("C12", "c12-positive", _replication_payload(C09_C12_CONTEXT, "c12p", "positive"), CohortAlphaState.SUPPORTED, "positive", ("study-a", "study-b"), "two cohort effects agree in direction"),
        _record("C12", "c12-ambiguous", _replication_payload(C09_C12_CONTEXT, "c12x", "ambiguous"), CohortAlphaState.AMBIGUOUS, "contradictory_control", ("study-a", "study-b"), "cohort effect directions disagree"),
        _record("C12", "c12-foreign", _replication_payload(C09_C12_FOREIGN_CONTEXT, "c12f", "foreign"), CohortAlphaState.OUT_OF_DOMAIN, "foreign_context", ("study-a",), "foreign replication rows are isolated"),
        _record("C12", "c12-abstained", _replication_payload(C09_C12_CONTEXT, "c12a", "abstained"), CohortAlphaState.ABSTAINED, "empty_control", ("study-a",), "empty input produces explicit abstention"),
    )
    body = {"fixture_id": "cohort-alpha-frontier-c09-c12", "fixture_version": C09_C12_FIXTURE_VERSION, "context_key": C09_C12_CONTEXT, "foreign_context_key": C09_C12_FOREIGN_CONTEXT, "boundary": C09_C12_BOUNDARY, "sources": sources, "records": records}
    return CohortAlphaFrontierFixture(**body, metadata={"row_policy": "pseudonymous public aggregate", "operation_count": 4}, content_address=content_hash(body, prefix="alpha-fixture"))


def audit_cohort_alpha_frontier_data(fixture: CohortAlphaFrontierFixture) -> CohortAlphaFrontierDataAudit:
    operation_counts = {operation: sum(item.operation == operation for item in fixture.records) for operation in fixture.operations}
    control_counts = {control: sum(item.control_class == control for item in fixture.records) for control in sorted({item.control_class for item in fixture.records})}
    foreign = sum(item.control_class == "foreign_context" for item in fixture.records)
    findings = ("all rows are pseudonymous aggregate inputs", "each operation has positive, incomplete, foreign, and empty paths", "phase and cohort boundaries remain explicit")
    accepted = len(fixture.sources) == 6 and len(fixture.records) == 16 and foreign == 4 and all(count == 4 for count in operation_counts.values())
    body = {"fixture_id": fixture.fixture_id, "source_count": len(fixture.sources), "record_count": len(fixture.records), "operation_counts": operation_counts, "control_counts": control_counts, "foreign": foreign, "accepted": accepted}
    return CohortAlphaFrontierDataAudit(fixture.fixture_id, len(fixture.sources), len(fixture.records), operation_counts, control_counts, foreign, accepted, findings, content_hash(body, prefix="alpha-audit"))


def cohort_alpha_frontier_fixture_json(fixture: CohortAlphaFrontierFixture | None = None) -> str:
    import json
    return json.dumps((fixture or default_cohort_alpha_frontier_fixture()).to_dict(), sort_keys=True, indent=2)


__all__ = ["C09_C12_BOUNDARY", "C09_C12_CONTEXT", "C09_C12_FIXTURE_VERSION", "C09_C12_FOREIGN_CONTEXT", "CohortAlphaFrontierDataAudit", "CohortAlphaFrontierFixture", "CohortAlphaFrontierRecord", "CohortAlphaFrontierSource", "audit_cohort_alpha_frontier_data", "cohort_alpha_frontier_fixture_json", "default_cohort_alpha_frontier_fixture"]
