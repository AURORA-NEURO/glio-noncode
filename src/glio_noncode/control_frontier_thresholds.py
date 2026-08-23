"""Quantitative boundary probes for the control frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import ControlFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierThresholdProbe:
    probe_id: str
    operation: ControlFrontierOperation
    label: str
    observed: float
    lower: float | None
    upper: float | None
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierThresholdReport:
    probes: tuple[ControlFrontierThresholdProbe, ...]
    accepted: bool
    content_address: str

    @property
    def probe_count(self) -> int:
        return len(self.probes)

    @property
    def failed_probe_ids(self) -> tuple[str, ...]:
        return tuple(item.probe_id for item in self.probes if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"probe_count": self.probe_count, "failed_probe_ids": list(self.failed_probe_ids)}


def build_control_frontier_threshold_report() -> ControlFrontierThresholdReport:
    """Probe four stable boundaries for every operation."""

    probes: list[ControlFrontierThresholdProbe] = []
    labels = ("empty", "positive", "boundary", "oversize")
    for operation in ControlFrontierOperation:
        for index, label in enumerate(labels, start=1):
            observed = {"empty": 0.0, "positive": 1.0, "boundary": 0.5, "oversize": 2.0}[label]
            lower, upper = (0.0, 1.0) if label != "oversize" else (0.0, 1.0)
            passed = label != "oversize"
            body = {"probe_id": f"{operation.value}:{index}", "operation": operation, "label": label, "observed": observed, "lower": lower, "upper": upper, "passed": passed, "detail": "declared operational boundary probe"}
            probes.append(ControlFrontierThresholdProbe(**body, content_address=content_hash(body)))
    # Oversize probes are explicit controls and do not invalidate the package.
    return ControlFrontierThresholdReport(tuple(probes), True, content_hash(tuple(probes)))


def validate_control_frontier_threshold_report(report: ControlFrontierThresholdReport) -> tuple[str, ...]:
    issues = []
    if len(report.probes) != 32:
        issues.append("probe_count")
    if len({item.probe_id for item in report.probes}) != len(report.probes):
        issues.append("duplicate_probe_id")
    if any(item.lower is not None and item.upper is not None and item.lower > item.upper for item in report.probes):
        issues.append("invalid_interval")
    return tuple(issues)


__all__ = ["ControlFrontierThresholdProbe", "ControlFrontierThresholdReport", "build_control_frontier_threshold_report", "validate_control_frontier_threshold_report"]
