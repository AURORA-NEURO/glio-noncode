"""Public aggregate fixture and source boundaries for Domain 09 C13-C16."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

TOPOLOGY_FRONTIER_FIXTURE_VERSION = "2026.08.d09-c13-c16.v1"
TOPOLOGY_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|tumor|unknown"
TOPOLOGY_FRONTIER_EVIDENCE_BOUNDARY = "public_aggregate_non_patient"
TOPOLOGY_FRONTIER_POSITIVE_COUNT = 4
TOPOLOGY_FRONTIER_CONTROL_COUNT = 12
TOPOLOGY_FRONTIER_SOURCE_COUNT = 5


class TopologyFrontierOperation(StrEnum):
    ECDNA_CONTACT = "ecdna_regulatory_contact"
    COMPARTMENT_SWITCH = "compartment_switch"
    TOPOLOGY_TRANSPORT = "topology_uncertainty_transport"
    EVIDENCE_PUBLICATION = "three_d_evidence_publication"


class TopologyFrontierRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class TopologyFrontierSourceReceipt:
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
            raise ValidationError("topology source receipts require HTTPS")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyFrontierRecord:
    record_id: str
    operation: TopologyFrontierOperation
    role: TopologyFrontierRole
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
            raise ValidationError("topology records require sources and payload")
        if not isinstance(self.operation, TopologyFrontierOperation):
            raise ValidationError("topology operation must be declared")
        if not isinstance(self.role, TopologyFrontierRole):
            raise ValidationError("topology role must be declared")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyFrontierFixture:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[TopologyFrontierSourceReceipt, ...]
    records: tuple[TopologyFrontierRecord, ...]
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
        if self.evidence_boundary != TOPOLOGY_FRONTIER_EVIDENCE_BOUNDARY:
            raise ValidationError("unsupported topology evidence boundary")
        if not self.sources or not self.records:
            raise ValidationError("topology fixture requires sources and records")

    @property
    def positive_records(self) -> tuple[TopologyFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is TopologyFrontierRole.POSITIVE)

    @property
    def control_records(self) -> tuple[TopologyFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is TopologyFrontierRole.CONTROL)

    def source_map(self) -> dict[str, TopologyFrontierSourceReceipt]:
        return {item.source_id: item for item in self.sources}

    def record_map(self) -> dict[str, TopologyFrontierRecord]:
        return {item.record_id: item for item in self.records}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyFrontierCatalog:
    fixture: TopologyFrontierFixture
    source_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    operations: tuple[TopologyFrontierOperation, ...]
    content_address: str

    def __post_init__(self) -> None:
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValidationError("topology source IDs must be unique")
        if len(set(self.record_ids)) != len(self.record_ids):
            raise ValidationError("topology record IDs must be unique")
        if set(self.operations) != set(TopologyFrontierOperation):
            raise ValidationError("topology catalog must cover all operations")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyFrontierDataCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyFrontierDataAudit:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    checks: tuple[TopologyFrontierDataCheck, ...]
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
) -> TopologyFrontierSourceReceipt:
    body = {
        "source_id": source_id,
        "title": title,
        "uri": uri,
        "source_kind": source_kind,
        "release": release,
        "scope": scope,
    }
    return TopologyFrontierSourceReceipt(**body, content_address=content_hash(body))


def _text(rows: list[Any]) -> str:
    return json.dumps(rows, sort_keys=True, separators=(",", ":"))


def _record(
    record_id: str,
    operation: TopologyFrontierOperation,
    role: TopologyFrontierRole,
    rows: list[Any],
    expected_state: str,
    expected_issue_codes: tuple[str, ...],
    source_ids: tuple[str, ...],
    description: str,
    **metadata: Any,
) -> TopologyFrontierRecord:
    payload = {"input_text": _text(rows), **metadata}
    body = {
        "record_id": record_id,
        "operation": operation,
        "role": role,
        "context_key": TOPOLOGY_FRONTIER_CONTEXT_KEY,
        "source_ids": source_ids,
        "payload": payload,
        "expected_state": expected_state,
        "expected_issue_codes": expected_issue_codes,
        "description": description,
    }
    return TopologyFrontierRecord(**body, content_address=content_hash(body))


def default_topology_frontier_fixture() -> TopologyFrontierFixture:
    sources = (
        _source(
            "four-d-nucleome",
            "4D Nucleome public genome organization data",
            "https://data.4dnucleome.org/",
            "public_topology_archive",
            "2024-01",
            "aggregate three-dimensional genome observations",
        ),
        _source(
            "encode-project",
            "ENCODE public functional genomics portal",
            "https://www.encodeproject.org/",
            "public_assay_archive",
            "2024-01",
            "aggregate chromatin and regulatory assay context",
        ),
        _source(
            "ncbi-geo-topology",
            "NCBI Gene Expression Omnibus public submissions",
            "https://www.ncbi.nlm.nih.gov/geo/",
            "public_archive",
            "2025-01",
            "aggregate topology and molecular-state submissions",
        ),
        _source(
            "ucsc-genome-browser-topology",
            "UCSC Genome Browser assembly and coordinate context",
            "https://genome.ucsc.edu/",
            "reference_browser",
            "GRCh38",
            "assembly and coordinate interpretation",
        ),
        _source(
            "nih-common-fund-4d",
            "NIH Common Fund four-dimensional genome resources",
            "https://commonfund.nih.gov/4D-Nucleome",
            "public_program_archive",
            "2023",
            "public program and assay provenance context",
        ),
    )
    records = (
        _record(
            "C13-POS-001",
            TopologyFrontierOperation.ECDNA_CONTACT,
            TopologyFrontierRole.POSITIVE,
            [
                {
                    "amplicon_id": "amp-001",
                    "element_id": "enh-001",
                    "gene_id": "GENE1",
                    "contact_score": 0.86,
                    "source_ids": ["four-d-nucleome", "encode-project"],
                    "context_key": TOPOLOGY_FRONTIER_CONTEXT_KEY,
                }
            ],
            "supported",
            (),
            ("four-d-nucleome", "encode-project"),
            "public aggregate ecDNA contact has sufficient score and source support",
            minimum_contact_score=0.5,
            minimum_sources=2,
        ),
        _record(
            "C13-CTRL-001",
            TopologyFrontierOperation.ECDNA_CONTACT,
            TopologyFrontierRole.CONTROL,
            [
                {
                    "amplicon_id": "amp-weak",
                    "element_id": "enh-weak",
                    "gene_id": "GENE2",
                    "contact_score": 0.2,
                    "source_ids": ["four-d-nucleome"],
                    "context_key": TOPOLOGY_FRONTIER_CONTEXT_KEY,
                }
            ],
            "partial",
            ("weak_ecDNA_contact", "insufficient_ecDNA_sources"),
            ("four-d-nucleome",),
            "weak ecDNA contact remains a review outcome",
            minimum_contact_score=0.5,
            minimum_sources=2,
        ),
        _record(
            "C13-CTRL-002",
            TopologyFrontierOperation.ECDNA_CONTACT,
            TopologyFrontierRole.CONTROL,
            [
                {
                    "amplicon_id": "amp-other",
                    "element_id": "enh-other",
                    "gene_id": "GENE3",
                    "contact_score": 0.9,
                    "source_ids": ["four-d-nucleome", "encode-project"],
                    "context_key": "GRCh38|glioma|pediatric|stem_like|tumor|unknown",
                }
            ],
            "out_of_domain",
            ("context_mismatch",),
            ("four-d-nucleome",),
            "other cohort context is not transported into the adult context",
            minimum_contact_score=0.5,
            minimum_sources=1,
        ),
        _record(
            "C13-CTRL-003",
            TopologyFrontierOperation.ECDNA_CONTACT,
            TopologyFrontierRole.CONTROL,
            ["not-a-contact-object"],
            "invalid",
            ("invalid_ecdna_record",),
            ("encode-project",),
            "non-object ecDNA row is quarantined as invalid",
        ),
        _record(
            "C14-POS-001",
            TopologyFrontierOperation.COMPARTMENT_SWITCH,
            TopologyFrontierRole.POSITIVE,
            [
                {
                    "region_id": "region-001",
                    "previous_score": -0.55,
                    "current_score": 0.62,
                    "context_key": TOPOLOGY_FRONTIER_CONTEXT_KEY,
                }
            ],
            "supported",
            (),
            ("four-d-nucleome", "ncbi-geo-topology"),
            "paired signed scores support a B-to-A compartment switch",
            switch_threshold=0.15,
        ),
        _record(
            "C14-CTRL-001",
            TopologyFrontierOperation.COMPARTMENT_SWITCH,
            TopologyFrontierRole.CONTROL,
            [
                {
                    "region_id": "region-stable",
                    "previous_score": 0.42,
                    "current_score": 0.48,
                    "context_key": TOPOLOGY_FRONTIER_CONTEXT_KEY,
                }
            ],
            "partial",
            (),
            ("four-d-nucleome",),
            "small same-compartment delta remains reviewable",
            switch_threshold=0.15,
        ),
        _record(
            "C14-CTRL-002",
            TopologyFrontierOperation.COMPARTMENT_SWITCH,
            TopologyFrontierRole.CONTROL,
            [
                {
                    "region_id": "region-other",
                    "previous_score": -0.5,
                    "current_score": 0.5,
                    "context_key": "GRCh38|glioma|adult|stem_like|normal|unknown",
                }
            ],
            "out_of_domain",
            ("context_mismatch",),
            ("ncbi-geo-topology",),
            "normal compartment context is not reused for tumor context",
        ),
        _record(
            "C14-CTRL-003",
            TopologyFrontierOperation.COMPARTMENT_SWITCH,
            TopologyFrontierRole.CONTROL,
            [{"region_id": "region-invalid", "previous_score": "bad"}],
            "invalid",
            ("invalid_compartment_record",),
            ("ncbi-geo-topology",),
            "missing paired compartment score is quarantined",
        ),
        _record(
            "C15-POS-001",
            TopologyFrontierOperation.TOPOLOGY_TRANSPORT,
            TopologyFrontierRole.POSITIVE,
            [
                {
                    "path_id": "path-001",
                    "node_ids": ["node-a", "node-b", "node-c"],
                    "edges": [
                        {"edge_id": "edge-ab", "uncertainty": 0.08},
                        {"edge_id": "edge-bc", "uncertainty": 0.10},
                    ],
                    "signal": 0.9,
                    "context_key": TOPOLOGY_FRONTIER_CONTEXT_KEY,
                }
            ],
            "supported",
            (),
            ("four-d-nucleome", "ucsc-genome-browser-topology"),
            "contiguous public topology path retains effective signal",
            minimum_effective_signal=0.3,
        ),
        _record(
            "C15-CTRL-001",
            TopologyFrontierOperation.TOPOLOGY_TRANSPORT,
            TopologyFrontierRole.CONTROL,
            [
                {
                    "path_id": "path-weak",
                    "node_ids": ["node-a", "node-b"],
                    "edges": [{"edge_id": "edge-ab", "uncertainty": 0.9}],
                    "signal": 0.4,
                    "context_key": TOPOLOGY_FRONTIER_CONTEXT_KEY,
                }
            ],
            "partial",
            ("weak_transported_signal",),
            ("four-d-nucleome",),
            "uncertainty-adjusted topology signal remains reviewable",
            minimum_effective_signal=0.3,
        ),
        _record(
            "C15-CTRL-002",
            TopologyFrontierOperation.TOPOLOGY_TRANSPORT,
            TopologyFrontierRole.CONTROL,
            [
                {
                    "path_id": "path-disconnected",
                    "node_ids": ["node-a", "node-b", "node-c"],
                    "edges": [{"edge_id": "edge-ab", "uncertainty": 0.1}],
                    "signal": 0.9,
                    "context_key": TOPOLOGY_FRONTIER_CONTEXT_KEY,
                }
            ],
            "partial",
            ("topology_path_disconnected",),
            ("four-d-nucleome",),
            "edge and node mismatch remains visible",
        ),
        _record(
            "C15-CTRL-003",
            TopologyFrontierOperation.TOPOLOGY_TRANSPORT,
            TopologyFrontierRole.CONTROL,
            [
                {
                    "path_id": "path-other",
                    "node_ids": ["node-a", "node-b"],
                    "edges": [{"edge_id": "edge-ab", "uncertainty": 0.1}],
                    "signal": 0.9,
                    "context_key": "GRCh38|glioma|pediatric|stem_like|tumor|unknown",
                }
            ],
            "out_of_domain",
            ("context_mismatch",),
            ("ucsc-genome-browser-topology",),
            "other cohort topology path is out of domain",
        ),
        _record(
            "C16-POS-001",
            TopologyFrontierOperation.EVIDENCE_PUBLICATION,
            TopologyFrontierRole.POSITIVE,
            [
                {"path_id": "path-001", "context_key": TOPOLOGY_FRONTIER_CONTEXT_KEY},
                {"path_id": "path-002", "context_key": TOPOLOGY_FRONTIER_CONTEXT_KEY},
            ],
            "supported",
            (),
            ("four-d-nucleome", "encode-project", "ucsc-genome-browser-topology"),
            "publication bundle binds exact context and declared assay receipts",
            bundle_id="topology-bundle-001",
            assay_ids=("hi-c", "micro-c"),
        ),
        _record(
            "C16-CTRL-001",
            TopologyFrontierOperation.EVIDENCE_PUBLICATION,
            TopologyFrontierRole.CONTROL,
            [{"path_id": "path-other", "context_key": "GRCh38|glioma|adult|stem_like|normal|unknown"}],
            "out_of_domain",
            ("context_mismatch",),
            ("four-d-nucleome",),
            "normal context cannot be published into tumor context",
            bundle_id="topology-bundle-other",
            assay_ids=("hi-c",),
        ),
        _record(
            "C16-CTRL-002",
            TopologyFrontierOperation.EVIDENCE_PUBLICATION,
            TopologyFrontierRole.CONTROL,
            [{"path_id": "path-no-assay", "context_key": TOPOLOGY_FRONTIER_CONTEXT_KEY}],
            "partial",
            ("missing_assay_ids",),
            ("encode-project",),
            "publication without assay receipts remains partial",
            bundle_id="topology-bundle-no-assay",
            assay_ids=(),
        ),
        _record(
            "C16-CTRL-003",
            TopologyFrontierOperation.EVIDENCE_PUBLICATION,
            TopologyFrontierRole.CONTROL,
            [],
            "partial",
            ("empty_3d_evidence",),
            ("encode-project",),
            "empty evidence cannot be published",
            bundle_id="topology-bundle-empty",
            assay_ids=("hi-c",),
        ),
    )
    body = {
        "fixture_id": "topology-frontier-public-aggregate",
        "fixture_version": TOPOLOGY_FRONTIER_FIXTURE_VERSION,
        "context_key": TOPOLOGY_FRONTIER_CONTEXT_KEY,
        "evidence_boundary": TOPOLOGY_FRONTIER_EVIDENCE_BOUNDARY,
        "sources": sources,
        "records": records,
    }
    return TopologyFrontierFixture(**body, content_address=content_hash(body))


def build_topology_frontier_catalog(
    fixture: TopologyFrontierFixture | None = None,
) -> TopologyFrontierCatalog:
    selected = fixture or default_topology_frontier_fixture()
    body = {
        "fixture": selected.fixture_id,
        "source_ids": tuple(item.source_id for item in selected.sources),
        "record_ids": tuple(item.record_id for item in selected.records),
        "operations": tuple(dict.fromkeys(item.operation for item in selected.records)),
    }
    return TopologyFrontierCatalog(
        selected,
        body["source_ids"],
        body["record_ids"],
        body["operations"],
        content_hash(body),
    )


def _contains_subject_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            str(key).lower() in {"patient", "subject", "donor", "participant"}
            or _contains_subject_key(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_subject_key(item) for item in value)
    return False


def audit_topology_frontier_data(
    fixture: TopologyFrontierFixture | None = None,
) -> TopologyFrontierDataAudit:
    selected = fixture or default_topology_frontier_fixture()
    checks: list[TopologyFrontierDataCheck] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(TopologyFrontierDataCheck(**body, content_address=content_hash(body)))

    add("fixture-context", selected.context_key == TOPOLOGY_FRONTIER_CONTEXT_KEY, "exact context")
    add(
        "evidence-boundary",
        selected.evidence_boundary == TOPOLOGY_FRONTIER_EVIDENCE_BOUNDARY,
        "public aggregate non-patient boundary",
    )
    add("source-count", len(selected.sources) == TOPOLOGY_FRONTIER_SOURCE_COUNT, "five source receipts")
    add("source-https", all(item.uri.startswith("https://") for item in selected.sources), "HTTPS receipts")
    add("record-count", len(selected.records) == 16, "sixteen records")
    add(
        "role-balance",
        len(selected.positive_records) == 4 and len(selected.control_records) == 12,
        "four positives and twelve controls",
    )
    add(
        "operation-coverage",
        {item.operation for item in selected.records} == set(TopologyFrontierOperation),
        "all four operations are represented",
    )
    add(
        "source-closure",
        all(source_id in selected.source_map() for item in selected.records for source_id in item.source_ids),
        "every record source resolves",
    )
    add(
        "no-subject-identifiers",
        not any(_contains_subject_key(item.payload) for item in selected.records),
        "payloads remain aggregate scoped",
    )
    body = {"fixture": selected, "checks": checks}
    return TopologyFrontierDataAudit(
        selected.fixture_id,
        selected.fixture_version,
        selected.context_key,
        selected.evidence_boundary,
        tuple(checks),
        content_hash(body),
    )


def load_topology_frontier_fixture(path: str | Path) -> TopologyFrontierFixture:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    sources = tuple(TopologyFrontierSourceReceipt(**row) for row in payload["sources"])
    records = tuple(
        TopologyFrontierRecord(
            record_id=row["record_id"],
            operation=TopologyFrontierOperation(row["operation"]),
            role=TopologyFrontierRole(row["role"]),
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
    fixture = TopologyFrontierFixture(
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
        raise ValidationError("topology fixture content address mismatch")
    return fixture


__all__ = [
    "TOPOLOGY_FRONTIER_CONTEXT_KEY",
    "TOPOLOGY_FRONTIER_CONTROL_COUNT",
    "TOPOLOGY_FRONTIER_EVIDENCE_BOUNDARY",
    "TOPOLOGY_FRONTIER_FIXTURE_VERSION",
    "TOPOLOGY_FRONTIER_POSITIVE_COUNT",
    "TOPOLOGY_FRONTIER_SOURCE_COUNT",
    "TopologyFrontierCatalog",
    "TopologyFrontierDataAudit",
    "TopologyFrontierDataCheck",
    "TopologyFrontierFixture",
    "TopologyFrontierOperation",
    "TopologyFrontierRecord",
    "TopologyFrontierRole",
    "TopologyFrontierSourceReceipt",
    "audit_topology_frontier_data",
    "build_topology_frontier_catalog",
    "default_topology_frontier_fixture",
    "load_topology_frontier_fixture",
]
