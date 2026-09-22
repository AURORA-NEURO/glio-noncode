"""Public aggregate fixture for Domain 12 C09-C12."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .cohort_alpha import CohortAlphaState
from .serialization import content_hash, jsonable, require_non_empty

C09_C12_CONTEXT = "GRCh38|glioma|adult|stem_like|tumor_core|pre_treatment"
C09_C12_FOREIGN_CONTEXT = "GRCh38|glioma|adult|stem_like|tumor_margin|post_treatment"
C09_C12_FIXTURE_VERSION = "2026.08.d12-c09-c12.v1"
C09_C12_BOUNDARY = "descriptive_public_longitudinal_aggregate_evidence"
C09_C12_OPERATIONS = ("C09", "C10", "C11", "C12")
C09_C12_EXPECTED_RECORD_IDS_BY_OPERATION = (
    ("C09", ("c09-positive", "c09-partial", "c09-foreign", "c09-abstained")),
    ("C10", ("c10-positive", "c10-partial", "c10-foreign", "c10-abstained")),
    ("C11", ("c11-positive", "c11-partial", "c11-foreign", "c11-abstained")),
    ("C12", ("c12-positive", "c12-ambiguous", "c12-foreign", "c12-abstained")),
)
_MAX_C09_C12_FIXTURE_RECORDS = 256


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
        if type(self.records) is not tuple:
            raise ValueError("C09-C12 fixture records must be a tuple")
        if len(self.records) > _MAX_C09_C12_FIXTURE_RECORDS:
            raise ValueError("C09-C12 fixture exceeds its record safety limit")
        record_ids = tuple(item.record_id for item in self.records)
        if len(set(record_ids)) != len(record_ids):
            raise ValueError("C09-C12 fixture record IDs must be unique")
        unsupported = {item.operation for item in self.records} - set(C09_C12_OPERATIONS)
        if unsupported:
            raise ValueError(f"C09-C12 fixture has unsupported operations: {sorted(unsupported)}")

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
    expected_by_operation = dict(C09_C12_EXPECTED_RECORD_IDS_BY_OPERATION)
    observed_by_operation = {
        operation: tuple(item.record_id for item in fixture.records if item.operation == operation)
        for operation in C09_C12_OPERATIONS
    }
    operation_counts = {operation: len(ids) for operation, ids in observed_by_operation.items()}
    control_counts = {control: sum(item.control_class == control for item in fixture.records) for control in sorted({item.control_class for item in fixture.records})}
    foreign_ids = {item.record_id for item in fixture.records if item.control_class == "foreign_context"}
    expected_foreign_ids = {"c09-foreign", "c10-foreign", "c11-foreign", "c12-foreign"}
    findings = ["rows are treated as pseudonymous aggregate inputs", "phase and cohort boundaries remain explicit"]
    missing_ids = {
        operation: tuple(sorted(set(expected_by_operation[operation]) - set(observed_by_operation[operation])))
        for operation in C09_C12_OPERATIONS
    }
    extra_ids = {
        operation: tuple(sorted(set(observed_by_operation[operation]) - set(expected_by_operation[operation])))
        for operation in C09_C12_OPERATIONS
    }
    if any(missing_ids.values()):
        findings.append("one or more manifest-declared record IDs are missing")
    if any(extra_ids.values()):
        findings.append("one or more record IDs are outside the declared cohort")
    if foreign_ids != expected_foreign_ids:
        findings.append("foreign-context control identities differ from the declared controls")
    accepted = (
        len(fixture.sources) == 6
        and not any(missing_ids.values())
        and not any(extra_ids.values())
        and foreign_ids == expected_foreign_ids
    )
    foreign = len(foreign_ids)
    body = {"fixture_id": fixture.fixture_id, "source_count": len(fixture.sources), "record_count": len(fixture.records), "operation_counts": operation_counts, "control_counts": control_counts, "foreign": foreign, "accepted": accepted}
    return CohortAlphaFrontierDataAudit(fixture.fixture_id, len(fixture.sources), len(fixture.records), operation_counts, control_counts, foreign, accepted, tuple(findings), content_hash(body, prefix="alpha-audit"))


def cohort_alpha_frontier_fixture_json(fixture: CohortAlphaFrontierFixture | None = None) -> str:
    import json
    return json.dumps((fixture or default_cohort_alpha_frontier_fixture()).to_dict(), sort_keys=True, indent=2)


__all__ = ["C09_C12_BOUNDARY", "C09_C12_CONTEXT", "C09_C12_EXPECTED_RECORD_IDS_BY_OPERATION", "C09_C12_FIXTURE_VERSION", "C09_C12_FOREIGN_CONTEXT", "C09_C12_OPERATIONS", "CohortAlphaFrontierDataAudit", "CohortAlphaFrontierFixture", "CohortAlphaFrontierRecord", "CohortAlphaFrontierSource", "audit_cohort_alpha_frontier_data", "cohort_alpha_frontier_fixture_json", "default_cohort_alpha_frontier_fixture"]
