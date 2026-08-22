"""Public aggregate fixture and source boundaries for Domain 08 C13-C16."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

CELL_STATE_FRONTIER_FIXTURE_VERSION = "2026.08.d08-c13-c16.v1"
CELL_STATE_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|tumor|unknown"
CELL_STATE_FRONTIER_EVIDENCE_BOUNDARY = "public_aggregate_non_patient"
CELL_STATE_FRONTIER_POSITIVE_COUNT = 4
CELL_STATE_FRONTIER_CONTROL_COUNT = 12
CELL_STATE_FRONTIER_SOURCE_COUNT = 5


class CellStateFrontierOperation(StrEnum):
    ABUNDANCE_INTERVAL = "cell_state_abundance_interval"
    REFERENCE_MAPPING = "single_cell_reference_mapping"
    OOD_DETECTION = "cell_state_ood_detection"
    CONTEXT_PUBLICATION = "cell_state_context_publication"


class CellStateFrontierRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class CellStateFrontierSourceReceipt:
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
            raise ValidationError("cell state source receipts require HTTPS")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateFrontierRecord:
    record_id: str
    operation: CellStateFrontierOperation
    role: CellStateFrontierRole
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
            raise ValidationError("cell state records require sources and payload")
        if not isinstance(self.operation, CellStateFrontierOperation):
            raise ValidationError("cell state operation must be declared")
        if not isinstance(self.role, CellStateFrontierRole):
            raise ValidationError("cell state role must be declared")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateFrontierFixture:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[CellStateFrontierSourceReceipt, ...]
    records: tuple[CellStateFrontierRecord, ...]
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
        if self.evidence_boundary != CELL_STATE_FRONTIER_EVIDENCE_BOUNDARY:
            raise ValidationError("unsupported cell state evidence boundary")
        if not self.sources or not self.records:
            raise ValidationError("cell state fixture requires sources and records")

    @property
    def positive_records(self) -> tuple[CellStateFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is CellStateFrontierRole.POSITIVE)

    @property
    def control_records(self) -> tuple[CellStateFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is CellStateFrontierRole.CONTROL)

    def source_map(self) -> dict[str, CellStateFrontierSourceReceipt]:
        return {item.source_id: item for item in self.sources}

    def record_map(self) -> dict[str, CellStateFrontierRecord]:
        return {item.record_id: item for item in self.records}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateFrontierCatalog:
    fixture: CellStateFrontierFixture
    source_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    operations: tuple[CellStateFrontierOperation, ...]
    content_address: str

    def __post_init__(self) -> None:
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValidationError("cell state source IDs must be unique")
        if len(set(self.record_ids)) != len(self.record_ids):
            raise ValidationError("cell state record IDs must be unique")
        if set(self.operations) != set(CellStateFrontierOperation):
            raise ValidationError("cell state catalog must cover all operations")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateFrontierDataCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateFrontierDataAudit:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    checks: tuple[CellStateFrontierDataCheck, ...]
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


def _source(
    source_id: str,
    title: str,
    uri: str,
    source_kind: str,
    release: str,
    scope: str,
) -> CellStateFrontierSourceReceipt:
    body = {
        "source_id": source_id,
        "title": title,
        "uri": uri,
        "source_kind": source_kind,
        "release": release,
        "scope": scope,
    }
    return CellStateFrontierSourceReceipt(**body, content_address=content_hash(body))


def _text(rows: list[dict[str, Any]]) -> str:
    return json.dumps(rows, sort_keys=True, separators=(",", ":"))


def _record(
    record_id: str,
    operation: CellStateFrontierOperation,
    role: CellStateFrontierRole,
    rows: list[dict[str, Any]],
    expected_state: str,
    expected_issue_codes: tuple[str, ...],
    source_ids: tuple[str, ...],
    description: str,
    **metadata: Any,
) -> CellStateFrontierRecord:
    payload = {"input_text": _text(rows), **metadata}
    body = {
        "record_id": record_id,
        "operation": operation,
        "role": role,
        "context_key": CELL_STATE_FRONTIER_CONTEXT_KEY,
        "source_ids": source_ids,
        "payload": payload,
        "expected_state": expected_state,
        "expected_issue_codes": expected_issue_codes,
        "description": description,
    }
    return CellStateFrontierRecord(**body, content_address=content_hash(body))


def default_cell_state_frontier_fixture() -> CellStateFrontierFixture:
    sources = (
        _source(
            "cellxgene-census",
            "CELLxGENE Census aggregate cell-state references",
            "https://chanzuckerberg.github.io/cellxgene-census/",
            "public_reference",
            "2024-07",
            "aggregate cell-state reference observations",
        ),
        _source(
            "human-cell-atlas",
            "Human Cell Atlas public atlas",
            "https://data.humancellatlas.org/",
            "public_atlas",
            "2024-06",
            "aggregate cell-state and tissue context",
        ),
        _source(
            "tabula-sapiens",
            "Tabula Sapiens cell-state reference",
            "https://tabula-sapiens-portal.ds.czbiohub.org/",
            "public_reference",
            "2022",
            "reference state score context",
        ),
        _source(
            "ncbi-geo-cell-state",
            "NCBI Gene Expression Omnibus aggregate submissions",
            "https://www.ncbi.nlm.nih.gov/geo/",
            "public_archive",
            "2025-01",
            "aggregate assay submission context",
        ),
        _source(
            "ucsc-genome-browser-cell",
            "UCSC Genome Browser reference assembly context",
            "https://genome.ucsc.edu/",
            "reference_browser",
            "GRCh38",
            "assembly and coordinate context",
        ),
    )
    records = (
        _record(
            "C13-POS-001",
            CellStateFrontierOperation.ABUNDANCE_INTERVAL,
            CellStateFrontierRole.POSITIVE,
            [
                {
                    "sample_id": "aggregate-sample-a",
                    "state_id": "stem_like",
                    "count": 40,
                    "total_cells": 100,
                    "context_key": CELL_STATE_FRONTIER_CONTEXT_KEY,
                }
            ],
            "supported",
            (),
            ("cellxgene-census", "human-cell-atlas"),
            "bounded aggregate abundance has a valid interval",
            interval_multiplier=1.96,
        ),
        _record(
            "C13-CTRL-001",
            CellStateFrontierOperation.ABUNDANCE_INTERVAL,
            CellStateFrontierRole.CONTROL,
            [
                {
                    "sample_id": "aggregate-sample-invalid",
                    "state_id": "stem_like",
                    "count": -1,
                    "total_cells": 100,
                    "context_key": CELL_STATE_FRONTIER_CONTEXT_KEY,
                }
            ],
            "partial",
            ("invalid_cell_count",),
            ("cellxgene-census",),
            "negative count remains a review outcome",
        ),
        _record(
            "C13-CTRL-002",
            CellStateFrontierOperation.ABUNDANCE_INTERVAL,
            CellStateFrontierRole.CONTROL,
            [
                {
                    "sample_id": "aggregate-sample-other-context",
                    "state_id": "stem_like",
                    "count": 30,
                    "total_cells": 100,
                    "context_key": "GRCh38|glioma|pediatric|stem_like|tumor|unknown",
                }
            ],
            "out_of_domain",
            ("context_mismatch",),
            ("cellxgene-census",),
            "pediatric context is not reused for adult evidence",
        ),
        _record(
            "C13-CTRL-003",
            CellStateFrontierOperation.ABUNDANCE_INTERVAL,
            CellStateFrontierRole.CONTROL,
            [
                {
                    "sample_id": "aggregate-sample-empty",
                    "state_id": "stem_like",
                    "count": 0,
                    "total_cells": 0,
                    "context_key": CELL_STATE_FRONTIER_CONTEXT_KEY,
                }
            ],
            "partial",
            ("invalid_cell_count",),
            ("cellxgene-census",),
            "empty denominator is retained as partial",
        ),
        _record(
            "C14-POS-001",
            CellStateFrontierOperation.REFERENCE_MAPPING,
            CellStateFrontierRole.POSITIVE,
            [
                {
                    "cell_id": "aggregate-cell-001",
                    "reference_scores": {"stem_like": 0.92, "differentiated": 0.20},
                    "context_key": CELL_STATE_FRONTIER_CONTEXT_KEY,
                }
            ],
            "supported",
            (),
            ("tabula-sapiens", "human-cell-atlas"),
            "reference score and margin support a mapped state",
            minimum_score=0.6,
            minimum_margin=0.1,
        ),
        _record(
            "C14-CTRL-001",
            CellStateFrontierOperation.REFERENCE_MAPPING,
            CellStateFrontierRole.CONTROL,
            [
                {
                    "cell_id": "aggregate-cell-ambiguous",
                    "reference_scores": {"stem_like": 0.62, "differentiated": 0.58},
                    "context_key": CELL_STATE_FRONTIER_CONTEXT_KEY,
                }
            ],
            "partial",
            ("ambiguous_reference_mapping",),
            ("tabula-sapiens",),
            "close reference scores remain ambiguous",
        ),
        _record(
            "C14-CTRL-002",
            CellStateFrontierOperation.REFERENCE_MAPPING,
            CellStateFrontierRole.CONTROL,
            [
                {
                    "cell_id": "aggregate-cell-other-context",
                    "reference_scores": {"stem_like": 0.90, "differentiated": 0.20},
                    "context_key": "GRCh38|glioma|adult|differentiated|tumor|unknown",
                }
            ],
            "out_of_domain",
            ("context_mismatch",),
            ("tabula-sapiens",),
            "differentiated context is not silently mapped to stem-like context",
        ),
        _record(
            "C14-CTRL-003",
            CellStateFrontierOperation.REFERENCE_MAPPING,
            CellStateFrontierRole.CONTROL,
            [
                {
                    "cell_id": "aggregate-cell-missing-scores",
                    "reference_scores": {},
                    "context_key": CELL_STATE_FRONTIER_CONTEXT_KEY,
                }
            ],
            "partial",
            ("no_reference_scores",),
            ("tabula-sapiens",),
            "missing reference scores do not create a state label",
        ),
        _record(
            "C15-POS-001",
            CellStateFrontierOperation.OOD_DETECTION,
            CellStateFrontierRole.POSITIVE,
            [
                {
                    "cell_id": "aggregate-cell-in-domain",
                    "distance": 0.5,
                    "support_score": 0.9,
                    "support_boundary": 3.0,
                    "context_key": CELL_STATE_FRONTIER_CONTEXT_KEY,
                }
            ],
            "supported",
            (),
            ("cellxgene-census", "tabula-sapiens"),
            "distance and support remain inside declared cell-state territory",
            maximum_distance=3.0,
            minimum_support=0.5,
        ),
        _record(
            "C15-CTRL-001",
            CellStateFrontierOperation.OOD_DETECTION,
            CellStateFrontierRole.CONTROL,
            [
                {
                    "cell_id": "aggregate-cell-far",
                    "distance": 5.0,
                    "support_score": 0.2,
                    "support_boundary": 3.0,
                    "context_key": CELL_STATE_FRONTIER_CONTEXT_KEY,
                }
            ],
            "partial",
            ("cell_state_out_of_domain",),
            ("tabula-sapiens",),
            "low support and large distance remain out of domain",
        ),
        _record(
            "C15-CTRL-002",
            CellStateFrontierOperation.OOD_DETECTION,
            CellStateFrontierRole.CONTROL,
            [
                {
                    "cell_id": "aggregate-cell-other-context",
                    "distance": 0.5,
                    "support_score": 0.9,
                    "support_boundary": 3.0,
                    "context_key": "GRCh38|glioma|adult|stem_like|normal|unknown",
                }
            ],
            "out_of_domain",
            ("context_mismatch",),
            ("tabula-sapiens",),
            "normal territory is not reused for tumor territory",
        ),
        _record(
            "C15-CTRL-003",
            CellStateFrontierOperation.OOD_DETECTION,
            CellStateFrontierRole.CONTROL,
            [{"cell_id": "aggregate-cell-invalid", "distance": "not-a-number"}],
            "partial",
            ("invalid_cell_state_row",),
            ("tabula-sapiens",),
            "invalid distance is quarantined",
        ),
        _record(
            "C16-POS-001",
            CellStateFrontierOperation.CONTEXT_PUBLICATION,
            CellStateFrontierRole.POSITIVE,
            [{"context_key": CELL_STATE_FRONTIER_CONTEXT_KEY}],
            "supported",
            (),
            ("human-cell-atlas", "cellxgene-census", "tabula-sapiens"),
            "context envelope binds three aggregate receipts",
            cell_ids=("aggregate-cell-001", "aggregate-cell-002"),
            mapping_address="sha256:aggregate-mapping",
            abundance_address="sha256:aggregate-abundance",
            ood_address="sha256:aggregate-ood",
        ),
        _record(
            "C16-CTRL-001",
            CellStateFrontierOperation.CONTEXT_PUBLICATION,
            CellStateFrontierRole.CONTROL,
            [{"context_key": CELL_STATE_FRONTIER_CONTEXT_KEY}],
            "partial",
            ("empty_cell_ids",),
            ("human-cell-atlas",),
            "empty cell list blocks publication",
            cell_ids=(),
            mapping_address="sha256:aggregate-mapping",
            abundance_address="sha256:aggregate-abundance",
            ood_address="sha256:aggregate-ood",
        ),
        _record(
            "C16-CTRL-002",
            CellStateFrontierOperation.CONTEXT_PUBLICATION,
            CellStateFrontierRole.CONTROL,
            [{"context_key": "GRCh38|glioma|adult|stem_like|normal|unknown"}],
            "out_of_domain",
            ("context_mismatch",),
            ("human-cell-atlas",),
            "normal territory cannot be published into tumor context",
            cell_ids=("aggregate-cell-normal",),
            mapping_address="sha256:aggregate-mapping",
            abundance_address="sha256:aggregate-abundance",
            ood_address="sha256:aggregate-ood",
        ),
        _record(
            "C16-CTRL-003",
            CellStateFrontierOperation.CONTEXT_PUBLICATION,
            CellStateFrontierRole.CONTROL,
            [{"context_key": CELL_STATE_FRONTIER_CONTEXT_KEY}],
            "partial",
            ("missing_receipt_address",),
            ("human-cell-atlas",),
            "missing upstream receipt remains unpublished",
            cell_ids=("aggregate-cell-missing-receipt",),
            mapping_address="",
            abundance_address="sha256:aggregate-abundance",
            ood_address="sha256:aggregate-ood",
        ),
    )
    body = {
        "fixture_id": "cell-state-frontier-public-aggregate",
        "fixture_version": CELL_STATE_FRONTIER_FIXTURE_VERSION,
        "context_key": CELL_STATE_FRONTIER_CONTEXT_KEY,
        "evidence_boundary": CELL_STATE_FRONTIER_EVIDENCE_BOUNDARY,
        "sources": sources,
        "records": records,
    }
    return CellStateFrontierFixture(**body, content_address=content_hash(body))


def build_cell_state_frontier_catalog(
    fixture: CellStateFrontierFixture | None = None,
) -> CellStateFrontierCatalog:
    selected = fixture or default_cell_state_frontier_fixture()
    body = {
        "fixture": selected.fixture_id,
        "source_ids": tuple(item.source_id for item in selected.sources),
        "record_ids": tuple(item.record_id for item in selected.records),
        "operations": tuple(dict.fromkeys(item.operation for item in selected.records)),
    }
    return CellStateFrontierCatalog(
        selected,
        body["source_ids"],
        body["record_ids"],
        body["operations"],
        content_hash(body),
    )


def _contains_prohibited_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            str(key).lower() in {"patient", "subject", "donor", "participant"}
            or _contains_prohibited_key(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_prohibited_key(item) for item in value)
    return False


def audit_cell_state_frontier_data(
    fixture: CellStateFrontierFixture | None = None,
) -> CellStateFrontierDataAudit:
    selected = fixture or default_cell_state_frontier_fixture()
    checks: list[CellStateFrontierDataCheck] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(CellStateFrontierDataCheck(**body, content_address=content_hash(body)))

    add("fixture-context", selected.context_key == CELL_STATE_FRONTIER_CONTEXT_KEY, "exact context")
    add(
        "evidence-boundary",
        selected.evidence_boundary == CELL_STATE_FRONTIER_EVIDENCE_BOUNDARY,
        "public aggregate non-patient boundary",
    )
    add("source-count", len(selected.sources) == CELL_STATE_FRONTIER_SOURCE_COUNT, "five source receipts")
    add("source-https", all(item.uri.startswith("https://") for item in selected.sources), "HTTPS receipts")
    add("record-count", len(selected.records) == 16, "sixteen records")
    add(
        "role-balance",
        len(selected.positive_records) == 4 and len(selected.control_records) == 12,
        "four positives and twelve controls",
    )
    add(
        "operation-coverage",
        {item.operation for item in selected.records} == set(CellStateFrontierOperation),
        "all four operations are represented",
    )
    add(
        "source-closure",
        all(source_id in selected.source_map() for item in selected.records for source_id in item.source_ids),
        "every record source resolves",
    )
    add(
        "no-subject-identifiers",
        not any(_contains_prohibited_key(item.payload) for item in selected.records),
        "payloads remain aggregate scoped",
    )
    body = {"fixture": selected, "checks": checks}
    return CellStateFrontierDataAudit(
        selected.fixture_id,
        selected.fixture_version,
        selected.context_key,
        selected.evidence_boundary,
        tuple(checks),
        content_hash(body),
    )


def load_cell_state_frontier_fixture(path: str | Path) -> CellStateFrontierFixture:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    sources = tuple(CellStateFrontierSourceReceipt(**row) for row in payload["sources"])
    records = tuple(
        CellStateFrontierRecord(
            record_id=row["record_id"],
            operation=CellStateFrontierOperation(row["operation"]),
            role=CellStateFrontierRole(row["role"]),
            context_key=row["context_key"],
            source_ids=tuple(row["source_ids"]),
            payload=dict(row["payload"]),
            expected_state=row["expected_state"],
            expected_issue_codes=tuple(row["expected_issue_codes"]),
            description=row["description"],
            content_address=row["content_address"],
        )
        for row in payload["records"]
    )
    fixture = CellStateFrontierFixture(
        fixture_id=payload["fixture_id"],
        fixture_version=payload["fixture_version"],
        context_key=payload["context_key"],
        evidence_boundary=payload["evidence_boundary"],
        sources=sources,
        records=records,
        content_address=payload["content_address"],
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "fixture_version": fixture.fixture_version,
        "context_key": fixture.context_key,
        "evidence_boundary": fixture.evidence_boundary,
        "sources": fixture.sources,
        "records": fixture.records,
    }
    if fixture.content_address != content_hash(body):
        raise ValidationError("cell state fixture content address mismatch")
    return fixture


__all__ = [
    "CELL_STATE_FRONTIER_CONTEXT_KEY",
    "CELL_STATE_FRONTIER_CONTROL_COUNT",
    "CELL_STATE_FRONTIER_EVIDENCE_BOUNDARY",
    "CELL_STATE_FRONTIER_FIXTURE_VERSION",
    "CELL_STATE_FRONTIER_POSITIVE_COUNT",
    "CELL_STATE_FRONTIER_SOURCE_COUNT",
    "CellStateFrontierCatalog",
    "CellStateFrontierDataAudit",
    "CellStateFrontierDataCheck",
    "CellStateFrontierFixture",
    "CellStateFrontierOperation",
    "CellStateFrontierRecord",
    "CellStateFrontierRole",
    "CellStateFrontierSourceReceipt",
    "audit_cell_state_frontier_data",
    "build_cell_state_frontier_catalog",
    "default_cell_state_frontier_fixture",
    "load_cell_state_frontier_fixture",
]
