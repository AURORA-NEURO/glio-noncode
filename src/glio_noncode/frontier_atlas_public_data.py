"""Public aggregate fixture for Domain 05 C13-C16.

The fixture exercises the four existing frontier adapters at their public-data
boundary. Rows are compact aggregate examples shaped after official ENCODE
Hi-C/SCREEN contracts and NCI context vocabulary. They are not claimed to be
verbatim rows from an upstream release and contain no subject-level data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

FRONTIER_ATLAS_FIXTURE_VERSION = "2026.08.d05-c13-c16.v1"
FRONTIER_ATLAS_CONTEXT_KEY = "GRCh38|diffuse_glioma|adult|stem_like|core|untreated"
FRONTIER_ATLAS_EVIDENCE_BOUNDARY = "public_aggregate_non_patient"
FRONTIER_ATLAS_POSITIVE_COUNT = 4
FRONTIER_ATLAS_CONTROL_COUNT = 12
FRONTIER_ATLAS_SOURCE_COUNT = 5


class FrontierAtlasOperation(StrEnum):
    """Executable C13-C16 operation families."""

    BOUNDARY_ATLAS = "insulator_boundary_atlas"
    HOTSPOT_ATLAS = "regulatory_hotspot_atlas"
    EVIDENCE_TIER = "atlas_evidence_tier_adjudication"
    SNAPSHOT_PUBLISH = "atlas_snapshot_publish"


class FrontierAtlasRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class FrontierAtlasSourceReceipt:
    """Public source identity and scope receipt."""

    source_id: str
    title: str
    uri: str
    source_kind: str
    release: str
    accessed_on: str
    license: str
    scope: str
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "source_id",
            "title",
            "uri",
            "source_kind",
            "release",
            "accessed_on",
            "license",
            "scope",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.uri.startswith("https://"):
            raise ValidationError("frontier atlas source URI must use HTTPS")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierAtlasRecord:
    """One adapter payload with expected state and issue floors."""

    record_id: str
    operation: FrontierAtlasOperation
    role: FrontierAtlasRole
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
            raise ValidationError("frontier atlas records require sources and payload")
        if not isinstance(self.operation, FrontierAtlasOperation):
            raise ValidationError("frontier atlas operation must be declared")
        if not isinstance(self.role, FrontierAtlasRole):
            raise ValidationError("frontier atlas role must be declared")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierAtlasFixture:
    """Versioned balanced fixture for C13-C16."""

    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[FrontierAtlasSourceReceipt, ...]
    records: tuple[FrontierAtlasRecord, ...]
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
        if self.evidence_boundary != FRONTIER_ATLAS_EVIDENCE_BOUNDARY:
            raise ValidationError("unsupported frontier atlas evidence boundary")
        if not self.sources or not self.records:
            raise ValidationError("frontier atlas fixture requires sources and records")

    @property
    def positive_records(self) -> tuple[FrontierAtlasRecord, ...]:
        return tuple(record for record in self.records if record.role is FrontierAtlasRole.POSITIVE)

    @property
    def control_records(self) -> tuple[FrontierAtlasRecord, ...]:
        return tuple(record for record in self.records if record.role is FrontierAtlasRole.CONTROL)

    def source_map(self) -> dict[str, FrontierAtlasSourceReceipt]:
        return {source.source_id: source for source in self.sources}

    def record_map(self) -> dict[str, FrontierAtlasRecord]:
        return {record.record_id: record for record in self.records}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierAtlasCatalog:
    fixture: FrontierAtlasFixture
    source_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    operations: tuple[FrontierAtlasOperation, ...]
    content_address: str

    def __post_init__(self) -> None:
        if len(set(self.source_ids)) != len(self.source_ids) or len(set(self.record_ids)) != len(
            self.record_ids
        ):
            raise ValidationError("frontier atlas catalog identifiers must be unique")
        if set(self.operations) != set(FrontierAtlasOperation):
            raise ValidationError("frontier atlas catalog must cover all operations")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierAtlasDataCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierAtlasDataAudit:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    checks: tuple[FrontierAtlasDataCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_check_ids": list(self.failed_check_ids),
        }


def _address(body: Any) -> str:
    return content_hash(body)


def _source(
    source_id: str, title: str, uri: str, source_kind: str, release: str, scope: str
) -> FrontierAtlasSourceReceipt:
    body = {
        "source_id": source_id,
        "title": title,
        "uri": uri,
        "source_kind": source_kind,
        "release": release,
        "accessed_on": "2026-08-21",
        "license": "public portal terms",
        "scope": scope,
    }
    return FrontierAtlasSourceReceipt(**body, content_address=_address(body))


def _record(
    record_id: str,
    operation: FrontierAtlasOperation,
    role: FrontierAtlasRole,
    payload: dict[str, Any],
    expected_state: str,
    expected_issue_codes: tuple[str, ...],
    source_ids: tuple[str, ...],
    description: str,
    *,
    context_key: str = FRONTIER_ATLAS_CONTEXT_KEY,
) -> FrontierAtlasRecord:
    body = {
        "record_id": record_id,
        "operation": operation,
        "role": role,
        "context_key": context_key,
        "source_ids": source_ids,
        "payload": payload,
        "expected_state": expected_state,
        "expected_issue_codes": expected_issue_codes,
        "description": description,
    }
    return FrontierAtlasRecord(**body, content_address=_address(body))


def _json_rows(rows: list[dict[str, Any]]) -> str:
    return json.dumps({"records": rows}, sort_keys=True)


def _boundary_rows(mode: str) -> str:
    context = FRONTIER_ATLAS_CONTEXT_KEY
    if mode == "positive":
        rows = [
            {
                "boundary_id": "boundary-egfr",
                "chromosome": "chr7",
                "start": 100,
                "end": 120,
                "insulation_score": 0.82,
                "boundary_support": 0.91,
                "orientation": "convergent",
                "context_key": context,
            }
        ]
    elif mode == "low-support":
        rows = [
            {
                "boundary_id": "boundary-low",
                "chromosome": "chr7",
                "start": 100,
                "end": 120,
                "insulation_score": 0.42,
                "boundary_support": 0.2,
                "orientation": "convergent",
                "context_key": context,
            }
        ]
    elif mode == "invalid":
        rows = [
            {
                "boundary_id": "boundary-invalid",
                "chromosome": "chr7",
                "start": 200,
                "end": 100,
                "insulation_score": 0.8,
                "boundary_support": 0.9,
                "orientation": "convergent",
                "context_key": context,
            }
        ]
    else:
        rows = [
            {
                "boundary_id": "boundary-pediatric",
                "chromosome": "chr7",
                "start": 100,
                "end": 120,
                "insulation_score": 0.82,
                "boundary_support": 0.91,
                "orientation": "convergent",
                "context_key": "GRCh38|diffuse_glioma|pediatric|stem_like|core|untreated",
            }
        ]
    return _json_rows(rows)


def _hotspot_rows(mode: str) -> str:
    context = FRONTIER_ATLAS_CONTEXT_KEY
    if mode == "positive":
        rows = [
            {
                "hotspot_id": "hotspot-egfr",
                "evidence_type": "accessibility",
                "source_id": "encode-screen",
                "direction": "gain",
                "context_key": context,
            },
            {
                "hotspot_id": "hotspot-egfr",
                "evidence_type": "contact",
                "source_id": "encode-hic",
                "direction": "gain",
                "context_key": context,
            },
        ]
    elif mode == "one-source":
        rows = [
            {
                "hotspot_id": "hotspot-one",
                "evidence_type": "accessibility",
                "source_id": "encode-screen",
                "direction": "gain",
                "context_key": context,
            }
        ]
    elif mode == "disagreement":
        rows = [
            {
                "hotspot_id": "hotspot-disagree",
                "evidence_type": "accessibility",
                "source_id": "encode-screen",
                "direction": "gain",
                "context_key": context,
            },
            {
                "hotspot_id": "hotspot-disagree",
                "evidence_type": "contact",
                "source_id": "encode-hic",
                "direction": "loss",
                "context_key": context,
            },
        ]
    else:
        rows = [
            {
                "hotspot_id": "hotspot-pediatric",
                "evidence_type": "accessibility",
                "source_id": "encode-screen",
                "direction": "gain",
                "context_key": "GRCh38|diffuse_glioma|pediatric|stem_like|core|untreated",
            },
            {
                "hotspot_id": "hotspot-pediatric",
                "evidence_type": "contact",
                "source_id": "encode-hic",
                "direction": "gain",
                "context_key": "GRCh38|diffuse_glioma|pediatric|stem_like|core|untreated",
            },
        ]
    return _json_rows(rows)


def _tier_rows(mode: str) -> str:
    context = FRONTIER_ATLAS_CONTEXT_KEY
    if mode == "positive":
        rows = [
            {
                "atlas_id": "atlas-egfr",
                "source_count": 3,
                "consistency": 0.92,
                "reproducibility": 0.9,
                "context_key": context,
            }
        ]
    elif mode == "low":
        rows = [
            {
                "atlas_id": "atlas-low",
                "source_count": 2,
                "consistency": 0.3,
                "reproducibility": 0.4,
                "context_key": context,
            }
        ]
    elif mode == "no-source":
        rows = [
            {
                "atlas_id": "atlas-none",
                "source_count": 0,
                "consistency": 0.9,
                "reproducibility": 0.9,
                "context_key": context,
            }
        ]
    else:
        rows = [
            {
                "atlas_id": "atlas-pediatric",
                "source_count": 3,
                "consistency": 0.92,
                "reproducibility": 0.9,
                "context_key": "GRCh38|diffuse_glioma|pediatric|stem_like|core|untreated",
            }
        ]
    return _json_rows(rows)


def _snapshot_rows(mode: str) -> str:
    context = FRONTIER_ATLAS_CONTEXT_KEY
    if mode == "positive":
        return _json_rows(
            [
                {
                    "id": "cCRE-egfr",
                    "context_key": context,
                    "chromosome": "chr7",
                    "start": 100,
                    "end": 120,
                },
                {
                    "id": "cCRE-pdgfra",
                    "context_key": context,
                    "chromosome": "chr4",
                    "start": 200,
                    "end": 220,
                },
            ]
        )
    if mode == "empty":
        return _json_rows([])
    if mode == "wrong-context":
        return _json_rows(
            [
                {
                    "id": "cCRE-pediatric",
                    "context_key": "GRCh38|diffuse_glioma|pediatric|stem_like|core|untreated",
                    "chromosome": "chr7",
                    "start": 100,
                    "end": 120,
                }
            ]
        )
    return _json_rows(
        [
            {
                "id": "cCRE-metadata",
                "context_key": context,
                "chromosome": "chr7",
                "start": 100,
                "end": 120,
            }
        ]
    )


def default_frontier_atlas_fixture() -> FrontierAtlasFixture:
    """Return the deterministic public aggregate C13-C16 fixture."""

    sources = (
        _source(
            "encode-hic",
            "ENCODE Hi-C data standards and processing",
            "https://www.encodeproject.org/hic/",
            "official_assay_standard",
            "released-overview",
            "3D chromatin contact and context boundary",
        ),
        _source(
            "encode-hic-pipeline",
            "ENCODE released Hi-C pipeline",
            "https://www.encodeproject.org/pipelines/ENCPL839OAB/",
            "official_pipeline_receipt",
            "released",
            "Hi-C processing and replicate/library boundary",
        ),
        _source(
            "encode-pipelines",
            "ENCODE data processing pipeline catalog",
            "https://www.encodeproject.org/pipelines/",
            "official_pipeline_catalog",
            "current-public-page",
            "versioned uniform processing boundary",
        ),
        _source(
            "encode-screen",
            "ENCODE SCREEN candidate cis-regulatory elements",
            "https://screen.encodeproject.org/index/about",
            "official_annotation_resource",
            "current-public-page",
            "cCRE and candidate regulatory-element boundary",
        ),
        _source(
            "nci-adult-glioma",
            "NCI adult central nervous system tumor reference",
            "https://www.cancer.gov/types/brain/hp/adult-brain-treatment-pdq",
            "official_disease_reference",
            "current-public-page",
            "adult glioma context vocabulary",
        ),
    )
    records = (
        _record(
            "C13-POS-001",
            FrontierAtlasOperation.BOUNDARY_ATLAS,
            FrontierAtlasRole.POSITIVE,
            {
                "input_format": "json",
                "input_text": _boundary_rows("positive"),
                "source_id": "fixture-boundary",
                "source_version": "v1",
                "minimum_support": 0.7,
            },
            "accepted",
            (),
            ("encode-hic", "encode-hic-pipeline"),
            "convergent supported boundary with strong insulation support",
        ),
        _record(
            "C13-CTRL-001",
            FrontierAtlasOperation.BOUNDARY_ATLAS,
            FrontierAtlasRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _boundary_rows("low-support"),
                "source_id": "fixture-boundary",
                "source_version": "v1",
                "minimum_support": 0.7,
            },
            "review",
            ("boundary_low_support",),
            ("encode-hic",),
            "boundary support below the declared acceptance floor",
        ),
        _record(
            "C13-CTRL-002",
            FrontierAtlasOperation.BOUNDARY_ATLAS,
            FrontierAtlasRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _boundary_rows("invalid"),
                "source_id": "fixture-boundary",
                "source_version": "v1",
                "minimum_support": 0.7,
            },
            "review",
            ("invalid_boundary_interval",),
            ("encode-hic",),
            "invalid interval is retained as review",
        ),
        _record(
            "C13-CTRL-003",
            FrontierAtlasOperation.BOUNDARY_ATLAS,
            FrontierAtlasRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _boundary_rows("wrong-context"),
                "source_id": "fixture-boundary",
                "source_version": "v1",
                "minimum_support": 0.7,
            },
            "out_of_domain",
            ("boundary_context_mismatch",),
            ("encode-hic", "nci-adult-glioma"),
            "pediatric boundary is not transported into adult context",
        ),
        _record(
            "C14-POS-001",
            FrontierAtlasOperation.HOTSPOT_ATLAS,
            FrontierAtlasRole.POSITIVE,
            {
                "input_format": "json",
                "input_text": _hotspot_rows("positive"),
                "source_id": "fixture-hotspot",
                "source_version": "v1",
                "minimum_support_count": 2,
                "minimum_concordance": 0.7,
            },
            "accepted",
            (),
            ("encode-screen", "encode-hic"),
            "two independent concordant regulatory signals support a hotspot",
        ),
        _record(
            "C14-CTRL-001",
            FrontierAtlasOperation.HOTSPOT_ATLAS,
            FrontierAtlasRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _hotspot_rows("one-source"),
                "source_id": "fixture-hotspot",
                "source_version": "v1",
                "minimum_support_count": 2,
                "minimum_concordance": 0.7,
            },
            "review",
            ("insufficient_hotspot_sources",),
            ("encode-screen",),
            "one source does not satisfy independent-source floor",
        ),
        _record(
            "C14-CTRL-002",
            FrontierAtlasOperation.HOTSPOT_ATLAS,
            FrontierAtlasRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _hotspot_rows("disagreement"),
                "source_id": "fixture-hotspot",
                "source_version": "v1",
                "minimum_support_count": 2,
                "minimum_concordance": 0.7,
            },
            "review",
            ("hotspot_direction_disagreement",),
            ("encode-screen", "encode-hic"),
            "opposing directions remain reviewable",
        ),
        _record(
            "C14-CTRL-003",
            FrontierAtlasOperation.HOTSPOT_ATLAS,
            FrontierAtlasRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _hotspot_rows("wrong-context"),
                "source_id": "fixture-hotspot",
                "source_version": "v1",
                "minimum_support_count": 2,
                "minimum_concordance": 0.7,
            },
            "out_of_domain",
            ("hotspot_context_mismatch",),
            ("encode-screen", "encode-hic", "nci-adult-glioma"),
            "hotspot source context is outside the requested adult context",
        ),
        _record(
            "C15-POS-001",
            FrontierAtlasOperation.EVIDENCE_TIER,
            FrontierAtlasRole.POSITIVE,
            {
                "input_format": "json",
                "input_text": _tier_rows("positive"),
                "source_id": "fixture-tier",
                "source_version": "v1",
                "high_source_count": 3,
                "high_consistency": 0.8,
                "medium_consistency": 0.6,
            },
            "accepted",
            (),
            ("encode-pipelines", "encode-screen", "encode-hic"),
            "high source count and concordant reproducibility produce a high tier",
        ),
        _record(
            "C15-CTRL-001",
            FrontierAtlasOperation.EVIDENCE_TIER,
            FrontierAtlasRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _tier_rows("low"),
                "source_id": "fixture-tier",
                "source_version": "v1",
                "high_source_count": 3,
                "high_consistency": 0.8,
                "medium_consistency": 0.6,
            },
            "review",
            ("low_evidence_tier",),
            ("encode-pipelines",),
            "low consistency remains review rather than a confidence claim",
        ),
        _record(
            "C15-CTRL-002",
            FrontierAtlasOperation.EVIDENCE_TIER,
            FrontierAtlasRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _tier_rows("no-source"),
                "source_id": "fixture-tier",
                "source_version": "v1",
                "high_source_count": 3,
                "high_consistency": 0.8,
                "medium_consistency": 0.6,
            },
            "review",
            ("no_evidence_sources",),
            ("encode-pipelines",),
            "zero source count is a blocking evidence issue",
        ),
        _record(
            "C15-CTRL-003",
            FrontierAtlasOperation.EVIDENCE_TIER,
            FrontierAtlasRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _tier_rows("wrong-context"),
                "source_id": "fixture-tier",
                "source_version": "v1",
                "high_source_count": 3,
                "high_consistency": 0.8,
                "medium_consistency": 0.6,
            },
            "out_of_domain",
            ("tier_context_mismatch",),
            ("encode-pipelines", "nci-adult-glioma"),
            "tier evidence is not borrowed across age context",
        ),
        _record(
            "C16-POS-001",
            FrontierAtlasOperation.SNAPSHOT_PUBLISH,
            FrontierAtlasRole.POSITIVE,
            {
                "input_format": "json",
                "input_text": _snapshot_rows("positive"),
                "source_id": "fixture-snapshot",
                "source_version": "v1",
                "snapshot_id": "atlas-snapshot-adult",
                "atlas_type": "regulatory-boundary",
                "version": "2026.08",
                "schema_version": "atlas-frontier-v1",
            },
            "published",
            (),
            ("encode-screen", "encode-hic", "encode-pipelines"),
            "context-qualified records publish into a content-addressed snapshot manifest",
        ),
        _record(
            "C16-CTRL-001",
            FrontierAtlasOperation.SNAPSHOT_PUBLISH,
            FrontierAtlasRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _snapshot_rows("empty"),
                "source_id": "fixture-snapshot",
                "source_version": "v1",
                "snapshot_id": "atlas-empty",
                "atlas_type": "regulatory-boundary",
                "version": "2026.08",
                "schema_version": "atlas-frontier-v1",
            },
            "abstained",
            ("empty_snapshot_records",),
            ("encode-screen",),
            "an empty snapshot abstains rather than publishing absence",
        ),
        _record(
            "C16-CTRL-002",
            FrontierAtlasOperation.SNAPSHOT_PUBLISH,
            FrontierAtlasRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _snapshot_rows("wrong-context"),
                "source_id": "fixture-snapshot",
                "source_version": "v1",
                "snapshot_id": "atlas-pediatric",
                "atlas_type": "regulatory-boundary",
                "version": "2026.08",
                "schema_version": "atlas-frontier-v1",
            },
            "out_of_domain",
            ("snapshot_context_mismatch",),
            ("encode-screen", "nci-adult-glioma"),
            "snapshot publisher blocks context drift",
        ),
        _record(
            "C16-CTRL-003",
            FrontierAtlasOperation.SNAPSHOT_PUBLISH,
            FrontierAtlasRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _snapshot_rows("metadata-invalid"),
                "source_id": "fixture-snapshot",
                "source_version": "v1",
                "snapshot_id": "",
                "atlas_type": "regulatory-boundary",
                "version": "2026.08",
                "schema_version": "atlas-frontier-v1",
            },
            "invalid",
            ("snapshot_metadata_invalid",),
            ("encode-screen",),
            "empty snapshot identity is rejected by the release boundary",
        ),
    )
    body = {
        "fixture_id": "frontier-atlas-public-aggregate",
        "fixture_version": FRONTIER_ATLAS_FIXTURE_VERSION,
        "context_key": FRONTIER_ATLAS_CONTEXT_KEY,
        "evidence_boundary": FRONTIER_ATLAS_EVIDENCE_BOUNDARY,
        "sources": sources,
        "records": records,
    }
    return FrontierAtlasFixture(**body, content_address=_address(body))


def build_frontier_atlas_catalog(fixture: FrontierAtlasFixture) -> FrontierAtlasCatalog:
    """Build a deterministic source and operation index."""

    body = {
        "fixture_id": fixture.fixture_id,
        "fixture_version": fixture.fixture_version,
        "source_ids": tuple(source.source_id for source in fixture.sources),
        "record_ids": tuple(record.record_id for record in fixture.records),
        "operations": tuple(dict.fromkeys(record.operation for record in fixture.records)),
    }
    return FrontierAtlasCatalog(
        fixture, body["source_ids"], body["record_ids"], body["operations"], _address(body)
    )


def audit_frontier_atlas_data(
    fixture: FrontierAtlasFixture | None = None,
) -> FrontierAtlasDataAudit:
    """Audit aggregate scope, source closure, balance, and subject boundaries."""

    selected = fixture or default_frontier_atlas_fixture()
    source_ids = set(selected.source_map())
    checks: list[FrontierAtlasDataCheck] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(FrontierAtlasDataCheck(check_id, passed, detail, _address(body)))

    add(
        "fixture-context",
        selected.context_key == FRONTIER_ATLAS_CONTEXT_KEY,
        "fixture context is exact",
    )
    add(
        "fixture-boundary",
        selected.evidence_boundary == FRONTIER_ATLAS_EVIDENCE_BOUNDARY,
        "fixture is public aggregate non-patient",
    )
    add(
        "source-count",
        len(selected.sources) == FRONTIER_ATLAS_SOURCE_COUNT,
        "expected public source receipts are present",
    )
    add(
        "source-closure",
        all(
            source_id in source_ids
            for record in selected.records
            for source_id in record.source_ids
        ),
        "every record source resolves",
    )
    add(
        "record-ids-unique",
        len(selected.record_map()) == len(selected.records),
        "record IDs are unique",
    )
    add(
        "operation-coverage",
        {record.operation for record in selected.records} == set(FrontierAtlasOperation),
        "all four operations are represented",
    )
    add(
        "positive-floor",
        len(selected.positive_records) == FRONTIER_ATLAS_POSITIVE_COUNT,
        "one positive path per operation",
    )
    add(
        "control-floor",
        len(selected.control_records) == FRONTIER_ATLAS_CONTROL_COUNT,
        "three controls per operation",
    )
    add(
        "positive-context",
        all(record.context_key == selected.context_key for record in selected.positive_records),
        "positive records declare exact context",
    )
    add(
        "no-subject-identifiers",
        not any(_contains_subject_key(record.payload) for record in selected.records),
        "payloads contain no subject identifiers",
    )
    add(
        "https-receipts",
        all(source.uri.startswith("https://") for source in selected.sources),
        "source receipts use HTTPS",
    )
    body = {
        "fixture_id": selected.fixture_id,
        "fixture_version": selected.fixture_version,
        "context_key": selected.context_key,
        "evidence_boundary": selected.evidence_boundary,
        "checks": checks,
    }
    return FrontierAtlasDataAudit(
        selected.fixture_id,
        selected.fixture_version,
        selected.context_key,
        selected.evidence_boundary,
        tuple(checks),
        _address(body),
    )


def _contains_subject_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            key.lower() in {"patient", "subject", "donor", "participant", "sample_id"}
            or _contains_subject_key(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_subject_key(item) for item in value)
    return False


def load_frontier_atlas_fixture(path: str) -> FrontierAtlasFixture:
    """Load and address-check a serialized fixture."""

    from pathlib import Path

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    sources = tuple(FrontierAtlasSourceReceipt(**row) for row in payload["sources"])
    records = tuple(
        FrontierAtlasRecord(
            record_id=row["record_id"],
            operation=FrontierAtlasOperation(row["operation"]),
            role=FrontierAtlasRole(row["role"]),
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
    fixture = FrontierAtlasFixture(
        fixture_id=payload["fixture_id"],
        fixture_version=payload["fixture_version"],
        context_key=payload["context_key"],
        evidence_boundary=payload["evidence_boundary"],
        sources=sources,
        records=records,
        content_address=payload["content_address"],
    )
    body = {key: value for key, value in fixture.to_dict().items() if key != "content_address"}
    if fixture.content_address != _address(body):
        raise ValidationError("frontier atlas fixture content address does not verify")
    return fixture


__all__ = [
    "FRONTIER_ATLAS_CONTEXT_KEY",
    "FRONTIER_ATLAS_CONTROL_COUNT",
    "FRONTIER_ATLAS_EVIDENCE_BOUNDARY",
    "FRONTIER_ATLAS_FIXTURE_VERSION",
    "FRONTIER_ATLAS_POSITIVE_COUNT",
    "FRONTIER_ATLAS_SOURCE_COUNT",
    "FrontierAtlasCatalog",
    "FrontierAtlasDataAudit",
    "FrontierAtlasDataCheck",
    "FrontierAtlasFixture",
    "FrontierAtlasOperation",
    "FrontierAtlasRecord",
    "FrontierAtlasRole",
    "FrontierAtlasSourceReceipt",
    "audit_frontier_atlas_data",
    "build_frontier_atlas_catalog",
    "default_frontier_atlas_fixture",
    "load_frontier_atlas_fixture",
]
