"""Public aggregate evidence boundary for Domain 12 C01-C04.

The fixture is deliberately aggregate-only.  It contains pseudonymous row
identifiers, callable-space counts, sequence windows, and normalized chromatin
features; it does not contain patient identifiers, raw specimens, or clinical
outcomes.  Every row carries a source receipt and exact context so transport
errors remain observable during replay.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping

from .errors import ValidationError
from .serialization import content_hash, jsonable


COHORT_FOUNDATION_FRONTIER_FIXTURE_VERSION = "2026.08.d12-c01-c04.v1"
COHORT_FOUNDATION_FRONTIER_CONTEXT_KEY = (
    "GRCh38|glioma|adult|stem_like|tumor_core|pre_treatment"
)
COHORT_FOUNDATION_FRONTIER_FOREIGN_CONTEXT_KEY = (
    "GRCh38|glioma|adult|stem_like|tumor_margin|post_treatment"
)
COHORT_FOUNDATION_FRONTIER_BOUNDARY = "public_aggregate_non_patient"


class CohortFoundationOperation(StrEnum):
    """The four Domain 12 C01-C04 work packages."""

    COHORT_QUERY = "cohort_query"
    BACKGROUND_RATE = "background_rate"
    SEQUENCE_CONTROL = "sequence_control"
    CHROMATIN_CONTROL = "chromatin_control"


class CohortFoundationRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class CohortFoundationSourceReceipt:
    """A stable public source receipt used for provenance, not live retrieval."""

    source_id: str
    title: str
    url: str
    version: str
    license: str
    context_key: str
    aggregate_only: bool = True
    retrieval_note: str = "public metadata receipt; fixture values are checked-in aggregates"
    content_address: str = ""

    def __post_init__(self) -> None:
        for name in ("source_id", "title", "url", "version", "license", "context_key"):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"source receipt {name} is required")
        if not self.url.startswith("https://"):
            raise ValidationError("source receipt URL must use HTTPS")
        if not self.aggregate_only:
            raise ValidationError("cohort foundation fixture requires aggregate-only sources")

    def to_dict(self) -> dict[str, Any]:
        body = jsonable(self)
        body["content_address"] = content_hash({key: value for key, value in body.items() if key != "content_address"})
        return body


@dataclass(frozen=True, slots=True)
class CohortFoundationRecord:
    """One operation input plus an expected state for a bounded control path."""

    record_id: str
    operation: CohortFoundationOperation
    role: CohortFoundationRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    expected_state: str
    expected_issues: tuple[str, ...] = ()
    description: str = ""
    content_address: str = ""

    def __post_init__(self) -> None:
        for name in ("record_id", "context_key", "expected_state"):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"fixture record {name} is required")
        if not self.source_ids:
            raise ValidationError("fixture record must cite at least one source")
        if not isinstance(self.payload, Mapping):
            raise ValidationError("fixture record payload must be an object")

    def to_dict(self) -> dict[str, Any]:
        body = jsonable(self)
        body["content_address"] = content_hash({key: value for key, value in body.items() if key != "content_address"})
        return body


@dataclass(frozen=True, slots=True)
class CohortFoundationFixture:
    """Immutable public aggregate fixture with explicit source closure."""

    fixture_id: str
    fixture_version: str
    context_key: str
    foreign_context_key: str
    boundary: str
    sources: tuple[CohortFoundationSourceReceipt, ...]
    records: tuple[CohortFoundationRecord, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.fixture_id.strip() or not self.fixture_version.strip():
            raise ValidationError("cohort foundation fixture identity is required")
        if self.context_key == self.foreign_context_key:
            raise ValidationError("foreign context must differ from fixture context")
        if self.boundary != COHORT_FOUNDATION_FRONTIER_BOUNDARY:
            raise ValidationError("fixture boundary must remain public aggregate")
        if len(self.records) < 16:
            raise ValidationError("cohort foundation fixture requires positive and control depth")
        ids = [item.record_id for item in self.records]
        if len(set(ids)) != len(ids):
            raise ValidationError("fixture record IDs must be unique")
        operations = {item.operation for item in self.records}
        if operations != set(CohortFoundationOperation):
            raise ValidationError("fixture must cover every foundation operation")

    @property
    def positive_records(self) -> tuple[CohortFoundationRecord, ...]:
        return tuple(item for item in self.records if item.role is CohortFoundationRole.POSITIVE)

    @property
    def control_records(self) -> tuple[CohortFoundationRecord, ...]:
        return tuple(item for item in self.records if item.role is CohortFoundationRole.CONTROL)

    def records_for(self, operation: CohortFoundationOperation) -> tuple[CohortFoundationRecord, ...]:
        return tuple(item for item in self.records if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        body = jsonable(self)
        body["positive_count"] = len(self.positive_records)
        body["control_count"] = len(self.control_records)
        body["content_address"] = content_hash({key: value for key, value in body.items() if key != "content_address"})
        return body


@dataclass(frozen=True, slots=True)
class CohortFoundationDataCheck:
    check_id: str
    passed: bool
    observed: Any
    expected: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationDataAudit:
    fixture_id: str
    accepted: bool
    checks: tuple[CohortFoundationDataCheck, ...]
    content_address: str

    @property
    def failures(self) -> tuple[CohortFoundationDataCheck, ...]:
        return tuple(item for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _source(source_id: str, title: str, url: str, version: str, license: str) -> CohortFoundationSourceReceipt:
    return CohortFoundationSourceReceipt(
        source_id=source_id,
        title=title,
        url=url,
        version=version,
        license=license,
        context_key=COHORT_FOUNDATION_FRONTIER_CONTEXT_KEY,
    )


def _record(
    record_id: str,
    operation: CohortFoundationOperation,
    role: CohortFoundationRole,
    payload: Mapping[str, Any],
    expected_state: str,
    source_ids: tuple[str, ...],
    *,
    context_key: str = COHORT_FOUNDATION_FRONTIER_CONTEXT_KEY,
    expected_issues: tuple[str, ...] = (),
    description: str = "",
) -> CohortFoundationRecord:
    return CohortFoundationRecord(
        record_id=record_id,
        operation=operation,
        role=role,
        context_key=context_key,
        source_ids=source_ids,
        payload=dict(payload),
        expected_state=expected_state,
        expected_issues=expected_issues,
        description=description,
    )


def _variant_row(
    record_id: str,
    *,
    chromosome: str = "7",
    start: int = 55249071,
    context_key: str = COHORT_FOUNDATION_FRONTIER_CONTEXT_KEY,
    callable: bool = True,
    sequence_context: str = "ACGTACGTACGTACGT",
    chromatin_features: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    return {
        "record_id": record_id,
        "variant_id": f"var-{record_id}",
        "kind": "snv",
        "chromosome": chromosome,
        "start": start,
        "end": start,
        "reference": "C",
        "alternate": "T",
        "genome_build": "GRCh38",
        "origin": "somatic",
        "sample_id": f"sample-{record_id}",
        "context_key": context_key,
        "callable": callable,
        "sequence_context": sequence_context,
        "chromatin_features": dict(chromatin_features or {"atac": 0.72, "h3k27ac": 0.61, "ctcf": 0.44}),
    }


def _background_payload(*, records: list[dict[str, Any]], intervals: list[dict[str, Any]], target: int) -> dict[str, Any]:
    return {"background_records": records, "callable_intervals": intervals, "target_callable_bases": target}


def _interval(interval_id: str, *, context_key: str = COHORT_FOUNDATION_FRONTIER_CONTEXT_KEY, bases: int = 100_000) -> dict[str, Any]:
    return {
        "interval_id": interval_id,
        "chromosome": "7",
        "start": 55249000,
        "end": 55250000,
        "callable_bases": bases,
        "context_key": context_key,
        "source_id": "source-icgc",
        "source_version": "release-28",
        "raw_hash": content_hash({"interval_id": interval_id, "bases": bases}),
    }


def default_cohort_foundation_frontier_fixture() -> CohortFoundationFixture:
    """Return a deterministic fixture with four positives and twelve controls."""

    sources = (
        _source("source-gdc", "NCI Genomic Data Commons", "https://gdc.cancer.gov/", "2026-01", "public-data-notice"),
        _source("source-icgc", "ICGC Data Portal", "https://dcc.icgc.org/", "release-28", "public-data-notice"),
        _source("source-gnomad", "gnomAD aggregate variation", "https://gnomad.broadinstitute.org/", "v4.1", "gnomAD-terms"),
        _source("source-encode", "ENCODE portal", "https://www.encodeproject.org/", "2025-12", "ENCODE-terms"),
        _source("source-depmap", "DepMap portal", "https://depmap.org/portal/", "24Q4", "CC-BY-4.0"),
    )
    query_rows = [_variant_row("q-01", start=55249071), _variant_row("q-02", start=55249072)]
    query_partial = query_rows + [_variant_row("q-03", callable=False)]
    sequence_target = _variant_row("seq-target", sequence_context="ACGTACGTACGTACGT")
    sequence_same = _variant_row("seq-same", sequence_context="ACGTACGTACGTACGT")
    sequence_near = _variant_row("seq-near", sequence_context="ACGTACGTACGTACGA")
    chromatin_target = _variant_row("chrom-target", chromatin_features={"atac": 0.72, "h3k27ac": 0.61, "ctcf": 0.44})
    chromatin_same = _variant_row("chrom-same", chromatin_features={"atac": 0.73, "h3k27ac": 0.60, "ctcf": 0.45})
    chromatin_near = _variant_row("chrom-near", chromatin_features={"atac": 0.70, "h3k27ac": 0.63, "ctcf": 0.43})
    records = (
        _record("C01-POS-001", CohortFoundationOperation.COHORT_QUERY, CohortFoundationRole.POSITIVE, {"query_id": "glioma-core-snv", "variant_kinds": ["snv"], "origins": ["somatic"], "chromosomes": ["7"], "require_callable": True, "rows": query_rows}, "supported", ("source-gdc", "source-icgc"), description="exact-context callable somatic query"),
        _record("C01-CTRL-001", CohortFoundationOperation.COHORT_QUERY, CohortFoundationRole.CONTROL, {"query_id": "partial-callability", "variant_kinds": ["snv"], "origins": ["somatic"], "chromosomes": ["7"], "require_callable": True, "rows": query_partial}, "partial", ("source-gdc",), expected_issues=("excluded_records",), description="callability exclusion remains visible"),
        _record("C01-CTRL-002", CohortFoundationOperation.COHORT_QUERY, CohortFoundationRole.CONTROL, {"query_id": "foreign-query", "variant_kinds": ["snv"], "origins": ["somatic"], "chromosomes": ["7"], "require_callable": True, "rows": [_variant_row("q-foreign", context_key=COHORT_FOUNDATION_FRONTIER_FOREIGN_CONTEXT_KEY)]}, "out_of_domain", ("source-gdc",), expected_issues=("context_mismatch",), context_key=COHORT_FOUNDATION_FRONTIER_FOREIGN_CONTEXT_KEY, description="foreign territory cannot be transported"),
        _record("C01-CTRL-003", CohortFoundationOperation.COHORT_QUERY, CohortFoundationRole.CONTROL, {"query_id": "empty-query", "variant_kinds": ["snv"], "origins": ["somatic"], "chromosomes": ["7"], "require_callable": True, "rows": []}, "absent", ("source-icgc",), expected_issues=("empty_selection",), description="empty cohort selection"),
        _record("C02-POS-001", CohortFoundationOperation.BACKGROUND_RATE, CohortFoundationRole.POSITIVE, _background_payload(records=[_variant_row("bg-01"), _variant_row("bg-02", start=55249072), _variant_row("bg-03", start=55249073)], intervals=[_interval("callable-01"), _interval("callable-02", bases=120_000)], target=75_000), "supported", ("source-icgc", "source-gnomad"), description="callable-space background estimate"),
        _record("C02-CTRL-001", CohortFoundationOperation.BACKGROUND_RATE, CohortFoundationRole.CONTROL, _background_payload(records=[_variant_row("bg-foreign", context_key=COHORT_FOUNDATION_FRONTIER_FOREIGN_CONTEXT_KEY)], intervals=[_interval("callable-foreign", context_key=COHORT_FOUNDATION_FRONTIER_FOREIGN_CONTEXT_KEY)], target=75_000), "out_of_domain", ("source-icgc",), expected_issues=("context_mismatch",), context_key=COHORT_FOUNDATION_FRONTIER_FOREIGN_CONTEXT_KEY, description="foreign callable intervals"),
        _record("C02-CTRL-002", CohortFoundationOperation.BACKGROUND_RATE, CohortFoundationRole.CONTROL, _background_payload(records=[], intervals=[_interval("callable-zero")], target=75_000), "partial", ("source-icgc",), expected_issues=("zero_observation",), description="zero observed background is partial, not negative"),
        _record("C02-CTRL-003", CohortFoundationOperation.BACKGROUND_RATE, CohortFoundationRole.CONTROL, _background_payload(records=[_variant_row("bg-no-interval")], intervals=[], target=75_000), "abstained", ("source-gnomad",), expected_issues=("missing_callable_intervals",), description="missing callable-space denominator"),
        _record("C03-POS-001", CohortFoundationOperation.SEQUENCE_CONTROL, CohortFoundationRole.POSITIVE, {"target": sequence_target, "candidates": [sequence_same, sequence_near], "max_controls": 2, "max_distance": 0.0625}, "supported", ("source-gdc", "source-gnomad"), description="sequence-matched controls"),
        _record("C03-CTRL-001", CohortFoundationOperation.SEQUENCE_CONTROL, CohortFoundationRole.CONTROL, {"target": sequence_target, "candidates": [sequence_same], "max_controls": 2, "max_distance": 0.0}, "partial", ("source-gnomad",), expected_issues=("insufficient_controls",), description="one exact sequence control"),
        _record("C03-CTRL-002", CohortFoundationOperation.SEQUENCE_CONTROL, CohortFoundationRole.CONTROL, {"target": sequence_target, "candidates": [_variant_row("seq-far", sequence_context="TTTTTTTTTTTTTTTT")], "max_controls": 1, "max_distance": 0.0}, "absent", ("source-gnomad",), expected_issues=("no_matching_control",), description="distance threshold excludes candidate"),
        _record("C03-CTRL-003", CohortFoundationOperation.SEQUENCE_CONTROL, CohortFoundationRole.CONTROL, {"target": sequence_target, "candidates": [_variant_row("seq-foreign", context_key=COHORT_FOUNDATION_FRONTIER_FOREIGN_CONTEXT_KEY)], "max_controls": 1, "max_distance": 0.0}, "out_of_domain", ("source-gnomad",), expected_issues=("context_mismatch",), description="sequence candidate only exists in foreign context"),
        _record("C04-POS-001", CohortFoundationOperation.CHROMATIN_CONTROL, CohortFoundationRole.POSITIVE, {"target": chromatin_target, "candidates": [chromatin_same, chromatin_near], "feature_ranges": {"atac": [0.0, 1.0], "h3k27ac": [0.0, 1.0], "ctcf": [0.0, 1.0]}, "max_controls": 2, "max_distance": 0.06}, "supported", ("source-encode", "source-depmap"), description="chromatin-feature matched controls"),
        _record("C04-CTRL-001", CohortFoundationOperation.CHROMATIN_CONTROL, CohortFoundationRole.CONTROL, {"target": chromatin_target, "candidates": [chromatin_same], "feature_ranges": {"atac": [0.0, 1.0], "h3k27ac": [0.0, 1.0], "ctcf": [0.0, 1.0]}, "max_controls": 2, "max_distance": 0.02}, "partial", ("source-encode",), expected_issues=("insufficient_controls",), description="one chromatin control below cutoff"),
        _record("C04-CTRL-002", CohortFoundationOperation.CHROMATIN_CONTROL, CohortFoundationRole.CONTROL, {"target": chromatin_target, "candidates": [_variant_row("chrom-far", chromatin_features={"atac": 0.05, "h3k27ac": 0.10, "ctcf": 0.90})], "feature_ranges": {"atac": [0.0, 1.0], "h3k27ac": [0.0, 1.0], "ctcf": [0.0, 1.0]}, "max_controls": 1, "max_distance": 0.02}, "absent", ("source-encode",), expected_issues=("no_matching_control",), description="feature distance excludes candidate"),
        _record("C04-CTRL-003", CohortFoundationOperation.CHROMATIN_CONTROL, CohortFoundationRole.CONTROL, {"target": chromatin_target, "candidates": [_variant_row("chrom-foreign", context_key=COHORT_FOUNDATION_FRONTIER_FOREIGN_CONTEXT_KEY, chromatin_features={"atac": 0.72, "h3k27ac": 0.61, "ctcf": 0.44})], "feature_ranges": {"atac": [0.0, 1.0], "h3k27ac": [0.0, 1.0], "ctcf": [0.0, 1.0]}, "max_controls": 1, "max_distance": 0.02}, "out_of_domain", ("source-encode",), expected_issues=("context_mismatch",), description="chromatin candidate only exists in foreign context"),
    )
    return CohortFoundationFixture(
        fixture_id="cohort-foundation-frontier-public-aggregate",
        fixture_version=COHORT_FOUNDATION_FRONTIER_FIXTURE_VERSION,
        context_key=COHORT_FOUNDATION_FRONTIER_CONTEXT_KEY,
        foreign_context_key=COHORT_FOUNDATION_FRONTIER_FOREIGN_CONTEXT_KEY,
        boundary=COHORT_FOUNDATION_FRONTIER_BOUNDARY,
        sources=sources,
        records=records,
    )


def audit_cohort_foundation_frontier_data(fixture: CohortFoundationFixture) -> CohortFoundationDataAudit:
    """Audit source closure, context closure, and positive/control balance."""

    source_ids = {item.source_id for item in fixture.sources}
    referenced = {source_id for item in fixture.records for source_id in item.source_ids}
    checks_raw = (
        ("fixture-version", bool(fixture.fixture_version), fixture.fixture_version, True, "non-empty fixture version"),
        ("source-count", len(fixture.sources) >= 5, len(fixture.sources), ">=5 source receipts", "source receipt depth"),
        ("record-count", len(fixture.records) >= 16, len(fixture.records), ">=16 operation records", "positive and control depth"),
        ("source-closure", referenced <= source_ids, sorted(referenced - source_ids), [], "all cited sources declared"),
        ("context-closure", all(item.context_key in {fixture.context_key, fixture.foreign_context_key} for item in fixture.records), False, True, "records use declared contexts"),
        ("operation-coverage", {item.operation for item in fixture.records} == set(CohortFoundationOperation), sorted(item.value for item in {item.operation for item in fixture.records}), [item.value for item in CohortFoundationOperation], "all four operations present"),
        ("positive-coverage", all(any(item.role is CohortFoundationRole.POSITIVE for item in fixture.records_for(operation)) for operation in CohortFoundationOperation), True, True, "one positive per operation"),
        ("control-coverage", all(sum(item.role is CohortFoundationRole.CONTROL for item in fixture.records_for(operation)) >= 3 for operation in CohortFoundationOperation), True, True, ">=3 controls per operation"),
        ("https-receipts", all(item.url.startswith("https://") for item in fixture.sources), True, True, "source URLs use HTTPS"),
        ("aggregate-boundary", all(item.aggregate_only for item in fixture.sources), True, True, "sources are aggregate-only"),
    )
    checks = tuple(
        CohortFoundationDataCheck(
            check_id=check_id,
            passed=passed,
            observed=observed,
            expected=expected,
            detail=detail,
            content_address=content_hash((check_id, passed, observed, expected, detail)),
        )
        for check_id, passed, observed, expected, detail in checks_raw
    )
    body = {"fixture_id": fixture.fixture_id, "checks": checks}
    return CohortFoundationDataAudit(fixture.fixture_id, all(item.passed for item in checks), checks, content_hash(body))


def cohort_foundation_frontier_fixture_json(fixture: CohortFoundationFixture | None = None) -> str:
    """Serialize the checked-in fixture into deterministic JSON."""

    return json.dumps((fixture or default_cohort_foundation_frontier_fixture()).to_dict(), sort_keys=True, indent=2, default=str)


def load_cohort_foundation_frontier_fixture(path: str | Path) -> CohortFoundationFixture:
    """Load an externally supplied aggregate fixture with strict enum parsing."""

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    sources = tuple(CohortFoundationSourceReceipt(**item) for item in raw["sources"])
    records = tuple(
        CohortFoundationRecord(
            record_id=item["record_id"],
            operation=CohortFoundationOperation(item["operation"]),
            role=CohortFoundationRole(item["role"]),
            context_key=item["context_key"],
            source_ids=tuple(item["source_ids"]),
            payload=item["payload"],
            expected_state=item["expected_state"],
            expected_issues=tuple(item.get("expected_issues", ())),
            description=item.get("description", ""),
            content_address=item.get("content_address", ""),
        )
        for item in raw["records"]
    )
    return CohortFoundationFixture(
        fixture_id=raw["fixture_id"],
        fixture_version=raw["fixture_version"],
        context_key=raw["context_key"],
        foreign_context_key=raw["foreign_context_key"],
        boundary=raw["boundary"],
        sources=sources,
        records=records,
        content_address=raw.get("content_address", ""),
    )


__all__ = [
    "COHORT_FOUNDATION_FRONTIER_BOUNDARY",
    "COHORT_FOUNDATION_FRONTIER_CONTEXT_KEY",
    "COHORT_FOUNDATION_FRONTIER_FIXTURE_VERSION",
    "COHORT_FOUNDATION_FRONTIER_FOREIGN_CONTEXT_KEY",
    "CohortFoundationDataAudit",
    "CohortFoundationDataCheck",
    "CohortFoundationFixture",
    "CohortFoundationOperation",
    "CohortFoundationRecord",
    "CohortFoundationRole",
    "CohortFoundationSourceReceipt",
    "audit_cohort_foundation_frontier_data",
    "cohort_foundation_frontier_fixture_json",
    "default_cohort_foundation_frontier_fixture",
    "load_cohort_foundation_frontier_fixture",
]
