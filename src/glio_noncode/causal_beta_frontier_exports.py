"""Canonical export surfaces for the C05-C08 frontier release."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from typing import Any

from .causal_beta_frontier_artifacts import CausalBetaFrontierArtifactInventory
from .causal_beta_frontier_bundle import CausalBetaFrontierReleaseBundle
from .causal_beta_frontier_fixture_eval import CausalBetaFrontierEvaluation
from .causal_beta_frontier_metrics import CausalBetaFrontierMetrics
from .causal_beta_frontier_public_data import CausalBetaFrontierFixture
from .causal_beta_frontier_release import CausalBetaFrontierReleaseManifest
from .causal_beta_frontier_views import CausalBetaFrontierReviewView
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierExportEnvelope:
    export_id: str
    fixture_id: str
    export_kind: str
    schema_version: str
    row_count: int
    content_type: str
    payload: Any
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"export_id": self.export_id, "fixture_id": self.fixture_id, "export_kind": self.export_kind, "schema_version": self.schema_version, "row_count": self.row_count, "content_type": self.content_type, "payload": self.payload}
        if include_address:
            value["content_address"] = self.content_address
        return value

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=2, default=str)


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierExportInventory:
    fixture_id: str
    envelopes: tuple[CausalBetaFrontierExportEnvelope, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def export_kinds(self) -> tuple[str, ...]:
        return tuple(item.export_kind for item in self.envelopes)

    def by_kind(self, export_kind: str) -> CausalBetaFrontierExportEnvelope:
        return next(item for item in self.envelopes if item.export_kind == export_kind)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "envelopes": [item.to_dict() for item in self.envelopes], "export_kinds": self.export_kinds, "export_count": len(self.envelopes), "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _review_payload(view: CausalBetaFrontierReviewView) -> list[dict[str, Any]]:
    return [item.to_dict() for item in view.rows]


def _markdown_table(view: CausalBetaFrontierReviewView) -> str:
    lines = ["| " + " | ".join(view.columns) + " |", "| " + " | ".join("---" for _ in view.columns) + " |"]
    for row in view.rows:
        values = row.to_dict(False)
        rendered = []
        for column in view.columns:
            value = values.get(column, "")
            if isinstance(value, tuple):
                value = ", ".join(map(str, value))
            rendered.append(str(value).replace("|", "\\|"))
        lines.append("| " + " | ".join(rendered) + " |")
    return "\n".join(lines) + "\n"


def _csv_payload(view: CausalBetaFrontierReviewView) -> str:
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(view.columns)
    for row in view.rows:
        values = row.to_dict(False)
        writer.writerow([";".join(map(str, values.get(column, ()))) if isinstance(values.get(column), tuple) else values.get(column, "") for column in view.columns])
    return stream.getvalue()


def build_causal_beta_frontier_exports(fixture: CausalBetaFrontierFixture, evaluation: CausalBetaFrontierEvaluation, metrics: CausalBetaFrontierMetrics, view: CausalBetaFrontierReviewView, bundle: CausalBetaFrontierReleaseBundle, release: CausalBetaFrontierReleaseManifest, artifacts: CausalBetaFrontierArtifactInventory) -> CausalBetaFrontierExportInventory:
    summary_payload = {"fixture_id": fixture.fixture_id, "evaluation": evaluation.to_dict(), "metrics": metrics.to_dict(), "bundle_id": bundle.bundle_id, "release_id": release.release_id, "artifact_count": len(artifacts.artifacts)}
    manifest_payload = {"bundle": bundle.to_dict(), "release": release.to_dict(), "artifacts": artifacts.to_dict()}
    envelopes = (
        CausalBetaFrontierExportEnvelope("causal-beta-frontier:fixture", fixture.fixture_id, "fixture-json", "1", len(fixture.records), "application/json", fixture.to_dict()),
        CausalBetaFrontierExportEnvelope("causal-beta-frontier:evaluation", fixture.fixture_id, "evaluation-json", "1", len(evaluation.rows), "application/json", evaluation.to_dict()),
        CausalBetaFrontierExportEnvelope("causal-beta-frontier:summary", fixture.fixture_id, "summary-json", "1", len(evaluation.rows), "application/json", summary_payload),
        CausalBetaFrontierExportEnvelope("causal-beta-frontier:review-csv", fixture.fixture_id, "review-csv", "1", len(view.rows), "text/csv", _csv_payload(view)),
        CausalBetaFrontierExportEnvelope("causal-beta-frontier:review-markdown", fixture.fixture_id, "review-markdown", "1", len(view.rows), "text/markdown", _markdown_table(view)),
        CausalBetaFrontierExportEnvelope("causal-beta-frontier:release-manifest", fixture.fixture_id, "release-manifest-json", "1", len(artifacts.artifacts), "application/json", manifest_payload),
    )
    accepted = bool(envelopes) and all(item.fixture_id == fixture.fixture_id and item.row_count >= 0 for item in envelopes)
    return CausalBetaFrontierExportInventory(fixture.fixture_id, envelopes, accepted)


def export_causal_beta_frontier_json(inventory: CausalBetaFrontierExportInventory) -> str:
    return json.dumps(inventory.to_dict(), sort_keys=True, indent=2, default=str)


def export_causal_beta_frontier_review_csv(view: CausalBetaFrontierReviewView) -> str:
    return _csv_payload(view)


def export_causal_beta_frontier_review_markdown(view: CausalBetaFrontierReviewView) -> str:
    return _markdown_table(view)


__all__ = ["CausalBetaFrontierExportEnvelope", "CausalBetaFrontierExportInventory", "build_causal_beta_frontier_exports", "export_causal_beta_frontier_json", "export_causal_beta_frontier_review_csv", "export_causal_beta_frontier_review_markdown"]
