"""Sanitized JSON, CSV, and Markdown bundles for Domain 03 C09-C12."""

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
from .specimen_lineage_fixture_eval import evaluate_specimen_lineage_fixture
from .specimen_lineage_lineage import build_specimen_lineage_lineage
from .specimen_lineage_public_data import SpecimenLineageFixtureCatalog
from .specimen_lineage_quality_gate import evaluate_specimen_lineage_quality_gate


class SpecimenLineageBundleFormat(StrEnum):
    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"


@dataclass(frozen=True, slots=True)
class SpecimenLineageBundleEntry:
    """One compact release entry without raw adapter input."""

    entry_id: str
    record_id: str
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
            "operation",
            "fixture_state",
            "result_state",
            "context_key",
            "record_address",
            "result_address",
        ):
            require_non_empty(str(getattr(self, name)), f"lineage bundle entry {name}")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenLineageEvidenceBundle:
    """Addressed bundle envelope."""

    schema: str
    bundle_id: str
    fixture_id: str
    state: str
    context_key: str
    source_ids: tuple[str, ...]
    entries: tuple[SpecimenLineageBundleEntry, ...]
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


class SpecimenLineageEvidenceBundleBuilder:
    """Build, verify, and write compact release projections."""

    schema = "specimen-lineage-bundle-v1"

    def build(
        self,
        catalog: SpecimenLineageFixtureCatalog,
        *,
        bundle_id: str = "specimen-lineage-c09-c12",
        allow_review: bool = False,
    ) -> SpecimenLineageEvidenceBundle:
        require_non_empty(bundle_id, "lineage bundle ID")
        quality = evaluate_specimen_lineage_quality_gate(catalog)
        if not quality.passed and not allow_review:
            raise ValidationError("cannot build lineage bundle before quality gate passes")
        evaluation = evaluate_specimen_lineage_fixture(catalog)
        graph = build_specimen_lineage_lineage(catalog)
        receipts = {receipt.record_id: receipt for receipt in evaluation.receipts}
        entries = tuple(
            SpecimenLineageBundleEntry(
                entry_id="entry:" + content_hash(record.record_id).split(":", 1)[1][:24],
                record_id=record.record_id,
                operation=record.operation.value,
                fixture_state=record.expected_fixture_state.value,
                result_state=receipts[record.record_id].observed_result_state,
                issue_codes=receipts[record.record_id].observed_issue_codes,
                source_ids=record.source_ids,
                context_key=record.context_key,
                record_address=record.content_address,
                result_address=receipts[record.record_id].output_address,
            )
            for record in catalog.records
        )
        state = quality.state
        body = {
            "schema": self.schema,
            "bundle_id": bundle_id,
            "fixture_id": catalog.fixture_id,
            "state": state,
            "context_key": catalog.context_key,
            "source_ids": catalog.source_ids,
            "entries": entries,
            "quality_address": quality.content_address,
            "lineage_address": graph.content_address,
        }
        return SpecimenLineageEvidenceBundle(
            schema=self.schema,
            bundle_id=bundle_id,
            fixture_id=catalog.fixture_id,
            state=state,
            context_key=catalog.context_key,
            source_ids=catalog.source_ids,
            entries=entries,
            quality_address=quality.content_address,
            lineage_address=graph.content_address,
            content_address=content_hash(body),
        )

    def verify(self, bundle: SpecimenLineageEvidenceBundle) -> bool:
        """Verify the envelope address and all entry addresses."""

        if bundle.content_address != content_hash(bundle._address_body()):
            return False
        if len(bundle.entries) != 12:
            return False
        if any(not entry.record_address.startswith("sha256:") for entry in bundle.entries):
            return False
        if any(not entry.result_address.startswith("sha256:") for entry in bundle.entries):
            return False
        if any(entry.context_key != bundle.context_key for entry in bundle.entries):
            return False
        return True

    def write(
        self,
        bundle: SpecimenLineageEvidenceBundle,
        path: str | Path,
        *,
        format: SpecimenLineageBundleFormat = SpecimenLineageBundleFormat.JSON,
    ) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if format == SpecimenLineageBundleFormat.JSON:
            destination.write_text(
                json.dumps(bundle.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            return
        if format == SpecimenLineageBundleFormat.CSV:
            destination.write_text(self._csv(bundle), encoding="utf-8")
            return
        if format == SpecimenLineageBundleFormat.MARKDOWN:
            destination.write_text(self._markdown(bundle), encoding="utf-8")
            return
        raise ValidationError(f"unsupported lineage bundle format: {format}")

    @staticmethod
    def _csv(bundle: SpecimenLineageEvidenceBundle) -> str:
        output = io.StringIO()
        fields = (
            "entry_id",
            "record_id",
            "operation",
            "fixture_state",
            "result_state",
            "issue_codes",
            "source_ids",
            "context_key",
            "record_address",
            "result_address",
        )
        writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for entry in bundle.entries:
            row = entry.to_dict()
            row["issue_codes"] = "|".join(entry.issue_codes)
            row["source_ids"] = "|".join(entry.source_ids)
            writer.writerow(row)
        return output.getvalue()

    @staticmethod
    def _markdown(bundle: SpecimenLineageEvidenceBundle) -> str:
        lines = [
            f"# {bundle.bundle_id}",
            "",
            f"- Fixture: `{bundle.fixture_id}`",
            f"- State: `{bundle.state}`",
            f"- Context: `{bundle.context_key}`",
            f"- Entries: `{bundle.entry_count}`",
            f"- Quality address: `{bundle.quality_address}`",
            f"- Lineage address: `{bundle.lineage_address}`",
            "",
            "| Record | Operation | Fixture state | Result state | Issues |",
            "| --- | --- | --- | --- | --- |",
        ]
        for entry in bundle.entries:
            issues = ", ".join(entry.issue_codes) if entry.issue_codes else "none"
            lines.append(
                f"| `{entry.record_id}` | `{entry.operation}` | `{entry.fixture_state}` | "
                f"`{entry.result_state}` | `{issues}` |"
            )
        return "\n".join(lines) + "\n"


__all__ = [
    "SpecimenLineageBundleEntry",
    "SpecimenLineageBundleFormat",
    "SpecimenLineageEvidenceBundle",
    "SpecimenLineageEvidenceBundleBuilder",
]
