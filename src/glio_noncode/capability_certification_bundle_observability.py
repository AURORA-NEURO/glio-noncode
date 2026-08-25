"""Deterministic events and metrics for certification bundle operations."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .capability_certification import capability_certification_percent
from .capability_certification_contracts import CapabilityCertificationRuntime
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CertificationBundleEvent:
    event_id: str
    ordinal: int
    event_type: str
    state: str
    object_id: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CertificationBundleMetric:
    metric_id: str
    value: int | float | bool
    unit: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CertificationBundleObservability:
    bundle_id: str
    events: tuple[CertificationBundleEvent, ...]
    metrics: tuple[CertificationBundleMetric, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _event(
    bundle_id: str,
    ordinal: int,
    event_type: str,
    state: str,
    subject_id: str,
    detail: str,
) -> CertificationBundleEvent:
    body = {
        "event_id": f"{bundle_id}:{ordinal:03d}:{event_type}",
        "ordinal": ordinal,
        "event_type": event_type,
        "state": state,
        "object_id": subject_id,
        "detail": detail,
    }
    return CertificationBundleEvent(
        **body,
        content_address=content_hash(body, prefix="capability-certification-bundle-event"),
    )


def _metric(metric_id: str, value: int | float | bool, unit: str, detail: str) -> CertificationBundleMetric:
    body = {"metric_id": metric_id, "value": value, "unit": unit, "detail": detail}
    return CertificationBundleMetric(
        **body,
        content_address=content_hash(body, prefix="capability-certification-bundle-metric"),
    )


def build_capability_certification_bundle_observability(
    bundle_id: str,
    runtime: CapabilityCertificationRuntime,
    *,
    artifact_count: int,
    artifact_bytes: int,
) -> CertificationBundleObservability:
    """Build an address-only certification lifecycle trace."""

    events: list[CertificationBundleEvent] = [
        _event(bundle_id, 1, "bundle-selected", runtime.state.value, bundle_id, "certification bundle identity selected"),
    ]
    for stage in runtime.stages:
        events.append(
            _event(
                bundle_id,
                len(events) + 1,
                "runtime-stage",
                stage.state.value,
                stage.stage_id,
                f"{stage.ordinal}:{stage.output_address}",
            )
        )
    for event_type, detail in (
        ("artifact-inventory-closed", f"{artifact_count} artifacts indexed"),
        ("public-boundary-closed", "public projection evaluated"),
        ("bundle-finalized", "offline certification handoff finalized"),
    ):
        events.append(_event(bundle_id, len(events) + 1, event_type, runtime.state.value, bundle_id, detail))
    report = runtime.report
    metrics = (
        _metric("capability_count", report.capability_count, "count", "certified catalog rows"),
        _metric("domain_count", len(report.domain_summaries), "count", "certified catalog domains"),
        _metric("total_checks", report.total_checks, "count", "row and global checks"),
        _metric("passed_checks", report.passed_checks, "count", "passed certification checks"),
        _metric("failed_checks", report.failed_checks, "count", "failed certification checks"),
        _metric("implementation_references", sum(item.implementation_count for item in report.certificates), "count", "declared implementation references"),
        _metric("test_references", sum(item.test_count for item in report.certificates), "count", "declared test references"),
        _metric("artifact_count", artifact_count, "count", "materialized bundle artifacts"),
        _metric("artifact_bytes", artifact_bytes, "bytes", "exact UTF-8 artifact bytes"),
        _metric("certification_percent", capability_certification_percent(report), "percent", "accepted capability rows"),
        _metric("release_accepted", runtime.accepted, "boolean", "certification runtime acceptance"),
    )
    accepted = (
        tuple(item.ordinal for item in events) == tuple(range(1, len(events) + 1))
        and all(item.content_address for item in events)
        and all(item.content_address for item in metrics)
    )
    body = {"bundle_id": bundle_id, "events": events, "metrics": metrics, "accepted": accepted}
    return CertificationBundleObservability(
        bundle_id=bundle_id,
        events=tuple(events),
        metrics=tuple(metrics),
        accepted=accepted,
        content_address=content_hash(body, prefix="capability-certification-bundle-observability"),
    )


def certification_bundle_events_csv(report: CertificationBundleObservability) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("event_id", "ordinal", "event_type", "state", "object_id", "detail", "content_address"))
    for item in report.events:
        writer.writerow((item.event_id, item.ordinal, item.event_type, item.state, item.object_id, item.detail, item.content_address))
    return output.getvalue()


def certification_bundle_metrics_csv(report: CertificationBundleObservability) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("metric_id", "value", "unit", "detail", "content_address"))
    for item in report.metrics:
        writer.writerow((item.metric_id, item.value, item.unit, item.detail, item.content_address))
    return output.getvalue()


def certification_bundle_observability_from_dict(value: Mapping[str, Any]) -> CertificationBundleObservability:
    """Hydrate the addressed observability artifact without running certification."""

    events = tuple(
        CertificationBundleEvent(
            event_id=str(item.get("event_id", "")),
            ordinal=int(item.get("ordinal", 0)),
            event_type=str(item.get("event_type", "")),
            state=str(item.get("state", "")),
            object_id=str(item.get("object_id", "")),
            detail=str(item.get("detail", "")),
            content_address=str(item.get("content_address", "")),
        )
        for item in value.get("events", ())
        if isinstance(item, Mapping)
    )
    metrics = tuple(
        CertificationBundleMetric(
            metric_id=str(item.get("metric_id", "")),
            value=item.get("value", 0),
            unit=str(item.get("unit", "")),
            detail=str(item.get("detail", "")),
            content_address=str(item.get("content_address", "")),
        )
        for item in value.get("metrics", ())
        if isinstance(item, Mapping)
    )
    return CertificationBundleObservability(
        bundle_id=str(value.get("bundle_id", "")),
        events=events,
        metrics=metrics,
        accepted=bool(value.get("accepted", False)),
        content_address=str(value.get("content_address", "")),
    )


__all__ = [
    "CertificationBundleEvent",
    "CertificationBundleMetric",
    "CertificationBundleObservability",
    "build_capability_certification_bundle_observability",
    "certification_bundle_events_csv",
    "certification_bundle_metrics_csv",
    "certification_bundle_observability_from_dict",
]
