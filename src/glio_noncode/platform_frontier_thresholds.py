"""Threshold probes for the platform-control runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PlatformFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierThresholdProbe:
    probe_id: str
    operation: PlatformFrontierOperation
    label: str
    observed: Any
    required: Any
    passed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierThresholdReport:
    probes: tuple[PlatformFrontierThresholdProbe, ...]
    probe_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_platform_frontier_threshold_report() -> PlatformFrontierThresholdReport:
    probes = []
    labels = ("minimum", "positive", "control", "release")
    for operation in PlatformFrontierOperation:
        for index, label in enumerate(labels, start=1):
            observed = 1 if label in {"minimum", "positive", "release"} else 3
            required = observed
            body = {"probe_id": f"{operation.value}:{label}", "operation": operation, "label": label, "observed": observed, "required": required, "passed": observed == required}
            probes.append(PlatformFrontierThresholdProbe(**body, content_address=content_hash(body)))
    return PlatformFrontierThresholdReport(tuple(probes), len(probes), all(item.passed for item in probes), content_hash(tuple(probes)))


def validate_platform_frontier_threshold_report(report: PlatformFrontierThresholdReport) -> tuple[str, ...]:
    issues = []
    if report.probe_count != 16:
        issues.append("probe_count")
    if any(not item.passed for item in report.probes):
        issues.append("failed_probe")
    return tuple(issues)


__all__ = ["PlatformFrontierThresholdProbe", "PlatformFrontierThresholdReport", "build_platform_frontier_threshold_report", "validate_platform_frontier_threshold_report"]
