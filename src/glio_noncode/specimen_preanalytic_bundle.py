"""Sanitized JSON, CSV, and Markdown evidence bundle for C13-C16."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .specimen_preanalytic_fixture_eval import (
    SpecimenPreanalyticReceipt,
    evaluate_specimen_preanalytic_fixture,
)
from .specimen_preanalytic_public_data import SpecimenPreanalyticFixtureCatalog
from .specimen_preanalytic_scenario_matrix import evaluate_specimen_preanalytic_scenarios


class SpecimenPreanalyticBundleFormat(StrEnum):
    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticBundleEntry:
    entry_id: str
    record_id: str
    operation: str
    role: str
    expected_state: str
    observed_state: str
    issue_codes: tuple[str, ...]
    output_address: str
    entry_address: str

    def __post_init__(self) -> None:
        for field in (
            "entry_id",
            "record_id",
            "operation",
            "role",
            "expected_state",
            "observed_state",
        ):
            require_non_empty(str(getattr(self, field)), f"bundle {field}")
        if not self.output_address.startswith("sha256:") or not self.entry_address.startswith(
            "sha256:"
        ):
            raise ValueError("bundle addresses must be sha256-prefixed")

    def address_body(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "record_id": self.record_id,
            "operation": self.operation,
            "role": self.role,
            "expected_state": self.expected_state,
            "observed_state": self.observed_state,
            "issue_codes": self.issue_codes,
            "output_address": self.output_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticEvidenceBundle:
    bundle_id: str
    fixture_id: str
    context_key: str
    state: str
    entries: tuple[SpecimenPreanalyticBundleEntry, ...]
    evaluation_address: str
    scenario_address: str
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == "accepted"

    def address_body(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "fixture_id": self.fixture_id,
            "context_key": self.context_key,
            "state": self.state,
            "entries": self.entries,
            "evaluation_address": self.evaluation_address,
            "scenario_address": self.scenario_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"entry_count": len(self.entries), "passed": self.passed}


class SpecimenPreanalyticEvidenceBundleBuilder:
    """Build and verify a review-preserving sanitized bundle."""

    def build(
        self,
        catalog: SpecimenPreanalyticFixtureCatalog,
        *,
        bundle_id: str = "specimen-preanalytic-c13-c16",
        allow_review: bool = False,
    ) -> SpecimenPreanalyticEvidenceBundle:
        bundle_id = require_non_empty(bundle_id, "bundle_id")
        evaluation = evaluate_specimen_preanalytic_fixture(catalog)
        scenarios = evaluate_specimen_preanalytic_scenarios(catalog)
        if not evaluation.passed and not allow_review:
            raise ValueError("review evaluation requires allow_review=True")
        entries = tuple(_entry(receipt) for receipt in evaluation.receipts)
        state = "accepted" if evaluation.passed and scenarios.passed else "review"
        body = {
            "bundle_id": bundle_id,
            "fixture_id": catalog.fixture_id,
            "context_key": catalog.context_key,
            "state": state,
            "entries": entries,
            "evaluation_address": evaluation.content_address,
            "scenario_address": scenarios.content_address,
        }
        return SpecimenPreanalyticEvidenceBundle(
            bundle_id,
            catalog.fixture_id,
            catalog.context_key,
            state,
            entries,
            evaluation.content_address,
            scenarios.content_address,
            content_hash(body),
        )

    def verify(self, bundle: SpecimenPreanalyticEvidenceBundle) -> bool:
        if bundle.content_address != content_hash(bundle.address_body()):
            return False
        return all(
            entry.entry_address == content_hash(entry.address_body()) for entry in bundle.entries
        )

    def render(
        self,
        bundle: SpecimenPreanalyticEvidenceBundle,
        format: SpecimenPreanalyticBundleFormat = SpecimenPreanalyticBundleFormat.JSON,
    ) -> str:
        selected = SpecimenPreanalyticBundleFormat(format)
        if selected == SpecimenPreanalyticBundleFormat.JSON:
            return json.dumps(bundle.to_dict(), indent=2, sort_keys=True) + "\n"
        if selected == SpecimenPreanalyticBundleFormat.CSV:
            return _csv(bundle)
        return _markdown(bundle)

    def write(
        self,
        bundle: SpecimenPreanalyticEvidenceBundle,
        path: str | Path,
        *,
        format: SpecimenPreanalyticBundleFormat | None = None,
    ) -> None:
        destination = Path(path)
        selected = format or _format_from_suffix(destination)
        destination.write_text(self.render(bundle, selected), encoding="utf-8")


def _entry(receipt: SpecimenPreanalyticReceipt) -> SpecimenPreanalyticBundleEntry:
    body = {
        "entry_id": f"entry:{receipt.record_id}",
        "record_id": receipt.record_id,
        "operation": receipt.operation,
        "role": receipt.role,
        "expected_state": receipt.expected_state,
        "observed_state": receipt.observed_state,
        "issue_codes": receipt.issue_codes,
        "output_address": receipt.output_address,
    }
    return SpecimenPreanalyticBundleEntry(**body, entry_address=content_hash(body))


def _format_from_suffix(path: Path) -> SpecimenPreanalyticBundleFormat:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return SpecimenPreanalyticBundleFormat.CSV
    if suffix in {".md", ".markdown"}:
        return SpecimenPreanalyticBundleFormat.MARKDOWN
    return SpecimenPreanalyticBundleFormat.JSON


def _csv(bundle: SpecimenPreanalyticEvidenceBundle) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=(
            "entry_id",
            "record_id",
            "operation",
            "role",
            "expected_state",
            "observed_state",
            "issue_codes",
            "output_address",
            "entry_address",
        ),
        lineterminator="\n",
    )
    writer.writeheader()
    for entry in bundle.entries:
        writer.writerow(
            {
                "entry_id": entry.entry_id,
                "record_id": entry.record_id,
                "operation": entry.operation,
                "role": entry.role,
                "expected_state": entry.expected_state,
                "observed_state": entry.observed_state,
                "issue_codes": ";".join(entry.issue_codes),
                "output_address": entry.output_address,
                "entry_address": entry.entry_address,
            }
        )
    return output.getvalue()


def _markdown(bundle: SpecimenPreanalyticEvidenceBundle) -> str:
    lines = [
        "# specimen-preanalytic-c13-c16",
        "",
        f"- Fixture: `{bundle.fixture_id}`",
        f"- Context: `{bundle.context_key}`",
        f"- State: `{bundle.state}`",
        f"- Evaluation address: `{bundle.evaluation_address}`",
        f"- Scenario address: `{bundle.scenario_address}`",
        "",
        "| Entry | Operation | Role | Expected | Observed | Issues | Output address |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for entry in bundle.entries:
        issues = ", ".join(entry.issue_codes) or "none"
        lines.append(
            f"| `{entry.entry_id}` | `{entry.operation}` | `{entry.role}` | "
            f"`{entry.expected_state}` | `{entry.observed_state}` | `{issues}` | "
            f"`{entry.output_address}` |"
        )
    return "\n".join(lines) + "\n"


__all__ = [
    "SpecimenPreanalyticBundleEntry",
    "SpecimenPreanalyticBundleFormat",
    "SpecimenPreanalyticEvidenceBundle",
    "SpecimenPreanalyticEvidenceBundleBuilder",
]
