"""Compact evidence bundle builders for Domain 04 C09–C12."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .reference_governance_fixture_eval import ReferenceGovernanceEvaluationReport
from .reference_governance_public_data import ReferenceGovernanceFixture, ReferenceGovernanceRole
from .serialization import content_hash, jsonable, require_non_empty


class ReferenceGovernanceBundleFormat(StrEnum):
    """Supported human- and machine-readable bundle formats."""

    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"


@dataclass(frozen=True, slots=True)
class ReferenceGovernanceBundleEntry:
    """One sanitized receipt summary in a bundle."""

    record_id: str
    capability_id: str
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
class ReferenceGovernanceBundle:
    """A bounded release-oriented view of execution receipts."""

    fixture_id: str
    fixture_version: str
    context_key: str
    output_format: ReferenceGovernanceBundleFormat
    accepted_only: bool
    entries: tuple[ReferenceGovernanceBundleEntry, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.entries) and all(entry.accepted for entry in self.entries)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


class ReferenceGovernanceBundleBuilder:
    """Build, render, write, and verify compact receipt bundles."""

    def build(
        self,
        evaluation: ReferenceGovernanceEvaluationReport,
        *,
        fixture: ReferenceGovernanceFixture,
        output_format: ReferenceGovernanceBundleFormat = ReferenceGovernanceBundleFormat.JSON,
        accepted_only: bool = False,
    ) -> ReferenceGovernanceBundle:
        entries: list[ReferenceGovernanceBundleEntry] = []
        for receipt in evaluation.receipts:
            if accepted_only and receipt.role is not ReferenceGovernanceRole.POSITIVE:
                continue
            body = {
                "record_id": receipt.record_id,
                "capability_id": receipt.capability_id,
                "operation": receipt.operation,
                "role": receipt.role,
                "state": receipt.adapter_state,
                "primary_count": receipt.primary_count,
                "secondary_count": receipt.secondary_count,
                "issue_codes": receipt.observed_issue_codes,
                "accepted": receipt.accepted,
            }
            entries.append(
                ReferenceGovernanceBundleEntry(**body, content_address=content_hash(body))
            )
        body = {
            "fixture_id": fixture.fixture_id,
            "fixture_version": fixture.fixture_version,
            "context_key": fixture.context_key,
            "output_format": output_format,
            "accepted_only": accepted_only,
            "entries": entries,
        }
        return ReferenceGovernanceBundle(**body, content_address=content_hash(body))

    def render(self, bundle: ReferenceGovernanceBundle) -> str:
        """Render without including original payload collections."""

        if bundle.output_format is ReferenceGovernanceBundleFormat.JSON:
            return json.dumps(bundle.to_dict(), indent=2, sort_keys=True) + "\n"
        rows = [entry.to_dict() for entry in bundle.entries]
        if bundle.output_format is ReferenceGovernanceBundleFormat.CSV:
            output = io.StringIO()
            fields = (
                "record_id",
                "capability_id",
                "operation",
                "role",
                "state",
                "primary_count",
                "secondary_count",
                "issue_codes",
                "accepted",
                "content_address",
            )
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                row["issue_codes"] = "|".join(row["issue_codes"])
                writer.writerow(row)
            return output.getvalue()
        if bundle.output_format is ReferenceGovernanceBundleFormat.MARKDOWN:
            lines = [
                f"# Reference governance bundle: {bundle.fixture_id}",
                "",
                f"Fixture version: `{bundle.fixture_version}`  ",
                f"Context: `{bundle.context_key}`  ",
                "",
                "| Record | Capability | Operation | Role | State | Counts | Accepted |",
                "|---|---|---|---|---|---:|---|",
            ]
            lines.extend(
                f"| {entry.record_id} | {entry.capability_id} | {entry.operation} | "
                f"{entry.role} | {entry.state} | {entry.primary_count}/{entry.secondary_count} | "
                f"{entry.accepted} |"
                for entry in bundle.entries
            )
            return "\n".join(lines) + "\n"
        raise ValidationError(f"unsupported governance bundle format: {bundle.output_format}")

    def verify(self, bundle: ReferenceGovernanceBundle) -> tuple[str, ...]:
        """Return stable verification failures; an empty tuple is valid."""

        failures: list[str] = []
        if not bundle.entries:
            failures.append("empty-bundle")
        if bundle.accepted_only and any(entry.role != "positive" for entry in bundle.entries):
            failures.append("accepted-only-contamination")
        if any(entry.role == "positive" and entry.state != "supported" for entry in bundle.entries):
            failures.append("positive-not-supported")
        if any(
            "records" in entry.to_dict() or "restrictions" in entry.to_dict()
            for entry in bundle.entries
        ):
            failures.append("input-collection-leak")
        if bundle.content_address != content_hash(
            {
                key: value
                for key, value in bundle.to_dict().items()
                if key != "accepted" and key != "content_address"
            }
        ):
            failures.append("bundle-address")
        for entry in bundle.entries:
            body = {
                key: value for key, value in entry.to_dict().items() if key != "content_address"
            }
            if entry.content_address != content_hash(body):
                failures.append(f"entry-address:{entry.record_id}")
        return tuple(failures)

    def write(self, bundle: ReferenceGovernanceBundle, path: str | Path) -> None:
        """Write a rendered bundle after verification."""

        failures = self.verify(bundle)
        if failures:
            raise ValidationError(f"cannot write invalid governance bundle: {', '.join(failures)}")
        output = Path(path)
        require_non_empty(str(output), "bundle output path")
        output.write_text(self.render(bundle), encoding="utf-8")


__all__ = [
    "ReferenceGovernanceBundle",
    "ReferenceGovernanceBundleBuilder",
    "ReferenceGovernanceBundleEntry",
    "ReferenceGovernanceBundleFormat",
]
