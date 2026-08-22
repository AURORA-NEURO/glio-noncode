"""Public aggregate fixture for the Domain 14 evidence lifecycle frontier."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty

EVIDENCE_LIFECYCLE_FIXTURE_VERSION = "2026.08.d14-c01-c04.v1"
EVIDENCE_LIFECYCLE_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|core|untreated"
EVIDENCE_LIFECYCLE_EVIDENCE_BOUNDARY = "public_aggregate_non_patient"
EVIDENCE_LIFECYCLE_SOURCE_COUNT = 5
EVIDENCE_LIFECYCLE_POSITIVE_COUNT = 4
EVIDENCE_LIFECYCLE_CONTROL_COUNT = 12


class EvidenceLifecycleOperation(StrEnum):
    CITATION_RESOLUTION = "citation_resolution"
    GRAPH_CONSTRUCTION = "graph_construction"
    EDGE_VALIDATION = "edge_validation"
    DISAGREEMENT_TRACKING = "disagreement_tracking"


class EvidenceLifecycleRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleSourceReceipt:
    source_id: str
    title: str
    uri: str
    access_note: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("source_id", "title", "uri", "access_note", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.uri.startswith("https://"):
            raise ValueError("evidence lifecycle source URI must use HTTPS")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleRecord:
    record_id: str
    operation: EvidenceLifecycleOperation
    role: EvidenceLifecycleRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: dict[str, Any]
    expected_state: str
    expected_issue_codes: tuple[str, ...]
    notes: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("record_id", "context_key", "expected_state", "notes", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.source_ids:
            raise ValueError("evidence lifecycle record requires source IDs")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleFixture:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[EvidenceLifecycleSourceReceipt, ...]
    records: tuple[EvidenceLifecycleRecord, ...]
    content_address: str

    @property
    def positive_records(self) -> tuple[EvidenceLifecycleRecord, ...]:
        return tuple(item for item in self.records if item.role is EvidenceLifecycleRole.POSITIVE)

    @property
    def control_records(self) -> tuple[EvidenceLifecycleRecord, ...]:
        return tuple(item for item in self.records if item.role is EvidenceLifecycleRole.CONTROL)

    def by_operation(self, operation: EvidenceLifecycleOperation) -> tuple[EvidenceLifecycleRecord, ...]:
        return tuple(item for item in self.records if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleCatalog:
    fixture_id: str
    record_ids: tuple[str, ...]
    operations: tuple[EvidenceLifecycleOperation, ...]
    source_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleDataCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleDataAudit:
    fixture_id: str
    checks: tuple[EvidenceLifecycleDataCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _source(source_id: str, title: str) -> EvidenceLifecycleSourceReceipt:
    body = {"source_id": source_id, "title": title, "uri": f"https://example.org/glio/{source_id}", "access_note": "public aggregate receipt"}
    return EvidenceLifecycleSourceReceipt(**body, content_address=content_hash(body))


def _citation(citation_id: str, source_id: str, *, context_key: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"citation_id": citation_id, "source_id": source_id, "source_uri": f"https://example.org/citation/{citation_id}", "title": f"Aggregate citation {citation_id}", "version": "v1", "citation_text": f"Public aggregate citation {citation_id}", "retrieved_at": "2026-08-20T00:00:00+00:00"}
    if context_key is not None:
        body["context_key"] = context_key
    return body


def _claim(claim_id: str, edge_id: str, source_id: str, *, state: str = "supported", context_key: str = EVIDENCE_LIFECYCLE_CONTEXT_KEY, supersedes: str | None = None, parent_claim_ids: tuple[str, ...] = (), value: str | None = None) -> dict[str, Any]:
    attributes: dict[str, Any] = {"claim_value": value} if value is not None else {}
    return {"claim_id": claim_id, "edge_id": edge_id, "context_key": context_key, "state": state, "support": 0.8, "confidence": 0.9, "claim_type": "functional", "summary": f"Aggregate claim {claim_id}", "source_ids": [source_id], "source_versions": {source_id: "v1"}, "raw_hash": f"sha256:{claim_id}", "parent_claim_ids": list(parent_claim_ids), "supersedes": supersedes, "attributes": attributes, "created_at": "2026-08-20T00:00:00+00:00"}


def _record(record_id: str, operation: EvidenceLifecycleOperation, role: EvidenceLifecycleRole, payload: dict[str, Any], expected_state: str, expected_issue_codes: tuple[str, ...], notes: str, source_ids: tuple[str, ...]) -> EvidenceLifecycleRecord:
    body = {"record_id": record_id, "operation": operation, "role": role, "context_key": EVIDENCE_LIFECYCLE_CONTEXT_KEY, "source_ids": source_ids, "payload": payload, "expected_state": expected_state, "expected_issue_codes": expected_issue_codes, "notes": notes}
    return EvidenceLifecycleRecord(**body, content_address=content_hash(body))


def default_evidence_lifecycle_fixture() -> EvidenceLifecycleFixture:
    sources = tuple(_source(*item) for item in (("src-citation", "Public citation manifest"), ("src-graph", "Versioned graph snapshot"), ("src-edge", "Claim edge validation"), ("src-disagreement", "Disagreement report"), ("src-control", "Negative control receipt")))
    context = EVIDENCE_LIFECYCLE_CONTEXT_KEY
    graph_citations = [_citation("citation-graph-1", "src-graph")]
    graph_claims = [_claim("c02-first", "edge-c02", "citation-graph-1"), _claim("c02-current", "edge-c02", "citation-graph-1", supersedes="c02-first")]
    edge_citations = [_citation("citation-edge-1", "src-edge")]
    disagreement_citations = [_citation("citation-disagreement-1", "src-disagreement"), _citation("citation-disagreement-2", "src-control")]
    disagreement_claims = [_claim("c04-positive", "edge-c04", "citation-disagreement-1", value="increases"), _claim("c04-negative", "edge-c04", "citation-disagreement-2", state="measured_negative", value="decreases")]
    records = (
        _record("C01-POS-001", EvidenceLifecycleOperation.CITATION_RESOLUTION, EvidenceLifecycleRole.POSITIVE, {"text": "citation_id\tsource_uri\ttitle\tversion\tcitation_text\tretrieved_at\ncv1\thttps://example.org/cv1\tValid\tv1\tPublic citation\t2026-08-20T00:00:00+00:00\ncv2\thttps://example.org/cv2\tIncomplete\tv1\t\t2026-08-20T00:00:00+00:00", "source_id": "src-citation", "source_version": "v1", "input_format": "tsv"}, "partial", ("missing_required_field",), "one valid row and one quarantined row", ("src-citation", "src-graph")),
        _record("C01-CTRL-001", EvidenceLifecycleOperation.CITATION_RESOLUTION, EvidenceLifecycleRole.CONTROL, {"text": "{not-json", "source_id": "src-citation", "source_version": "v1", "input_format": "json"}, "abstained", ("invalid_json",), "malformed JSON remains visible", ("src-control",)),
        _record("C01-CTRL-002", EvidenceLifecycleOperation.CITATION_RESOLUTION, EvidenceLifecycleRole.CONTROL, {"text": "citation_id,source_uri,title,version,citation_text,retrieved_at\ndup,https://example.org/a,A,v1,Text,2026-08-20T00:00:00+00:00\ndup,https://example.org/b,B,v1,Text,2026-08-20T00:00:00+00:00", "source_id": "src-citation", "source_version": "v1", "input_format": "csv"}, "partial", ("duplicate_citation_id",), "duplicate row is quarantined", ("src-control",)),
        _record("C01-CTRL-003", EvidenceLifecycleOperation.CITATION_RESOLUTION, EvidenceLifecycleRole.CONTROL, {"text": "", "source_id": "src-citation", "source_version": "v1", "input_format": "tsv"}, "abstained", ("missing_header",), "empty table has a declared header failure", ("src-control",)),
        _record("C02-POS-001", EvidenceLifecycleOperation.GRAPH_CONSTRUCTION, EvidenceLifecycleRole.POSITIVE, {"graph_id": "graph-c02", "graph_version": 2, "citations": graph_citations, "claims": graph_claims}, "supported", (), "append-only replacement retains historical claim", ("src-graph", "src-citation")),
        _record("C02-CTRL-001", EvidenceLifecycleOperation.GRAPH_CONSTRUCTION, EvidenceLifecycleRole.CONTROL, {"graph_id": "graph-c02-orphan", "citations": [_citation("citation-orphan", "src-graph")], "claims": [_claim("c02-orphan", "edge-c02", "missing-source", parent_claim_ids=("missing-parent",))]}, "partial", ("orphan_claim",), "missing lineage and citation are retained", ("src-control",)),
        _record("C02-CTRL-002", EvidenceLifecycleOperation.GRAPH_CONSTRUCTION, EvidenceLifecycleRole.CONTROL, {"graph_id": "graph-c02-context", "citations": graph_citations, "claims": [_claim("c02-context", "edge-c02", "citation-graph-1", context_key="GRCh38|glioma|pediatric|stem_like|core|untreated")]}, "invalid", ("graph_context_mismatch",), "claim context cannot cross the graph boundary", ("src-control",)),
        _record("C02-CTRL-003", EvidenceLifecycleOperation.GRAPH_CONSTRUCTION, EvidenceLifecycleRole.CONTROL, {"graph_id": "graph-c02-duplicate", "citations": graph_citations, "claims": [_claim("c02-duplicate", "edge-c02", "citation-graph-1"), _claim("c02-duplicate", "edge-c02", "citation-graph-1")]}, "invalid", ("duplicate_claim_id",), "duplicate claim IDs are rejected", ("src-control",)),
        _record("C03-POS-001", EvidenceLifecycleOperation.EDGE_VALIDATION, EvidenceLifecycleRole.POSITIVE, {"graph_id": "graph-c03", "citations": edge_citations, "claims": [_claim("c03-supported", "edge-c03", "citation-edge-1")], "edge_id": "edge-c03", "expected_context_key": context}, "supported", (), "supported edge has resolved citation", ("src-edge", "src-citation")),
        _record("C03-CTRL-001", EvidenceLifecycleOperation.EDGE_VALIDATION, EvidenceLifecycleRole.CONTROL, {"graph_id": "graph-c03-missing", "citations": (), "claims": [_claim("c03-missing", "edge-c03", "missing-source")], "edge_id": "edge-c03"}, "partial", ("missing_source",), "edge retains missing citation", ("src-control",)),
        _record("C03-CTRL-002", EvidenceLifecycleOperation.EDGE_VALIDATION, EvidenceLifecycleRole.CONTROL, {"graph_id": "graph-c03-context", "citations": edge_citations, "claims": [_claim("c03-context", "edge-c03", "citation-edge-1")], "edge_id": "edge-c03", "expected_context_key": "GRCh38|glioma|pediatric|stem_like|core|untreated"}, "out_of_domain", ("edge_context_mismatch",), "requested edge context is explicit", ("src-control",)),
        _record("C03-CTRL-003", EvidenceLifecycleOperation.EDGE_VALIDATION, EvidenceLifecycleRole.CONTROL, {"graph_id": "graph-c03-empty", "citations": edge_citations, "claims": [_claim("c03-other", "edge-other", "citation-edge-1")], "edge_id": "edge-none"}, "abstained", ("edge_absent",), "unknown edge abstains", ("src-control",)),
        _record("C04-POS-001", EvidenceLifecycleOperation.DISAGREEMENT_TRACKING, EvidenceLifecycleRole.POSITIVE, {"graph_id": "graph-c04", "citations": disagreement_citations, "claims": disagreement_claims, "edge_ids": ["edge-c04"]}, "contradictory", ("contradiction_unresolved",), "positive and negative observations stay separate", ("src-disagreement", "src-edge")),
        _record("C04-CTRL-001", EvidenceLifecycleOperation.DISAGREEMENT_TRACKING, EvidenceLifecycleRole.CONTROL, {"graph_id": "graph-c04-clear", "citations": [_citation("citation-clear", "src-disagreement")], "claims": [_claim("c04-clear", "edge-clear", "citation-clear", value="increases")], "edge_ids": ["edge-clear"]}, "clear", (), "one resolved observation is clear", ("src-control",)),
        _record("C04-CTRL-002", EvidenceLifecycleOperation.DISAGREEMENT_TRACKING, EvidenceLifecycleRole.CONTROL, {"graph_id": "graph-c04-empty", "citations": (), "claims": [], "edge_ids": ["edge-none"]}, "incomplete", ("incomplete_disagreement",), "an empty edge is incomplete", ("src-control",)),
        _record("C04-CTRL-003", EvidenceLifecycleOperation.DISAGREEMENT_TRACKING, EvidenceLifecycleRole.CONTROL, {"graph_id": "graph-c04-domain", "citations": [_citation("citation-domain", "src-disagreement", context_key="GRCh38|glioma|pediatric|stem_like|core|untreated")], "claims": [_claim("c04-domain", "edge-domain", "citation-domain", state="out_of_domain")], "edge_ids": ["edge-domain"]}, "out_of_domain", ("disagreement_out_of_domain",), "citation context remains out of domain", ("src-control",)),
    )
    body = {"fixture_id": "evidence-lifecycle-frontier", "fixture_version": EVIDENCE_LIFECYCLE_FIXTURE_VERSION, "context_key": context, "evidence_boundary": EVIDENCE_LIFECYCLE_EVIDENCE_BOUNDARY, "sources": sources, "records": records}
    return EvidenceLifecycleFixture(**body, content_address=content_hash(body))


def build_evidence_lifecycle_catalog(fixture: EvidenceLifecycleFixture) -> EvidenceLifecycleCatalog:
    body = {"fixture_id": fixture.fixture_id, "record_ids": tuple(item.record_id for item in fixture.records), "operations": tuple(sorted({item.operation for item in fixture.records}, key=lambda item: item.value)), "source_ids": tuple(item.source_id for item in fixture.sources)}
    return EvidenceLifecycleCatalog(**body, content_address=content_hash(body))


def audit_evidence_lifecycle_data(fixture: EvidenceLifecycleFixture | None = None) -> EvidenceLifecycleDataAudit:
    fixture = fixture or default_evidence_lifecycle_fixture()
    source_ids = {item.source_id for item in fixture.sources}
    checks = (
        EvidenceLifecycleDataCheck("data:boundary", fixture.evidence_boundary == EVIDENCE_LIFECYCLE_EVIDENCE_BOUNDARY, fixture.evidence_boundary, EVIDENCE_LIFECYCLE_EVIDENCE_BOUNDARY, "public aggregate boundary is exact", ""),
        EvidenceLifecycleDataCheck("data:source-count", len(fixture.sources) == EVIDENCE_LIFECYCLE_SOURCE_COUNT, len(fixture.sources), EVIDENCE_LIFECYCLE_SOURCE_COUNT, "source receipts are complete", ""),
        EvidenceLifecycleDataCheck("data:record-count", len(fixture.records) == 16, len(fixture.records), 16, "sixteen records are present", ""),
        EvidenceLifecycleDataCheck("data:positive-count", len(fixture.positive_records) == EVIDENCE_LIFECYCLE_POSITIVE_COUNT, len(fixture.positive_records), EVIDENCE_LIFECYCLE_POSITIVE_COUNT, "one positive per operation", ""),
        EvidenceLifecycleDataCheck("data:control-count", len(fixture.control_records) == EVIDENCE_LIFECYCLE_CONTROL_COUNT, len(fixture.control_records), EVIDENCE_LIFECYCLE_CONTROL_COUNT, "three controls per operation", ""),
        EvidenceLifecycleDataCheck("data:unique-records", len({item.record_id for item in fixture.records}) == len(fixture.records), len({item.record_id for item in fixture.records}), len(fixture.records), "record IDs are unique", ""),
        EvidenceLifecycleDataCheck("data:source-bindings", all(set(item.source_ids) <= source_ids for item in fixture.records), True, True, "record source receipts resolve", ""),
        EvidenceLifecycleDataCheck("data:operation-coverage", {item.operation for item in fixture.records} == set(EvidenceLifecycleOperation), tuple(sorted({item.operation.value for item in fixture.records})), tuple(item.value for item in EvidenceLifecycleOperation), "four operations are covered", ""),
        EvidenceLifecycleDataCheck("data:context", all(item.context_key == fixture.context_key for item in fixture.records), fixture.context_key, fixture.context_key, "record context remains exact", ""),
        EvidenceLifecycleDataCheck("data:addresses", all(item.content_address.startswith("sha256:") for item in fixture.records), True, True, "records are addressed", ""),
        EvidenceLifecycleDataCheck("data:source-addresses", all(item.content_address.startswith("sha256:") for item in fixture.sources), True, True, "sources are addressed", ""),
        EvidenceLifecycleDataCheck("data:version", fixture.fixture_version == EVIDENCE_LIFECYCLE_FIXTURE_VERSION, fixture.fixture_version, EVIDENCE_LIFECYCLE_FIXTURE_VERSION, "fixture version is exact", ""),
    )
    addressed = tuple(EvidenceLifecycleDataCheck(item.check_id, item.passed, item.observed, item.required, item.detail, content_hash({"check_id": item.check_id, "passed": item.passed, "observed": item.observed, "required": item.required, "detail": item.detail})) for item in checks)
    body = {"fixture_id": fixture.fixture_id, "checks": addressed, "accepted": all(item.passed for item in addressed)}
    return EvidenceLifecycleDataAudit(fixture.fixture_id, addressed, body["accepted"], content_hash(body))


def load_evidence_lifecycle_fixture(path: str | Path) -> EvidenceLifecycleFixture:
    payload = __import__("json").loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not payload.get("sources") or not payload.get("records"):
        raise ValueError("evidence lifecycle fixture requires sources and records")
    sources = tuple(EvidenceLifecycleSourceReceipt(**item) for item in payload["sources"])
    records = tuple(EvidenceLifecycleRecord(**{**item, "operation": EvidenceLifecycleOperation(str(item["operation"])), "role": EvidenceLifecycleRole(str(item["role"])), "source_ids": tuple(str(value) for value in item["source_ids"]), "expected_issue_codes": tuple(str(value) for value in item["expected_issue_codes"])}) for item in payload["records"])
    body = {key: payload[key] for key in ("fixture_id", "fixture_version", "context_key", "evidence_boundary")}
    return EvidenceLifecycleFixture(**body, sources=sources, records=records, content_address=str(payload.get("content_address", content_hash({**body, "sources": sources, "records": records}))))


__all__ = ["EVIDENCE_LIFECYCLE_CONTEXT_KEY", "EVIDENCE_LIFECYCLE_CONTROL_COUNT", "EVIDENCE_LIFECYCLE_EVIDENCE_BOUNDARY", "EVIDENCE_LIFECYCLE_FIXTURE_VERSION", "EVIDENCE_LIFECYCLE_POSITIVE_COUNT", "EVIDENCE_LIFECYCLE_SOURCE_COUNT", "EvidenceLifecycleCatalog", "EvidenceLifecycleDataAudit", "EvidenceLifecycleDataCheck", "EvidenceLifecycleFixture", "EvidenceLifecycleOperation", "EvidenceLifecycleRecord", "EvidenceLifecycleRole", "EvidenceLifecycleSourceReceipt", "audit_evidence_lifecycle_data", "build_evidence_lifecycle_catalog", "default_evidence_lifecycle_fixture", "load_evidence_lifecycle_fixture"]
