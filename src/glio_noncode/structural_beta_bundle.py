"""Compact JSON, CSV, and Markdown bundles for Domain 02 C05-C08."""

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
from .structural_beta_contracts import default_structural_beta_contract_registry
from .structural_beta_fixture_eval import evaluate_structural_beta_fixture
from .structural_beta_lineage import build_structural_beta_lineage
from .structural_beta_public_data import StructuralBetaFixtureCatalog, StructuralBetaFixtureState
from .structural_beta_quality_gate import evaluate_structural_beta_quality_gate
from .structural_beta_scenario_matrix import evaluate_structural_beta_scenarios


class StructuralBetaBundleFormat(StrEnum):
    """Supported compact beta evidence projections."""

    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"


@dataclass(frozen=True, slots=True)
class StructuralBetaBundleEntry:
    """One positive or review summary without raw detector payload."""

    entry_id: str
    entry_class: str
    capability_id: str
    operation: str
    state: str
    result_state: str
    structural_identifier: str
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
            "structural_identifier",
            "source_id",
            "evidence_address",
            "summary",
        ):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if self.evidence_address[:7] != "sha256:":
            raise ValidationError("beta evidence address must be content-addressed")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralBetaEvidenceBundle:
    """Quality-gated beta bundle with stable manifest metadata."""

    bundle_id: str
    fixture_id: str
    fixture_version: str
    context_key: str
    source_ids: tuple[str, ...]
    entries: tuple[StructuralBetaBundleEntry, ...]
    component_summaries: Mapping[str, Mapping[str, Any]]
    contract_manifest: Mapping[str, Any]
    quality_summary: Mapping[str, Any]
    lineage_address: str
    content_address: str
    state: StructuralBetaFixtureState

    @property
    def accepted(self) -> bool:
        return self.state == StructuralBetaFixtureState.ACCEPTED

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["accepted"] = self.accepted
        result["entry_count"] = len(self.entries)
        result["positive_entry_count"] = sum(item.entry_class == "positive" for item in self.entries)
        result["review_entry_count"] = sum(item.entry_class == "review" for item in self.entries)
        return result

    def render(self, output_format: StructuralBetaBundleFormat | str) -> str:
        selected = StructuralBetaBundleFormat(str(output_format))
        if selected == StructuralBetaBundleFormat.JSON:
            return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if selected == StructuralBetaBundleFormat.CSV:
            buffer = io.StringIO()
            fields = (
                "entry_id",
                "entry_class",
                "capability_id",
                "operation",
                "state",
                "result_state",
                "structural_identifier",
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
            "# Structural beta evidence bundle",
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
                        entry.structural_identifier,
                        entry.evidence_address,
                    )
                )
                + " |"
            )
        lines.extend(("", "## Boundary", "", str(self.quality_summary.get("evidence_boundary", "")), "", "## Sources", ""))
        lines.extend(f"- `{source_id}`" for source_id in self.source_ids)
        return "\n".join(lines) + "\n"


class StructuralBetaEvidenceBundleBuilder:
    """Build a compact bundle only after the beta quality gate passes."""

    _capability_by_operation = {
        "focal_amplification": "GNC-D02-C05",
        "chromothripsis": "GNC-D02-C06",
        "ecdna": "GNC-D02-C07",
        "enhancer_hijacking": "GNC-D02-C08",
    }

    def build(
        self,
        path: str | Path,
        *,
        bundle_id: str | None = None,
        allow_review: bool = False,
    ) -> StructuralBetaEvidenceBundle:
        catalog = StructuralBetaFixtureCatalog.from_file(path)
        quality = evaluate_structural_beta_quality_gate(catalog)
        if not quality.passed and not allow_review:
            raise ValidationError("beta evidence bundle requires a passing quality gate")
        evaluation = evaluate_structural_beta_fixture(catalog)
        lineage = build_structural_beta_lineage(catalog, evaluation=evaluation)
        receipt_by_id = {receipt.record_id: receipt for receipt in evaluation.receipts}
        entries: list[StructuralBetaBundleEntry] = []
        for entry_class, records in (("positive", catalog.positives), ("review", catalog.controls)):
            for record in records:
                receipt = receipt_by_id[record.record_id]
                entries.append(
                    StructuralBetaBundleEntry(
                        entry_id=f"{entry_class}:{record.record_id}",
                        entry_class=entry_class,
                        capability_id=self._capability_by_operation[record.operation.value],
                        operation=record.operation.value,
                        state=receipt.observed_state.value,
                        result_state=receipt.observed_result_state,
                        structural_identifier=record.record_id,
                        source_id=record.source_id,
                        evidence_address=receipt.output_address,
                        summary=receipt.detail,
                    )
                )
        entries.sort(key=lambda item: (item.entry_class, item.capability_id, item.entry_id))
        scenarios = evaluate_structural_beta_scenarios(catalog)
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
            "failed_check_ids": tuple(check.check_id for check in quality.checks if not check.passed),
            "evidence_boundary": (
                "public aggregate C05-C08 structural-beta observations; focal boundaries, "
                "pattern indices, circularity, and enhancer bridges remain explicit candidates"
            ),
            "quality_address": quality.content_address,
            "lineage_address": lineage.content_address,
        }
        selected_id = require_non_empty(bundle_id or f"{catalog.fixture_id}-bundle", "bundle_id")
        body = {
            "bundle_id": selected_id,
            "fixture_id": catalog.fixture_id,
            "fixture_version": catalog.schema_version,
            "context_key": catalog.context_key,
            "source_ids": catalog.source_ids,
            "entries": entries,
            "component_summaries": component_summaries,
            "contract_manifest": default_structural_beta_contract_registry().manifest(),
            "quality_summary": quality_summary,
            "lineage_address": lineage.content_address,
            "state": quality.state,
        }
        return StructuralBetaEvidenceBundle(
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
        output_format: StructuralBetaBundleFormat | str | None = None,
        bundle_id: str | None = None,
        allow_review: bool = False,
    ) -> StructuralBetaEvidenceBundle:
        bundle = self.build(path, bundle_id=bundle_id, allow_review=allow_review)
        output_path = Path(output)
        output_path.write_text(
            bundle.render(self._format_for_path(output_path, output_format)),
            encoding="utf-8",
        )
        return bundle

    @staticmethod
    def verify(payload: Mapping[str, Any]) -> bool:
        """Verify a serialized JSON beta bundle without trusting convenience fields."""

        if not isinstance(payload, Mapping):
            return False
        address = payload.get("content_address")
        if not isinstance(address, str) or address[:7] != "sha256:":
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
        output_format: StructuralBetaBundleFormat | str | None,
    ) -> StructuralBetaBundleFormat:
        if output_format is not None:
            return StructuralBetaBundleFormat(str(output_format))
        if output.suffix.casefold() == ".csv":
            return StructuralBetaBundleFormat.CSV
        if output.suffix.casefold() in {".md", ".markdown"}:
            return StructuralBetaBundleFormat.MARKDOWN
        return StructuralBetaBundleFormat.JSON


def build_structural_beta_evidence_bundle(
    path: str | Path,
    *,
    bundle_id: str | None = None,
    allow_review: bool = False,
) -> StructuralBetaEvidenceBundle:
    """Build a compact C05-C08 evidence bundle."""

    return StructuralBetaEvidenceBundleBuilder().build(
        path,
        bundle_id=bundle_id,
        allow_review=allow_review,
    )


__all__ = [
    "StructuralBetaBundleEntry",
    "StructuralBetaBundleFormat",
    "StructuralBetaEvidenceBundle",
    "StructuralBetaEvidenceBundleBuilder",
    "build_structural_beta_evidence_bundle",
]
