"""Public aggregate fixture and source boundaries for Domain 10 C13-C16."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

LINK_FRONTIER_FIXTURE_VERSION = "2026.08.d10-c13-c16.v1"
LINK_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|core|unknown"
LINK_FRONTIER_EVIDENCE_BOUNDARY = "public_aggregate_non_patient"
LINK_FRONTIER_POSITIVE_COUNT = 4
LINK_FRONTIER_CONTROL_COUNT = 12
LINK_FRONTIER_SOURCE_COUNT = 5


class LinkFrontierOperation(StrEnum):
    DEPENDENCE_CORRECTION = "link_dependence_correction"
    TARGET_GENE_RANKING = "target_gene_ranking"
    CALIBRATION_ABSTENTION = "link_calibration_abstention"
    EVIDENCE_PUBLICATION = "link_evidence_publication"


class LinkFrontierRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class LinkFrontierSourceReceipt:
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
            raise ValidationError("link source receipts require HTTPS")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkFrontierRecord:
    record_id: str
    operation: LinkFrontierOperation
    role: LinkFrontierRole
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
            raise ValidationError("link records require sources and payload")
        if not isinstance(self.operation, LinkFrontierOperation):
            raise ValidationError("link operation must be declared")
        if not isinstance(self.role, LinkFrontierRole):
            raise ValidationError("link role must be declared")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkFrontierFixture:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[LinkFrontierSourceReceipt, ...]
    records: tuple[LinkFrontierRecord, ...]
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
        if self.evidence_boundary != LINK_FRONTIER_EVIDENCE_BOUNDARY:
            raise ValidationError("unsupported link evidence boundary")
        if not self.sources or not self.records:
            raise ValidationError("link fixture requires sources and records")

    @property
    def positive_records(self) -> tuple[LinkFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is LinkFrontierRole.POSITIVE)

    @property
    def control_records(self) -> tuple[LinkFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is LinkFrontierRole.CONTROL)

    def source_map(self) -> dict[str, LinkFrontierSourceReceipt]:
        return {item.source_id: item for item in self.sources}

    def record_map(self) -> dict[str, LinkFrontierRecord]:
        return {item.record_id: item for item in self.records}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkFrontierCatalog:
    fixture: LinkFrontierFixture
    source_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    operations: tuple[LinkFrontierOperation, ...]
    content_address: str

    def __post_init__(self) -> None:
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValidationError("link source IDs must be unique")
        if len(set(self.record_ids)) != len(self.record_ids):
            raise ValidationError("link record IDs must be unique")
        if set(self.operations) != set(LinkFrontierOperation):
            raise ValidationError("link catalog must cover all operations")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkFrontierDataCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkFrontierDataAudit:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    checks: tuple[LinkFrontierDataCheck, ...]
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
) -> LinkFrontierSourceReceipt:
    body = {
        "source_id": source_id,
        "title": title,
        "uri": uri,
        "source_kind": source_kind,
        "release": release,
        "scope": scope,
    }
    return LinkFrontierSourceReceipt(**body, content_address=content_hash(body))


def _text(rows: list[Any]) -> str:
    return json.dumps(rows, sort_keys=True, separators=(",", ":"))


def _record(
    record_id: str,
    operation: LinkFrontierOperation,
    role: LinkFrontierRole,
    rows: list[Any],
    expected_state: str,
    expected_issue_codes: tuple[str, ...],
    source_ids: tuple[str, ...],
    description: str,
    **metadata: Any,
) -> LinkFrontierRecord:
    payload = {"input_records": rows, **metadata}
    body = {
        "record_id": record_id,
        "operation": operation,
        "role": role,
        "context_key": LINK_FRONTIER_CONTEXT_KEY,
        "source_ids": source_ids,
        "payload": payload,
        "expected_state": expected_state,
        "expected_issue_codes": expected_issue_codes,
        "description": description,
    }
    payload["input_hash"] = content_hash(_text(rows))
    return LinkFrontierRecord(**body, content_address=content_hash(body))


def default_link_frontier_fixture() -> LinkFrontierFixture:
    sources = (
        _source(
            "encode-project",
            "ENCODE public functional genomics portal",
            "https://www.encodeproject.org/",
            "public_assay_archive",
            "2024-01",
            "aggregate regulatory activity and link evidence",
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
            "ebi-expression-atlas",
            "EMBL-EBI Expression Atlas",
            "https://www.ebi.ac.uk/gxa/home",
            "public_expression_archive",
            "2025-01",
            "aggregate activity and calibration context",
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
            "ucsc-genome-browser",
            "UCSC Genome Browser assembly and coordinate context",
            "https://genome.ucsc.edu/",
            "reference_browser",
            "GRCh38",
            "assembly and coordinate interpretation",
        ),
    )
    context = LINK_FRONTIER_CONTEXT_KEY
    records = (
        _record(
            "C13-POS-001",
            LinkFrontierOperation.DEPENDENCE_CORRECTION,
            LinkFrontierRole.POSITIVE,
            [
                {"link_id": "link-a", "dependence_group": "contact-1", "support": 0.90},
                {"link_id": "link-b", "dependence_group": "contact-1", "support": 0.80},
                {"link_id": "link-c", "dependence_group": "activity-1", "support": 0.60},
            ],
            "supported",
            (),
            ("four-d-nucleome", "encode-project"),
            "correlated support is downweighted while every positive path remains visible",
        ),
        _record(
            "C13-CTRL-001",
            LinkFrontierOperation.DEPENDENCE_CORRECTION,
            LinkFrontierRole.CONTROL,
            [{"link_id": "link-zero", "dependence_group": "empty", "support": 0.0}],
            "partial",
            ("zero_corrected_support",),
            ("four-d-nucleome",),
            "zero support remains review state",
        ),
        _record(
            "C13-CTRL-002",
            LinkFrontierOperation.DEPENDENCE_CORRECTION,
            LinkFrontierRole.CONTROL,
            [],
            "invalid",
            ("empty_dependence_input",),
            ("four-d-nucleome",),
            "empty dependence input is rejected",
        ),
        _record(
            "C13-CTRL-003",
            LinkFrontierOperation.DEPENDENCE_CORRECTION,
            LinkFrontierRole.CONTROL,
            [{"link_id": "link-bad", "dependence_group": "bad", "support": 1.4}],
            "invalid",
            ("invalid_dependence_input",),
            ("four-d-nucleome",),
            "support outside the declared bound is rejected",
        ),
        _record(
            "C14-POS-001",
            LinkFrontierOperation.TARGET_GENE_RANKING,
            LinkFrontierRole.POSITIVE,
            [
                {
                    "link_id": "rank-1",
                    "variant_id": "v1",
                    "element_id": "enh-1",
                    "gene_id": "GENE1",
                    "component_scores": {"contact": 0.90, "activity": 0.80, "distance": 0.70},
                },
                {
                    "link_id": "rank-2",
                    "variant_id": "v1",
                    "element_id": "enh-1",
                    "gene_id": "GENE2",
                    "component_scores": {"contact": 0.50, "activity": 0.50},
                },
            ],
            "supported",
            (),
            ("encode-project", "ucsc-genome-browser"),
            "ranking retains component scores and alternative genes",
        ),
        _record(
            "C14-CTRL-001",
            LinkFrontierOperation.TARGET_GENE_RANKING,
            LinkFrontierRole.CONTROL,
            [{"link_id": "rank-zero", "variant_id": "v1", "element_id": "enh-1", "gene_id": "GENE1", "component_scores": {}}],
            "partial",
            ("zero_rank_support",),
            ("encode-project",),
            "empty score components produce review state",
        ),
        _record(
            "C14-CTRL-002",
            LinkFrontierOperation.TARGET_GENE_RANKING,
            LinkFrontierRole.CONTROL,
            [{"link_id": "rank-missing", "variant_id": "v1", "element_id": "enh-1"}],
            "invalid",
            ("invalid_rank_input",),
            ("encode-project",),
            "missing gene identity is quarantined",
        ),
        _record(
            "C14-CTRL-003",
            LinkFrontierOperation.TARGET_GENE_RANKING,
            LinkFrontierRole.CONTROL,
            [],
            "invalid",
            ("empty_rank_input",),
            ("encode-project",),
            "empty ranking input is rejected",
        ),
        _record(
            "C15-POS-001",
            LinkFrontierOperation.CALIBRATION_ABSTENTION,
            LinkFrontierRole.POSITIVE,
            [{"link_id": "cal-1", "predicted_score": 0.80, "observed_score": 0.75, "uncertainty": 0.05}],
            "supported",
            (),
            ("ebi-expression-atlas", "ncbi-geo"),
            "calibrated link remains accepted below uncertainty and error thresholds",
            maximum_uncertainty=0.25,
            maximum_calibration_error=0.30,
        ),
        _record(
            "C15-CTRL-001",
            LinkFrontierOperation.CALIBRATION_ABSTENTION,
            LinkFrontierRole.CONTROL,
            [{"link_id": "cal-high-u", "predicted_score": 0.80, "observed_score": 0.75, "uncertainty": 0.70}],
            "partial",
            ("link_uncertainty_high",),
            ("ebi-expression-atlas",),
            "high uncertainty forces abstention",
        ),
        _record(
            "C15-CTRL-002",
            LinkFrontierOperation.CALIBRATION_ABSTENTION,
            LinkFrontierRole.CONTROL,
            [{"link_id": "cal-high-e", "predicted_score": 0.95, "observed_score": 0.20, "uncertainty": 0.05}],
            "partial",
            ("link_calibration_error_high",),
            ("ebi-expression-atlas",),
            "calibration error forces abstention",
        ),
        _record(
            "C15-CTRL-003",
            LinkFrontierOperation.CALIBRATION_ABSTENTION,
            LinkFrontierRole.CONTROL,
            [],
            "invalid",
            ("empty_calibration_input",),
            ("ebi-expression-atlas",),
            "empty calibration input is rejected",
        ),
        _record(
            "C16-POS-001",
            LinkFrontierOperation.EVIDENCE_PUBLICATION,
            LinkFrontierRole.POSITIVE,
            [
                {"link_id": "pub-1", "source_id": "encode-project", "context_key": context},
                {"link_id": "pub-2", "source_id": "four-d-nucleome", "context_key": context},
            ],
            "published",
            (),
            ("encode-project", "four-d-nucleome"),
            "link evidence bundle binds source and context receipts",
            bundle_id="link-bundle-1",
        ),
        _record(
            "C16-CTRL-001",
            LinkFrontierOperation.EVIDENCE_PUBLICATION,
            LinkFrontierRole.CONTROL,
            [{"link_id": "pub-other", "source_id": "encode-project", "context_key": "other"}],
            "invalid",
            ("publication_context_mismatch",),
            ("encode-project",),
            "cross-context publication is rejected",
            bundle_id="link-bundle-bad-context",
        ),
        _record(
            "C16-CTRL-002",
            LinkFrontierOperation.EVIDENCE_PUBLICATION,
            LinkFrontierRole.CONTROL,
            [{"link_id": "pub-no-source", "context_key": context}],
            "invalid",
            ("invalid_publication_input",),
            ("encode-project",),
            "missing source receipt is rejected",
            bundle_id="link-bundle-bad-source",
        ),
        _record(
            "C16-CTRL-003",
            LinkFrontierOperation.EVIDENCE_PUBLICATION,
            LinkFrontierRole.CONTROL,
            [],
            "invalid",
            ("empty_publication_input",),
            ("encode-project",),
            "empty publication input is rejected",
            bundle_id="link-bundle-empty",
        ),
    )
    body = {
        "fixture_id": "link-frontier-public-aggregate",
        "fixture_version": LINK_FRONTIER_FIXTURE_VERSION,
        "context_key": context,
        "evidence_boundary": LINK_FRONTIER_EVIDENCE_BOUNDARY,
        "sources": sources,
        "records": records,
    }
    return LinkFrontierFixture(**body, content_address=content_hash(body))


def build_link_frontier_catalog(
    fixture: LinkFrontierFixture | None = None,
) -> LinkFrontierCatalog:
    fixture = fixture or default_link_frontier_fixture()
    catalog = LinkFrontierCatalog(
        fixture=fixture,
        source_ids=tuple(item.source_id for item in fixture.sources),
        record_ids=tuple(item.record_id for item in fixture.records),
        operations=tuple(sorted({item.operation for item in fixture.records}, key=str)),
        content_address="",
    )
    return LinkFrontierCatalog(
        fixture=catalog.fixture,
        source_ids=catalog.source_ids,
        record_ids=catalog.record_ids,
        operations=catalog.operations,
        content_address=content_hash(catalog),
    )


def audit_link_frontier_data(
    fixture: LinkFrontierFixture | None = None,
) -> LinkFrontierDataAudit:
    fixture = fixture or default_link_frontier_fixture()
    checks: list[LinkFrontierDataCheck] = []

    def check(check_id: str, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(LinkFrontierDataCheck(**body, content_address=content_hash(body)))

    check("fixture_boundary", fixture.evidence_boundary == LINK_FRONTIER_EVIDENCE_BOUNDARY, "public aggregate boundary is declared")
    check("fixture_version", fixture.fixture_version == LINK_FRONTIER_FIXTURE_VERSION, "fixture version is pinned")
    check("context_uniform", all(item.context_key == fixture.context_key for item in fixture.records), "records use one declared context")
    check("source_count", len(fixture.sources) == LINK_FRONTIER_SOURCE_COUNT, "source receipt count matches manifest")
    check("record_count", len(fixture.records) == LINK_FRONTIER_POSITIVE_COUNT + LINK_FRONTIER_CONTROL_COUNT, "positive and control count matches manifest")
    check("positive_count", len(fixture.positive_records) == LINK_FRONTIER_POSITIVE_COUNT, "one positive record exists per operation")
    check("control_count", len(fixture.control_records) == LINK_FRONTIER_CONTROL_COUNT, "three controls exist per operation")
    check("operation_coverage", {item.operation for item in fixture.records} == set(LinkFrontierOperation), "all link frontier operations are represented")
    source_ids = set(fixture.source_map())
    check("source_references", all(set(item.source_ids) <= source_ids for item in fixture.records), "every record source ID resolves")
    check("https_receipts", all(item.uri.startswith("https://") for item in fixture.sources), "all public receipts use HTTPS")
    check("unique_record_ids", len(fixture.record_map()) == len(fixture.records), "record IDs are unique")
    check("unique_source_ids", len(fixture.source_map()) == len(fixture.sources), "source IDs are unique")
    body = {
        "fixture_id": fixture.fixture_id,
        "fixture_version": fixture.fixture_version,
        "context_key": fixture.context_key,
        "evidence_boundary": fixture.evidence_boundary,
        "checks": checks,
    }
    return LinkFrontierDataAudit(**body, content_address=content_hash(body))


def load_link_frontier_fixture(path: str | Path) -> LinkFrontierFixture:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValidationError("link fixture JSON must be an object")
    return default_link_frontier_fixture() if raw.get("fixture_id") == "link-frontier-public-aggregate" else _fixture_from_dict(raw)


def _fixture_from_dict(raw: dict[str, Any]) -> LinkFrontierFixture:
    sources = tuple(LinkFrontierSourceReceipt(**item) for item in raw.get("sources", ()))
    record_values: list[LinkFrontierRecord] = []
    for item in raw.get("records", ()):
        record_body = dict(item)
        record_body["operation"] = LinkFrontierOperation(item["operation"])
        record_body["role"] = LinkFrontierRole(item["role"])
        record_values.append(LinkFrontierRecord(**record_body))
    records = tuple(record_values)
    body = {key: raw[key] for key in ("fixture_id", "fixture_version", "context_key", "evidence_boundary")}
    body.update({"sources": sources, "records": records})
    return LinkFrontierFixture(**body, content_address=raw.get("content_address", content_hash(body)))


__all__ = [
    "LINK_FRONTIER_CONTEXT_KEY",
    "LINK_FRONTIER_CONTROL_COUNT",
    "LINK_FRONTIER_EVIDENCE_BOUNDARY",
    "LINK_FRONTIER_FIXTURE_VERSION",
    "LINK_FRONTIER_POSITIVE_COUNT",
    "LINK_FRONTIER_SOURCE_COUNT",
    "LinkFrontierCatalog",
    "LinkFrontierDataAudit",
    "LinkFrontierDataCheck",
    "LinkFrontierFixture",
    "LinkFrontierOperation",
    "LinkFrontierRecord",
    "LinkFrontierRole",
    "LinkFrontierSourceReceipt",
    "audit_link_frontier_data",
    "build_link_frontier_catalog",
    "default_link_frontier_fixture",
    "load_link_frontier_fixture",
]
