"""Sanitized JSON, CSV, and Markdown bundles for C05–C08 evidence."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .reference_annotation_fixture_eval import ReferenceAnnotationEvaluationReport
from .reference_annotation_public_data import (
    REFERENCE_ANNOTATION_EVIDENCE_BOUNDARY,
    ReferenceAnnotationFixture,
    ReferenceAnnotationOperation,
    ReferenceAnnotationRole,
    default_reference_annotation_fixture,
)
from .serialization import content_hash, jsonable, require_non_empty


class ReferenceAnnotationBundleFormat(StrEnum):
    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationBundleEntry:
    entry_id: str
    record_id: str
    capability_id: str
    operation: ReferenceAnnotationOperation
    role: ReferenceAnnotationRole
    context_key: str
    state: str
    issue_codes: tuple[str, ...]
    match_count: int
    source_ids: tuple[str, ...]
    evidence_boundary: str
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "entry_id",
            "record_id",
            "capability_id",
            "context_key",
            "state",
            "evidence_boundary",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.match_count < 0:
            raise ValidationError("annotation bundle match_count cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationBundle:
    bundle_id: str
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    published: bool
    entries: tuple[ReferenceAnnotationBundleEntry, ...]
    content_address: str

    @property
    def accepted_count(self) -> int:
        return sum(entry.state == "supported" for entry in self.entries)

    @property
    def review_count(self) -> int:
        return len(self.entries) - self.accepted_count

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "entry_count": len(self.entries),
            "accepted_count": self.accepted_count,
            "review_count": self.review_count,
        }


class ReferenceAnnotationBundleBuilder:
    """Build content-addressed, non-raw projections of evaluation receipts."""

    def build(
        self,
        report: ReferenceAnnotationEvaluationReport,
        *,
        fixture: ReferenceAnnotationFixture | None = None,
        accepted_only: bool = False,
        bundle_id: str = "reference-annotation-bundle",
    ) -> ReferenceAnnotationBundle:
        selected = fixture or default_reference_annotation_fixture()
        source_ids_by_record = {record.record_id: record.source_ids for record in selected.records}
        entries: list[ReferenceAnnotationBundleEntry] = []
        for receipt in report.receipts:
            if accepted_only and receipt.resolution_state != "supported":
                continue
            body = {
                "entry_id": f"{bundle_id}:{receipt.record_id}",
                "record_id": receipt.record_id,
                "capability_id": receipt.capability_id,
                "operation": receipt.operation,
                "role": receipt.role,
                "context_key": receipt.context_key,
                "state": receipt.resolution_state,
                "issue_codes": receipt.observed_issue_codes,
                "match_count": receipt.match_count,
                "source_ids": source_ids_by_record.get(receipt.record_id, ()),
                "evidence_boundary": REFERENCE_ANNOTATION_EVIDENCE_BOUNDARY,
            }
            entries.append(
                ReferenceAnnotationBundleEntry(**body, content_address=content_hash(body))
            )
        entries_tuple = tuple(sorted(entries, key=lambda entry: entry.entry_id))
        body = {
            "bundle_id": bundle_id,
            "fixture_id": report.fixture_id,
            "fixture_version": report.fixture_version,
            "context_key": report.context_key,
            "evidence_boundary": REFERENCE_ANNOTATION_EVIDENCE_BOUNDARY,
            "published": bool(accepted_only and report.accepted),
            "entries": entries_tuple,
        }
        return ReferenceAnnotationBundle(**body, content_address=content_hash(body))

    def verify(self, bundle: ReferenceAnnotationBundle) -> tuple[str, ...]:
        failures: list[str] = []
        if bundle.evidence_boundary != REFERENCE_ANNOTATION_EVIDENCE_BOUNDARY:
            failures.append("boundary")
        if len({entry.entry_id for entry in bundle.entries}) != len(bundle.entries):
            failures.append("entry-identity")
        if any(
            entry.content_address
            != content_hash(
                {key: value for key, value in entry.to_dict().items() if key != "content_address"}
            )
            for entry in bundle.entries
        ):
            failures.append("entry-address")
        body = {
            "bundle_id": bundle.bundle_id,
            "fixture_id": bundle.fixture_id,
            "fixture_version": bundle.fixture_version,
            "context_key": bundle.context_key,
            "evidence_boundary": bundle.evidence_boundary,
            "published": bundle.published,
            "entries": bundle.entries,
        }
        if bundle.content_address != content_hash(body):
            failures.append("bundle-address")
        if bundle.published and any(entry.state != "supported" for entry in bundle.entries):
            failures.append("published-review-entry")
        return tuple(failures)

    def render(
        self, bundle: ReferenceAnnotationBundle, format: ReferenceAnnotationBundleFormat | str
    ) -> str:
        selected = (
            format
            if isinstance(format, ReferenceAnnotationBundleFormat)
            else ReferenceAnnotationBundleFormat(format)
        )
        if selected is ReferenceAnnotationBundleFormat.JSON:
            return json.dumps(bundle.to_dict(), indent=2, sort_keys=True) + "\n"
        if selected is ReferenceAnnotationBundleFormat.CSV:
            output = io.StringIO()
            fields = (
                "entry_id",
                "record_id",
                "capability_id",
                "operation",
                "role",
                "context_key",
                "state",
                "issue_codes",
                "match_count",
                "source_ids",
                "evidence_boundary",
                "content_address",
            )
            writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            for entry in bundle.entries:
                row = entry.to_dict()
                row["issue_codes"] = "|".join(entry.issue_codes)
                row["source_ids"] = "|".join(entry.source_ids)
                writer.writerow({field: row[field] for field in fields})
            return output.getvalue()
        lines = [
            f"# {bundle.bundle_id}",
            "",
            f"- Fixture: `{bundle.fixture_id}`",
            f"- Version: `{bundle.fixture_version}`",
            f"- Context: `{bundle.context_key}`",
            f"- Boundary: `{bundle.evidence_boundary}`",
            f"- Published: `{str(bundle.published).lower()}`",
            f"- Entries: `{len(bundle.entries)}`",
            "",
            "| Record | Capability | Operation | Role | State | Issues | Matches | Address |",
            "|---|---|---|---|---|---|---:|---|",
        ]
        for entry in bundle.entries:
            issues = ", ".join(entry.issue_codes) or "—"
            lines.append(
                f"| {entry.record_id} | {entry.capability_id} | {entry.operation.value} | {entry.role.value} | {entry.state} | {issues} | {entry.match_count} | `{entry.content_address}` |"  # noqa: E501
            )
        return "\n".join(lines) + "\n"

    def write(
        self,
        bundle: ReferenceAnnotationBundle,
        path: str | Path,
        format: ReferenceAnnotationBundleFormat | str | None = None,
    ) -> Path:
        output = Path(path)
        selected = format or output.suffix.lstrip(".") or "json"
        if selected == "md":
            selected = ReferenceAnnotationBundleFormat.MARKDOWN
        output.write_text(self.render(bundle, selected), encoding="utf-8")
        return output


__all__ = [
    "ReferenceAnnotationBundle",
    "ReferenceAnnotationBundleBuilder",
    "ReferenceAnnotationBundleEntry",
    "ReferenceAnnotationBundleFormat",
]
