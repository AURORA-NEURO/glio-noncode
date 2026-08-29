"""Deterministic aggregate reports for verified observability-bundle catalogs.

The catalog is the immutable inventory.  This module derives a compact,
addressed report for operators that need denominators, basis-point ratios,
state distributions, and label-level readiness without reopening any source
directory.  The report is intentionally a lossy projection of catalog entries:
it keeps public receipts and addresses while excluding filesystem identity.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog as catalog_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = catalog_model.VERSION + "-report-v1"
BOUNDARY = catalog_model.BOUNDARY + "_report"
REPORT_PREFIX = catalog_model.CATALOG_PREFIX + "-report"
ROW_PREFIX = REPORT_PREFIX + "-row"
DEFAULT_REPORT_ID = "glio-noncode-observability-bundle-catalog-report"
ENTRY_STATES = ("ready", "held", "blocked")
PIPELINE_STATES = ("ready", "held", "blocked")
OBSERVABILITY_STATES = ("ready", "held", "blocked")
AUDIT_STATES = ("complete", "incomplete")
MAX_ROWS = catalog_model.MAX_ENTRIES
MAX_LABELS = MAX_ROWS
MAX_TEXT = 1024


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _label(value: Any, field: str) -> str:
    return catalog_model._label(value, field)


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or value.startswith(("/", "\\")) or "\\" in value:
        raise ValidationError(f"{field} has an invalid public namespace")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an invalid public namespace")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    return catalog_model._public(value)


def _accepted(entry: catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry) -> bool:
    return entry.pipeline_accepted and entry.audit_accepted


def _entry_state(entry: catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry) -> str:
    if _accepted(entry) and entry.pipeline_state == "ready" and entry.observability_state == "ready" and entry.audit_state == "complete":
        return "ready"
    if _accepted(entry):
        return "held"
    return "blocked"


def _distribution(values: Sequence[str], allowed: Sequence[str], field: str) -> tuple[tuple[str, int], ...]:
    counts = {key: 0 for key in allowed}
    for value in values:
        if value not in counts:
            raise ValidationError(f"{field} contains unsupported value")
        counts[value] += 1
    return tuple((key, counts[key]) for key in allowed)


def _distribution_mapping(value: Any, allowed: Sequence[str], field: str) -> tuple[tuple[str, int], ...]:
    values = _sequence(value, field, len(allowed))
    pairs: list[tuple[str, int]] = []
    for item in values:
        pair = _sequence(item, field + " pair", 2)
        if len(pair) != 2 or pair[0] not in allowed:
            raise ValidationError(f"{field} must contain canonical state pairs")
        pairs.append((pair[0], _count(pair[1], field + " count", MAX_ROWS)))
    result = tuple(pairs)
    if result != tuple((key, next((count for name, count in result if name == key), None)) for key in allowed):
        raise ValidationError(f"{field} must contain every state in canonical order")
    return result


def _labels(value: Any, field: str) -> tuple[str, ...]:
    values = tuple(_label(item, field) for item in _sequence(value, field, MAX_LABELS))
    if values != tuple(sorted(set(values))):
        raise ValidationError(f"{field} must be sorted and unique")
    return values


def _basis_points(count: int, total: int) -> int:
    return 0 if total == 0 else (count * 10000 + total // 2) // total


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportRow:
    """A path-free label row in an aggregate catalog report."""

    FIELDS = (
        "ordinal",
        "label",
        "bundle_address",
        "entry_address",
        "accepted",
        "state",
        "pipeline_state",
        "pipeline_accepted",
        "observability_state",
        "audit_state",
        "audit_accepted",
        "artifact_count",
        "content_address",
    )

    def __init__(self, ordinal: int, label: str, bundle_address: str, entry_address: str, accepted: bool, state: str, pipeline_state: str, pipeline_accepted: bool, observability_state: str, audit_state: str, audit_accepted: bool, artifact_count: int, content_address: str) -> None:
        self.ordinal = _count(ordinal, "observability bundle catalog report row ordinal", MAX_ROWS, positive=True)
        self.label = _label(label, "observability bundle catalog report row label")
        self.bundle_address = _address(bundle_address, "observability bundle catalog report row bundle address", catalog_model.bundle_model.BUNDLE_PREFIX)
        self.entry_address = _address(entry_address, "observability bundle catalog report row entry address", catalog_model.ENTRY_PREFIX)
        self.accepted = _bool(accepted, "observability bundle catalog report row accepted")
        self.state = _text(state, "observability bundle catalog report row state", 32)
        self.pipeline_state = _text(pipeline_state, "observability bundle catalog report row pipeline state", 32)
        self.pipeline_accepted = _bool(pipeline_accepted, "observability bundle catalog report row pipeline accepted")
        self.observability_state = _text(observability_state, "observability bundle catalog report row observability state", 32)
        self.audit_state = _text(audit_state, "observability bundle catalog report row audit state", 32)
        self.audit_accepted = _bool(audit_accepted, "observability bundle catalog report row audit accepted")
        self.artifact_count = _count(artifact_count, "observability bundle catalog report row artifact count", len(catalog_model.bundle_model.ARTIFACT_FILES))
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.state not in ENTRY_STATES or self.pipeline_state not in PIPELINE_STATES or self.observability_state not in OBSERVABILITY_STATES or self.audit_state not in AUDIT_STATES:
            raise ValidationError("observability bundle catalog report row contains an unsupported state")
        if self.accepted != (self.pipeline_accepted and self.audit_accepted):
            raise ValidationError("observability bundle catalog report row acceptance is not derived")
        expected_state = "ready" if self.accepted and self.pipeline_state == "ready" and self.observability_state == "ready" and self.audit_state == "complete" else "held" if self.accepted else "blocked"
        if self.state != expected_state:
            raise ValidationError("observability bundle catalog report row state is not derived")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle catalog report row content address")
        else:
            _address(self.content_address, "observability bundle catalog report row content address", ROW_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_row(self) != self.content_address):
            raise ValidationError("observability bundle catalog report row address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "label": self.label, "bundle_address": self.bundle_address, "entry_address": self.entry_address, "accepted": self.accepted, "state": self.state, "pipeline_state": self.pipeline_state, "pipeline_accepted": self.pipeline_accepted, "observability_state": self.observability_state, "audit_state": self.audit_state, "audit_accepted": self.audit_accepted, "artifact_count": self.artifact_count, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportRow:
        value = _mapping(value, "observability bundle catalog report row")
        _strict(value, set(cls.FIELDS), "observability bundle catalog report row")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog report row is missing fields: {missing}")
        return cls(*(value[field] for field in cls.FIELDS))


def _row_address_body(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportRow) -> dict[str, Any]:
    body = value.to_dict()
    body["content_address"] = None
    return body


def address_row(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportRow) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportRow):
        raise ValidationError("observability bundle catalog report row address requires a typed row")
    return content_hash(_row_address_body(value), prefix=ROW_PREFIX)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReport:
    """Addressed aggregate health and distribution report for a catalog."""

    FIELDS = (
        "report_id",
        "catalog_id",
        "catalog_address",
        "entry_count",
        "accepted_count",
        "ready_count",
        "rejected_count",
        "acceptance_basis_points",
        "readiness_basis_points",
        "artifact_count",
        "artifact_count_per_entry",
        "entry_state_counts",
        "pipeline_state_counts",
        "observability_state_counts",
        "audit_state_counts",
        "accepted_labels",
        "ready_labels",
        "rejected_labels",
        "rows",
        "content_address",
    )

    def __init__(self, report_id: str, catalog_id: str, catalog_address: str, entry_count: int, accepted_count: int, ready_count: int, rejected_count: int, acceptance_basis_points: int, readiness_basis_points: int, artifact_count: int, artifact_count_per_entry: int, entry_state_counts: Sequence[tuple[str, int]], pipeline_state_counts: Sequence[tuple[str, int]], observability_state_counts: Sequence[tuple[str, int]], audit_state_counts: Sequence[tuple[str, int]], accepted_labels: Sequence[str], ready_labels: Sequence[str], rejected_labels: Sequence[str], rows: Sequence[RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportRow], content_address: str) -> None:
        self.report_id = _label(report_id, "observability bundle catalog report ID")
        self.catalog_id = _label(catalog_id, "observability bundle catalog report catalog ID")
        self.catalog_address = _address(catalog_address, "observability bundle catalog report catalog address", catalog_model.CATALOG_PREFIX)
        self.entry_count = _count(entry_count, "observability bundle catalog report entry count", MAX_ROWS)
        self.accepted_count = _count(accepted_count, "observability bundle catalog report accepted count", MAX_ROWS)
        self.ready_count = _count(ready_count, "observability bundle catalog report ready count", MAX_ROWS)
        self.rejected_count = _count(rejected_count, "observability bundle catalog report rejected count", MAX_ROWS)
        self.acceptance_basis_points = _count(acceptance_basis_points, "observability bundle catalog report acceptance basis points", 10000)
        self.readiness_basis_points = _count(readiness_basis_points, "observability bundle catalog report readiness basis points", 10000)
        self.artifact_count = _count(artifact_count, "observability bundle catalog report artifact count", MAX_ROWS * len(catalog_model.bundle_model.ARTIFACT_FILES))
        self.artifact_count_per_entry = _count(artifact_count_per_entry, "observability bundle catalog report artifact count per entry", len(catalog_model.bundle_model.ARTIFACT_FILES))
        self.entry_state_counts = _distribution_mapping(entry_state_counts, ENTRY_STATES, "observability bundle catalog report entry state counts")
        self.pipeline_state_counts = _distribution_mapping(pipeline_state_counts, PIPELINE_STATES, "observability bundle catalog report pipeline state counts")
        self.observability_state_counts = _distribution_mapping(observability_state_counts, OBSERVABILITY_STATES, "observability bundle catalog report observability state counts")
        self.audit_state_counts = _distribution_mapping(audit_state_counts, AUDIT_STATES, "observability bundle catalog report audit state counts")
        self.accepted_labels = _labels(accepted_labels, "observability bundle catalog report accepted labels")
        self.ready_labels = _labels(ready_labels, "observability bundle catalog report ready labels")
        self.rejected_labels = _labels(rejected_labels, "observability bundle catalog report rejected labels")
        self.rows = tuple(rows)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if any(not isinstance(row, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportRow) for row in self.rows):
            raise ValidationError("observability bundle catalog report rows must be typed")
        if self.entry_count != len(self.rows) or self.accepted_count + self.rejected_count != self.entry_count or self.ready_count > self.accepted_count:
            raise ValidationError("observability bundle catalog report denominators are not conserved")
        if tuple(row.ordinal for row in self.rows) != tuple(range(1, self.entry_count + 1)) or tuple(row.label for row in self.rows) != tuple(sorted(row.label for row in self.rows)):
            raise ValidationError("observability bundle catalog report rows are not canonical")
        if self.artifact_count != self.entry_count * len(catalog_model.bundle_model.ARTIFACT_FILES) or self.artifact_count_per_entry != (len(catalog_model.bundle_model.ARTIFACT_FILES) if self.entry_count else 0):
            raise ValidationError("observability bundle catalog report artifact totals are not conserved")
        if self.acceptance_basis_points != _basis_points(self.accepted_count, self.entry_count) or self.readiness_basis_points != _basis_points(self.ready_count, self.entry_count):
            raise ValidationError("observability bundle catalog report ratios are not derived")
        expected_entry = _distribution(tuple(row.state for row in self.rows), ENTRY_STATES, "entry states")
        expected_pipeline = _distribution(tuple(row.pipeline_state for row in self.rows), PIPELINE_STATES, "pipeline states")
        expected_observability = _distribution(tuple(row.observability_state for row in self.rows), OBSERVABILITY_STATES, "observability states")
        expected_audit = _distribution(tuple(row.audit_state for row in self.rows), AUDIT_STATES, "audit states")
        if self.entry_state_counts != expected_entry or self.pipeline_state_counts != expected_pipeline or self.observability_state_counts != expected_observability or self.audit_state_counts != expected_audit:
            raise ValidationError("observability bundle catalog report state distributions are not derived")
        accepted = tuple(sorted(row.label for row in self.rows if row.accepted))
        ready = tuple(sorted(row.label for row in self.rows if row.state == "ready"))
        rejected = tuple(sorted(row.label for row in self.rows if not row.accepted))
        if self.accepted_labels != accepted or self.ready_labels != ready or self.rejected_labels != rejected:
            raise ValidationError("observability bundle catalog report label partitions are not derived")
        if sum(count for _, count in self.entry_state_counts) != self.entry_count or sum(count for _, count in self.pipeline_state_counts) != self.entry_count or sum(count for _, count in self.observability_state_counts) != self.entry_count or sum(count for _, count in self.audit_state_counts) != self.entry_count:
            raise ValidationError("observability bundle catalog report distributions do not conserve rows")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle catalog report content address")
        else:
            _address(self.content_address, "observability bundle catalog report content address", REPORT_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_report(self) != self.content_address):
            raise ValidationError("observability bundle catalog report address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"report_id": self.report_id, "catalog_id": self.catalog_id, "catalog_address": self.catalog_address, "entry_count": self.entry_count, "accepted_count": self.accepted_count, "ready_count": self.ready_count, "rejected_count": self.rejected_count, "acceptance_basis_points": self.acceptance_basis_points, "readiness_basis_points": self.readiness_basis_points, "artifact_count": self.artifact_count, "artifact_count_per_entry": self.artifact_count_per_entry, "entry_state_counts": self.entry_state_counts, "pipeline_state_counts": self.pipeline_state_counts, "observability_state_counts": self.observability_state_counts, "audit_state_counts": self.audit_state_counts, "accepted_labels": self.accepted_labels, "ready_labels": self.ready_labels, "rejected_labels": self.rejected_labels, "rows": tuple(row.to_dict() for row in self.rows), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in self.FIELDS if key != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReport:
        value = _mapping(value, "observability bundle catalog report")
        _strict(value, set(cls.FIELDS), "observability bundle catalog report")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog report is missing fields: {missing}")
        rows = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportRow.from_mapping(item) for item in _sequence(value["rows"], "observability bundle catalog report rows", MAX_ROWS))
        return cls(value["report_id"], value["catalog_id"], value["catalog_address"], value["entry_count"], value["accepted_count"], value["ready_count"], value["rejected_count"], value["acceptance_basis_points"], value["readiness_basis_points"], value["artifact_count"], value["artifact_count_per_entry"], _sequence(value["entry_state_counts"], "observability bundle catalog report entry state counts", len(ENTRY_STATES)), _sequence(value["pipeline_state_counts"], "observability bundle catalog report pipeline state counts", len(PIPELINE_STATES)), _sequence(value["observability_state_counts"], "observability bundle catalog report observability state counts", len(OBSERVABILITY_STATES)), _sequence(value["audit_state_counts"], "observability bundle catalog report audit state counts", len(AUDIT_STATES)), _sequence(value["accepted_labels"], "observability bundle catalog report accepted labels", MAX_LABELS), _sequence(value["ready_labels"], "observability bundle catalog report ready labels", MAX_LABELS), _sequence(value["rejected_labels"], "observability bundle catalog report rejected labels", MAX_LABELS), rows, value["content_address"])


def _report_address_body(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReport) -> dict[str, Any]:
    body = value.to_dict()
    body["content_address"] = None
    return body


def address_report(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReport) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReport):
        raise ValidationError("observability bundle catalog report address requires a typed report")
    return content_hash(_report_address_body(value), prefix=REPORT_PREFIX)


def _report_row(entry: catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportRow:
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportRow(entry.ordinal, entry.label, entry.bundle_address, entry.content_address, _accepted(entry), _entry_state(entry), entry.pipeline_state, entry.pipeline_accepted, entry.observability_state, entry.audit_state, entry.audit_accepted, entry.artifact_count, "pending:observability-bundle-catalog-report-row")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportRow(provisional.ordinal, provisional.label, provisional.bundle_address, provisional.entry_address, provisional.accepted, provisional.state, provisional.pipeline_state, provisional.pipeline_accepted, provisional.observability_state, provisional.audit_state, provisional.audit_accepted, provisional.artifact_count, address_row(provisional))


def build_report(catalog: catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog | Mapping[str, Any], *, report_id: str = DEFAULT_REPORT_ID) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReport:
    """Build a deterministic aggregate report from a verified catalog."""

    value = catalog if isinstance(catalog, catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog) else catalog_model.catalog_from_mapping(_mapping(catalog, "observability bundle catalog report catalog"))
    value = catalog_model.verify_catalog(value)
    rows = tuple(_report_row(entry) for entry in value.entries)
    body = {"report_id": _label(report_id, "observability bundle catalog report ID"), "catalog_id": value.catalog_id, "catalog_address": value.content_address, "entry_count": value.entry_count, "accepted_count": value.accepted_count, "ready_count": value.ready_count, "rejected_count": value.rejected_count, "acceptance_basis_points": _basis_points(value.accepted_count, value.entry_count), "readiness_basis_points": _basis_points(value.ready_count, value.entry_count), "artifact_count": value.entry_count * len(catalog_model.bundle_model.ARTIFACT_FILES), "artifact_count_per_entry": len(catalog_model.bundle_model.ARTIFACT_FILES) if value.entry_count else 0, "entry_state_counts": _distribution(tuple(row.state for row in rows), ENTRY_STATES, "entry states"), "pipeline_state_counts": _distribution(tuple(row.pipeline_state for row in rows), PIPELINE_STATES, "pipeline states"), "observability_state_counts": _distribution(tuple(row.observability_state for row in rows), OBSERVABILITY_STATES, "observability states"), "audit_state_counts": _distribution(tuple(row.audit_state for row in rows), AUDIT_STATES, "audit states"), "accepted_labels": tuple(sorted(row.label for row in rows if row.accepted)), "ready_labels": tuple(sorted(row.label for row in rows if row.state == "ready")), "rejected_labels": tuple(sorted(row.label for row in rows if not row.accepted)), "rows": rows}
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReport(**body, content_address="pending:observability-bundle-catalog-report")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReport(**body, content_address=address_report(provisional))


def report_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReport:
    return verify_report(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReport.from_mapping(value))


def verify_report(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReport) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReport:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReport):
        raise ValidationError("observability bundle catalog report verification requires a typed report")
    value._validate()
    if address_report(value) != value.content_address:
        raise ValidationError("observability bundle catalog report content address does not replay")
    return value


def report_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReport) -> str:
    return canonical_json(verify_report(value).to_dict())


def report_csv(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReport) -> str:
    value = verify_report(value)
    output = io.StringIO()
    fields = ("ordinal", "label", "accepted", "state", "pipeline_state", "observability_state", "audit_state", "artifact_count", "bundle_address", "entry_address", "content_address")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in value.rows:
        writer.writerow({field: row.to_dict().get(field, "") for field in fields})
    return output.getvalue()


def render_report_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReport) -> str:
    value = verify_report(value)
    lines = ["# Assurance History Observatory Observability Bundle Catalog Report", "", f"- Catalog: `{value.catalog_id}`", f"- Entries: `{value.entry_count}`", f"- Accepted: `{value.accepted_count}` ({value.acceptance_basis_points} bp)", f"- Ready: `{value.ready_count}` ({value.readiness_basis_points} bp)", f"- Rejected: `{value.rejected_count}`", f"- Artifacts: `{value.artifact_count}`", f"- Content address: `{value.content_address}`", "", "| ordinal | label | accepted | state | pipeline | observability | audit |", "| ---: | --- | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {row.ordinal} | `{row.label}` | `{row.accepted}` | `{row.state}` | `{row.pipeline_state}` | `{row.observability_state}` | `{row.audit_state}` |" for row in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportRow.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_ROWS}, "label": {"type": "string", "maxLength": 128}, "bundle_address": {"type": "string", "pattern": "^" + catalog_model.bundle_model.BUNDLE_PREFIX + ":"}, "entry_address": {"type": "string", "pattern": "^" + catalog_model.ENTRY_PREFIX + ":"}, "accepted": {"type": "boolean"}, "state": {"type": "string", "enum": list(ENTRY_STATES)}, "pipeline_state": {"type": "string", "enum": list(PIPELINE_STATES)}, "pipeline_accepted": {"type": "boolean"}, "observability_state": {"type": "string", "enum": list(OBSERVABILITY_STATES)}, "audit_state": {"type": "string", "enum": list(AUDIT_STATES)}, "audit_accepted": {"type": "boolean"}, "artifact_count": {"type": "integer", "const": len(catalog_model.bundle_model.ARTIFACT_FILES)}, "content_address": {"type": "string", "pattern": "^" + ROW_PREFIX + ":"}}}


def report_schema() -> dict[str, Any]:
    def distribution(states: Sequence[str]) -> dict[str, Any]:
        return {"type": "array", "minItems": len(states), "maxItems": len(states), "items": {"type": "array", "minItems": 2, "maxItems": 2}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReport.FIELDS), "properties": {"report_id": {"type": "string", "maxLength": 128}, "catalog_id": {"type": "string", "maxLength": 128}, "catalog_address": {"type": "string", "pattern": "^" + catalog_model.CATALOG_PREFIX + ":"}, "entry_count": {"type": "integer", "minimum": 0, "maximum": MAX_ROWS}, "accepted_count": {"type": "integer", "minimum": 0, "maximum": MAX_ROWS}, "ready_count": {"type": "integer", "minimum": 0, "maximum": MAX_ROWS}, "rejected_count": {"type": "integer", "minimum": 0, "maximum": MAX_ROWS}, "acceptance_basis_points": {"type": "integer", "minimum": 0, "maximum": 10000}, "readiness_basis_points": {"type": "integer", "minimum": 0, "maximum": 10000}, "artifact_count": {"type": "integer", "minimum": 0, "maximum": MAX_ROWS * len(catalog_model.bundle_model.ARTIFACT_FILES)}, "artifact_count_per_entry": {"type": "integer", "minimum": 0, "maximum": len(catalog_model.bundle_model.ARTIFACT_FILES)}, "entry_state_counts": distribution(ENTRY_STATES), "pipeline_state_counts": distribution(PIPELINE_STATES), "observability_state_counts": distribution(OBSERVABILITY_STATES), "audit_state_counts": distribution(AUDIT_STATES), "accepted_labels": {"type": "array", "maxItems": MAX_LABELS, "items": {"type": "string"}}, "ready_labels": {"type": "array", "maxItems": MAX_LABELS, "items": {"type": "string"}}, "rejected_labels": {"type": "array", "maxItems": MAX_LABELS, "items": {"type": "string"}}, "rows": {"type": "array", "maxItems": MAX_ROWS, "items": row_schema()}, "content_address": {"type": "string", "pattern": "^" + REPORT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "report_prefix": REPORT_PREFIX, "row_prefix": ROW_PREFIX, "entry_states": ENTRY_STATES, "pipeline_states": PIPELINE_STATES, "observability_states": OBSERVABILITY_STATES, "audit_states": AUDIT_STATES, "limits": {"max_rows": MAX_ROWS, "max_labels": MAX_LABELS, "basis_point_scale": 10000, "artifact_count_per_entry": len(catalog_model.bundle_model.ARTIFACT_FILES)}, "features": ("verified catalog report input", "acceptance and readiness denominators", "integer basis-point ratios", "entry pipeline observability and audit distributions", "accepted ready and rejected label partitions", "path-free row projections", "content-addressed report and row replay", "JSON CSV and Markdown exports"), "schemas": ("row", "report")}


__all__ = [
    "AUDIT_STATES",
    "BOUNDARY",
    "DEFAULT_REPORT_ID",
    "ENTRY_STATES",
    "MAX_LABELS",
    "MAX_ROWS",
    "OBSERVABILITY_STATES",
    "PIPELINE_STATES",
    "REPORT_PREFIX",
    "ROW_PREFIX",
    "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReport",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportRow",
    "address_report",
    "address_row",
    "build_report",
    "capabilities",
    "report_csv",
    "report_from_mapping",
    "report_json",
    "report_schema",
    "render_report_markdown",
    "row_schema",
    "verify_report",
]
