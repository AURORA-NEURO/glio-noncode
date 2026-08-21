"""Content-addressed evidence bundle export for Domain 01 identity operations."""

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
from .identity_contracts import default_identity_contract_registry
from .identity_fixture_eval import IdentityFixtureEvaluator
from .identity_public_data import IdentityDataState, IdentityFixtureCatalog
from .identity_quality_gate import IdentityQualityGate
from .identity_scenario_matrix import IdentityScenarioMatrix
from .serialization import content_hash, jsonable, require_non_empty


class IdentityBundleFormat(StrEnum):
    """Supported deterministic bundle renderings."""

    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"


@dataclass(frozen=True, slots=True)
class IdentityBundleEntry:
    """One compact operation receipt in an exported identity bundle."""

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
class IdentityEvidenceBundle:
    """Portable summary of identity, replay, scenario, and contract evidence."""

    bundle_id: str
    fixture_id: str
    fixture_version: str
    context_key: str
    source_ids: tuple[str, ...]
    quality_state: IdentityDataState
    entries: tuple[IdentityBundleEntry, ...]
    component_summaries: Mapping[str, Mapping[str, Any]]
    contract_manifest: Mapping[str, Any]
    evidence_boundary: str
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.quality_state == IdentityDataState.ACCEPTED

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

    def render(self, output_format: IdentityBundleFormat | str) -> str:
        """Render the same bundle deterministically as JSON, CSV, or Markdown."""

        format_value = IdentityBundleFormat(str(output_format))
        if format_value == IdentityBundleFormat.JSON:
            return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"
        if format_value == IdentityBundleFormat.CSV:
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
            f"# Identity evidence bundle: {self.bundle_id}",
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


class IdentityEvidenceBundleBuilder:
    """Build compact identity bundles without copying raw payload values."""

    def __init__(
        self,
        *,
        evaluator: IdentityFixtureEvaluator | None = None,
        quality_gate: IdentityQualityGate | None = None,
    ) -> None:
        self.evaluator = evaluator or IdentityFixtureEvaluator()
        self.quality_gate = quality_gate or IdentityQualityGate(evaluator=self.evaluator)

    def build(self, path: str | Path, *, bundle_id: str | None = None) -> IdentityEvidenceBundle:
        raw = self.evaluator.load_file(path)
        fixture_report = self.evaluator.evaluate(raw)
        quality_report = self.quality_gate.evaluate_file(path)
        catalog = IdentityFixtureCatalog.from_fixture(raw)
        scenarios = IdentityScenarioMatrix(raw, evaluator=self.evaluator).run()
        contracts = default_identity_contract_registry().manifest()
        entries: list[IdentityBundleEntry] = []
        for record_id, receipt in fixture_report.positive_reports.items():
            record = catalog.record(record_id)
            if record is None:
                raise ValidationError(f"identity report contains unknown record {record_id}")
            entries.append(
                IdentityBundleEntry(
                    record_id,
                    "positive",
                    record.kind.value,
                    str(receipt.get("state", "invalid")),
                    record.source_id,
                    record.public_identifier,
                    str(receipt.get("content_address", "")),
                )
            )
        for control_id, receipt in fixture_report.negative_reports.items():
            control = catalog.control(control_id)
            if control is None:
                raise ValidationError(f"identity report contains unknown control {control_id}")
            entries.append(
                IdentityBundleEntry(
                    f"negative:{control_id}",
                    "review",
                    control.kind.value,
                    str(receipt.get("state", "invalid")),
                    control.source_id,
                    control.public_identifier,
                    str(receipt.get("content_address", "")),
                )
            )
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
                "positive_count": quality_report.component_receipts["data"]["positive_count"],
                "negative_control_count": quality_report.component_receipts["data"][
                    "negative_control_count"
                ],
                "content_address": quality_report.component_receipts["data"]["content_address"],
            },
            "scenarios": {
                "state": scenarios.state.value,
                "scenario_count": len(scenarios.results),
                "failed_scenario_ids": scenarios.failed_scenario_ids,
                "content_address": scenarios.content_address,
            },
            "contracts": {
                "contract_count": contracts["contract_count"],
                "content_address": contracts["content_address"],
            },
        }
        identifier = bundle_id or f"{fixture_report.fixture_id}:identity-evidence"
        require_non_empty(identifier, "bundle_id")
        body = {
            "bundle_id": identifier,
            "fixture_id": fixture_report.fixture_id,
            "fixture_version": fixture_report.fixture_version,
            "context_key": fixture_report.context_key,
            "source_ids": fixture_report.source_ids,
            "quality_state": quality_report.state,
            "entries": tuple(entries),
            "component_summaries": summaries,
            "contract_manifest": contracts,
            "evidence_boundary": fixture_report.evidence_boundary,
        }
        return IdentityEvidenceBundle(
            identifier,
            fixture_report.fixture_id,
            fixture_report.fixture_version,
            fixture_report.context_key,
            fixture_report.source_ids,
            quality_report.state,
            tuple(entries),
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
        output_format: IdentityBundleFormat | str | None = None,
        bundle_id: str | None = None,
    ) -> IdentityEvidenceBundle:
        """Build one bundle and write a deterministic representation."""

        bundle = self.build(path, bundle_id=bundle_id)
        output_path = Path(output)
        if output_format is not None:
            format_value = IdentityBundleFormat(str(output_format))
        elif output_path.suffix.lower() in {".json", ".csv", ".md", ".markdown"}:
            format_value = {
                ".json": IdentityBundleFormat.JSON,
                ".csv": IdentityBundleFormat.CSV,
                ".md": IdentityBundleFormat.MARKDOWN,
                ".markdown": IdentityBundleFormat.MARKDOWN,
            }[output_path.suffix.lower()]
        else:
            format_value = IdentityBundleFormat.JSON
        output_path.write_text(bundle.render(format_value), encoding="utf-8", newline="\n")
        return bundle

    @staticmethod
    def verify(bundle: Mapping[str, Any]) -> bool:
        """Verify the content address without trusting derived conveniences."""

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


def build_identity_evidence_bundle(
    path: str | Path,
    *,
    bundle_id: str | None = None,
) -> IdentityEvidenceBundle:
    """Convenience function for one compact identity evidence bundle."""

    return IdentityEvidenceBundleBuilder().build(path, bundle_id=bundle_id)


__all__ = [
    "IdentityBundleEntry",
    "IdentityBundleFormat",
    "IdentityEvidenceBundle",
    "IdentityEvidenceBundleBuilder",
    "build_identity_evidence_bundle",
]
