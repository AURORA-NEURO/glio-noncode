"""Deterministic events and metrics for offline module-fabric bundles."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any

from .module_fabric_bundle_contracts import FabricBundle
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class FabricBundleEvent:
    event_id: str
    ordinal: int
    event_type: str
    state: str
    subject_id: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricBundleMetric:
    metric_id: str
    value: int | float | bool
    unit: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricBundleObservability:
    bundle_id: str
    events: tuple[FabricBundleEvent, ...]
    metrics: tuple[FabricBundleMetric, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _event(
    bundle: FabricBundle,
    ordinal: int,
    event_type: str,
    state: str,
    subject_id: str,
    detail: str,
) -> FabricBundleEvent:
    body = {
        "event_id": f"{bundle.bundle_id}:{ordinal:03d}:{event_type}",
        "ordinal": ordinal,
        "event_type": event_type,
        "state": state,
        "subject_id": subject_id,
        "detail": detail,
    }
    return FabricBundleEvent(
        **body,
        content_address=content_hash(body, prefix="module-fabric-bundle-event"),
    )


def _metric(metric_id: str, value: int | float | bool, unit: str, detail: str) -> FabricBundleMetric:
    body = {"metric_id": metric_id, "value": value, "unit": unit, "detail": detail}
    return FabricBundleMetric(
        **body,
        content_address=content_hash(body, prefix="module-fabric-bundle-metric"),
    )


def build_module_fabric_bundle_observability(bundle: FabricBundle) -> FabricBundleObservability:
    """Create a stable lifecycle trace without embedding artifact payloads."""

    events: list[FabricBundleEvent] = [
        _event(bundle, 1, "bundle-selected", bundle.state.value, bundle.bundle_id, "bundle identity selected"),
        _event(bundle, 2, "artifact-inventory-closed", bundle.state.value, bundle.bundle_id, "artifact inventory indexed"),
    ]
    for index, artifact in enumerate(bundle.artifacts, start=3):
        events.append(
            _event(
                bundle,
                index,
                "artifact-addressed",
                "accepted",
                artifact.artifact_id,
                f"{artifact.media_type}:{artifact.byte_count} bytes",
            )
        )
    base = len(events)
    events.extend(
        (
            _event(bundle, base + 1, "checks-evaluated", "accepted" if bundle.failed_check_count == 0 else "blocked", bundle.bundle_id, f"{len(bundle.checks)} checks retained"),
            _event(bundle, base + 2, "public-boundary-closed", "accepted" if bundle.failed_check_count == 0 else "blocked", bundle.bundle_id, "public projection boundary evaluated"),
            _event(bundle, base + 3, "bundle-finalized", bundle.state.value, bundle.bundle_id, "offline handoff finalized"),
        )
    )
    metrics = (
        _metric("artifact_count", bundle.artifact_count, "count", "materialized artifact count"),
        _metric("artifact_bytes", sum(item.byte_count for item in bundle.artifacts), "bytes", "total exact UTF-8 artifact bytes"),
        _metric("check_count", len(bundle.checks), "count", "retained bundle checks"),
        _metric("passed_check_count", bundle.passed_check_count, "count", "passed bundle checks"),
        _metric("failed_check_count", bundle.failed_check_count, "count", "failed bundle checks"),
        _metric("warning_count", bundle.warning_count, "count", "bundle warning count"),
        _metric("release_accepted", bundle.accepted, "boolean", "manifest acceptance state"),
    )
    accepted = (
        tuple(item.ordinal for item in events) == tuple(range(1, len(events) + 1))
        and all(item.content_address for item in events)
        and all(item.content_address for item in metrics)
    )
    body = {"bundle_id": bundle.bundle_id, "events": events, "metrics": metrics, "accepted": accepted}
    return FabricBundleObservability(
        bundle_id=bundle.bundle_id,
        events=tuple(events),
        metrics=tuple(metrics),
        accepted=accepted,
        content_address=content_hash(body, prefix="module-fabric-bundle-observability"),
    )


def fabric_bundle_events_csv(observability: FabricBundleObservability) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("event_id", "ordinal", "event_type", "state", "subject_id", "detail", "content_address"))
    for event in observability.events:
        writer.writerow((event.event_id, event.ordinal, event.event_type, event.state, event.subject_id, event.detail, event.content_address))
    return output.getvalue()


def fabric_bundle_metrics_csv(observability: FabricBundleObservability) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("metric_id", "value", "unit", "detail", "content_address"))
    for metric in observability.metrics:
        writer.writerow((metric.metric_id, metric.value, metric.unit, metric.detail, metric.content_address))
    return output.getvalue()


__all__ = [
    "FabricBundleEvent",
    "FabricBundleMetric",
    "FabricBundleObservability",
    "build_module_fabric_bundle_observability",
    "fabric_bundle_events_csv",
    "fabric_bundle_metrics_csv",
]
