"""Sanitized JSON, CSV, and Markdown bundles for C05-C08."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .specimen_beta_frontier_fixture_eval import evaluate_specimen_beta_frontier_fixture
from .specimen_beta_frontier_public_data import SpecimenBetaFrontierFixtureCatalog
from .specimen_beta_frontier_quality_gate import evaluate_specimen_beta_frontier_quality_gate


class SpecimenBetaFrontierBundleFormat(StrEnum):
    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"


@dataclass(frozen=True, slots=True)
class SpecimenBetaFrontierBundleEntry:
    """One compact entry with no raw adapter payload."""

    entry_id: str
    record_id: str
    specimen_identifier: str
    operation: str
    fixture_state: str
    result_state: str
    issue_codes: tuple[str, ...]
    source_ids: tuple[str, ...]
    context_key: str
    record_address: str
    result_address: str

    def __post_init__(self) -> None:
        for name in (
            "entry_id",
            "record_id",
            "specimen_identifier",
            "operation",
            "fixture_state",
            "result_state",
            "context_key",
            "record_address",
            "result_address",
        ):
            require_non_empty(str(getattr(self, name)), f"beta bundle entry {name}")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenBetaFrontierEvidenceBundle:
    """Addressed bundle envelope."""

    schema: str
    bundle_id: str
    fixture_id: str
    state: str
    context_key: str
    source_ids: tuple[str, ...]
    entries: tuple[SpecimenBetaFrontierBundleEntry, ...]
    quality_address: str
    lineage_address: str
    content_address: str

    @property
    def entry_count(self) -> int:
        return len(self.entries)

    def _address_body(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "bundle_id": self.bundle_id,
            "fixture_id": self.fixture_id,
            "state": self.state,
            "context_key": self.context_key,
            "source_ids": self.source_ids,
            "entries": self.entries,
            "quality_address": self.quality_address,
            "lineage_address": self.lineage_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"entry_count": self.entry_count}


class SpecimenBetaFrontierEvidenceBundleBuilder:
    """Build and verify compact release projections."""

    schema = "specimen-beta-frontier-bundle-v1"

    def build(
        self,
        catalog: SpecimenBetaFrontierFixtureCatalog,
        *,
        bundle_id: str = "specimen-beta-frontier-c05-c08",
        allow_review: bool = False,
    ) -> SpecimenBetaFrontierEvidenceBundle:
        require_non_empty(bundle_id, "beta bundle ID")
        evaluation = evaluate_specimen_beta_frontier_fixture(catalog)
        quality = evaluate_specimen_beta_frontier_quality_gate(catalog)
        if not evaluation.passed or not quality.passed:
            if not allow_review:
                raise ValidationError("beta evidence bundle requires a passing quality gate")
            state = "review"
        else:
            state = "accepted"
        from .specimen_beta_frontier_lineage import build_specimen_beta_frontier_lineage

        lineage = build_specimen_beta_frontier_lineage(catalog)
        receipt_by_id = {receipt.record_id: receipt for receipt in evaluation.receipts}
        entries = tuple(
            SpecimenBetaFrontierBundleEntry(
                entry_id=f"entry:{record.record_id}",
                record_id=record.record_id,
                specimen_identifier=record.record_id,
                operation=record.operation.value,
                fixture_state=record.expected_fixture_state.value,
                result_state=receipt_by_id[record.record_id].observed_result_state,
                issue_codes=receipt_by_id[record.record_id].observed_issue_codes,
                source_ids=record.source_ids,
                context_key=catalog.context_key,
                record_address=record.content_address,
                result_address=receipt_by_id[record.record_id].output_address,
            )
            for record in catalog.records
        )
        body = {
            "schema": self.schema,
            "bundle_id": bundle_id,
            "fixture_id": catalog.fixture_id,
            "state": state,
            "context_key": catalog.context_key,
            "source_ids": catalog.source_ids,
            "entries": entries,
            "quality_address": quality.content_address,
            "lineage_address": lineage.content_address,
        }
        return SpecimenBetaFrontierEvidenceBundle(
            schema=self.schema,
            bundle_id=bundle_id,
            fixture_id=catalog.fixture_id,
            state=state,
            context_key=catalog.context_key,
            source_ids=catalog.source_ids,
            entries=entries,
            quality_address=quality.content_address,
            lineage_address=lineage.content_address,
            content_address=content_hash(body),
        )

    def verify(self, bundle: SpecimenBetaFrontierEvidenceBundle) -> bool:
        if bundle.schema != self.schema:
            return False
        if bundle.state not in {"accepted", "review"}:
            return False
        if bundle.entry_count != len(bundle.entries):
            return False
        if len({entry.entry_id for entry in bundle.entries}) != bundle.entry_count:
            return False
        if any(entry.context_key != bundle.context_key for entry in bundle.entries):
            return False
        if any(not entry.record_address.startswith("sha256:") for entry in bundle.entries):
            return False
        if any(not entry.result_address.startswith("sha256:") for entry in bundle.entries):
            return False
        return bundle.content_address == content_hash(bundle._address_body())

    def write(
        self,
        bundle: SpecimenBetaFrontierEvidenceBundle,
        path: str | Path,
        *,
        format: SpecimenBetaFrontierBundleFormat = SpecimenBetaFrontierBundleFormat.JSON,
    ) -> None:
        destination = Path(path)
        if format == SpecimenBetaFrontierBundleFormat.JSON:
            text = json.dumps(bundle.to_dict(), indent=2, sort_keys=True) + "\n"
        elif format == SpecimenBetaFrontierBundleFormat.CSV:
            text = _csv_text(bundle)
        elif format == SpecimenBetaFrontierBundleFormat.MARKDOWN:
            text = _markdown_text(bundle)
        else:
            raise ValidationError(f"unsupported beta bundle format: {format}")
        destination.write_text(text, encoding="utf-8")


def _csv_text(bundle: SpecimenBetaFrontierEvidenceBundle) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "entry_id",
            "record_id",
            "specimen_identifier",
            "operation",
            "fixture_state",
            "result_state",
            "issue_codes",
            "source_ids",
            "context_key",
            "record_address",
            "result_address",
        )
    )
    for entry in bundle.entries:
        writer.writerow(
            (
                entry.entry_id,
                entry.record_id,
                entry.specimen_identifier,
                entry.operation,
                entry.fixture_state,
                entry.result_state,
                ";".join(entry.issue_codes),
                ";".join(entry.source_ids),
                entry.context_key,
                entry.record_address,
                entry.result_address,
            )
        )
    return output.getvalue()


def _markdown_text(bundle: SpecimenBetaFrontierEvidenceBundle) -> str:
    lines = [
        "# Specimen beta frontier evidence bundle",
        "",
        f"- Bundle: `{bundle.bundle_id}`",
        f"- Fixture: `{bundle.fixture_id}`",
        f"- State: `{bundle.state}`",
        f"- Context: `{bundle.context_key}`",
        f"- Quality address: `{bundle.quality_address}`",
        f"- Lineage address: `{bundle.lineage_address}`",
        f"- Content address: `{bundle.content_address}`",
        "",
        "| Record | Operation | Fixture state | Result state | Issues |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| `{entry.record_id}` | `{entry.operation}` | `{entry.fixture_state}` | "
        f"`{entry.result_state}` | `{';'.join(entry.issue_codes)}` |"
        for entry in bundle.entries
    )
    return "\n".join(lines) + "\n"


def build_specimen_beta_frontier_bundle(
    catalog: SpecimenBetaFrontierFixtureCatalog,
    *,
    bundle_id: str = "specimen-beta-frontier-c05-c08",
    allow_review: bool = False,
) -> SpecimenBetaFrontierEvidenceBundle:
    """Convenience function used by package consumers."""

    return SpecimenBetaFrontierEvidenceBundleBuilder().build(
        catalog,
        bundle_id=bundle_id,
        allow_review=allow_review,
    )


__all__ = [
    "SpecimenBetaFrontierBundleEntry",
    "SpecimenBetaFrontierBundleFormat",
    "SpecimenBetaFrontierEvidenceBundle",
    "SpecimenBetaFrontierEvidenceBundleBuilder",
    "build_specimen_beta_frontier_bundle",
]
