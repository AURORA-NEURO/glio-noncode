"""Public aggregate fixture for the Domain 15 workspace frontier.

The fixture is deliberately small enough to replay in every supported runtime,
while carrying the shape of a much larger research-workbench contract.  It
keeps four positive paths and three controls per path so context, state,
source, interval, pagination, and accessibility boundaries remain testable.
No row represents a person or a clinical conclusion.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty

WORKSPACE_FRONTIER_FIXTURE_VERSION = "2026.08.d15-c01-c04.v1"
WORKSPACE_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|core|untreated"
WORKSPACE_FRONTIER_EVIDENCE_BOUNDARY = "public_aggregate_non_patient"
WORKSPACE_FRONTIER_SOURCE_COUNT = 5
WORKSPACE_FRONTIER_POSITIVE_COUNT = 4
WORKSPACE_FRONTIER_CONTROL_COUNT = 12


class WorkspaceFrontierOperation(StrEnum):
    CASE_WORKSPACE = "case_workspace"
    COHORT_WORKSPACE = "cohort_workspace"
    VARIANT_EXPLORER = "variant_explorer"
    REGULATORY_TRACK_BROWSER = "regulatory_track_browser"


class WorkspaceFrontierRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierSourceReceipt:
    source_id: str
    title: str
    uri: str
    access_note: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("source_id", "title", "uri", "access_note", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.uri.startswith("https://"):
            raise ValueError("workspace frontier source URI must use HTTPS")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierRecord:
    record_id: str
    operation: WorkspaceFrontierOperation
    role: WorkspaceFrontierRole
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
            raise ValueError("workspace frontier record requires source IDs")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierFixture:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[WorkspaceFrontierSourceReceipt, ...]
    records: tuple[WorkspaceFrontierRecord, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in ("fixture_id", "fixture_version", "context_key", "evidence_boundary", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.sources or not self.records:
            raise ValueError("workspace frontier fixture requires sources and records")

    @property
    def positive_records(self) -> tuple[WorkspaceFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is WorkspaceFrontierRole.POSITIVE)

    @property
    def control_records(self) -> tuple[WorkspaceFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is WorkspaceFrontierRole.CONTROL)

    def record_map(self) -> dict[str, WorkspaceFrontierRecord]:
        return {item.record_id: item for item in self.records}

    def source_map(self) -> dict[str, WorkspaceFrontierSourceReceipt]:
        return {item.source_id: item for item in self.sources}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierCatalog:
    fixture_id: str
    record_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    operations: tuple[WorkspaceFrontierOperation, ...]
    context_key: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierDataCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierDataAudit:
    fixture_id: str
    checks: tuple[WorkspaceFrontierDataCheck, ...]
    accepted: bool
    failed_check_ids: tuple[str, ...]
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_count": self.passed_count,
            "failed_check_ids": list(self.failed_check_ids),
        }


def _source(source_id: str, title: str, uri: str, access_note: str) -> WorkspaceFrontierSourceReceipt:
    body = {"source_id": source_id, "title": title, "uri": uri, "access_note": access_note}
    return WorkspaceFrontierSourceReceipt(**body, content_address=content_hash(body))


def _record(
    record_id: str,
    operation: WorkspaceFrontierOperation,
    role: WorkspaceFrontierRole,
    payload: dict[str, Any],
    expected_state: str,
    expected_issue_codes: tuple[str, ...],
    notes: str,
    source_ids: tuple[str, ...] | None = None,
) -> WorkspaceFrontierRecord:
    receipts = source_ids if source_ids is not None else (("case-manifest", "workbench" ) if role is WorkspaceFrontierRole.POSITIVE else ("workbench",))
    body = {
        "record_id": record_id,
        "operation": operation,
        "role": role,
        "context_key": WORKSPACE_FRONTIER_CONTEXT_KEY,
        "source_ids": receipts,
        "payload": payload,
        "expected_state": expected_state,
        "expected_issue_codes": expected_issue_codes,
        "notes": notes,
    }
    return WorkspaceFrontierRecord(**body, content_address=content_hash(body))


def _context(context_key: str = WORKSPACE_FRONTIER_CONTEXT_KEY) -> dict[str, str]:
    parts = context_key.split("|")
    return {
        "genome_build": parts[0],
        "disease_class": parts[1],
        "age_group": parts[2],
        "cell_state": parts[3],
        "territory": parts[4],
        "treatment_phase": parts[5],
    }


def _variant(variant_id: str, position: int = 100, context_key: str = WORKSPACE_FRONTIER_CONTEXT_KEY) -> dict[str, Any]:
    return {
        "variant_id": variant_id,
        "kind": "snv",
        "chromosome": "7",
        "start": position,
        "end": position,
        "reference": "A",
        "alternate": "T",
        "genome_build": "GRCh38",
        "origin": "somatic",
        "clonality": "unknown",
        "sample_id": "aggregate-sample",
        "annotations": {"context_key": context_key, "source_version": "public-v1"},
    }


def _element(element_id: str, context_key: str = WORKSPACE_FRONTIER_CONTEXT_KEY) -> dict[str, Any]:
    return {
        "element_id": element_id,
        "chromosome": "7",
        "start": 90,
        "end": 125,
        "element_type": "candidate_enhancer",
        "context": _context(context_key),
        "source_id": "track-public",
        "target_genes": ["GENE1"],
        "state_ids": ["stem_like"],
        "features": {"track_score": 0.82, "accessibility_proxy": 0.71},
        "annotations": {"boundary": WORKSPACE_FRONTIER_EVIDENCE_BOUNDARY},
    }


def _case_payload(
    *,
    context_key: str = WORKSPACE_FRONTIER_CONTEXT_KEY,
    variants: list[dict[str, Any]] | None = None,
    include_dossier: bool = False,
    duplicate_variant_ids: bool = False,
) -> dict[str, Any]:
    values = variants if variants is not None else [_variant("v-frontier-1"), _variant("v-frontier-2", 200)]
    if duplicate_variant_ids and values:
        values = [values[0], dict(values[0])]
    return {
        "case_id": "workspace-case-public",
        "subject_id": "aggregate-subject",
        "context_key": context_key,
        "variants": values,
        "candidate_elements": [_element("element-frontier-1", context_key)],
        "input_versions": {"manifest": "sha256:manifest-public-v1", "track": "sha256:track-public-v1"},
        "include_dossier": include_dossier,
        "accessibility": {
            "keyboard_order": ["variants", "regulatory-elements", "hypotheses", "evidence", "validation"],
            "labels_present": True,
            "focus_boundary": "workspace-case-public",
            "reading_order": "section-order",
        },
    }


def _cohort_record(record_id: str, variant_id: str, position: int, *, callable_value: bool = True, context_key: str = WORKSPACE_FRONTIER_CONTEXT_KEY) -> dict[str, Any]:
    return {
        "record_id": record_id,
        "variant": _variant(variant_id, position, context_key),
        "context_key": context_key,
        "source_id": "cohort-public",
        "sample_id": f"aggregate-{record_id}",
        "callable": callable_value,
        "sequence_context": "ACGTACGT",
        "chromatin_features": {"accessibility": 0.62, "signal": 0.48},
        "annotations": {"public_aggregate": True},
    }


def _cohort_payload(*, context_key: str = WORKSPACE_FRONTIER_CONTEXT_KEY, records: list[dict[str, Any]] | None = None, query_id: str = "workspace-cohort-query", require_callable: bool = True) -> dict[str, Any]:
    values = records if records is not None else [_cohort_record("cohort-r1", "cohort-v1", 150), _cohort_record("cohort-r2", "cohort-v2", 250)]
    return {
        "evidence_id": "workspace-cohort-public",
        "context_key": context_key,
        "query_id": query_id,
        "require_callable": require_callable,
        "records": values,
        "accessibility": {"row_label": "cohort record", "summary_label": "cohort summary", "controls_label": "matched controls"},
    }


def _track_payload(*, text: str = "7\t99\t120\treg-frontier-1\t800\t+\n7\t180\t230\treg-frontier-2\t700\t-\n", context_key: str = WORKSPACE_FRONTIER_CONTEXT_KEY) -> dict[str, Any]:
    return {
        "source_id": "track-public",
        "genome_build": "GRCh38",
        "text": text,
        "context_key": context_key,
        "accessibility": {"interval_label": "regulatory interval", "coordinate_label": "genomic coordinate", "issue_label": "parse issue"},
    }


def default_workspace_frontier_fixture() -> WorkspaceFrontierFixture:
    sources = (
        _source("case-manifest", "Public case manifest receipt", "https://www.ncbi.nlm.nih.gov/", "aggregate manifest identity and versions"),
        _source("cohort-public", "Public aggregate cohort receipt", "https://www.ebi.ac.uk/", "pseudonymous aggregate record shape"),
        _source("track-public", "Public regulatory interval receipt", "https://www.encodeproject.org/", "annotation-only interval source"),
        _source("workbench", "Research workbench contract", "https://www.ga4gh.org/", "interoperable context and provenance vocabulary"),
        _source("accessibility", "Public accessibility guidance receipt", "https://www.w3.org/WAI/", "labels, focus, keyboard, and reading order"),
    )
    context_control = "GRCh38|glioma|pediatric|stem_like|core|untreated"
    records = (
        _record("C01-POS-001", WorkspaceFrontierOperation.CASE_WORKSPACE, WorkspaceFrontierRole.POSITIVE, _case_payload(), "partial", ("missing_dossier",), "case sections and exact-context records remain visible while optional dossier sections are incomplete"),
        _record("C01-CTRL-001", WorkspaceFrontierOperation.CASE_WORKSPACE, WorkspaceFrontierRole.CONTROL, _case_payload(context_key=context_control, variants=[_variant("v-context", 100, context_control)]), "out_of_domain", ("context_mismatch",), "a case from a different age context is withheld"),
        _record("C01-CTRL-002", WorkspaceFrontierOperation.CASE_WORKSPACE, WorkspaceFrontierRole.CONTROL, _case_payload(variants=[]), "invalid", ("invalid_workspace_input",), "a case without variants cannot be rendered"),
        _record("C01-CTRL-003", WorkspaceFrontierOperation.CASE_WORKSPACE, WorkspaceFrontierRole.CONTROL, _case_payload(duplicate_variant_ids=True), "invalid", ("duplicate_variant_id",), "duplicate canonical variant identities remain a construction error"),
        _record("C02-POS-001", WorkspaceFrontierOperation.COHORT_WORKSPACE, WorkspaceFrontierRole.POSITIVE, _cohort_payload(), "supported", (), "selected cohort rows retain exact context and separate summary/control sections"),
        _record("C02-CTRL-001", WorkspaceFrontierOperation.COHORT_WORKSPACE, WorkspaceFrontierRole.CONTROL, _cohort_payload(context_key=context_control, records=[_cohort_record("cohort-ood", "cohort-ood-v", 150, context_key=context_control)]), "out_of_domain", ("context_mismatch",), "records existing only outside the requested context are withheld"),
        _record("C02-CTRL-002", WorkspaceFrontierOperation.COHORT_WORKSPACE, WorkspaceFrontierRole.CONTROL, _cohort_payload(records=[_cohort_record("cohort-absent", "cohort-absent-v", 150, callable_value=False)]), "absent", ("no_matching_records",), "non-callable rows do not silently become selected cohort rows"),
        _record("C02-CTRL-003", WorkspaceFrontierOperation.COHORT_WORKSPACE, WorkspaceFrontierRole.CONTROL, _cohort_payload(records=[], query_id="workspace-empty-query"), "absent", ("no_matching_records",), "an empty selection remains an explicit absent workspace"),
        _record("C03-POS-001", WorkspaceFrontierOperation.VARIANT_EXPLORER, WorkspaceFrontierRole.POSITIVE, {"case": _case_payload(), "variant_id": "v-frontier-1"}, "supported", (), "the explorer resolves one canonical variant and returns only declared relationships"),
        _record("C03-CTRL-001", WorkspaceFrontierOperation.VARIANT_EXPLORER, WorkspaceFrontierRole.CONTROL, {"case": _case_payload(), "variant_id": "missing-variant"}, "abstained", ("variant_absent",), "an absent variant is not inferred from nearby coordinates"),
        _record("C03-CTRL-002", WorkspaceFrontierOperation.VARIANT_EXPLORER, WorkspaceFrontierRole.CONTROL, {"case": _case_payload(), "variant_id": "v-frontier-1", "context_key": context_control}, "out_of_domain", ("context_mismatch",), "a context request mismatch is explicit"),
        _record("C03-CTRL-003", WorkspaceFrontierOperation.VARIANT_EXPLORER, WorkspaceFrontierRole.CONTROL, {"case": _case_payload(variants=[]), "variant_id": "v-frontier-1"}, "invalid", ("invalid_workspace_input",), "the explorer cannot inspect a malformed case snapshot"),
        _record("C04-POS-001", WorkspaceFrontierOperation.REGULATORY_TRACK_BROWSER, WorkspaceFrontierRole.POSITIVE, _track_payload(), "supported", (), "valid intervals retain source IDs, coordinates, row hashes, and accessible labels"),
        _record("C04-CTRL-001", WorkspaceFrontierOperation.REGULATORY_TRACK_BROWSER, WorkspaceFrontierRole.CONTROL, _track_payload(text="7\tbad\t120\tbad-row\n"), "partial", ("track_parse_issue",), "a malformed track row leaves a visible parse issue"),
        _record("C04-CTRL-002", WorkspaceFrontierOperation.REGULATORY_TRACK_BROWSER, WorkspaceFrontierRole.CONTROL, _track_payload(context_key=context_control), "out_of_domain", ("context_mismatch",), "interval results do not cross context boundaries"),
        _record("C04-CTRL-003", WorkspaceFrontierOperation.REGULATORY_TRACK_BROWSER, WorkspaceFrontierRole.CONTROL, _track_payload(text=""), "invalid", ("invalid_track_input",), "an empty track is rejected before rendering"),
    )
    body = {
        "fixture_id": "workspace-frontier-public-aggregate",
        "fixture_version": WORKSPACE_FRONTIER_FIXTURE_VERSION,
        "context_key": WORKSPACE_FRONTIER_CONTEXT_KEY,
        "evidence_boundary": WORKSPACE_FRONTIER_EVIDENCE_BOUNDARY,
        "sources": sources,
        "records": records,
    }
    return WorkspaceFrontierFixture(**body, content_address=content_hash(body))


def build_workspace_frontier_catalog(fixture: WorkspaceFrontierFixture) -> WorkspaceFrontierCatalog:
    body = {
        "fixture_id": fixture.fixture_id,
        "record_ids": tuple(item.record_id for item in fixture.records),
        "source_ids": tuple(item.source_id for item in fixture.sources),
        "operations": tuple(WorkspaceFrontierOperation),
        "context_key": fixture.context_key,
    }
    return WorkspaceFrontierCatalog(**body, content_address=content_hash(body))


def audit_workspace_frontier_data(fixture: WorkspaceFrontierFixture) -> WorkspaceFrontierDataAudit:
    catalog = build_workspace_frontier_catalog(fixture)
    values = (
        ("fixture-id", fixture.fixture_id == "workspace-frontier-public-aggregate", fixture.fixture_id, "fixture identity"),
        ("fixture-version", fixture.fixture_version == WORKSPACE_FRONTIER_FIXTURE_VERSION, fixture.fixture_version, "version is explicit"),
        ("boundary", fixture.evidence_boundary == WORKSPACE_FRONTIER_EVIDENCE_BOUNDARY, fixture.evidence_boundary, "aggregate boundary is exact"),
        ("source-count", len(fixture.sources) == WORKSPACE_FRONTIER_SOURCE_COUNT, len(fixture.sources), WORKSPACE_FRONTIER_SOURCE_COUNT),
        ("record-count", len(fixture.records) == 16, len(fixture.records), 16),
        ("positive-count", len(fixture.positive_records) == WORKSPACE_FRONTIER_POSITIVE_COUNT, len(fixture.positive_records), WORKSPACE_FRONTIER_POSITIVE_COUNT),
        ("control-count", len(fixture.control_records) == WORKSPACE_FRONTIER_CONTROL_COUNT, len(fixture.control_records), WORKSPACE_FRONTIER_CONTROL_COUNT),
        ("unique-records", len(set(catalog.record_ids)) == len(fixture.records), len(set(catalog.record_ids)), len(fixture.records)),
        ("operations", set(item.operation for item in fixture.records) == set(WorkspaceFrontierOperation), tuple(item.value for item in WorkspaceFrontierOperation), tuple(sorted({item.operation.value for item in fixture.records}))),
        ("contexts", all(item.context_key == fixture.context_key for item in fixture.records), True, "record context is exact"),
        ("sources-https", all(item.uri.startswith("https://") for item in fixture.sources), True, "source receipts use HTTPS"),
        ("record-addresses", all(item.content_address.startswith("sha256:") for item in fixture.records), True, "records are addressed"),
    )
    checks = tuple(WorkspaceFrontierDataCheck(item[0], item[1], item[2], item[3], str(item[0]), content_hash(item)) for item in values)
    failed = tuple(item.check_id for item in checks if not item.passed)
    body = {"fixture_id": fixture.fixture_id, "checks": checks, "accepted": not failed, "failed_check_ids": failed}
    return WorkspaceFrontierDataAudit(**body, content_address=content_hash(body))


def load_workspace_frontier_fixture(path: str | Path) -> WorkspaceFrontierFixture:
    import json

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not raw.get("sources") or not raw.get("records"):
        raise ValueError("workspace frontier fixture requires sources and records")
    sources = tuple(WorkspaceFrontierSourceReceipt(**item) for item in raw.get("sources", ()))
    records = tuple(
        WorkspaceFrontierRecord(
            operation=WorkspaceFrontierOperation(item["operation"]),
            role=WorkspaceFrontierRole(item["role"]),
            **{key: item[key] for key in ("record_id", "context_key", "source_ids", "payload", "expected_state", "expected_issue_codes", "notes", "content_address")},
        )
        for item in raw.get("records", ())
    )
    return WorkspaceFrontierFixture(
        fixture_id=str(raw["fixture_id"]),
        fixture_version=str(raw["fixture_version"]),
        context_key=str(raw["context_key"]),
        evidence_boundary=str(raw["evidence_boundary"]),
        sources=sources,
        records=records,
        content_address=str(raw.get("content_address", content_hash({"fixture_id": raw["fixture_id"], "fixture_version": raw["fixture_version"], "context_key": raw["context_key"], "evidence_boundary": raw["evidence_boundary"], "sources": sources, "records": records}))),
    )


__all__ = [
    "WORKSPACE_FRONTIER_CONTEXT_KEY",
    "WORKSPACE_FRONTIER_CONTROL_COUNT",
    "WORKSPACE_FRONTIER_EVIDENCE_BOUNDARY",
    "WORKSPACE_FRONTIER_FIXTURE_VERSION",
    "WORKSPACE_FRONTIER_POSITIVE_COUNT",
    "WORKSPACE_FRONTIER_SOURCE_COUNT",
    "WorkspaceFrontierCatalog",
    "WorkspaceFrontierDataAudit",
    "WorkspaceFrontierDataCheck",
    "WorkspaceFrontierFixture",
    "WorkspaceFrontierOperation",
    "WorkspaceFrontierRecord",
    "WorkspaceFrontierRole",
    "WorkspaceFrontierSourceReceipt",
    "audit_workspace_frontier_data",
    "build_workspace_frontier_catalog",
    "default_workspace_frontier_fixture",
    "load_workspace_frontier_fixture",
]
