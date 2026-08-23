"""Public aggregate source receipts and deterministic workbench scenarios."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .serialization import content_hash, jsonable
from .workbench_release_frontier_contracts import WORKBENCH_RELEASE_FRONTIER_BOUNDARY, WORKBENCH_RELEASE_FRONTIER_CONTEXT_KEY, WORKBENCH_RELEASE_FRONTIER_FOREIGN_CONTEXT, WORKBENCH_RELEASE_FRONTIER_VERSION, WorkbenchReleaseFixture, WorkbenchReleaseOperation, WorkbenchReleaseRecord, WorkbenchReleaseRole, WorkbenchReleaseSourceReceipt, WorkbenchReleaseState

WORKBENCH_RELEASE_FRONTIER_SOURCE_COUNT = 5
WORKBENCH_RELEASE_FRONTIER_RECORD_COUNT = 16
WORKBENCH_RELEASE_FRONTIER_POSITIVE_COUNT = 4
WORKBENCH_RELEASE_FRONTIER_CONTROL_COUNT = 12


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseDataCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseDataAudit:
    fixture_id: str
    checks: tuple[WorkbenchReleaseDataCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _source(source_id: str, title: str, uri: str, scope: str) -> WorkbenchReleaseSourceReceipt:
    body = {"source_id": source_id, "title": title, "uri": uri, "scope": scope, "version": "public portal receipt"}
    return WorkbenchReleaseSourceReceipt(**body, content_address=content_hash(body))


def _sources() -> tuple[WorkbenchReleaseSourceReceipt, ...]:
    return (
        _source("europepmc", "Europe PMC literature service", "https://europepmc.org/", "public literature and citation index"),
        _source("pubmed", "PubMed biomedical literature", "https://pubmed.ncbi.nlm.nih.gov/", "public indexed article metadata"),
        _source("gdc", "NCI Genomic Data Commons", "https://gdc.cancer.gov/", "public aggregate disease and genomic reference"),
        _source("encode", "ENCODE project portal", "https://www.encodeproject.org/", "public functional assay reference"),
        _source("ga4gh", "Global Alliance for Genomics and Health", "https://www.ga4gh.org/", "public interoperability and data-use reference"),
    )


def _record(record_id: str, capability: str, operation: WorkbenchReleaseOperation, role: WorkbenchReleaseRole, payload: Mapping[str, Any], state: WorkbenchReleaseState, issues: tuple[str, ...], notes: str, source_ids: tuple[str, ...]) -> WorkbenchReleaseRecord:
    context = payload.get("context_key") if isinstance(payload.get("context_key"), str) else WORKBENCH_RELEASE_FRONTIER_CONTEXT_KEY
    body = {"record_id": record_id, "capability": capability, "operation": operation, "role": role, "context_key": context, "source_ids": source_ids, "payload": dict(payload), "expected_state": state, "expected_issue_codes": issues, "notes": notes}
    return WorkbenchReleaseRecord(**body, content_address=content_hash(body))


def _review(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {"form_id": "review-form-001", "reviewer_id": "reviewer-a", "context_key": WORKBENCH_RELEASE_FRONTIER_CONTEXT_KEY, "schema": [{"field_id": "decision", "label": "Decision", "required": True, "choices": ["accept", "review"]}, {"field_id": "rationale", "label": "Rationale", "required": True}], "response": {"decision": "accept", "rationale": "aggregate receipt reviewed"}}
    value.update(overrides)
    return value


def _report(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {"report_id": "report-001", "context_key": WORKBENCH_RELEASE_FRONTIER_CONTEXT_KEY, "format": "markdown", "sections": [{"section_id": "summary", "title": "Summary", "order": 2, "content": {"scope": "aggregate"}}, {"section_id": "evidence", "title": "Evidence", "order": 1, "content": {"source_count": 5}}]}
    value.update(overrides)
    return value


def _search(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {"query": "EGFR", "context_key": WORKBENCH_RELEASE_FRONTIER_CONTEXT_KEY, "records": [{"record_id": "claim-egfr", "record_type": "claim", "title": "EGFR regulatory evidence", "context_key": WORKBENCH_RELEASE_FRONTIER_CONTEXT_KEY, "source": "europepmc"}, {"record_id": "claim-idh", "record_type": "claim", "title": "IDH context", "context_key": WORKBENCH_RELEASE_FRONTIER_CONTEXT_KEY, "source": "gdc"}], "commands": ["open-claim", "publish-report"], "maximum_results": 10}
    value.update(overrides)
    return value


def _accessibility(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {"surface_id": "review-panel", "context_key": WORKBENCH_RELEASE_FRONTIER_CONTEXT_KEY, "surface": {"keyboard": True, "label": True, "focus_order": True, "contrast": True, "motion": True, "reading_order": True}, "required_criteria": ["keyboard", "label", "focus_order", "contrast", "motion", "reading_order"]}
    value.update(overrides)
    return value


def default_workbench_release_frontier_fixture() -> WorkbenchReleaseFixture:
    records = (
        _record("D15-C13-POS-001", "structured-review-form", WorkbenchReleaseOperation.REVIEW_FORM, WorkbenchReleaseRole.POSITIVE, _review(), WorkbenchReleaseState.REVIEWED, (), "required review fields and declared choices are complete", ("europepmc", "gdc")),
        _record("D15-C13-CTRL-001", "structured-review-form", WorkbenchReleaseOperation.REVIEW_FORM, WorkbenchReleaseRole.CONTROL, _review(response={"decision": "accept"}), WorkbenchReleaseState.REVIEW, ("required_field_missing",), "missing rationale remains review-only", ("europepmc", "gdc")),
        _record("D15-C13-CTRL-002", "structured-review-form", WorkbenchReleaseOperation.REVIEW_FORM, WorkbenchReleaseRole.CONTROL, _review(response={"decision": "publish", "rationale": "not in choices"}), WorkbenchReleaseState.REVIEW, ("value_not_in_declared_choices",), "an undeclared choice is review-only", ("europepmc", "gdc")),
        _record("D15-C13-CTRL-003", "structured-review-form", WorkbenchReleaseOperation.REVIEW_FORM, WorkbenchReleaseRole.CONTROL, _review(context_key=WORKBENCH_RELEASE_FRONTIER_FOREIGN_CONTEXT), WorkbenchReleaseState.BLOCKED, ("context_mismatch",), "foreign review context is blocked", ("europepmc", "gdc")),
        _record("D15-C14-POS-001", "report-export", WorkbenchReleaseOperation.REPORT_EXPORT, WorkbenchReleaseRole.POSITIVE, _report(), WorkbenchReleaseState.EXPORTED, (), "ordered markdown sections receive content addresses", ("pubmed", "encode")),
        _record("D15-C14-CTRL-001", "report-export", WorkbenchReleaseOperation.REPORT_EXPORT, WorkbenchReleaseRole.CONTROL, _report(sections=[]), WorkbenchReleaseState.REVIEW, ("sections_missing",), "empty reports remain review-only", ("pubmed", "encode")),
        _record("D15-C14-CTRL-002", "report-export", WorkbenchReleaseOperation.REPORT_EXPORT, WorkbenchReleaseRole.CONTROL, _report(sections=[_report()["sections"][0], {**_report()["sections"][1], "section_id": "summary"}]), WorkbenchReleaseState.REVIEW, ("duplicate_section_id",), "duplicate section identity is review-only", ("pubmed", "encode")),
        _record("D15-C14-CTRL-003", "report-export", WorkbenchReleaseOperation.REPORT_EXPORT, WorkbenchReleaseRole.CONTROL, _report(context_key=WORKBENCH_RELEASE_FRONTIER_FOREIGN_CONTEXT), WorkbenchReleaseState.BLOCKED, ("context_mismatch",), "foreign report context is blocked", ("pubmed", "encode")),
        _record("D15-C15-POS-001", "global-search-palette", WorkbenchReleaseOperation.SEARCH_PALETTE, WorkbenchReleaseRole.POSITIVE, _search(), WorkbenchReleaseState.SEARCHED, (), "search returns deterministic record and command matches", ("europepmc", "gdc", "ga4gh")),
        _record("D15-C15-CTRL-001", "global-search-palette", WorkbenchReleaseOperation.SEARCH_PALETTE, WorkbenchReleaseRole.CONTROL, _search(query="not-present"), WorkbenchReleaseState.REVIEW, ("no_matches",), "no results remain an explicit review state", ("europepmc", "gdc", "ga4gh")),
        _record("D15-C15-CTRL-002", "global-search-palette", WorkbenchReleaseOperation.SEARCH_PALETTE, WorkbenchReleaseRole.CONTROL, _search(context_key=WORKBENCH_RELEASE_FRONTIER_FOREIGN_CONTEXT), WorkbenchReleaseState.BLOCKED, ("context_mismatch",), "foreign search context is blocked", ("europepmc", "gdc", "ga4gh")),
        _record("D15-C15-CTRL-003", "global-search-palette", WorkbenchReleaseOperation.SEARCH_PALETTE, WorkbenchReleaseRole.CONTROL, _search(records=[{"title": "missing record id"}]), WorkbenchReleaseState.REJECTED, ("invalid_payload",), "records without stable identity are rejected", ("europepmc", "gdc", "ga4gh")),
        _record("D15-C16-POS-001", "accessibility-human-factors", WorkbenchReleaseOperation.ACCESSIBILITY, WorkbenchReleaseRole.POSITIVE, _accessibility(), WorkbenchReleaseState.PASSED, (), "all declared review-surface criteria pass", ("encode", "ga4gh")),
        _record("D15-C16-CTRL-001", "accessibility-human-factors", WorkbenchReleaseOperation.ACCESSIBILITY, WorkbenchReleaseRole.CONTROL, _accessibility(surface={**_accessibility()["surface"], "contrast": False}), WorkbenchReleaseState.REVIEW, ("criterion_failed",), "a failed contrast criterion requires remediation", ("encode", "ga4gh")),
        _record("D15-C16-CTRL-002", "accessibility-human-factors", WorkbenchReleaseOperation.ACCESSIBILITY, WorkbenchReleaseRole.CONTROL, _accessibility(context_key=WORKBENCH_RELEASE_FRONTIER_FOREIGN_CONTEXT), WorkbenchReleaseState.BLOCKED, ("context_mismatch",), "foreign accessibility context is blocked", ("encode", "ga4gh")),
        _record("D15-C16-CTRL-003", "accessibility-human-factors", WorkbenchReleaseOperation.ACCESSIBILITY, WorkbenchReleaseRole.CONTROL, _accessibility(surface={"keyboard": True}), WorkbenchReleaseState.REVIEW, ("criterion_failed",), "partial criterion coverage remains review-only", ("encode", "ga4gh")),
    )
    body = {"fixture_id": "workbench-release-public-aggregate-001", "fixture_version": WORKBENCH_RELEASE_FRONTIER_VERSION, "context_key": WORKBENCH_RELEASE_FRONTIER_CONTEXT_KEY, "evidence_boundary": WORKBENCH_RELEASE_FRONTIER_BOUNDARY, "sources": _sources(), "records": records}
    return WorkbenchReleaseFixture(**body, content_address=content_hash(body))


def audit_workbench_release_frontier_data(fixture: WorkbenchReleaseFixture) -> WorkbenchReleaseDataAudit:
    source_ids = {source.source_id for source in fixture.sources}
    record_ids = tuple(record.record_id for record in fixture.records)
    operation_counts = Counter(record.operation.value for record in fixture.records)
    marker_rows = tuple(record.record_id for record in fixture.records if any(marker in json.dumps(record.payload).lower() for marker in ("api_key", "password", "patient_id", "sample_id", "access_token")))
    values = (
        ("source-count", len(fixture.sources), WORKBENCH_RELEASE_FRONTIER_SOURCE_COUNT, "public source receipts"),
        ("record-count", len(fixture.records), WORKBENCH_RELEASE_FRONTIER_RECORD_COUNT, "four rows per capability"),
        ("positive-count", len(fixture.positive_records), WORKBENCH_RELEASE_FRONTIER_POSITIVE_COUNT, "one positive per operation"),
        ("control-count", len(fixture.control_records), WORKBENCH_RELEASE_FRONTIER_CONTROL_COUNT, "three controls per operation"),
        ("unique-record-ids", len(record_ids), len(set(record_ids)), "record identities are unique"),
        ("known-sources", all(set(record.source_ids) <= source_ids for record in fixture.records), True, "rows resolve to source receipts"),
        ("https-receipts", all(source.uri.startswith("https://") for source in fixture.sources), True, "receipts use HTTPS"),
        ("no-private-markers", marker_rows, (), "fixture contains no private markers"),
        ("balanced-operations", sorted(operation_counts.values()), [4, 4, 4, 4], "operations are balanced"),
        ("fixture-context", fixture.context_key == WORKBENCH_RELEASE_FRONTIER_CONTEXT_KEY, True, "fixture context is exact"),
    )
    checks = []
    for check_id, observed, required, detail in values:
        body = {"check_id": check_id, "passed": observed == required, "observed": observed, "required": required, "detail": detail}
        checks.append(WorkbenchReleaseDataCheck(**body, content_address=content_hash(body)))
    return WorkbenchReleaseDataAudit(fixture.fixture_id, tuple(checks), all(check.passed for check in checks), content_hash(tuple(checks)))


def load_workbench_release_frontier_fixture(path: str | Path) -> WorkbenchReleaseFixture:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping) or raw.get("fixture_version") != WORKBENCH_RELEASE_FRONTIER_VERSION:
        raise ValueError("workbench fixture version mismatch")
    expected = default_workbench_release_frontier_fixture()
    if raw.get("fixture_id") != expected.fixture_id or raw.get("content_address") != expected.content_address:
        raise ValueError("workbench fixture identity or address mismatch")
    return expected


def workbench_release_frontier_fixture_json(fixture: WorkbenchReleaseFixture | None = None) -> str:
    return json.dumps(jsonable(fixture or default_workbench_release_frontier_fixture()), indent=2, sort_keys=True) + "\n"


__all__ = ["WORKBENCH_RELEASE_FRONTIER_CONTROL_COUNT", "WORKBENCH_RELEASE_FRONTIER_POSITIVE_COUNT", "WORKBENCH_RELEASE_FRONTIER_RECORD_COUNT", "WORKBENCH_RELEASE_FRONTIER_SOURCE_COUNT", "WorkbenchReleaseDataAudit", "WorkbenchReleaseDataCheck", "audit_workbench_release_frontier_data", "default_workbench_release_frontier_fixture", "load_workbench_release_frontier_fixture", "workbench_release_frontier_fixture_json"]
