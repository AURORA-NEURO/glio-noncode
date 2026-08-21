"""Sanitized JSON, CSV, and Markdown bundles for reference-coordinate evidence."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .reference_coordinate_fixture_eval import (
    ReferenceCoordinateOperationReceipt,
    evaluate_reference_coordinate_fixture,
)
from .reference_coordinate_public_data import ReferenceCoordinateFixtureCatalog
from .serialization import content_hash, jsonable, require_non_empty


class ReferenceCoordinateBundleFormat(StrEnum):
    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"


@dataclass(frozen=True, slots=True)
class ReferenceCoordinateBundleEntry:
    """One sanitized receipt projection inside a release bundle."""

    record_id: str
    operation: str
    role: str
    state: str
    issue_codes: tuple[str, ...]
    source_ids: tuple[str, ...]
    context_key: str
    result_summary: dict[str, Any]
    record_address: str
    receipt_address: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.record_id, "bundle record ID")
        require_non_empty(self.operation, "bundle operation")
        require_non_empty(self.role, "bundle role")
        require_non_empty(self.state, "bundle state")
        require_non_empty(self.context_key, "bundle context")
        if not self.source_ids:
            raise ValidationError("bundle entry requires source IDs")
        if not self.record_address.startswith("sha256:"):
            raise ValidationError("bundle entry requires record address")
        if not self.receipt_address.startswith("sha256:"):
            raise ValidationError("bundle entry requires receipt address")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("bundle entry requires content address")
        forbidden = {"payload", "chain_text", "patient_id", "subject_id", "secret"}
        if any(key.lower() in forbidden for key in self.result_summary):
            raise ValidationError("bundle summary contains a forbidden raw field")

    @classmethod
    def from_receipt(
        cls,
        receipt: ReferenceCoordinateOperationReceipt,
        record_address: str,
    ) -> ReferenceCoordinateBundleEntry:
        body = {
            "record_id": receipt.record_id,
            "operation": receipt.operation.value,
            "role": receipt.role.value,
            "state": receipt.state.value,
            "issue_codes": receipt.issue_codes,
            "source_ids": receipt.source_ids,
            "context_key": receipt.context_key,
            "result_summary": dict(receipt.result_summary),
            "record_address": record_address,
            "receipt_address": receipt.content_address,
        }
        return cls(**body, content_address=content_hash(body))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceCoordinateBundleVerification:
    state: str
    checks: tuple[dict[str, Any], ...]
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == "accepted" and all(bool(check["passed"]) for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed": self.passed}


@dataclass(frozen=True, slots=True)
class ReferenceCoordinateEvidenceBundle:
    fixture_id: str
    fixture_version: str
    context_key: str
    format: ReferenceCoordinateBundleFormat
    entries: tuple[ReferenceCoordinateBundleEntry, ...]
    included_controls: bool
    published: bool
    state: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.fixture_id, "bundle fixture ID")
        require_non_empty(self.fixture_version, "bundle fixture version")
        require_non_empty(self.context_key, "bundle context")
        if not self.entries:
            raise ValidationError("bundle requires entries")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("bundle must be content-addressed")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "entry_count": len(self.entries),
            "control_count": sum(entry.role == "control" for entry in self.entries),
            "positive_count": sum(entry.role == "positive" for entry in self.entries),
        }


class ReferenceCoordinateBundleBuilder:
    """Build and verify a sanitized projection of coordinate receipts."""

    def build(
        self,
        catalog: ReferenceCoordinateFixtureCatalog,
        *,
        output_format: ReferenceCoordinateBundleFormat = ReferenceCoordinateBundleFormat.JSON,
        accepted_only: bool = False,
        allow_review: bool = False,
    ) -> ReferenceCoordinateEvidenceBundle:
        evaluation = evaluate_reference_coordinate_fixture(catalog)
        records_by_id = {record.record_id: record for record in catalog.records}
        entries = tuple(
            ReferenceCoordinateBundleEntry.from_receipt(
                receipt,
                records_by_id[receipt.record_id].content_address,
            )
            for receipt in evaluation.receipts
            if not accepted_only or receipt.role.value == "positive"
        )
        if not entries:
            raise ValidationError("accepted-only bundle has no accepted entries")
        included_controls = any(entry.role == "control" for entry in entries)
        published = bool(accepted_only and evaluation.passed)
        if included_controls and not allow_review:
            published = False
        state = "accepted" if evaluation.passed else "review"
        body = {
            "fixture_id": catalog.fixture_id,
            "fixture_version": catalog.fixture_version,
            "context_key": catalog.context_key,
            "format": output_format.value,
            "entries": entries,
            "included_controls": included_controls,
            "published": published,
            "state": state,
        }
        return ReferenceCoordinateEvidenceBundle(
            fixture_id=catalog.fixture_id,
            fixture_version=catalog.fixture_version,
            context_key=catalog.context_key,
            format=output_format,
            entries=entries,
            included_controls=included_controls,
            published=published,
            state=state,
            content_address=content_hash(body),
        )

    def render(self, bundle: ReferenceCoordinateEvidenceBundle) -> str:
        if bundle.format == ReferenceCoordinateBundleFormat.JSON:
            return json.dumps(bundle.to_dict(), indent=2, sort_keys=True) + "\n"
        if bundle.format == ReferenceCoordinateBundleFormat.CSV:
            output = io.StringIO()
            fields = (
                "record_id",
                "operation",
                "role",
                "state",
                "issue_codes",
                "source_ids",
                "context_key",
                "record_address",
                "receipt_address",
                "content_address",
                "result_summary",
            )
            writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            for entry in bundle.entries:
                writer.writerow(
                    {
                        "record_id": entry.record_id,
                        "operation": entry.operation,
                        "role": entry.role,
                        "state": entry.state,
                        "issue_codes": ";".join(entry.issue_codes),
                        "source_ids": ";".join(entry.source_ids),
                        "context_key": entry.context_key,
                        "record_address": entry.record_address,
                        "receipt_address": entry.receipt_address,
                        "content_address": entry.content_address,
                        "result_summary": json.dumps(entry.result_summary, sort_keys=True),
                    }
                )
            return output.getvalue()
        lines = [
            f"# Reference-coordinate evidence bundle: `{bundle.fixture_id}`",
            "",
            f"- State: `{bundle.state}`",
            f"- Published: `{str(bundle.published).lower()}`",
            f"- Context: `{bundle.context_key}`",
            f"- Entries: `{len(bundle.entries)}`",
            f"- Content address: `{bundle.content_address}`",
            "",
            "| Record | Operation | Role | State | Issues | Sources | Entry address |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for entry in bundle.entries:
            issues = ", ".join(entry.issue_codes) or "—"
            sources = ", ".join(entry.source_ids)
            lines.append(
                f"| {entry.record_id} | {entry.operation} | {entry.role} | {entry.state} | "
                f"{issues} | {sources} | `{entry.content_address}` |"
            )
        return "\n".join(lines) + "\n"

    def verify(
        self,
        bundle: ReferenceCoordinateEvidenceBundle,
        catalog: ReferenceCoordinateFixtureCatalog,
    ) -> ReferenceCoordinateBundleVerification:
        records_by_id = {record.record_id: record for record in catalog.records}
        checks: list[dict[str, Any]] = []

        def add(check_id: str, passed: bool, observed: Any, expected: Any, message: str) -> None:
            checks.append(
                {
                    "check_id": check_id,
                    "passed": bool(passed),
                    "observed": observed,
                    "expected": expected,
                    "message": message,
                }
            )

        add(
            "fixture-id",
            bundle.fixture_id == catalog.fixture_id,
            bundle.fixture_id,
            catalog.fixture_id,
            "bundle fixture ID matches",
        )
        add(
            "fixture-version",
            bundle.fixture_version == catalog.fixture_version,
            bundle.fixture_version,
            catalog.fixture_version,
            "bundle version matches",
        )
        add(
            "context",
            bundle.context_key == catalog.context_key,
            bundle.context_key,
            catalog.context_key,
            "bundle context matches",
        )
        add(
            "entry-identity",
            len({entry.record_id for entry in bundle.entries}) == len(bundle.entries),
            True,
            True,
            "bundle record IDs are unique",
        )
        add(
            "entry-membership",
            all(entry.record_id in records_by_id for entry in bundle.entries),
            True,
            True,
            "bundle entries belong to the fixture",
        )
        add(
            "entry-addresses",
            all(entry.content_address.startswith("sha256:") for entry in bundle.entries),
            True,
            True,
            "bundle entries are addressed",
        )
        add(
            "receipt-addresses",
            all(entry.receipt_address.startswith("sha256:") for entry in bundle.entries),
            True,
            True,
            "receipt addresses are retained",
        )
        add(
            "record-addresses",
            all(
                entry.record_address == records_by_id[entry.record_id].content_address
                for entry in bundle.entries
            ),
            True,
            True,
            "record addresses match typed records",
        )
        add(
            "context-retention",
            all(entry.context_key == catalog.context_key for entry in bundle.entries),
            True,
            True,
            "entries retain exact context",
        )
        add(
            "raw-boundary",
            "chain_text" not in self.render(bundle).lower(),
            True,
            True,
            "rendered bundle has no raw chain payload",
        )
        add(
            "control-declaration",
            bundle.included_controls == any(entry.role == "control" for entry in bundle.entries),
            bundle.included_controls,
            True,
            "control inclusion flag is truthful",
        )
        add(
            "bundle-address",
            bundle.content_address.startswith("sha256:"),
            bundle.content_address,
            "sha256:<address>",
            "bundle is content-addressed",
        )
        state = "accepted" if all(bool(check["passed"]) for check in checks) else "review"
        body = {"state": state, "checks": checks, "bundle_address": bundle.content_address}
        return ReferenceCoordinateBundleVerification(state, tuple(checks), content_hash(body))


def build_reference_coordinate_bundle(
    catalog: ReferenceCoordinateFixtureCatalog,
    *,
    output_format: ReferenceCoordinateBundleFormat = ReferenceCoordinateBundleFormat.JSON,
    accepted_only: bool = False,
    allow_review: bool = False,
) -> ReferenceCoordinateEvidenceBundle:
    return ReferenceCoordinateBundleBuilder().build(
        catalog,
        output_format=output_format,
        accepted_only=accepted_only,
        allow_review=allow_review,
    )


__all__ = [
    "ReferenceCoordinateBundleBuilder",
    "ReferenceCoordinateBundleEntry",
    "ReferenceCoordinateBundleFormat",
    "ReferenceCoordinateBundleVerification",
    "ReferenceCoordinateEvidenceBundle",
    "build_reference_coordinate_bundle",
]
