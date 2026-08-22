"""Evidence bundle assembly for accepted and reviewable release receipts."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .reference_release_frontier_public_data import ReferenceReleaseFixture
from .reference_release_frontier_release import ReferenceReleaseManifest
from .reference_release_frontier_runtime import ReferenceReleaseRuntimeReport
from .serialization import content_hash, jsonable, require_non_empty


class ReferenceReleaseBundleFormat(StrEnum):
    """Supported deterministic bundle renderings."""

    JSON = "json"
    NDJSON = "ndjson"
    CSV = "csv"


@dataclass(frozen=True, slots=True)
class ReferenceReleaseBundleEntry:
    """Sanitized receipt row in a release bundle."""

    record_id: str
    operation: str
    role: str
    state: str
    accepted: bool
    issue_codes: tuple[str, ...]
    receipt_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseEvidenceBundle:
    """Versioned evidence bundle with stable entries and output format."""

    bundle_id: str
    fixture_id: str
    fixture_version: str
    context_key: str
    output_format: ReferenceReleaseBundleFormat
    accepted_only: bool
    entries: tuple[ReferenceReleaseBundleEntry, ...]
    manifest_address: str
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.entries) and all(
            item.content_address.startswith("bundle-entry:") for item in self.entries
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def _entry(execution: Any) -> ReferenceReleaseBundleEntry:
    body = {
        "record_id": execution.record_id,
        "operation": execution.operation.value,
        "role": execution.role.value,
        "state": execution.state,
        "accepted": execution.accepted,
        "issue_codes": execution.issue_codes,
        "receipt_address": execution.content_address,
    }
    return ReferenceReleaseBundleEntry(
        **body, content_address=content_hash(body, prefix="bundle-entry")
    )


class ReferenceReleaseBundleBuilder:
    """Build, verify, and render a release bundle without raw operation rows."""

    def build(
        self,
        runtime: ReferenceReleaseRuntimeReport,
        manifest: ReferenceReleaseManifest,
        *,
        fixture: ReferenceReleaseFixture,
        bundle_id: str = "reference-release-frontier-bundle",
        accepted_only: bool = True,
        output_format: ReferenceReleaseBundleFormat = ReferenceReleaseBundleFormat.JSON,
    ) -> ReferenceReleaseEvidenceBundle:
        require_non_empty(bundle_id, "bundle_id")
        selected = tuple(
            item for item in runtime.evaluation.executions if not accepted_only or item.accepted
        )
        entries = tuple(_entry(item) for item in selected)
        body = {
            "bundle_id": bundle_id,
            "fixture_id": fixture.fixture_id,
            "fixture_version": fixture.fixture_version,
            "context_key": fixture.context_key,
            "output_format": output_format,
            "accepted_only": accepted_only,
            "entries": entries,
            "manifest_address": manifest.content_address,
        }
        return ReferenceReleaseEvidenceBundle(
            **body, content_address=content_hash(body, prefix="release-bundle")
        )

    def verify(self, bundle: ReferenceReleaseEvidenceBundle) -> tuple[str, ...]:
        failures: list[str] = []
        if not bundle.content_address.startswith("release-bundle:"):
            failures.append("bundle-address")
        if not bundle.entries:
            failures.append("bundle-empty")
        if len({entry.record_id for entry in bundle.entries}) != len(bundle.entries):
            failures.append("entry-duplicates")
        if any(not entry.content_address.startswith("bundle-entry:") for entry in bundle.entries):
            failures.append("entry-address")
        if any({"output", "payload", "records"} & set(entry.to_dict()) for entry in bundle.entries):
            failures.append("entry-redaction")
        return tuple(failures)

    def render(self, bundle: ReferenceReleaseEvidenceBundle) -> str:
        """Render JSON, NDJSON, or CSV with stable columns and terminal newline."""

        entries = [entry.to_dict() for entry in bundle.entries]
        if bundle.output_format is ReferenceReleaseBundleFormat.JSON:
            return json.dumps(bundle.to_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        if bundle.output_format is ReferenceReleaseBundleFormat.NDJSON:
            return "".join(
                json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in entries
            )
        buffer = io.StringIO()
        fields = (
            "record_id",
            "operation",
            "role",
            "state",
            "accepted",
            "issue_codes",
            "receipt_address",
            "content_address",
        )
        writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for entry in entries:
            row = dict(entry)
            row["issue_codes"] = "|".join(row["issue_codes"])
            writer.writerow({field: row[field] for field in fields})
        return buffer.getvalue()


def assemble_reference_release_bundle(
    fixture: ReferenceReleaseFixture,
    runtime: ReferenceReleaseRuntimeReport,
    manifest: ReferenceReleaseManifest,
    *,
    bundle_id: str = "reference-release-frontier-bundle",
) -> ReferenceReleaseEvidenceBundle:
    """Assemble the canonical JSON bundle used by the pipeline."""

    return ReferenceReleaseBundleBuilder().build(
        runtime, manifest, fixture=fixture, bundle_id=bundle_id
    )


__all__ = [
    "ReferenceReleaseBundleBuilder",
    "ReferenceReleaseBundleEntry",
    "ReferenceReleaseBundleFormat",
    "ReferenceReleaseEvidenceBundle",
    "assemble_reference_release_bundle",
]
