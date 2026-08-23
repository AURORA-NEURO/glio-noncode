"""Public aggregate source receipts and deterministic D14 release scenarios."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .evidence_release_frontier_contracts import (
    EVIDENCE_RELEASE_FRONTIER_BOUNDARY,
    EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY,
    EVIDENCE_RELEASE_FRONTIER_FOREIGN_CONTEXT,
    EVIDENCE_RELEASE_FRONTIER_VERSION,
    EvidenceReleaseFixture,
    EvidenceReleaseOperation,
    EvidenceReleaseRecord,
    EvidenceReleaseRole,
    EvidenceReleaseSourceReceipt,
    EvidenceReleaseState,
)
from .serialization import content_hash, jsonable, require_non_empty

EVIDENCE_RELEASE_FRONTIER_SOURCE_COUNT = 5
EVIDENCE_RELEASE_FRONTIER_RECORD_COUNT = 16
EVIDENCE_RELEASE_FRONTIER_POSITIVE_COUNT = 4
EVIDENCE_RELEASE_FRONTIER_CONTROL_COUNT = 12


@dataclass(frozen=True, slots=True)
class EvidenceReleaseDataCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceReleaseDataAudit:
    fixture_id: str
    checks: tuple[EvidenceReleaseDataCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _source(source_id: str, title: str, uri: str, scope: str) -> EvidenceReleaseSourceReceipt:
    body = {"source_id": source_id, "title": title, "uri": uri, "scope": scope, "version": "public portal receipt"}
    return EvidenceReleaseSourceReceipt(**body, content_address=content_hash(body))


def _sources() -> tuple[EvidenceReleaseSourceReceipt, ...]:
    return (
        _source("europepmc", "Europe PMC literature service", "https://europepmc.org/", "public literature and citation index"),
        _source("pubmed", "PubMed biomedical literature", "https://pubmed.ncbi.nlm.nih.gov/", "public indexed article metadata"),
        _source("gdc", "NCI Genomic Data Commons", "https://gdc.cancer.gov/", "public aggregate disease and genomic reference"),
        _source("encode", "ENCODE project portal", "https://www.encodeproject.org/", "public functional assay reference"),
        _source("ga4gh", "Global Alliance for Genomics and Health", "https://www.ga4gh.org/", "public interoperability and data-use reference"),
    )


def _record(record_id: str, capability: str, operation: EvidenceReleaseOperation, role: EvidenceReleaseRole, payload: Mapping[str, Any], state: EvidenceReleaseState, issues: tuple[str, ...], notes: str, source_ids: tuple[str, ...]) -> EvidenceReleaseRecord:
    body = {"record_id": record_id, "capability": capability, "operation": operation, "role": role, "context_key": VALIDATION_CONTEXT(payload), "source_ids": source_ids, "payload": dict(payload), "expected_state": state, "expected_issue_codes": issues, "notes": notes}
    return EvidenceReleaseRecord(**body, content_address=content_hash(body))


def VALIDATION_CONTEXT(payload: Mapping[str, Any]) -> str:
    """Keep row context as a first-class field while permitting controls."""
    value = payload.get("context_key")
    return value if isinstance(value, str) else EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY


def _reclassification(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {"evidence_id": "evidence-claim-001", "context_key": EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY, "previous_tier": "provisional", "proposed_tier": "supported", "evidence_score": 0.88, "threshold": 0.75, "reviewer_ids": ["reviewer-a", "reviewer-b"], "source_ids": ["europepmc", "gdc"], "rationale": "independent aggregate sources converge"}
    value.update(overrides)
    return value


def _supersession(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {"context_key": EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY, "records": [{"record_id": "claim-old", "status": "deprecated", "supersedes": None, "context_key": EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY}, {"record_id": "claim-current", "status": "active", "supersedes": "claim-old", "context_key": EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY}]}
    value.update(overrides)
    return value


def _bundle(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {"bundle_id": "audit-bundle-001", "context_key": EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY, "sections": [{"section_id": "evidence-section", "kind": "evidence", "context_key": EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY, "items": [{"record_id": "evidence-001", "content_address": "sha256:evidence-001"}]}, {"section_id": "review-section", "kind": "review", "context_key": EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY, "items": [{"record_id": "review-001", "content_address": "sha256:review-001"}]}, {"section_id": "release-section", "kind": "release", "context_key": EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY, "items": [{"record_id": "release-001", "content_address": "sha256:release-001"}]}]}
    value.update(overrides)
    return value


def _dossier(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {"dossier_id": "dossier-001", "context_key": EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY, "audience": "research review board", "key_id": "evidence-release-fixture-key-001", "expires_at": "2030-01-01T00:00:00Z", "payload": {"claim_ids": ["claim-current"], "bundle_address": "sha256:bundle-001", "release_scope": "aggregate research review"}}
    value.update(overrides)
    return value


def default_evidence_release_frontier_fixture() -> EvidenceReleaseFixture:
    sources = _sources()
    records = (
        _record("D14-C13-POS-001", "evidence-tier-reclassification", EvidenceReleaseOperation.RECLASSIFICATION, EvidenceReleaseRole.POSITIVE, _reclassification(), EvidenceReleaseState.RECLASSIFIED, (), "two reviewers and two public source receipts clear the transition", ("europepmc", "gdc")),
        _record("D14-C13-CTRL-001", "evidence-tier-reclassification", EvidenceReleaseOperation.RECLASSIFICATION, EvidenceReleaseRole.CONTROL, _reclassification(evidence_id="evidence-low-score", evidence_score=0.42), EvidenceReleaseState.REVIEW, ("score_below_threshold",), "a low score remains review-only", ("europepmc", "gdc")),
        _record("D14-C13-CTRL-002", "evidence-tier-reclassification", EvidenceReleaseOperation.RECLASSIFICATION, EvidenceReleaseRole.CONTROL, _reclassification(evidence_id="evidence-one-reviewer", reviewer_ids=["reviewer-a"]), EvidenceReleaseState.REVIEW, ("independent_reviewers_missing",), "one reviewer does not close the transition", ("europepmc", "gdc")),
        _record("D14-C13-CTRL-003", "evidence-tier-reclassification", EvidenceReleaseOperation.RECLASSIFICATION, EvidenceReleaseRole.CONTROL, _reclassification(evidence_id="evidence-foreign", context_key=EVIDENCE_RELEASE_FRONTIER_FOREIGN_CONTEXT), EvidenceReleaseState.BLOCKED, ("context_mismatch",), "a foreign context is quarantined", ("europepmc", "gdc")),
        _record("D14-C14-POS-001", "record-deprecation-supersession", EvidenceReleaseOperation.SUPERSESSION, EvidenceReleaseRole.POSITIVE, _supersession(), EvidenceReleaseState.SUPERSEDED, (), "a two-record chain closes with one active record", ("pubmed", "ga4gh")),
        _record("D14-C14-CTRL-001", "record-deprecation-supersession", EvidenceReleaseOperation.SUPERSESSION, EvidenceReleaseRole.CONTROL, _supersession(records=[{"record_id": "claim-current", "status": "active", "supersedes": "claim-missing", "context_key": EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY}]), EvidenceReleaseState.REVIEW, ("supersession_target_missing",), "a missing target cannot be silently retired", ("pubmed", "ga4gh")),
        _record("D14-C14-CTRL-002", "record-deprecation-supersession", EvidenceReleaseOperation.SUPERSESSION, EvidenceReleaseRole.CONTROL, _supersession(records=[{"record_id": "claim-a", "status": "active", "supersedes": "claim-b", "context_key": EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY}, {"record_id": "claim-b", "status": "deprecated", "supersedes": "claim-a", "context_key": EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY}]), EvidenceReleaseState.BLOCKED, ("supersession_cycle",), "a cycle blocks publication", ("pubmed", "ga4gh")),
        _record("D14-C14-CTRL-003", "record-deprecation-supersession", EvidenceReleaseOperation.SUPERSESSION, EvidenceReleaseRole.CONTROL, _supersession(context_key=EVIDENCE_RELEASE_FRONTIER_FOREIGN_CONTEXT), EvidenceReleaseState.BLOCKED, ("context_mismatch",), "foreign lifecycle state is not transported", ("pubmed", "ga4gh")),
        _record("D14-C15-POS-001", "audit-reproducibility-bundle", EvidenceReleaseOperation.REPRODUCIBILITY_BUNDLE, EvidenceReleaseRole.POSITIVE, _bundle(), EvidenceReleaseState.BUNDLED, (), "evidence, review, and release sections close with addresses", ("gdc", "encode", "ga4gh")),
        _record("D14-C15-CTRL-001", "audit-reproducibility-bundle", EvidenceReleaseOperation.REPRODUCIBILITY_BUNDLE, EvidenceReleaseRole.CONTROL, _bundle(sections=[]), EvidenceReleaseState.REVIEW, ("required_section_missing",), "an empty bundle is reviewable but not published", ("gdc", "encode", "ga4gh")),
        _record("D14-C15-CTRL-002", "audit-reproducibility-bundle", EvidenceReleaseOperation.REPRODUCIBILITY_BUNDLE, EvidenceReleaseRole.CONTROL, _bundle(sections=[{**_bundle()["sections"][0], "section_id": "duplicate"}, {**_bundle()["sections"][1], "section_id": "duplicate"}, _bundle()["sections"][2]]), EvidenceReleaseState.REVIEW, ("duplicate_section_id",), "duplicate section identity is held for review", ("gdc", "encode", "ga4gh")),
        _record("D14-C15-CTRL-003", "audit-reproducibility-bundle", EvidenceReleaseOperation.REPRODUCIBILITY_BUNDLE, EvidenceReleaseRole.CONTROL, _bundle(context_key=EVIDENCE_RELEASE_FRONTIER_FOREIGN_CONTEXT), EvidenceReleaseState.BLOCKED, ("context_mismatch",), "foreign bundle context is blocked", ("gdc", "encode", "ga4gh")),
        _record("D14-C16-POS-001", "signed-research-dossier", EvidenceReleaseOperation.SIGNED_DOSSIER, EvidenceReleaseRole.POSITIVE, _dossier(), EvidenceReleaseState.SIGNED, (), "the dossier receives a key ID and verifiable HMAC receipt", ("europepmc", "gdc", "ga4gh")),
        _record("D14-C16-CTRL-001", "signed-research-dossier", EvidenceReleaseOperation.SIGNED_DOSSIER, EvidenceReleaseRole.CONTROL, _dossier(dossier_id="dossier-expired", expires_at="expired:2024-01-01T00:00:00Z"), EvidenceReleaseState.REVIEW, ("dossier_expired",), "expired material cannot be published", ("europepmc", "gdc", "ga4gh")),
        _record("D14-C16-CTRL-002", "signed-research-dossier", EvidenceReleaseOperation.SIGNED_DOSSIER, EvidenceReleaseRole.CONTROL, _dossier(dossier_id="dossier-foreign", context_key=EVIDENCE_RELEASE_FRONTIER_FOREIGN_CONTEXT), EvidenceReleaseState.BLOCKED, ("context_mismatch",), "foreign dossier context cannot be signed", ("europepmc", "gdc", "ga4gh")),
        _record("D14-C16-CTRL-003", "signed-research-dossier", EvidenceReleaseOperation.SIGNED_DOSSIER, EvidenceReleaseRole.CONTROL, _dossier(dossier_id="dossier-empty", payload={}), EvidenceReleaseState.REVIEW, ("dossier_payload_empty",), "empty dossier payload is not released", ("europepmc", "gdc", "ga4gh")),
    )
    body = {"fixture_id": "evidence-release-public-aggregate-001", "fixture_version": EVIDENCE_RELEASE_FRONTIER_VERSION, "context_key": EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY, "evidence_boundary": EVIDENCE_RELEASE_FRONTIER_BOUNDARY, "sources": sources, "records": records}
    return EvidenceReleaseFixture(**body, content_address=content_hash(body))


def audit_evidence_release_frontier_data(fixture: EvidenceReleaseFixture) -> EvidenceReleaseDataAudit:
    source_ids = {item.source_id for item in fixture.sources}
    record_ids = tuple(item.record_id for item in fixture.records)
    operation_counts = Counter(item.operation.value for item in fixture.records)
    marker_rows = tuple(item.record_id for item in fixture.records if any(marker in json.dumps(item.payload).lower() for marker in ("api_key", "password", "patient_id", "sample_id", "access_token")))
    values = (
        ("source-count", len(fixture.sources), EVIDENCE_RELEASE_FRONTIER_SOURCE_COUNT, "public provenance receipts"),
        ("record-count", len(fixture.records), EVIDENCE_RELEASE_FRONTIER_RECORD_COUNT, "four records per transition"),
        ("positive-count", len(fixture.positive_records), EVIDENCE_RELEASE_FRONTIER_POSITIVE_COUNT, "one positive per transition"),
        ("control-count", len(fixture.control_records), EVIDENCE_RELEASE_FRONTIER_CONTROL_COUNT, "three controls per transition"),
        ("unique-record-ids", len(record_ids), len(set(record_ids)), "record identities are unique"),
        ("known-sources", all(set(item.source_ids) <= source_ids for item in fixture.records), True, "rows link to source receipts"),
        ("https-receipts", all(item.uri.startswith("https://") for item in fixture.sources), True, "receipts use HTTPS"),
        ("no-sensitive-markers", marker_rows, (), "public fixture contains no sensitive markers"),
        ("balanced-operations", sorted(operation_counts.values()), [4, 4, 4, 4], "transition rows are balanced"),
        ("exact-context", fixture.context_key == EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY, True, "fixture declares the supported context"),
    )
    checks = []
    for check_id, observed, required, detail in values:
        body = {"check_id": check_id, "passed": observed == required, "observed": observed, "required": required, "detail": detail}
        checks.append(EvidenceReleaseDataCheck(**body, content_address=content_hash(body)))
    return EvidenceReleaseDataAudit(fixture.fixture_id, tuple(checks), all(item.passed for item in checks), content_hash(tuple(checks)))


def load_evidence_release_frontier_fixture(path: str | Path) -> EvidenceReleaseFixture:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping) or raw.get("fixture_version") != EVIDENCE_RELEASE_FRONTIER_VERSION:
        raise ValueError("evidence-release fixture version mismatch")
    expected = default_evidence_release_frontier_fixture()
    if raw.get("fixture_id") != expected.fixture_id or raw.get("content_address") != expected.content_address:
        raise ValueError("evidence-release fixture identity or address mismatch")
    return expected


def evidence_release_frontier_fixture_json(fixture: EvidenceReleaseFixture | None = None) -> str:
    return json.dumps(jsonable(fixture or default_evidence_release_frontier_fixture()), indent=2, sort_keys=True) + "\n"


__all__ = [
    "EVIDENCE_RELEASE_FRONTIER_CONTROL_COUNT",
    "EVIDENCE_RELEASE_FRONTIER_POSITIVE_COUNT",
    "EVIDENCE_RELEASE_FRONTIER_RECORD_COUNT",
    "EVIDENCE_RELEASE_FRONTIER_SOURCE_COUNT",
    "EvidenceReleaseDataAudit",
    "EvidenceReleaseDataCheck",
    "audit_evidence_release_frontier_data",
    "default_evidence_release_frontier_fixture",
    "evidence_release_frontier_fixture_json",
    "load_evidence_release_frontier_fixture",
]
