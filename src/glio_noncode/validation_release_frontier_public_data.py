"""Public source receipts and deterministic aggregate rows for D13 C13-C16."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .serialization import content_hash, jsonable, require_non_empty
from .validation_release_frontier_contracts import (
    VALIDATION_RELEASE_FRONTIER_BOUNDARY,
    VALIDATION_RELEASE_FRONTIER_CONTEXT_KEY,
    VALIDATION_RELEASE_FRONTIER_FOREIGN_CONTEXT,
    VALIDATION_RELEASE_FRONTIER_VERSION,
    ValidationReleaseFixture,
    ValidationReleaseOperation,
    ValidationReleaseRecord,
    ValidationReleaseRole,
    ValidationReleaseSourceReceipt,
    ValidationReleaseState,
)

VALIDATION_RELEASE_FRONTIER_SOURCE_COUNT = 5
VALIDATION_RELEASE_FRONTIER_RECORD_COUNT = 16
VALIDATION_RELEASE_FRONTIER_POSITIVE_COUNT = 4
VALIDATION_RELEASE_FRONTIER_CONTROL_COUNT = 12


@dataclass(frozen=True, slots=True)
class ValidationReleaseDataCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseDataAudit:
    fixture_id: str
    checks: tuple[ValidationReleaseDataCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _source(source_id: str, title: str, uri: str, scope: str) -> ValidationReleaseSourceReceipt:
    body = {"source_id": source_id, "title": title, "uri": uri, "scope": scope, "version": "current public portal"}
    return ValidationReleaseSourceReceipt(**body, content_address=content_hash(body))


def _sources() -> tuple[ValidationReleaseSourceReceipt, ...]:
    return (
        _source("ncbi", "NCBI Gene and Genome resources", "https://www.ncbi.nlm.nih.gov/", "public sequence and genome reference"),
        _source("ensembl", "Ensembl genome browser", "https://www.ensembl.org/", "public genome annotation reference"),
        _source("encode", "ENCODE project portal", "https://www.encodeproject.org/", "public regulatory assay reference"),
        _source("addgene", "Addgene plasmid repository", "https://www.addgene.org/", "public construct and protocol reference"),
        _source("gdc", "NCI Genomic Data Commons", "https://gdc.cancer.gov/", "public aggregate disease reference"),
    )


def _record(record_id: str, operation: ValidationReleaseOperation, role: ValidationReleaseRole, payload: Mapping[str, Any], state: ValidationReleaseState, issues: tuple[str, ...], notes: str, source_ids: tuple[str, ...]) -> ValidationReleaseRecord:
    body = {"record_id": record_id, "operation": operation, "role": role, "context_key": VALIDATION_RELEASE_FRONTIER_CONTEXT_KEY, "source_ids": source_ids, "payload": dict(payload), "expected_state": state, "expected_issue_codes": issues, "notes": notes}
    return ValidationReleaseRecord(**body, content_address=content_hash(body))


def _off_target(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {"target_id": "guide-001", "context_key": VALIDATION_RELEASE_FRONTIER_CONTEXT_KEY, "on_target_score": 0.92, "review_threshold": 0.25, "blocking_threshold": 0.60, "off_targets": [{"candidate_id": "alt-001", "score": 0.04, "weight": 1.0}, {"candidate_id": "alt-002", "score": 0.08, "weight": 0.5}]}
    value.update(overrides)
    return value


def _voi(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {"plan_id": "voi-plan-001", "context_key": VALIDATION_RELEASE_FRONTIER_CONTEXT_KEY, "budget": 12.0, "experiments": [{"experiment_id": "exp-baseline", "cost": 4.0, "information_gain": 0.45, "risk_reduction": 0.25, "prerequisites": []}, {"experiment_id": "exp-functional", "cost": 3.0, "information_gain": 0.35, "risk_reduction": 0.25, "prerequisites": ["exp-baseline"]}, {"experiment_id": "exp-replicate", "cost": 3.0, "information_gain": 0.25, "risk_reduction": 0.20, "prerequisites": ["exp-functional"]}]}
    value.update(overrides)
    return value


def _package(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {"package_id": "validation-package-001", "context_key": VALIDATION_RELEASE_FRONTIER_CONTEXT_KEY, "experiments": [{"experiment_id": "exp-baseline", "objective": "reference assay", "readout": "declared signal"}, {"experiment_id": "exp-functional", "objective": "functional follow-up", "readout": "replicate signal"}], "controls": [{"control_id": "ctrl-negative", "type": "negative"}, {"control_id": "ctrl-reference", "type": "reference"}], "protocols": [{"protocol_id": "protocol-aggregate-001", "version": "v1", "source_id": "addgene"}]}
    value.update(overrides)
    return value


def _claim(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {"context_key": VALIDATION_RELEASE_FRONTIER_CONTEXT_KEY, "claims": [{"claim_id": "claim-regulatory-001", "state": "hypothesis", "effect_direction": "increased"}], "results": [{"claim_id": "claim-regulatory-001", "result_id": "result-001", "claim_state": "supported", "effect_direction": "increased", "effect_size": 0.41, "context_key": VALIDATION_RELEASE_FRONTIER_CONTEXT_KEY, "evidence_address": "sha256:evidence-001"}]}
    value.update(overrides)
    return value


def default_validation_release_frontier_fixture() -> ValidationReleaseFixture:
    sources = _sources()
    records = (
        _record("C13-POS-001", ValidationReleaseOperation.OFF_TARGET_RISK, ValidationReleaseRole.POSITIVE, _off_target(), ValidationReleaseState.READY, (), "low weighted off-target burden remains eligible for review planning", ("ncbi", "ensembl", "encode")),
        _record("C13-CTRL-001", ValidationReleaseOperation.OFF_TARGET_RISK, ValidationReleaseRole.CONTROL, _off_target(target_id="guide-high", off_targets=[{"candidate_id": "alt-high", "score": 0.78, "weight": 1.0}]), ValidationReleaseState.BLOCKED, ("off_target_risk_high",), "high maximum burden blocks the target", ("ncbi", "ensembl", "encode")),
        _record("C13-CTRL-002", ValidationReleaseOperation.OFF_TARGET_RISK, ValidationReleaseRole.CONTROL, _off_target(target_id="guide-foreign", context_key=VALIDATION_RELEASE_FRONTIER_FOREIGN_CONTEXT), ValidationReleaseState.BLOCKED, ("context_mismatch",), "foreign context cannot be transported", ("ncbi", "ensembl", "encode")),
        _record("C13-CTRL-003", ValidationReleaseOperation.OFF_TARGET_RISK, ValidationReleaseRole.CONTROL, _off_target(target_id="guide-malformed", off_targets=[{"candidate_id": "alt-bad", "score": "not-a-score", "weight": 1.0}]), ValidationReleaseState.REJECTED, ("invalid_payload",), "malformed score is rejected explicitly", ("ncbi", "ensembl", "encode")),
        _record("C14-POS-001", ValidationReleaseOperation.VALUE_OF_INFORMATION, ValidationReleaseRole.POSITIVE, _voi(), ValidationReleaseState.READY, (), "dependency-safe experiments fit the declared planning budget", ("gdc", "encode")),
        _record("C14-CTRL-001", ValidationReleaseOperation.VALUE_OF_INFORMATION, ValidationReleaseRole.CONTROL, _voi(plan_id="voi-low-budget", budget=2.0), ValidationReleaseState.REVIEW, (), "insufficient budget leaves an explicit review plan", ("gdc", "encode")),
        _record("C14-CTRL-002", ValidationReleaseOperation.VALUE_OF_INFORMATION, ValidationReleaseRole.CONTROL, _voi(plan_id="voi-cycle", experiments=[{"experiment_id": "exp-a", "cost": 2.0, "information_gain": 0.5, "risk_reduction": 0.2, "prerequisites": ["exp-b"]}, {"experiment_id": "exp-b", "cost": 2.0, "information_gain": 0.4, "risk_reduction": 0.2, "prerequisites": ["exp-a"]}]), ValidationReleaseState.BLOCKED, ("prerequisite_cycle",), "cyclic prerequisites cannot be scheduled", ("gdc", "encode")),
        _record("C14-CTRL-003", ValidationReleaseOperation.VALUE_OF_INFORMATION, ValidationReleaseRole.CONTROL, _voi(plan_id="voi-foreign", context_key=VALIDATION_RELEASE_FRONTIER_FOREIGN_CONTEXT), ValidationReleaseState.BLOCKED, ("context_mismatch",), "foreign context cannot enter the plan", ("gdc", "encode")),
        _record("C15-POS-001", ValidationReleaseOperation.EXPERIMENT_PACKAGE, ValidationReleaseRole.POSITIVE, _package(), ValidationReleaseState.PACKAGED, (), "experiment, control, and protocol manifests close with addresses", ("addgene", "encode")),
        _record("C15-CTRL-001", ValidationReleaseOperation.EXPERIMENT_PACKAGE, ValidationReleaseRole.CONTROL, _package(package_id="package-missing", experiments=[]), ValidationReleaseState.REJECTED, ("experiments_missing",), "empty experiment set cannot be packaged", ("addgene", "encode")),
        _record("C15-CTRL-002", ValidationReleaseOperation.EXPERIMENT_PACKAGE, ValidationReleaseRole.CONTROL, _package(package_id="package-duplicate", controls=[{"control_id": "exp-baseline", "type": "collision"}]), ValidationReleaseState.REVIEW, ("duplicate_package_id",), "cross-file identity collision remains reviewable", ("addgene", "encode")),
        _record("C15-CTRL-003", ValidationReleaseOperation.EXPERIMENT_PACKAGE, ValidationReleaseRole.CONTROL, _package(package_id="package-foreign", context_key=VALIDATION_RELEASE_FRONTIER_FOREIGN_CONTEXT), ValidationReleaseState.BLOCKED, ("context_mismatch",), "foreign package context is blocked", ("addgene", "encode")),
        _record("C16-POS-001", ValidationReleaseOperation.CLAIM_UPDATE, ValidationReleaseRole.POSITIVE, _claim(), ValidationReleaseState.UPDATED, (), "known claim receives an exact-context result receipt", ("gdc", "encode")),
        _record("C16-CTRL-001", ValidationReleaseOperation.CLAIM_UPDATE, ValidationReleaseRole.CONTROL, _claim(results=[{"claim_id": "claim-unknown", "result_id": "result-unknown", "claim_state": "supported", "context_key": VALIDATION_RELEASE_FRONTIER_CONTEXT_KEY, "evidence_address": "sha256:evidence-unknown"}]), ValidationReleaseState.REVIEW, ("unknown_claim",), "unknown claim remains review-only", ("gdc", "encode")),
        _record("C16-CTRL-002", ValidationReleaseOperation.CLAIM_UPDATE, ValidationReleaseRole.CONTROL, _claim(results=[{**_claim()["results"][0], "context_key": VALIDATION_RELEASE_FRONTIER_FOREIGN_CONTEXT}]), ValidationReleaseState.BLOCKED, ("context_mismatch",), "foreign result cannot update a claim", ("gdc", "encode")),
        _record("C16-CTRL-003", ValidationReleaseOperation.CLAIM_UPDATE, ValidationReleaseRole.CONTROL, _claim(results=[{key: value for key, value in _claim()["results"][0].items() if key != "evidence_address"}]), ValidationReleaseState.REVIEW, ("evidence_address_missing",), "result without an evidence receipt stays review-only", ("gdc", "encode")),
    )
    body = {"fixture_id": "validation-release-public-aggregate-001", "fixture_version": VALIDATION_RELEASE_FRONTIER_VERSION, "context_key": VALIDATION_RELEASE_FRONTIER_CONTEXT_KEY, "evidence_boundary": VALIDATION_RELEASE_FRONTIER_BOUNDARY, "sources": sources, "records": records}
    return ValidationReleaseFixture(**body, content_address=content_hash(body))


def audit_validation_release_frontier_data(fixture: ValidationReleaseFixture) -> ValidationReleaseDataAudit:
    source_ids = {item.source_id for item in fixture.sources}
    record_ids = tuple(item.record_id for item in fixture.records)
    operation_counts = Counter(item.operation.value for item in fixture.records)
    marker_rows = tuple(item.record_id for item in fixture.records if any(marker in json.dumps(item.payload).lower() for marker in ("patient_id", "sample_id", "api_key", "password", "token")))
    values = (("source-count", len(fixture.sources), VALIDATION_RELEASE_FRONTIER_SOURCE_COUNT, "public provenance receipts"), ("record-count", len(fixture.records), VALIDATION_RELEASE_FRONTIER_RECORD_COUNT, "four records per operation"), ("positive-count", len(fixture.positive_records), VALIDATION_RELEASE_FRONTIER_POSITIVE_COUNT, "one positive per operation"), ("control-count", len(fixture.control_records), VALIDATION_RELEASE_FRONTIER_CONTROL_COUNT, "three controls per operation"), ("unique-record-ids", len(record_ids), len(set(record_ids)), "record IDs are unique"), ("known-sources", all(set(item.source_ids) <= source_ids for item in fixture.records), True, "every row links to a receipt"), ("https-receipts", all(item.uri.startswith("https://") for item in fixture.sources), True, "receipts use HTTPS"), ("exact-context", all(item.context_key == fixture.context_key for item in fixture.records), True, "rows share one context"), ("no-sensitive-markers", marker_rows, (), "no sensitive markers in the public fixture"), ("balanced-operations", sorted(operation_counts.values()), [4, 4, 4, 4], "operations are balanced"))
    checks = []
    for check_id, observed, required, detail in values:
        body = {"check_id": check_id, "passed": observed == required, "observed": observed, "required": required, "detail": detail}
        checks.append(ValidationReleaseDataCheck(**body, content_address=content_hash(body)))
    return ValidationReleaseDataAudit(fixture.fixture_id, tuple(checks), all(item.passed for item in checks), content_hash(tuple(checks)))


def load_validation_release_frontier_fixture(path: str | Path) -> ValidationReleaseFixture:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping) or raw.get("fixture_version") != VALIDATION_RELEASE_FRONTIER_VERSION:
        raise ValueError("validation-release fixture version mismatch")
    expected = default_validation_release_frontier_fixture()
    if raw.get("fixture_id") != expected.fixture_id or raw.get("content_address") != expected.content_address:
        raise ValueError("validation-release fixture identity or address mismatch")
    return expected


def validation_release_frontier_fixture_json(fixture: ValidationReleaseFixture | None = None) -> str:
    return json.dumps(jsonable(fixture or default_validation_release_frontier_fixture()), indent=2, sort_keys=True) + "\n"


__all__ = ["VALIDATION_RELEASE_FRONTIER_CONTROL_COUNT", "VALIDATION_RELEASE_FRONTIER_POSITIVE_COUNT", "VALIDATION_RELEASE_FRONTIER_RECORD_COUNT", "VALIDATION_RELEASE_FRONTIER_SOURCE_COUNT", "ValidationReleaseDataAudit", "ValidationReleaseDataCheck", "audit_validation_release_frontier_data", "default_validation_release_frontier_fixture", "load_validation_release_frontier_fixture", "validation_release_frontier_fixture_json"]
