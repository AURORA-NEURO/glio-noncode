"""Deterministic event and metric exports for offline program review."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any

from .program_runtime_offline_contracts import ProgramRuntimeOfflineBundle
from .program_runtime_offline_query import _payload, _rows
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ProgramRuntimeOfflineEvent:
    """One timestamp-free lifecycle event derived from a closed stage row."""

    sequence: int
    event_type: str
    stage_id: str
    state: str
    input_address: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramRuntimeOfflineMetric:
    """One stable aggregate metric with explicit plane and unit."""

    metric_id: str
    plane: str
    name: str
    value: int | float
    unit: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramRuntimeOfflineObservabilityReport:
    """Complete event and metric projection for one offline bundle."""

    bundle_id: str
    events: tuple[ProgramRuntimeOfflineEvent, ...]
    metrics: tuple[ProgramRuntimeOfflineMetric, ...]
    accepted: bool
    content_address: str

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def metric_count(self) -> int:
        return len(self.metrics)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "event_count": self.event_count,
            "metric_count": self.metric_count,
        }


def _event(
    sequence: int,
    event_type: str,
    stage: dict[str, Any],
    detail: str,
) -> ProgramRuntimeOfflineEvent:
    body = {
        "sequence": sequence,
        "event_type": event_type,
        "stage_id": str(stage.get("stage_id", "")),
        "state": str(stage.get("state", "")),
        "input_address": str(stage.get("input_address", "")),
        "output_address": str(stage.get("output_address", "")),
        "detail": detail,
    }
    return ProgramRuntimeOfflineEvent(
        **body,
        content_address=content_hash(body, prefix="program-runtime-offline-event"),
    )


def _metric(
    metric_id: str,
    plane: str,
    name: str,
    value: int | float,
    unit: str,
) -> ProgramRuntimeOfflineMetric:
    body = {
        "metric_id": metric_id,
        "plane": plane,
        "name": name,
        "value": value,
        "unit": unit,
    }
    return ProgramRuntimeOfflineMetric(
        **body,
        content_address=content_hash(body, prefix="program-runtime-offline-metric"),
    )


def build_program_runtime_offline_observability(
    bundle: ProgramRuntimeOfflineBundle,
) -> ProgramRuntimeOfflineObservabilityReport:
    """Build a stable lifecycle stream and aggregate metric set."""

    stages = sorted(_rows(bundle, "stages"), key=lambda item: int(item.get("ordinal", 0)))
    events: list[ProgramRuntimeOfflineEvent] = []
    for stage in stages:
        ordinal = int(stage.get("ordinal", 0))
        events.append(_event(ordinal * 2 - 1, "stage.started", stage, "stage input admitted"))
        events.append(_event(ordinal * 2, "stage.completed", stage, "stage output closed"))
    artifacts = bundle.artifacts
    runtime = _payload(bundle, "runtime") or {}
    domains = _rows(bundle, "domains")
    metrics = (
        _metric("artifact-count", "inventory", "artifact_count", len(artifacts), "artifacts"),
        _metric(
            "artifact-bytes",
            "inventory",
            "artifact_bytes",
            sum(item.byte_count for item in artifacts),
            "bytes",
        ),
        _metric(
            "artifact-lines",
            "inventory",
            "artifact_lines",
            sum(item.line_count for item in artifacts),
            "lines",
        ),
        _metric("domain-count", "runtime", "domain_count", len(domains), "domains"),
        _metric(
            "program-check-count",
            "runtime",
            "program_check_count",
            len(_rows(bundle, "checks")),
            "checks",
        ),
        _metric(
            "quality-check-count",
            "quality",
            "quality_check_count",
            len(_rows(bundle, "quality")),
            "checks",
        ),
        _metric(
            "release-check-count",
            "release",
            "release_check_count",
            len(_rows(bundle, "release_checks")),
            "checks",
        ),
        _metric(
            "source-stage-count",
            "runtime",
            "source_stage_count",
            int(runtime.get("stage_count", 0)),
            "stages",
        ),
        _metric(
            "offline-event-count", "observability", "offline_event_count", len(events), "events"
        ),
        _metric("accepted", "state", "accepted", int(bundle.ready), "boolean"),
        _metric("warning-count", "state", "warning_count", bundle.warning_count, "warnings"),
        _metric(
            "addressed-artifact-count",
            "integrity",
            "addressed_artifact_count",
            sum(bool(item.content_address) for item in artifacts),
            "artifacts",
        ),
    )
    accepted = (
        bundle.ready
        and len(events) == len(stages) * 2
        and [item.sequence for item in events] == list(range(1, len(events) + 1))
        and len({item.metric_id for item in metrics}) == len(metrics)
        and all(item.content_address for item in tuple(events) + tuple(metrics))
    )
    body = {
        "bundle_id": bundle.bundle_id,
        "events": events,
        "metrics": metrics,
        "accepted": accepted,
    }
    return ProgramRuntimeOfflineObservabilityReport(
        bundle_id=bundle.bundle_id,
        events=tuple(events),
        metrics=metrics,
        accepted=accepted,
        content_address=content_hash(body, prefix="program-runtime-offline-observability-report"),
    )


def audit_program_runtime_offline_observability(
    report: ProgramRuntimeOfflineObservabilityReport,
) -> dict[str, Any]:
    """Audit event sequence, metric uniqueness, and content addresses."""

    checks = (
        {
            "check_id": "accepted",
            "passed": report.accepted,
            "observed": report.accepted,
            "required": True,
        },
        {
            "check_id": "event-sequence",
            "passed": [item.sequence for item in report.events]
            == list(range(1, report.event_count + 1)),
            "observed": [item.sequence for item in report.events],
            "required": list(range(1, report.event_count + 1)),
        },
        {
            "check_id": "event-addresses",
            "passed": all(item.content_address for item in report.events),
            "observed": report.event_count,
            "required": report.event_count,
        },
        {
            "check_id": "metric-identities",
            "passed": len({item.metric_id for item in report.metrics}) == report.metric_count,
            "observed": report.metric_count,
            "required": report.metric_count,
        },
        {
            "check_id": "metric-addresses",
            "passed": all(item.content_address for item in report.metrics),
            "observed": report.metric_count,
            "required": report.metric_count,
        },
        {
            "check_id": "metric-count",
            "passed": report.metric_count == 12,
            "observed": report.metric_count,
            "required": 12,
        },
    )
    accepted = all(item["passed"] for item in checks)
    body = {"bundle_id": report.bundle_id, "checks": checks, "accepted": accepted}
    return body | {
        "content_address": content_hash(body, prefix="program-runtime-offline-observability-audit")
    }


def program_runtime_offline_events_csv(report: ProgramRuntimeOfflineObservabilityReport) -> str:
    output = io.StringIO()
    fields = (
        "sequence",
        "event_type",
        "stage_id",
        "state",
        "input_address",
        "output_address",
        "detail",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(item.to_dict() for item in report.events)
    return output.getvalue()


def program_runtime_offline_metrics_csv(report: ProgramRuntimeOfflineObservabilityReport) -> str:
    output = io.StringIO()
    fields = ("metric_id", "plane", "name", "value", "unit", "content_address")
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(item.to_dict() for item in report.metrics)
    return output.getvalue()


__all__ = [
    "ProgramRuntimeOfflineEvent",
    "ProgramRuntimeOfflineMetric",
    "ProgramRuntimeOfflineObservabilityReport",
    "audit_program_runtime_offline_observability",
    "build_program_runtime_offline_observability",
    "program_runtime_offline_events_csv",
    "program_runtime_offline_metrics_csv",
]
