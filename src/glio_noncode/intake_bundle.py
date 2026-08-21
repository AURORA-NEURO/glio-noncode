"""Compact evidence bundle for the Domain 01 intake quality gate."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .intake_contracts import default_intake_contract_registry
from .intake_fixture_eval import evaluate_intake_fixture
from .intake_public_data import IntakeDataState, IntakeFixtureCatalog
from .intake_quality_gate import evaluate_intake_quality_gate
from .serialization import content_hash, jsonable, require_non_empty


class IntakeBundleFormat(StrEnum):
    """Supported compact bundle renderings."""

    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"


@dataclass(frozen=True, slots=True)
class IntakeBundleEntry:
    """One traceable summary row, without copying the raw operation payload."""

    entry_id: str
    entry_class: str
    capability_id: str
    operation: str
    state: str
    public_identifier: str
    source_id: str
    evidence_address: str
    summary: str

    def __post_init__(self) -> None:
        for field_name in (
            "entry_id",
            "entry_class",
            "capability_id",
            "operation",
            "state",
            "public_identifier",
            "source_id",
            "evidence_address",
            "summary",
        ):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if not self.evidence_address.startswith("sha256:"):
            raise ValueError("intake evidence_address must be content-addressed")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeEvidenceBundle:
    """Quality-gated, compact, deterministic intake evidence bundle."""

    bundle_id: str
    fixture_id: str
    fixture_version: str
    context_key: str
    source_ids: tuple[str, ...]
    entries: tuple[IntakeBundleEntry, ...]
    component_summaries: Mapping[str, Mapping[str, Any]]
    contract_manifest: Mapping[str, Any]
    quality_summary: Mapping[str, Any]
    content_address: str
    state: IntakeDataState

    @property
    def accepted(self) -> bool:
        return self.state == IntakeDataState.ACCEPTED

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["accepted"] = self.accepted
        result["entry_count"] = len(self.entries)
        result["positive_entry_count"] = sum(
            entry.entry_class == "positive" for entry in self.entries
        )
        result["review_entry_count"] = sum(
            entry.entry_class == "review" for entry in self.entries
        )
        return result

    def render(self, output_format: IntakeBundleFormat | str) -> str:
        format_value = IntakeBundleFormat(str(output_format))
        if format_value == IntakeBundleFormat.JSON:
            return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if format_value == IntakeBundleFormat.CSV:
            buffer = io.StringIO()
            writer = csv.DictWriter(
                buffer,
                fieldnames=(
                    "entry_id",
                    "entry_class",
                    "capability_id",
                    "operation",
                    "state",
                    "public_identifier",
                    "source_id",
                    "evidence_address",
                    "summary",
                ),
                lineterminator="\n",
            )
            writer.writeheader()
            for entry in self.entries:
                writer.writerow(entry.to_dict())
            return buffer.getvalue()
        lines = [
            "# Intake evidence bundle",
            "",
            f"- Bundle: `{self.bundle_id}`",
            f"- Fixture: `{self.fixture_id}` ({self.fixture_version})",
            f"- Context: `{self.context_key}`",
            f"- State: `{self.state.value}`",
            f"- Content address: `{self.content_address}`",
            f"- Entries: {len(self.entries)}",
            "",
            "| Entry | Class | Capability | Operation | State | Public ID | Evidence |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for entry in self.entries:
            lines.append(
                "| "
                + " | ".join(
                    (
                        entry.entry_id,
                        entry.entry_class,
                        entry.capability_id,
                        entry.operation,
                        entry.state,
                        entry.public_identifier,
                        entry.evidence_address,
                    )
                )
                + " |"
            )
        lines.extend(
            (
                "",
                "## Boundary",
                "",
                str(self.quality_summary.get("evidence_boundary", "")),
                "",
                "## Sources",
                "",
            )
        )
        lines.extend(f"- `{source_id}`" for source_id in self.source_ids)
        return "\n".join(lines) + "\n"


class IntakeEvidenceBundleBuilder:
    """Build and verify a bundle only from a passing quality-gated fixture."""

    _capability_by_kind = {
        "consent": "GNC-D01-C13",
        "anomaly": "GNC-D01-C14",
        "completeness": "GNC-D01-C15",
        "bundle": "GNC-D01-C16",
    }

    def build(
        self,
        path: str | Path,
        *,
        bundle_id: str | None = None,
        allow_review: bool = False,
    ) -> IntakeEvidenceBundle:
        catalog = IntakeFixtureCatalog.from_file(path)
        quality = evaluate_intake_quality_gate(path)
        fixture = evaluate_intake_fixture(path)
        if not quality.passed and not allow_review:
            raise ValueError("intake evidence bundle requires a passing quality gate")
        selected_id = bundle_id or f"{catalog.fixture_id}-bundle"
        selected_id = require_non_empty(selected_id, "bundle_id")
        entries: list[IntakeBundleEntry] = []
        positive_by_id = fixture.positive_reports
        for record in catalog.records:
            receipt = positive_by_id[record.record_id]
            entries.append(
                IntakeBundleEntry(
                    f"positive:{record.record_id}",
                    "positive",
                    self._capability_by_kind[record.kind.value],
                    record.operation,
                    str(receipt["state"]),
                    record.public_identifier,
                    record.source_id,
                    str(receipt["content_address"]),
                    self._positive_summary(record.kind.value, receipt),
                )
            )
        for control in catalog.controls:
            receipt = fixture.negative_reports[control.control_id]
            entries.append(
                IntakeBundleEntry(
                    f"review:{control.control_id}",
                    "review",
                    self._capability_by_kind[control.kind.value],
                    control.operation,
                    str(receipt["state"]),
                    control.public_identifier,
                    control.source_id,
                    str(receipt["content_address"]),
                    self._review_summary(control.kind.value, receipt),
                )
            )
        entries.sort(key=lambda entry: (entry.entry_class, entry.capability_id, entry.entry_id))
        contract_manifest = default_intake_contract_registry().manifest()
        component_summaries = {
            "fixture": {
                "check_count": len(fixture.checks),
                "passed_count": len(fixture.passed_check_ids),
                "failed_count": len(fixture.failed_check_ids),
                "positive_count": len(catalog.records),
                "review_control_count": len(catalog.controls),
            },
            "data": {
                "record_count": quality.component_receipts["data"]["record_count"],
                "control_count": quality.component_receipts["data"]["control_count"],
                "issue_count": len(quality.component_receipts["data"]["issues"]),
                "state": quality.component_receipts["data"]["state"],
            },
            "scenarios": {
                "scenario_count": len(quality.component_receipts["scenarios"]["results"]),
                "failed_count": len(quality.component_receipts["scenarios"]["failed_scenario_ids"]),
                "state": quality.component_receipts["scenarios"]["state"],
            },
            "quality": {
                "check_count": len(quality.checks),
                "passed_count": len(quality.passed_check_ids),
                "failed_count": len(quality.failed_check_ids),
                "state": quality.state.value,
            },
        }
        quality_summary = {
            "state": quality.state.value,
            "passed": quality.passed,
            "check_count": len(quality.checks),
            "failed_check_ids": quality.failed_check_ids,
            "evidence_boundary": quality.evidence_boundary,
            "quality_address": quality.content_address,
        }
        body = {
            "bundle_id": selected_id,
            "fixture_id": catalog.fixture_id,
            "fixture_version": catalog.fixture_version,
            "context_key": catalog.context_key,
            "source_ids": tuple(sorted(source.source_id for source in catalog.sources)),
            "entries": entries,
            "component_summaries": component_summaries,
            "contract_manifest": contract_manifest,
            "quality_summary": quality_summary,
            "state": quality.state,
        }
        return IntakeEvidenceBundle(
            selected_id,
            catalog.fixture_id,
            catalog.fixture_version,
            catalog.context_key,
            tuple(sorted(source.source_id for source in catalog.sources)),
            tuple(entries),
            component_summaries,
            contract_manifest,
            quality_summary,
            content_hash(body),
            quality.state,
        )

    def write(
        self,
        path: str | Path,
        output: str | Path,
        *,
        output_format: IntakeBundleFormat | str | None = None,
        bundle_id: str | None = None,
        allow_review: bool = False,
    ) -> IntakeEvidenceBundle:
        bundle = self.build(path, bundle_id=bundle_id, allow_review=allow_review)
        output_path = Path(output)
        format_value = self._format_for_path(output_path, output_format)
        output_path.write_text(bundle.render(format_value), encoding="utf-8")
        return bundle

    @staticmethod
    def verify(payload: Mapping[str, Any]) -> bool:
        """Verify a serialized JSON bundle without trusting its address."""

        if not isinstance(payload, Mapping):
            return False
        address = payload.get("content_address")
        if not isinstance(address, str) or not address.startswith("sha256:"):
            return False
        body = dict(payload)
        body.pop("content_address", None)
        body.pop("accepted", None)
        body.pop("entry_count", None)
        body.pop("positive_entry_count", None)
        body.pop("review_entry_count", None)
        expected = content_hash(body)
        return address == expected

    @staticmethod
    def _format_for_path(
        output: Path,
        output_format: IntakeBundleFormat | str | None,
    ) -> IntakeBundleFormat:
        if output_format is not None:
            return IntakeBundleFormat(str(output_format))
        suffix = output.suffix.casefold()
        if suffix == ".csv":
            return IntakeBundleFormat.CSV
        if suffix in {".md", ".markdown"}:
            return IntakeBundleFormat.MARKDOWN
        return IntakeBundleFormat.JSON

    @staticmethod
    def _positive_summary(kind: str, receipt: Mapping[str, Any]) -> str:
        operation_output = receipt.get("operation_output", {})
        if kind == "consent":
            count = len(operation_output.get("accepted_record_ids", ()))
            return f"{count} record(s) have an active policy attachment"
        if kind == "anomaly":
            count = len(operation_output.get("accepted_record_ids", ()))
            return f"{count} record(s) pass anomaly inspection"
        if kind == "completeness":
            score = operation_output.get("mean_score", 0)
            return f"weighted mean completeness score {score}"
        return f"{operation_output.get('record_count', 0)} record(s) in deterministic bundle"

    @staticmethod
    def _review_summary(kind: str, receipt: Mapping[str, Any]) -> str:
        operation_output = receipt.get("operation_output", {})
        if receipt.get("state") == "review" and receipt.get("error_code"):
            return "operation rejected its input contract and retained a review receipt"
        if kind == "consent":
            return f"{len(operation_output.get('blocked_record_ids', ())) } record(s) blocked by policy"
        if kind == "anomaly":
            return f"{len(operation_output.get('quarantined_record_ids', ())) } record(s) quarantined"
        if kind == "completeness":
            return f"{len(operation_output.get('review_record_ids', ())) } record(s) require completeness review"
        return "bundle export is withheld until acceptance controls pass"


def build_intake_evidence_bundle(
    path: str | Path,
    *,
    bundle_id: str | None = None,
    allow_review: bool = False,
) -> IntakeEvidenceBundle:
    """Build a compact intake evidence bundle."""

    return IntakeEvidenceBundleBuilder().build(
        path,
        bundle_id=bundle_id,
        allow_review=allow_review,
    )


__all__ = [
    "IntakeBundleEntry",
    "IntakeBundleFormat",
    "IntakeEvidenceBundle",
    "IntakeEvidenceBundleBuilder",
    "build_intake_evidence_bundle",
]
