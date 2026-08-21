"""Compact release bundles for accepted Domain 05 regulatory receipts."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .regulatory_atlas_fixture_eval import RegulatoryAtlasEvaluationReport
from .regulatory_atlas_public_data import RegulatoryAtlasFixture, RegulatoryAtlasRole
from .serialization import content_hash, jsonable, require_non_empty


class RegulatoryAtlasBundleFormat(StrEnum):
    """Machine and reviewer-oriented renderings."""

    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"


@dataclass(frozen=True, slots=True)
class RegulatoryAtlasBundleEntry:
    """Sanitized receipt summary with no executable input payload."""

    record_id: str
    operation: str
    role: str
    state: str
    primary_count: int
    secondary_count: int
    issue_codes: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RegulatoryAtlasBundle:
    """Bounded evidence release view."""

    fixture_id: str
    fixture_version: str
    context_key: str
    output_format: RegulatoryAtlasBundleFormat
    accepted_only: bool
    entries: tuple[RegulatoryAtlasBundleEntry, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.entries) and all(entry.accepted for entry in self.entries)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


class RegulatoryAtlasBundleBuilder:
    """Build, render, verify, and write bounded receipt bundles."""

    def build(
        self,
        evaluation: RegulatoryAtlasEvaluationReport,
        *,
        fixture: RegulatoryAtlasFixture,
        output_format: RegulatoryAtlasBundleFormat = RegulatoryAtlasBundleFormat.JSON,
        accepted_only: bool = False,
    ) -> RegulatoryAtlasBundle:
        entries: list[RegulatoryAtlasBundleEntry] = []
        for receipt in evaluation.receipts:
            if accepted_only and receipt.role is not RegulatoryAtlasRole.POSITIVE:
                continue
            body = {
                "record_id": receipt.record_id,
                "operation": receipt.operation,
                "role": receipt.role,
                "state": receipt.adapter_state,
                "primary_count": receipt.primary_count,
                "secondary_count": receipt.secondary_count,
                "issue_codes": receipt.observed_issue_codes,
                "accepted": receipt.accepted,
            }
            entries.append(RegulatoryAtlasBundleEntry(**body, content_address=content_hash(body)))
        body = {
            "fixture_id": fixture.fixture_id,
            "fixture_version": fixture.fixture_version,
            "context_key": fixture.context_key,
            "output_format": output_format,
            "accepted_only": accepted_only,
            "entries": entries,
        }
        return RegulatoryAtlasBundle(**body, content_address=content_hash(body))

    def render(self, bundle: RegulatoryAtlasBundle) -> str:
        """Render a verified-safe bundle without raw input text."""

        if bundle.output_format is RegulatoryAtlasBundleFormat.JSON:
            return json.dumps(bundle.to_dict(), indent=2, sort_keys=True) + "\n"
        rows = [entry.to_dict() for entry in bundle.entries]
        if bundle.output_format is RegulatoryAtlasBundleFormat.CSV:
            output = io.StringIO()
            fields = [
                "record_id",
                "operation",
                "role",
                "state",
                "primary_count",
                "secondary_count",
                "issue_codes",
                "accepted",
                "content_address",
            ]
            writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            for row in rows:
                row["issue_codes"] = "|".join(row["issue_codes"])
                writer.writerow(row)
            return output.getvalue()
        if bundle.output_format is RegulatoryAtlasBundleFormat.MARKDOWN:
            lines = [
                f"# Regulatory atlas bundle: {bundle.fixture_id}",
                "",
                f"Fixture version: `{bundle.fixture_version}`  ",
                f"Context: `{bundle.context_key}`  ",
                f"Accepted only: `{bundle.accepted_only}`  ",
                "",
                "| Record | Operation | Role | State | Counts | Issues | Accepted |",
                "|---|---|---|---|---:|---|---|",
            ]
            lines.extend(
                f"| {entry.record_id} | {entry.operation} | {entry.role} | {entry.state} | "
                f"{entry.primary_count}/{entry.secondary_count} | {', '.join(entry.issue_codes) or 'none'} | {entry.accepted} |"
                for entry in bundle.entries
            )
            return "\n".join(lines) + "\n"
        raise ValidationError(f"unsupported regulatory atlas bundle format: {bundle.output_format}")

    def verify(self, bundle: RegulatoryAtlasBundle) -> tuple[str, ...]:
        """Return stable verification failures; empty means valid."""

        failures: list[str] = []
        if not bundle.entries:
            failures.append("empty-bundle")
        if bundle.accepted_only and any(entry.role != "positive" for entry in bundle.entries):
            failures.append("accepted-only-contamination")
        if any(entry.role == "positive" and entry.state != "supported" for entry in bundle.entries):
            failures.append("positive-not-supported")
        if any(
            {"payload", "input_text", "records", "restrictions"} & set(entry.to_dict())
            for entry in bundle.entries
        ):
            failures.append("input-collection-leak")
        expected = {
            key: value
            for key, value in bundle.to_dict().items()
            if key not in {"accepted", "content_address"}
        }
        if bundle.content_address != content_hash(expected):
            failures.append("bundle-address")
        for entry in bundle.entries:
            body = {
                key: value for key, value in entry.to_dict().items() if key != "content_address"
            }
            if entry.content_address != content_hash(body):
                failures.append(f"entry-address:{entry.record_id}")
        return tuple(failures)

    def write(self, bundle: RegulatoryAtlasBundle, path: str | Path) -> None:
        failures = self.verify(bundle)
        if failures:
            raise ValidationError(
                f"cannot write invalid regulatory atlas bundle: {', '.join(failures)}"
            )
        output = Path(path)
        require_non_empty(str(output), "regulatory atlas bundle output path")
        output.write_text(self.render(bundle), encoding="utf-8")


__all__ = [
    "RegulatoryAtlasBundle",
    "RegulatoryAtlasBundleBuilder",
    "RegulatoryAtlasBundleEntry",
    "RegulatoryAtlasBundleFormat",
]
