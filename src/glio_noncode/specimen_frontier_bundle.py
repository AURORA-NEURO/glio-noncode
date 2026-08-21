"""Compact release projections for Domain 03 C01-C04 evidence."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .specimen_frontier_contracts import default_specimen_frontier_contract_registry
from .specimen_frontier_fixture_eval import evaluate_specimen_frontier_fixture
from .specimen_frontier_lineage import build_specimen_frontier_lineage
from .specimen_frontier_public_data import (
    SpecimenFrontierFixtureCatalog,
    SpecimenFrontierFixtureState,
)
from .specimen_frontier_quality_gate import evaluate_specimen_frontier_quality_gate
from .specimen_frontier_scenario_matrix import evaluate_specimen_frontier_scenarios


class SpecimenFrontierBundleFormat(StrEnum):
    """Supported compact C01-C04 projections."""

    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"


@dataclass(frozen=True, slots=True)
class SpecimenFrontierBundleEntry:
    """One positive or review summary without raw specimen payload."""

    entry_id: str
    entry_class: str
    capability_id: str
    operation: str
    state: str
    result_state: str
    specimen_identifier: str
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
            "result_state",
            "specimen_identifier",
            "source_id",
            "evidence_address",
            "summary",
        ):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if not self.evidence_address.startswith("sha256:"):
            raise ValidationError("specimen frontier evidence address must be addressed")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenFrontierEvidenceBundle:
    """Quality-gated C01-C04 bundle with stable metadata."""

    bundle_id: str
    fixture_id: str
    fixture_version: str
    context_key: str
    source_ids: tuple[str, ...]
    entries: tuple[SpecimenFrontierBundleEntry, ...]
    component_summaries: Mapping[str, Mapping[str, Any]]
    contract_manifest: Mapping[str, Any]
    quality_summary: Mapping[str, Any]
    lineage_address: str
    content_address: str
    state: SpecimenFrontierFixtureState

    @property
    def accepted(self) -> bool:
        return self.state == SpecimenFrontierFixtureState.ACCEPTED

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "entry_count": len(self.entries),
            "positive_entry_count": sum(item.entry_class == "positive" for item in self.entries),
            "review_entry_count": sum(item.entry_class == "review" for item in self.entries),
        }

    def render(self, output_format: SpecimenFrontierBundleFormat | str) -> str:
        selected = SpecimenFrontierBundleFormat(str(output_format))
        if selected == SpecimenFrontierBundleFormat.JSON:
            return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if selected == SpecimenFrontierBundleFormat.CSV:
            buffer = io.StringIO()
            fields = (
                "entry_id",
                "entry_class",
                "capability_id",
                "operation",
                "state",
                "result_state",
                "specimen_identifier",
                "source_id",
                "evidence_address",
                "summary",
            )
            writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            for entry in self.entries:
                writer.writerow(entry.to_dict())
            return buffer.getvalue()
        lines = [
            "# Specimen frontier evidence bundle",
            "",
            f"- Bundle: `{self.bundle_id}`",
            f"- Fixture: `{self.fixture_id}` ({self.fixture_version})",
            f"- Context: `{self.context_key}`",
            f"- State: `{self.state.value}`",
            f"- Content address: `{self.content_address}`",
            f"- Entries: {len(self.entries)}",
            "",
            "| Entry | Class | Capability | Operation | State | Result | Identifier | Evidence |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
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
                        entry.result_state,
                        entry.specimen_identifier,
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


class SpecimenFrontierEvidenceBundleBuilder:
    """Build a compact bundle only after the C01-C04 quality gate passes."""

    _capability_by_operation = {
        "ontology_mapping": "GNC-D03-C01",
        "matched_normal": "GNC-D03-C02",
        "purity_ploidy": "GNC-D03-C03",
        "sample_integrity": "GNC-D03-C04",
    }

    def build(
        self,
        path: str | Path,
        *,
        bundle_id: str | None = None,
        allow_review: bool = False,
    ) -> SpecimenFrontierEvidenceBundle:
        catalog = SpecimenFrontierFixtureCatalog.from_file(path)
        quality = evaluate_specimen_frontier_quality_gate(catalog)
        if not quality.passed and not allow_review:
            raise ValidationError("specimen frontier bundle requires a passing quality gate")
        evaluation = evaluate_specimen_frontier_fixture(catalog)
        lineage = build_specimen_frontier_lineage(catalog, evaluation=evaluation)
        receipt_by_id = {receipt.record_id: receipt for receipt in evaluation.receipts}
        entries: list[SpecimenFrontierBundleEntry] = []
        for entry_class, records in (("positive", catalog.positives), ("review", catalog.controls)):
            for record in records:
                receipt = receipt_by_id[record.record_id]
                entries.append(
                    SpecimenFrontierBundleEntry(
                        entry_id=f"{entry_class}:{record.record_id}",
                        entry_class=entry_class,
                        capability_id=self._capability_by_operation[record.operation.value],
                        operation=record.operation.value,
                        state=receipt.observed_state.value,
                        result_state=receipt.observed_result_state,
                        specimen_identifier=record.record_id,
                        source_id=record.source_id,
                        evidence_address=receipt.output_address,
                        summary=receipt.detail,
                    )
                )
        entries.sort(key=lambda item: (item.entry_class, item.capability_id, item.entry_id))
        scenarios = evaluate_specimen_frontier_scenarios(catalog)
        component_summaries = {
            "fixture": {
                "check_count": len(evaluation.checks),
                "passed_count": sum(check.passed for check in evaluation.checks),
                "positive_count": len(catalog.positives),
                "review_control_count": len(catalog.controls),
            },
            "scenarios": {
                "scenario_count": len(scenarios.scenarios),
                "positive_count": scenarios.positive_count,
                "review_count": scenarios.review_count,
                "passed": scenarios.passed,
            },
            "quality": {
                "check_count": len(quality.checks),
                "passed_count": sum(check.passed for check in quality.checks),
                "state": quality.state.value,
            },
            "lineage": {
                "node_count": len(lineage.nodes),
                "edge_count": len(lineage.edges),
                "state": lineage.state.value,
                "content_address": lineage.content_address,
            },
        }
        quality_summary = {
            "state": quality.state.value,
            "passed": quality.passed,
            "check_count": len(quality.checks),
            "failed_check_ids": tuple(
                check.check_id for check in quality.checks if not check.passed
            ),
        "evidence_boundary": (
            "public aggregate C01-C04 specimen ontology, matched-normal, purity/ploidy, "
            "and integrity observations"
        ),
            "quality_address": quality.content_address,
            "lineage_address": lineage.content_address,
        }
        selected_id = require_non_empty(
            bundle_id or f"{catalog.fixture_id}-bundle",
            "bundle_id",
        )
        body = {
            "bundle_id": selected_id,
            "fixture_id": catalog.fixture_id,
            "fixture_version": catalog.schema_version,
            "context_key": catalog.context_key,
            "source_ids": catalog.source_ids,
            "entries": entries,
            "component_summaries": component_summaries,
            "contract_manifest": default_specimen_frontier_contract_registry().manifest(),
            "quality_summary": quality_summary,
            "lineage_address": lineage.content_address,
            "state": quality.state,
        }
        return SpecimenFrontierEvidenceBundle(
            bundle_id=selected_id,
            fixture_id=catalog.fixture_id,
            fixture_version=catalog.schema_version,
            context_key=catalog.context_key,
            source_ids=catalog.source_ids,
            entries=tuple(entries),
            component_summaries=component_summaries,
            contract_manifest=body["contract_manifest"],
            quality_summary=quality_summary,
            lineage_address=lineage.content_address,
            content_address=content_hash(body),
            state=quality.state,
        )

    def write(
        self,
        path: str | Path,
        output: str | Path,
        *,
        output_format: SpecimenFrontierBundleFormat | str | None = None,
        bundle_id: str | None = None,
        allow_review: bool = False,
    ) -> SpecimenFrontierEvidenceBundle:
        bundle = self.build(path, bundle_id=bundle_id, allow_review=allow_review)
        output_path = Path(output)
        output_path.write_text(
            bundle.render(self._format_for_path(output_path, output_format)),
            encoding="utf-8",
        )
        return bundle

    @staticmethod
    def verify(payload: Mapping[str, Any]) -> bool:
        """Verify a serialized JSON bundle without trusting convenience fields."""

        if not isinstance(payload, Mapping):
            return False
        address = payload.get("content_address")
        if not isinstance(address, str) or not address.startswith("sha256:"):
            return False
        body = dict(payload)
        for key in (
            "content_address",
            "accepted",
            "entry_count",
            "positive_entry_count",
            "review_entry_count",
        ):
            body.pop(key, None)
        return address == content_hash(body)

    @staticmethod
    def _format_for_path(
        output: Path,
        output_format: SpecimenFrontierBundleFormat | str | None,
    ) -> SpecimenFrontierBundleFormat:
        if output_format is not None:
            return SpecimenFrontierBundleFormat(str(output_format))
        if output.suffix.casefold() == ".csv":
            return SpecimenFrontierBundleFormat.CSV
        if output.suffix.casefold() in {".md", ".markdown"}:
            return SpecimenFrontierBundleFormat.MARKDOWN
        return SpecimenFrontierBundleFormat.JSON


def build_specimen_frontier_evidence_bundle(
    path: str | Path,
    *,
    bundle_id: str | None = None,
    allow_review: bool = False,
) -> SpecimenFrontierEvidenceBundle:
    """Build a compact C01-C04 evidence bundle."""

    return SpecimenFrontierEvidenceBundleBuilder().build(
        path,
        bundle_id=bundle_id,
        allow_review=allow_review,
    )


__all__ = [
    "SpecimenFrontierBundleEntry",
    "SpecimenFrontierBundleFormat",
    "SpecimenFrontierEvidenceBundle",
    "SpecimenFrontierEvidenceBundleBuilder",
    "build_specimen_frontier_evidence_bundle",
]
