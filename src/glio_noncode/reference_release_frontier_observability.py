"""Operational observations for release runs without raw payload logging."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from .reference_release_frontier_runtime import ReferenceReleaseRuntimeReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ReferenceReleaseObservation:
    """One redacted runtime observation."""

    observation_id: str
    category: str
    value: Any
    severity: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseObservabilityReport:
    """Counters, stage timings placeholders, and issue observations."""

    run_id: str
    observations: tuple[ReferenceReleaseObservation, ...]
    counters: tuple[tuple[str, int], ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "observation_count": len(self.observations),
            "counter_map": dict(self.counters),
        }


def _observation(
    index: int, category: str, value: Any, severity: str = "info"
) -> ReferenceReleaseObservation:
    body = {
        "observation_id": f"release-observation:{index:03d}",
        "category": category,
        "value": value,
        "severity": severity,
    }
    return ReferenceReleaseObservation(
        **body, content_address=content_hash(body, prefix="observation")
    )


def observe_reference_release(
    runtime: ReferenceReleaseRuntimeReport,
) -> ReferenceReleaseObservabilityReport:
    """Create stable stage, state, issue, and policy counters."""

    issue_counts = Counter(
        code for item in runtime.evaluation.executions for code in item.issue_codes
    )
    state_counts = Counter(item.state for item in runtime.evaluation.executions)
    observations: list[ReferenceReleaseObservation] = []
    index = 1
    for stage in runtime.stages:
        observations.append(
            _observation(
                index,
                "stage",
                {"stage_id": stage.stage_id, "sequence": stage.sequence, "state": stage.state},
                "info" if stage.state != "blocked" else "review",
            )
        )
        index += 1
    for state, count in sorted(state_counts.items()):
        observations.append(
            _observation(index, "execution_state", {"state": state, "count": count})
        )
        index += 1
    for code, count in sorted(issue_counts.items()):
        observations.append(
            _observation(index, "issue_code", {"code": code, "count": count}, "review")
        )
        index += 1
    counters = tuple(
        sorted(
            {
                "stage_count": len(runtime.stages),
                "execution_count": len(runtime.evaluation.executions),
                "check_count": len(runtime.evaluation.checks),
                "positive_count": runtime.evaluation.positive_count,
                "control_count": runtime.evaluation.control_count,
                "observation_count": len(observations),
                **{f"state:{key}": value for key, value in state_counts.items()},
                **{f"issue:{key}": value for key, value in issue_counts.items()},
            }.items()
        )
    )
    accepted = len(observations) >= len(runtime.stages) and all(
        item.content_address.startswith("observation:") for item in observations
    )
    body = {
        "run_id": runtime.run_id,
        "observations": tuple(observations),
        "counters": counters,
        "accepted": accepted,
    }
    return ReferenceReleaseObservabilityReport(
        **body, content_address=content_hash(body, prefix="observability")
    )


def verify_reference_release_observability(
    report: ReferenceReleaseObservabilityReport,
) -> tuple[str, ...]:
    """Return observation and counter integrity failures."""

    failures: list[str] = []
    if not report.accepted:
        failures.append("observability-not-accepted")
    if any(not item.content_address.startswith("observation:") for item in report.observations):
        failures.append("observation-address")
    if len(dict(report.counters)) != len(report.counters):
        failures.append("counter-duplicates")
    if report.to_dict().get("observation_count", 0) != len(report.observations):
        failures.append("observation-count")
    if not report.content_address.startswith("observability:"):
        failures.append("observability-address")
    return tuple(failures)


__all__ = [
    "ReferenceReleaseObservation",
    "ReferenceReleaseObservabilityReport",
    "observe_reference_release",
    "verify_reference_release_observability",
]
