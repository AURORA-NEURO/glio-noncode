"""Content-addressed evidence bundle export for the Domain 01 variation slice."""

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
from .variation_contracts import default_variation_contract_registry
from .variation_fixture_eval import VariationFixtureEvaluator
from .variation_public_data import VariationDataState, VariationFixtureCatalog
from .variation_quality_gate import VariationQualityGate
from .variation_scenario_matrix import VariationScenarioMatrix


class VariationBundleFormat(StrEnum):
    """Supported deterministic bundle renderings."""

    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"


@dataclass(frozen=True, slots=True)
class VariationBundleEntry:
    """One compact operation receipt in an exported evidence bundle."""

    entry_id: str
    entry_class: str
    kind: str
    state: str
    source_id: str
    public_identifier: str
    content_address: str

    def __post_init__(self) -> None:
        for field_name in (
            "entry_id",
            "entry_class",
            "kind",
            "state",
            "source_id",
            "public_identifier",
            "content_address",
        ):
            require_non_empty(getattr(self, field_name), field_name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class VariationEvidenceBundle:
    """Portable summary of all fixture, contract, and scenario evidence."""

    bundle_id: str
    fixture_id: str
    fixture_version: str
    context_key: str
    source_ids: tuple[str, ...]
    quality_state: VariationDataState
    entries: tuple[VariationBundleEntry, ...]
    component_summaries: Mapping[str, Mapping[str, Any]]
    contract_manifest: Mapping[str, Any]
    evidence_boundary: str
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.quality_state == VariationDataState.ACCEPTED

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

    def render(self, output_format: VariationBundleFormat | str) -> str:
        """Render the same bundle deterministically as JSON, CSV, or Markdown."""

        format_value = VariationBundleFormat(str(output_format))
        if format_value == VariationBundleFormat.JSON:
            return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"
        if format_value == VariationBundleFormat.CSV:
            buffer = io.StringIO(newline="")
            writer = csv.DictWriter(
                buffer,
                fieldnames=(
                    "entry_id",
                    "entry_class",
                    "kind",
                    "state",
                    "source_id",
                    "public_identifier",
                    "content_address",
                ),
                lineterminator="\n",
            )
            writer.writeheader()
            for entry in self.entries:
                writer.writerow(entry.to_dict())
            return buffer.getvalue()
        lines = [
            f"# Variation evidence bundle: {self.bundle_id}",
            "",
            f"- Fixture: `{self.fixture_id}` ({self.fixture_version})",
            f"- Context: `{self.context_key}`",
            f"- State: **{self.quality_state.value}**",
            f"- Content address: `{self.content_address}`",
            f"- Evidence boundary: {self.evidence_boundary}",
            "",
            "## Entries",
            "",
            "| Entry | Class | Kind | State | Source | Address |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for entry in self.entries:
            lines.append(
                "| "
                + " | ".join(
                    (
                        entry.entry_id,
                        entry.entry_class,
                        entry.kind,
                        entry.state,
                        entry.source_id,
                        entry.content_address,
                    )
                )
                + " |"
            )
        return "\n".join(lines) + "\n"


class VariationEvidenceBundleBuilder:
    """Build compact evidence bundles without copying raw fixture payloads."""

    def __init__(
        self,
        *,
        evaluator: VariationFixtureEvaluator | None = None,
        quality_gate: VariationQualityGate | None = None,
    ) -> None:
        self.evaluator = evaluator or VariationFixtureEvaluator()
        self.quality_gate = quality_gate or VariationQualityGate(evaluator=self.evaluator)

    def build(self, path: str | Path, *, bundle_id: str | None = None) -> VariationEvidenceBundle:
        raw = self.evaluator.load_file(path)
        fixture_report = self.evaluator.evaluate(raw)
        quality_report = self.quality_gate.evaluate_file(path)
        catalog = VariationFixtureCatalog.from_fixture(raw)
        scenarios = VariationScenarioMatrix(raw).run()
        contracts = default_variation_contract_registry().manifest()
        source_by_record = {record.record_id: record.source_id for record in catalog.records}
        entries: list[VariationBundleEntry] = []
        for record_id, receipt in fixture_report.positive_reports.items():
            record = catalog.record(record_id)
            if record is None:
                raise ValidationError(f"fixture report contains unknown record {record_id}")
            entries.append(
                VariationBundleEntry(
                    record_id,
                    "positive",
                    record.kind.value,
                    str(receipt.get("state", "invalid")),
                    source_by_record[record_id],
                    record.public_identifier,
                    str(receipt.get("content_address", "")),
                )
            )
        for control_id, receipt in fixture_report.negative_reports.items():
            entries.append(
                VariationBundleEntry(
                    f"negative:{control_id}",
                    "review",
                    _control_kind(raw, control_id),
                    str(receipt.get("state", "invalid")),
                    _control_source(raw, control_id),
                    _control_identifier(raw, control_id),
                    str(receipt.get("content_address", "")),
                )
            )
        entries_tuple = tuple(entries)
        summaries = {
            "quality": {
                "state": quality_report.state.value,
                "passed": quality_report.passed,
                "check_count": len(quality_report.checks),
                "failed_check_ids": quality_report.failed_check_ids,
                "content_address": quality_report.content_address,
            },
            "fixture": {
                "state": fixture_report.state.value,
                "check_count": len(fixture_report.checks),
                "content_address": fixture_report.content_address,
            },
            "data": {
                "state": quality_report.component_receipts["data"]["state"],
                "record_count": quality_report.component_receipts["data"]["record_count"],
                "content_address": quality_report.component_receipts["data"]["content_address"],
            },
            "scenarios": {
                "state": scenarios.state.value,
                "scenario_count": len(scenarios.results),
                "failed_scenario_ids": scenarios.failed_scenario_ids,
                "content_address": scenarios.content_address,
            },
        }
        identifier = bundle_id or f"{fixture_report.fixture_id}:variation-evidence"
        require_non_empty(identifier, "bundle_id")
        body = {
            "bundle_id": identifier,
            "fixture_id": fixture_report.fixture_id,
            "fixture_version": fixture_report.fixture_version,
            "context_key": fixture_report.context_key,
            "source_ids": fixture_report.source_ids,
            "quality_state": quality_report.state,
            "entries": entries_tuple,
            "component_summaries": summaries,
            "contract_manifest": contracts,
            "evidence_boundary": fixture_report.evidence_boundary,
        }
        return VariationEvidenceBundle(
            identifier,
            fixture_report.fixture_id,
            fixture_report.fixture_version,
            fixture_report.context_key,
            fixture_report.source_ids,
            quality_report.state,
            entries_tuple,
            summaries,
            contracts,
            fixture_report.evidence_boundary,
            content_hash(body),
        )

    def write(
        self,
        path: str | Path,
        output: str | Path,
        *,
        output_format: VariationBundleFormat | str | None = None,
        bundle_id: str | None = None,
    ) -> VariationEvidenceBundle:
        """Build one bundle and write a deterministic representation."""

        bundle = self.build(path, bundle_id=bundle_id)
        output_path = Path(output)
        format_value: VariationBundleFormat
        if output_format is not None:
            format_value = VariationBundleFormat(str(output_format))
        elif output_path.suffix.lower() in {".json", ".csv", ".md", ".markdown"}:
            inferred = {
                ".json": VariationBundleFormat.JSON,
                ".csv": VariationBundleFormat.CSV,
                ".md": VariationBundleFormat.MARKDOWN,
                ".markdown": VariationBundleFormat.MARKDOWN,
            }[output_path.suffix.lower()]
            format_value = inferred
        else:
            format_value = VariationBundleFormat.JSON
        output_path.write_text(bundle.render(format_value), encoding="utf-8", newline="\n")
        return bundle

    @staticmethod
    def verify(bundle: Mapping[str, Any]) -> bool:
        """Verify the content address without trusting the serialized address."""

        if not isinstance(bundle, Mapping):
            return False
        address = bundle.get("content_address")
        if not isinstance(address, str):
            return False
        body = dict(bundle)
        body.pop("content_address", None)
        body.pop("accepted", None)
        body.pop("entry_count", None)
        body.pop("positive_entry_count", None)
        body.pop("review_entry_count", None)
        return content_hash(body) == address


def _control_source(raw: Mapping[str, Any], control_id: str) -> str:
    for control in raw.get("negative_controls", ()):
        if isinstance(control, Mapping) and control.get("control_id") == control_id:
            return str(control.get("source_id", "fixture-negative"))
    return "fixture-negative"


def _control_identifier(raw: Mapping[str, Any], control_id: str) -> str:
    for control in raw.get("negative_controls", ()):
        if isinstance(control, Mapping) and control.get("control_id") == control_id:
            return str(control.get("public_identifier", control_id))
    return control_id


def _control_kind(raw: Mapping[str, Any], control_id: str) -> str:
    for control in raw.get("negative_controls", ()):
        if isinstance(control, Mapping) and control.get("control_id") == control_id:
            return str(control.get("kind", "unknown"))
    return "unknown"


def build_variation_evidence_bundle(
    path: str | Path,
    *,
    bundle_id: str | None = None,
) -> VariationEvidenceBundle:
    """Convenience function for one compact variation evidence bundle."""

    return VariationEvidenceBundleBuilder().build(path, bundle_id=bundle_id)


__all__ = [
    "VariationBundleEntry",
    "VariationBundleFormat",
    "VariationEvidenceBundle",
    "VariationEvidenceBundleBuilder",
    "build_variation_evidence_bundle",
]
