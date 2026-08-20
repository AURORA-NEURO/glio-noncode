"""Operational and scientific monitoring signals for local runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class SignalStatus(str, Enum):
    HEALTHY = "healthy"
    WATCH = "watch"
    ALERT = "alert"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class SignalDefinition:
    signal_id: str
    description: str
    unit: str
    watch_threshold: float | None = None
    alert_threshold: float | None = None
    higher_is_worse: bool = True

    def classify(self, value: float | None) -> SignalStatus:
        if value is None:
            return SignalStatus.UNKNOWN
        if self.alert_threshold is not None:
            alert = value >= self.alert_threshold if self.higher_is_worse else value <= self.alert_threshold
            if alert:
                return SignalStatus.ALERT
        if self.watch_threshold is not None:
            watch = value >= self.watch_threshold if self.higher_is_worse else value <= self.watch_threshold
            if watch:
                return SignalStatus.WATCH
        return SignalStatus.HEALTHY


@dataclass(frozen=True, slots=True)
class SignalObservation:
    signal_id: str
    value: float | None
    status: SignalStatus
    dimensions: Mapping[str, str] = field(default_factory=dict)
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "value": self.value,
            "status": self.status.value,
            "dimensions": dict(self.dimensions),
            "note": self.note,
        }


class MonitorRegistry:
    """Registry for signals that remain meaningful across run versions."""

    definitions = (
        SignalDefinition("run_duration_seconds", "Wall time for a case run", "seconds", 300.0, 900.0),
        SignalDefinition("unsupported_claim_fraction", "Share of claims without supported inputs", "fraction", 0.35, 0.65),
        SignalDefinition("abstention_fraction", "Share of hypotheses that abstain", "fraction", 0.25, 0.60),
        SignalDefinition("context_transport_fraction", "Share of claims requiring context transport", "fraction", 0.50, 0.80),
        SignalDefinition("negative_evidence_fraction", "Share of claims with measured negative or contradictory state", "fraction", 0.40, 0.75),
        SignalDefinition("review_turnaround_hours", "Elapsed review time", "hours", 72.0, 168.0),
        SignalDefinition("replay_mismatch_count", "Replay artifact mismatch count", "count", 1.0, 1.0),
        SignalDefinition("storage_write_failures", "Immutable storage write failures", "count", 1.0, 1.0),
    )

    def __init__(self) -> None:
        self._definitions = {item.signal_id: item for item in self.definitions}

    def observe(self, signal_id: str, value: float | None, *, dimensions: Mapping[str, str] | None = None, note: str = "") -> SignalObservation:
        definition = self._definitions[signal_id]
        return SignalObservation(
            signal_id=signal_id,
            value=value,
            status=definition.classify(value),
            dimensions=dimensions or {},
            note=note,
        )

    def evaluate_run(self, metrics: Mapping[str, float | None], *, case_id: str) -> tuple[SignalObservation, ...]:
        return tuple(
            self.observe(signal_id, metrics.get(signal_id), dimensions={"case_id": case_id})
            for signal_id in self._definitions
        )

    def summary(self, observations: tuple[SignalObservation, ...]) -> dict[str, Any]:
        counts = {status.value: 0 for status in SignalStatus}
        for observation in observations:
            counts[observation.status.value] += 1
        return {
            "total": len(observations),
            "counts": counts,
            "alerts": [item.to_dict() for item in observations if item.status == SignalStatus.ALERT],
            "watch": [item.to_dict() for item in observations if item.status == SignalStatus.WATCH],
        }
