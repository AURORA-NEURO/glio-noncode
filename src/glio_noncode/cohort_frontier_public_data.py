"""Public aggregate fixture boundary for Domain 12 cohort convergence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

COHORT_FRONTIER_FIXTURE_VERSION = "2026.08.d12-c13-c16.v1"
COHORT_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|core|unknown"
COHORT_FRONTIER_EVIDENCE_BOUNDARY = "public_aggregate_non_patient"
COHORT_FRONTIER_POSITIVE_COUNT = 4
COHORT_FRONTIER_CONTROL_COUNT = 12
COHORT_FRONTIER_SOURCE_COUNT = 5


class CohortFrontierOperation(StrEnum):
    SUBGROUP_FAIRNESS = "subgroup_fairness"
    TRANSPORTABILITY = "transportability"
    FEDERATED_SUMMARY = "federated_summary"
    COHORT_DISCOVERY = "cohort_discovery"


class CohortFrontierRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class CohortFrontierSourceReceipt:
    source_id: str
    title: str
    uri: str
    source_kind: str
    release: str
    scope: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("source_id", "title", "uri", "source_kind", "release", "scope", "content_address"):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFrontierRecord:
    record_id: str
    operation: CohortFrontierOperation
    role: CohortFrontierRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: dict[str, Any]
    expected_state: str
    expected_issue_codes: tuple[str, ...]
    description: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.record_id, "record_id")
        require_non_empty(self.context_key, "context_key")
        require_non_empty(self.expected_state, "expected_state")
        require_non_empty(self.description, "description")
        if not self.source_ids or not self.payload:
            raise ValidationError("cohort frontier records require sources and payload")
        if not isinstance(self.operation, CohortFrontierOperation) or not isinstance(self.role, CohortFrontierRole):
            raise ValidationError("cohort frontier record enums are invalid")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFrontierFixture:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[CohortFrontierSourceReceipt, ...]
    records: tuple[CohortFrontierRecord, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in ("fixture_id", "fixture_version", "context_key", "evidence_boundary", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.sources or not self.records:
            raise ValidationError("cohort frontier fixture requires sources and records")

    @property
    def positive_records(self) -> tuple[CohortFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is CohortFrontierRole.POSITIVE)

    @property
    def control_records(self) -> tuple[CohortFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is CohortFrontierRole.CONTROL)

    def source_map(self) -> dict[str, CohortFrontierSourceReceipt]:
        return {item.source_id: item for item in self.sources}

    def record_map(self) -> dict[str, CohortFrontierRecord]:
        return {item.record_id: item for item in self.records}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFrontierCatalog:
    fixture: CohortFrontierFixture
    source_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    operations: tuple[CohortFrontierOperation, ...]
    content_address: str

    def __post_init__(self) -> None:
        if len(set(self.source_ids)) != len(self.source_ids) or len(set(self.record_ids)) != len(self.record_ids):
            raise ValidationError("cohort catalog IDs must be unique")
        if set(self.operations) != set(CohortFrontierOperation):
            raise ValidationError("cohort catalog must cover every operation")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFrontierDataCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFrontierDataAudit:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    checks: tuple[CohortFrontierDataCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.checks) and all(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted, "failed_check_ids": list(self.failed_check_ids)}


def _source(source_id: str, title: str, uri: str, source_kind: str, release: str, scope: str) -> CohortFrontierSourceReceipt:
    body = {"source_id": source_id, "title": title, "uri": uri, "source_kind": source_kind, "release": release, "scope": scope}
    return CohortFrontierSourceReceipt(**body, content_address=content_hash(body))


def _record(record_id: str, operation: CohortFrontierOperation, role: CohortFrontierRole, rows: list[Any], expected_state: str, expected_issue_codes: tuple[str, ...], source_ids: tuple[str, ...], description: str, **metadata: Any) -> CohortFrontierRecord:
    payload = {"input_records": rows, **metadata}
    body = {"record_id": record_id, "operation": operation, "role": role, "context_key": COHORT_FRONTIER_CONTEXT_KEY, "source_ids": source_ids, "payload": payload, "expected_state": expected_state, "expected_issue_codes": expected_issue_codes, "description": description}
    payload["input_hash"] = content_hash(rows)
    return CohortFrontierRecord(**body, content_address=content_hash(body))


def default_cohort_frontier_fixture() -> CohortFrontierFixture:
    sources = (
        _source("ncbi-geo", "NCBI Gene Expression Omnibus public submissions", "https://www.ncbi.nlm.nih.gov/geo/", "public_archive", "2025-01", "aggregate cohort feature context"),
        _source("dbgap", "NIH controlled-access study index", "https://www.ncbi.nlm.nih.gov/gap/", "public_index", "2024-01", "study design and cohort metadata context"),
        _source("encode-project", "ENCODE public functional genomics portal", "https://www.encodeproject.org/", "public_assay_archive", "2024-01", "aggregate feature and assay context"),
        _source("pubmed", "PubMed public biomedical literature index", "https://pubmed.ncbi.nlm.nih.gov/", "public_literature_index", "2025-01", "aggregate citation and analysis context"),
        _source("nih-common-fund", "NIH Common Fund public program resources", "https://commonfund.nih.gov/", "public_program_archive", "2024", "research-use and provenance context"),
    )
    records = (
        _record("C13-POS-001", CohortFrontierOperation.SUBGROUP_FAIRNESS, CohortFrontierRole.POSITIVE, [{"group": "A", "positive": 1}, {"group": "A", "positive": 0}, {"group": "B", "positive": 1}, {"group": "B", "positive": 0}], "supported", (), ("ncbi-geo", "dbgap"), "balanced aggregate subgroup rates remain within parity boundary", maximum_parity_gap=0.20),
        _record("C13-CTRL-001", CohortFrontierOperation.SUBGROUP_FAIRNESS, CohortFrontierRole.CONTROL, [{"group": "A", "positive": 1}, {"group": "A", "positive": 1}, {"group": "B", "positive": 0}, {"group": "B", "positive": 0}], "review", ("parity_gap_high",), ("ncbi-geo",), "large subgroup parity gap remains review", maximum_parity_gap=0.20),
        _record("C13-CTRL-002", CohortFrontierOperation.SUBGROUP_FAIRNESS, CohortFrontierRole.CONTROL, [], "invalid", ("empty_fairness_input",), ("ncbi-geo",), "empty subgroup input is rejected", maximum_parity_gap=0.20),
        _record("C13-CTRL-003", CohortFrontierOperation.SUBGROUP_FAIRNESS, CohortFrontierRole.CONTROL, [{"positive": 1}], "invalid", ("invalid_fairness_input",), ("ncbi-geo",), "missing group identity is rejected", maximum_parity_gap=0.20),
        _record("C14-POS-001", CohortFrontierOperation.TRANSPORTABILITY, CohortFrontierRole.POSITIVE, [{"analysis_id": "analysis-1", "source_features": ["age", "state", "purity"], "target_features": ["age", "state", "purity"], "shift_score": 0.10}], "supported", (), ("dbgap", "ncbi-geo"), "matching feature sets have low declared shift", minimum_overlap=0.75, maximum_shift=0.25),
        _record("C14-CTRL-001", CohortFrontierOperation.TRANSPORTABILITY, CohortFrontierRole.CONTROL, [{"analysis_id": "analysis-gap", "source_features": ["age"], "target_features": ["age", "state", "purity"], "shift_score": 0.10}], "review", ("target_feature_gap",), ("dbgap",), "target feature gap remains review", minimum_overlap=0.75, maximum_shift=0.25),
        _record("C14-CTRL-002", CohortFrontierOperation.TRANSPORTABILITY, CohortFrontierRole.CONTROL, [{"analysis_id": "analysis-shift", "source_features": ["age", "state"], "target_features": ["age", "state"], "shift_score": 0.80}], "review", ("distribution_shift_high",), ("dbgap",), "high source-target shift remains review", minimum_overlap=0.75, maximum_shift=0.25),
        _record("C14-CTRL-003", CohortFrontierOperation.TRANSPORTABILITY, CohortFrontierRole.CONTROL, [], "invalid", ("empty_transportability_input",), ("dbgap",), "empty transportability input is rejected", minimum_overlap=0.75, maximum_shift=0.25),
        _record("C15-POS-001", CohortFrontierOperation.FEDERATED_SUMMARY, CohortFrontierRole.POSITIVE, [{"feature_id": "f-1", "site_id": "site-a", "count": 10, "mean": 0.40}, {"feature_id": "f-1", "site_id": "site-b", "count": 12, "mean": 0.60}], "supported", (), ("ncbi-geo", "encode-project"), "site summaries clear privacy floor with spread retained", privacy_floor=5),
        _record("C15-CTRL-001", CohortFrontierOperation.FEDERATED_SUMMARY, CohortFrontierRole.CONTROL, [{"feature_id": "f-low", "site_id": "site-a", "count": 2, "mean": 0.40}], "review", ("privacy_floor_violation",), ("ncbi-geo",), "privacy floor violation remains review", privacy_floor=5),
        _record("C15-CTRL-002", CohortFrontierOperation.FEDERATED_SUMMARY, CohortFrontierRole.CONTROL, [], "invalid", ("empty_federated_input",), ("ncbi-geo",), "empty federated input is rejected", privacy_floor=5),
        _record("C15-CTRL-003", CohortFrontierOperation.FEDERATED_SUMMARY, CohortFrontierRole.CONTROL, [{"feature_id": "f-bad", "site_id": "site-a", "count": 10, "mean": "bad"}], "invalid", ("invalid_federated_input",), ("ncbi-geo",), "invalid site mean is rejected", privacy_floor=5),
        _record("C16-POS-001", CohortFrontierOperation.COHORT_DISCOVERY, CohortFrontierRole.POSITIVE, [{"feature_id": "f-1", "context_key": COHORT_FRONTIER_CONTEXT_KEY, "weighted_mean": 0.50}], "published", (), ("pubmed", "nih-common-fund"), "aggregate cohort feature discovery manifest is addressed", bundle_id="cohort-frontier-1", analysis_ids=["analysis-1"]),
        _record("C16-CTRL-001", CohortFrontierOperation.COHORT_DISCOVERY, CohortFrontierRole.CONTROL, [{"feature_id": "f-1", "context_key": "other", "weighted_mean": 0.50}], "invalid", ("invalid_cohort_discovery_input",), ("pubmed",), "context mismatch is rejected", bundle_id="cohort-frontier-bad-context", analysis_ids=["analysis-1"]),
        _record("C16-CTRL-002", CohortFrontierOperation.COHORT_DISCOVERY, CohortFrontierRole.CONTROL, [], "invalid", ("empty_cohort_discovery_input",), ("pubmed",), "empty cohort discovery input is rejected", bundle_id="cohort-frontier-empty", analysis_ids=["analysis-1"]),
        _record("C16-CTRL-003", CohortFrontierOperation.COHORT_DISCOVERY, CohortFrontierRole.CONTROL, [{"feature_id": "f-1", "context_key": COHORT_FRONTIER_CONTEXT_KEY}], "invalid", ("invalid_cohort_discovery_input",), ("pubmed",), "missing analysis identity is rejected", bundle_id="cohort-frontier-no-analysis", analysis_ids=[]),
    )
    body = {"fixture_id": "cohort-frontier-public-aggregate", "fixture_version": COHORT_FRONTIER_FIXTURE_VERSION, "context_key": COHORT_FRONTIER_CONTEXT_KEY, "evidence_boundary": COHORT_FRONTIER_EVIDENCE_BOUNDARY, "sources": sources, "records": records}
    return CohortFrontierFixture(**body, content_address=content_hash(body))


def build_cohort_frontier_catalog(fixture: CohortFrontierFixture | None = None) -> CohortFrontierCatalog:
    fixture = fixture or default_cohort_frontier_fixture()
    body = {"fixture": fixture, "source_ids": tuple(item.source_id for item in fixture.sources), "record_ids": tuple(item.record_id for item in fixture.records), "operations": tuple(sorted({item.operation for item in fixture.records}, key=str))}
    return CohortFrontierCatalog(**body, content_address=content_hash(body))


def audit_cohort_frontier_data(fixture: CohortFrontierFixture | None = None) -> CohortFrontierDataAudit:
    fixture = fixture or default_cohort_frontier_fixture()
    checks: list[CohortFrontierDataCheck] = []
    def add(check_id: str, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(CohortFrontierDataCheck(**body, content_address=content_hash(body)))
    source_ids = set(fixture.source_map())
    add("fixture_boundary", fixture.evidence_boundary == COHORT_FRONTIER_EVIDENCE_BOUNDARY, "public aggregate boundary is declared")
    add("fixture_version", fixture.fixture_version == COHORT_FRONTIER_FIXTURE_VERSION, "fixture version is pinned")
    add("context_uniform", all(item.context_key == fixture.context_key for item in fixture.records), "records use one exact context")
    add("source_count", len(fixture.sources) == COHORT_FRONTIER_SOURCE_COUNT, "source count matches manifest")
    add("record_count", len(fixture.records) == COHORT_FRONTIER_POSITIVE_COUNT + COHORT_FRONTIER_CONTROL_COUNT, "record count matches manifest")
    add("positive_count", len(fixture.positive_records) == COHORT_FRONTIER_POSITIVE_COUNT, "positive count matches manifest")
    add("control_count", len(fixture.control_records) == COHORT_FRONTIER_CONTROL_COUNT, "control count matches manifest")
    add("operation_coverage", {item.operation for item in fixture.records} == set(CohortFrontierOperation), "all operations are represented")
    add("source_references", all(set(item.source_ids) <= source_ids for item in fixture.records), "source references resolve")
    add("https_receipts", all(item.uri.startswith("https://") for item in fixture.sources), "source receipts use HTTPS")
    add("unique_record_ids", len(fixture.record_map()) == len(fixture.records), "record IDs are unique")
    add("unique_source_ids", len(fixture.source_map()) == len(fixture.sources), "source IDs are unique")
    body = {"fixture_id": fixture.fixture_id, "fixture_version": fixture.fixture_version, "context_key": fixture.context_key, "evidence_boundary": fixture.evidence_boundary, "checks": checks}
    return CohortFrontierDataAudit(**body, content_address=content_hash(body))


def load_cohort_frontier_fixture(path: str | Path) -> CohortFrontierFixture:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValidationError("cohort fixture JSON must be an object")
    sources = tuple(CohortFrontierSourceReceipt(**item) for item in raw.get("sources", ()))
    records = []
    for item in raw.get("records", ()):
        body = dict(item)
        body["operation"] = CohortFrontierOperation(item["operation"])
        body["role"] = CohortFrontierRole(item["role"])
        records.append(CohortFrontierRecord(**body))
    fixture_body = {"fixture_id": raw["fixture_id"], "fixture_version": raw["fixture_version"], "context_key": raw["context_key"], "evidence_boundary": raw["evidence_boundary"], "sources": sources, "records": tuple(records)}
    return CohortFrontierFixture(**fixture_body, content_address=raw.get("content_address", content_hash(fixture_body)))


__all__ = [
    "COHORT_FRONTIER_CONTEXT_KEY", "COHORT_FRONTIER_CONTROL_COUNT", "COHORT_FRONTIER_EVIDENCE_BOUNDARY", "COHORT_FRONTIER_FIXTURE_VERSION", "COHORT_FRONTIER_POSITIVE_COUNT", "COHORT_FRONTIER_SOURCE_COUNT",
    "CohortFrontierCatalog", "CohortFrontierDataAudit", "CohortFrontierDataCheck", "CohortFrontierFixture", "CohortFrontierOperation", "CohortFrontierRecord", "CohortFrontierRole", "CohortFrontierSourceReceipt",
    "audit_cohort_frontier_data", "build_cohort_frontier_catalog", "default_cohort_frontier_fixture", "load_cohort_frontier_fixture",
]
