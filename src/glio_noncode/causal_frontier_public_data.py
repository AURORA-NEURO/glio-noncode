"""Public aggregate fixture and source boundary for Domain 11 C13-C16."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

CAUSAL_FRONTIER_FIXTURE_VERSION = "2026.08.d11-c13-c16.v1"
CAUSAL_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|core|unknown"
CAUSAL_FRONTIER_EVIDENCE_BOUNDARY = "public_aggregate_non_patient"
CAUSAL_FRONTIER_POSITIVE_COUNT = 4
CAUSAL_FRONTIER_CONTROL_COUNT = 12
CAUSAL_FRONTIER_SOURCE_COUNT = 5


class CausalFrontierOperation(StrEnum):
    POSTERIOR_DECOMPOSITION = "posterior_decomposition"
    DRIVER_POSTERIOR = "regulatory_driver_posterior"
    SELECTIVE_PREDICTION = "selective_prediction_abstention"
    DOSSIER_PUBLICATION = "causal_dossier_publication"


class CausalFrontierRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class CausalFrontierSourceReceipt:
    source_id: str
    title: str
    uri: str
    source_kind: str
    release: str
    scope: str
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "source_id",
            "title",
            "uri",
            "source_kind",
            "release",
            "scope",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.uri.startswith("https://"):
            raise ValidationError("causal source receipts require HTTPS")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalFrontierRecord:
    record_id: str
    operation: CausalFrontierOperation
    role: CausalFrontierRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: dict[str, Any]
    expected_state: str
    expected_issue_codes: tuple[str, ...]
    description: str
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "record_id",
            "context_key",
            "expected_state",
            "description",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.source_ids or not self.payload:
            raise ValidationError("causal records require sources and payload")
        if not isinstance(self.operation, CausalFrontierOperation):
            raise ValidationError("causal operation must be declared")
        if not isinstance(self.role, CausalFrontierRole):
            raise ValidationError("causal role must be declared")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalFrontierFixture:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[CausalFrontierSourceReceipt, ...]
    records: tuple[CausalFrontierRecord, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "fixture_id",
            "fixture_version",
            "context_key",
            "evidence_boundary",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.evidence_boundary != CAUSAL_FRONTIER_EVIDENCE_BOUNDARY:
            raise ValidationError("unsupported causal evidence boundary")
        if not self.sources or not self.records:
            raise ValidationError("causal fixture requires sources and records")

    @property
    def positive_records(self) -> tuple[CausalFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is CausalFrontierRole.POSITIVE)

    @property
    def control_records(self) -> tuple[CausalFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is CausalFrontierRole.CONTROL)

    def source_map(self) -> dict[str, CausalFrontierSourceReceipt]:
        return {item.source_id: item for item in self.sources}

    def record_map(self) -> dict[str, CausalFrontierRecord]:
        return {item.record_id: item for item in self.records}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalFrontierCatalog:
    fixture: CausalFrontierFixture
    source_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    operations: tuple[CausalFrontierOperation, ...]
    content_address: str

    def __post_init__(self) -> None:
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValidationError("causal source IDs must be unique")
        if len(set(self.record_ids)) != len(self.record_ids):
            raise ValidationError("causal record IDs must be unique")
        if set(self.operations) != set(CausalFrontierOperation):
            raise ValidationError("causal catalog must cover all operations")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalFrontierDataCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalFrontierDataAudit:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    checks: tuple[CausalFrontierDataCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.checks) and all(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_check_ids": list(self.failed_check_ids),
        }


def _source(source_id: str, title: str, uri: str, source_kind: str, release: str, scope: str) -> CausalFrontierSourceReceipt:
    body = {
        "source_id": source_id,
        "title": title,
        "uri": uri,
        "source_kind": source_kind,
        "release": release,
        "scope": scope,
    }
    return CausalFrontierSourceReceipt(**body, content_address=content_hash(body))


def _record(
    record_id: str,
    operation: CausalFrontierOperation,
    role: CausalFrontierRole,
    rows: list[Any],
    expected_state: str,
    expected_issue_codes: tuple[str, ...],
    source_ids: tuple[str, ...],
    description: str,
    **metadata: Any,
) -> CausalFrontierRecord:
    payload = {"input_records": rows, **metadata}
    body = {
        "record_id": record_id,
        "operation": operation,
        "role": role,
        "context_key": CAUSAL_FRONTIER_CONTEXT_KEY,
        "source_ids": source_ids,
        "payload": payload,
        "expected_state": expected_state,
        "expected_issue_codes": expected_issue_codes,
        "description": description,
    }
    payload["input_hash"] = content_hash(rows)
    return CausalFrontierRecord(**body, content_address=content_hash(body))


def default_causal_frontier_fixture() -> CausalFrontierFixture:
    sources = (
        _source(
            "encode-project",
            "ENCODE public functional genomics portal",
            "https://www.encodeproject.org/",
            "public_assay_archive",
            "2024-01",
            "aggregate regulatory measurements and evidence context",
        ),
        _source(
            "four-d-nucleome",
            "4D Nucleome public genome organization data",
            "https://data.4dnucleome.org/",
            "public_topology_archive",
            "2024-01",
            "aggregate contact and dependence context",
        ),
        _source(
            "ncbi-geo",
            "NCBI Gene Expression Omnibus public submissions",
            "https://www.ncbi.nlm.nih.gov/geo/",
            "public_archive",
            "2025-01",
            "aggregate molecular observations and study receipts",
        ),
        _source(
            "pubmed",
            "PubMed public biomedical literature index",
            "https://pubmed.ncbi.nlm.nih.gov/",
            "public_literature_index",
            "2025-01",
            "publication identifiers and evidence-address context",
        ),
        _source(
            "nih-common-fund",
            "NIH Common Fund public program resources",
            "https://commonfund.nih.gov/",
            "public_program_archive",
            "2024",
            "public research-use boundary and provenance context",
        ),
    )
    context = CAUSAL_FRONTIER_CONTEXT_KEY
    records = (
        _record(
            "C13-POS-001",
            CausalFrontierOperation.POSTERIOR_DECOMPOSITION,
            CausalFrontierRole.POSITIVE,
            [
                {"hypothesis_id": "h1", "prior": 0.60, "likelihood": 0.90, "measurement": 0.80, "dependency_penalty": 0.10},
                {"hypothesis_id": "h2", "prior": 0.40, "likelihood": 0.50, "measurement": 0.60, "dependency_penalty": 0.20},
            ],
            "supported",
            (),
            ("encode-project", "ncbi-geo"),
            "positive posterior decomposition retains named bounded components",
        ),
        _record(
            "C13-CTRL-001",
            CausalFrontierOperation.POSTERIOR_DECOMPOSITION,
            CausalFrontierRole.CONTROL,
            [{"hypothesis_id": "h-zero", "prior": 0.0, "likelihood": 0.0, "measurement": 0.0, "dependency_penalty": 1.0}],
            "partial",
            ("zero_posterior_mass",),
            ("encode-project",),
            "zero posterior mass remains review",
        ),
        _record(
            "C13-CTRL-002",
            CausalFrontierOperation.POSTERIOR_DECOMPOSITION,
            CausalFrontierRole.CONTROL,
            [],
            "invalid",
            ("empty_posterior_input",),
            ("encode-project",),
            "empty posterior input is rejected",
        ),
        _record(
            "C13-CTRL-003",
            CausalFrontierOperation.POSTERIOR_DECOMPOSITION,
            CausalFrontierRole.CONTROL,
            [{"hypothesis_id": "h-bad", "prior": 1.2, "likelihood": 0.4, "measurement": 0.5, "dependency_penalty": 0.0}],
            "invalid",
            ("invalid_posterior_input",),
            ("encode-project",),
            "out-of-bound posterior component is quarantined",
        ),
        _record(
            "C14-POS-001",
            CausalFrontierOperation.DRIVER_POSTERIOR,
            CausalFrontierRole.POSITIVE,
            [
                {"driver_id": "driver-1", "evidence_ids": ["e1", "e2"], "evidence_support": 0.85, "prior": 0.70},
                {"driver_id": "driver-2", "evidence_ids": ["e3"], "evidence_support": 0.60, "prior": 0.50},
            ],
            "supported",
            (),
            ("encode-project", "four-d-nucleome"),
            "positive driver posterior retains evidence paths and alternatives",
            minimum_support=0.20,
        ),
        _record(
            "C14-CTRL-001",
            CausalFrontierOperation.DRIVER_POSTERIOR,
            CausalFrontierRole.CONTROL,
            [{"driver_id": "driver-low", "evidence_ids": ["e-low"], "evidence_support": 0.05, "prior": 0.50}],
            "partial",
            ("low_driver_support",),
            ("encode-project",),
            "low-support driver remains review",
            minimum_support=0.20,
        ),
        _record(
            "C14-CTRL-002",
            CausalFrontierOperation.DRIVER_POSTERIOR,
            CausalFrontierRole.CONTROL,
            [],
            "invalid",
            ("empty_driver_input",),
            ("encode-project",),
            "empty driver input is rejected",
            minimum_support=0.20,
        ),
        _record(
            "C14-CTRL-003",
            CausalFrontierOperation.DRIVER_POSTERIOR,
            CausalFrontierRole.CONTROL,
            [{"driver_id": "driver-bad", "evidence_ids": [], "evidence_support": 0.8, "prior": -0.1}],
            "invalid",
            ("invalid_driver_input",),
            ("encode-project",),
            "invalid prior is quarantined",
            minimum_support=0.20,
        ),
        _record(
            "C15-POS-001",
            CausalFrontierOperation.SELECTIVE_PREDICTION,
            CausalFrontierRole.POSITIVE,
            [{"prediction_id": "pred-1", "score": 0.90, "uncertainty": 0.05}],
            "supported",
            (),
            ("ncbi-geo", "four-d-nucleome"),
            "positive selective prediction exceeds declared uncertainty-aware threshold",
            minimum_score=0.60,
            maximum_uncertainty=0.25,
        ),
        _record(
            "C15-CTRL-001",
            CausalFrontierOperation.SELECTIVE_PREDICTION,
            CausalFrontierRole.CONTROL,
            [{"prediction_id": "pred-low", "score": 0.20, "uncertainty": 0.05}],
            "partial",
            ("selective_prediction_abstention",),
            ("ncbi-geo",),
            "weak score abstains",
            minimum_score=0.60,
            maximum_uncertainty=0.25,
        ),
        _record(
            "C15-CTRL-002",
            CausalFrontierOperation.SELECTIVE_PREDICTION,
            CausalFrontierRole.CONTROL,
            [{"prediction_id": "pred-uncertain", "score": 0.90, "uncertainty": 0.80}],
            "partial",
            ("prediction_uncertainty_high", "selective_prediction_abstention"),
            ("ncbi-geo",),
            "high uncertainty abstains even with a strong score",
            minimum_score=0.60,
            maximum_uncertainty=0.25,
        ),
        _record(
            "C15-CTRL-003",
            CausalFrontierOperation.SELECTIVE_PREDICTION,
            CausalFrontierRole.CONTROL,
            [],
            "invalid",
            ("empty_prediction_input",),
            ("ncbi-geo",),
            "empty selective prediction input is rejected",
            minimum_score=0.60,
            maximum_uncertainty=0.25,
        ),
        _record(
            "C16-POS-001",
            CausalFrontierOperation.DOSSIER_PUBLICATION,
            CausalFrontierRole.POSITIVE,
            [{"hypothesis_id": "h1", "evidence_address": "sha256:evidence-1"}, {"hypothesis_id": "h2", "evidence_address": "sha256:evidence-2"}],
            "published",
            (),
            ("pubmed", "nih-common-fund"),
            "positive dossier binds hypotheses and evidence addresses",
            dossier_id="dossier-1",
            hypothesis_ids=["h1", "h2"],
            evidence_addresses=["sha256:evidence-1", "sha256:evidence-2"],
            top_hypothesis_id="h1",
        ),
        _record(
            "C16-CTRL-001",
            CausalFrontierOperation.DOSSIER_PUBLICATION,
            CausalFrontierRole.CONTROL,
            [{"hypothesis_id": "h1", "evidence_address": "sha256:evidence-1"}],
            "invalid",
            ("invalid_dossier_input",),
            ("pubmed",),
            "top hypothesis outside the declared set is rejected",
            dossier_id="dossier-bad-top",
            hypothesis_ids=["h1"],
            evidence_addresses=["sha256:evidence-1"],
            top_hypothesis_id="h2",
        ),
        _record(
            "C16-CTRL-002",
            CausalFrontierOperation.DOSSIER_PUBLICATION,
            CausalFrontierRole.CONTROL,
            [],
            "invalid",
            ("empty_dossier_input",),
            ("pubmed",),
            "empty dossier input is rejected",
            dossier_id="dossier-empty",
            hypothesis_ids=[],
            evidence_addresses=[],
            top_hypothesis_id=None,
        ),
        _record(
            "C16-CTRL-003",
            CausalFrontierOperation.DOSSIER_PUBLICATION,
            CausalFrontierRole.CONTROL,
            [{"hypothesis_id": "h1"}],
            "invalid",
            ("invalid_dossier_input",),
            ("pubmed",),
            "missing evidence address is rejected",
            dossier_id="dossier-missing-address",
            hypothesis_ids=["h1"],
            evidence_addresses=[],
            top_hypothesis_id="h1",
        ),
    )
    body = {
        "fixture_id": "causal-frontier-public-aggregate",
        "fixture_version": CAUSAL_FRONTIER_FIXTURE_VERSION,
        "context_key": context,
        "evidence_boundary": CAUSAL_FRONTIER_EVIDENCE_BOUNDARY,
        "sources": sources,
        "records": records,
    }
    return CausalFrontierFixture(**body, content_address=content_hash(body))


def build_causal_frontier_catalog(fixture: CausalFrontierFixture | None = None) -> CausalFrontierCatalog:
    fixture = fixture or default_causal_frontier_fixture()
    operations = tuple(sorted({item.operation for item in fixture.records}, key=str))
    body = {
        "fixture": fixture,
        "source_ids": tuple(item.source_id for item in fixture.sources),
        "record_ids": tuple(item.record_id for item in fixture.records),
        "operations": operations,
    }
    return CausalFrontierCatalog(
        fixture=fixture,
        source_ids=body["source_ids"],
        record_ids=body["record_ids"],
        operations=operations,
        content_address=content_hash(body),
    )


def audit_causal_frontier_data(fixture: CausalFrontierFixture | None = None) -> CausalFrontierDataAudit:
    fixture = fixture or default_causal_frontier_fixture()
    checks: list[CausalFrontierDataCheck] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(CausalFrontierDataCheck(**body, content_address=content_hash(body)))

    source_ids = set(fixture.source_map())
    add("fixture_boundary", fixture.evidence_boundary == CAUSAL_FRONTIER_EVIDENCE_BOUNDARY, "public aggregate boundary is declared")
    add("fixture_version", fixture.fixture_version == CAUSAL_FRONTIER_FIXTURE_VERSION, "fixture version is pinned")
    add("context_uniform", all(item.context_key == fixture.context_key for item in fixture.records), "records use one exact context")
    add("source_count", len(fixture.sources) == CAUSAL_FRONTIER_SOURCE_COUNT, "source count matches manifest")
    add("record_count", len(fixture.records) == CAUSAL_FRONTIER_POSITIVE_COUNT + CAUSAL_FRONTIER_CONTROL_COUNT, "record count matches manifest")
    add("positive_count", len(fixture.positive_records) == CAUSAL_FRONTIER_POSITIVE_COUNT, "one positive record per operation")
    add("control_count", len(fixture.control_records) == CAUSAL_FRONTIER_CONTROL_COUNT, "three controls per operation")
    add("operation_coverage", {item.operation for item in fixture.records} == set(CausalFrontierOperation), "all operations are represented")
    add("source_references", all(set(item.source_ids) <= source_ids for item in fixture.records), "source references resolve")
    add("https_receipts", all(item.uri.startswith("https://") for item in fixture.sources), "source receipts use HTTPS")
    add("unique_record_ids", len(fixture.record_map()) == len(fixture.records), "record IDs are unique")
    add("unique_source_ids", len(fixture.source_map()) == len(fixture.sources), "source IDs are unique")
    body = {
        "fixture_id": fixture.fixture_id,
        "fixture_version": fixture.fixture_version,
        "context_key": fixture.context_key,
        "evidence_boundary": fixture.evidence_boundary,
        "checks": checks,
    }
    return CausalFrontierDataAudit(**body, content_address=content_hash(body))


def load_causal_frontier_fixture(path: str | Path) -> CausalFrontierFixture:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValidationError("causal fixture JSON must be an object")
    sources = tuple(CausalFrontierSourceReceipt(**item) for item in raw.get("sources", ()))
    records: list[CausalFrontierRecord] = []
    for item in raw.get("records", ()):
        record_body = dict(item)
        record_body["operation"] = CausalFrontierOperation(item["operation"])
        record_body["role"] = CausalFrontierRole(item["role"])
        records.append(CausalFrontierRecord(**record_body))
    body = {
        "fixture_id": raw["fixture_id"],
        "fixture_version": raw["fixture_version"],
        "context_key": raw["context_key"],
        "evidence_boundary": raw["evidence_boundary"],
        "sources": sources,
        "records": tuple(records),
    }
    return CausalFrontierFixture(**body, content_address=raw.get("content_address", content_hash(body)))


__all__ = [
    "CAUSAL_FRONTIER_CONTEXT_KEY",
    "CAUSAL_FRONTIER_CONTROL_COUNT",
    "CAUSAL_FRONTIER_EVIDENCE_BOUNDARY",
    "CAUSAL_FRONTIER_FIXTURE_VERSION",
    "CAUSAL_FRONTIER_POSITIVE_COUNT",
    "CAUSAL_FRONTIER_SOURCE_COUNT",
    "CausalFrontierCatalog",
    "CausalFrontierDataAudit",
    "CausalFrontierDataCheck",
    "CausalFrontierFixture",
    "CausalFrontierOperation",
    "CausalFrontierRecord",
    "CausalFrontierRole",
    "CausalFrontierSourceReceipt",
    "audit_causal_frontier_data",
    "build_causal_frontier_catalog",
    "default_causal_frontier_fixture",
    "load_causal_frontier_fixture",
]
