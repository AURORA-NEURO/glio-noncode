"""Boundary probes for numeric and state thresholds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import VALIDATION_RELEASE_FRONTIER_CONTEXT_KEY, ValidationReleaseOperation, ValidationReleaseState
from .validation_release_frontier_operations import run_validation_release_operation
from .validation_release_frontier_public_data import _off_target, _voi


@dataclass(frozen=True, slots=True)
class ValidationReleaseThresholdProbe:
    probe_id: str
    operation: str
    boundary: str
    expected_state: str
    observed_state: str
    passed: bool
    issue_codes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseThresholdReport:
    probes: tuple[ValidationReleaseThresholdProbe, ...]
    accepted: bool
    content_address: str

    @property
    def probe_count(self) -> int:
        return len(self.probes)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_threshold_report() -> ValidationReleaseThresholdReport:
    cases = (("c13-review-edge", ValidationReleaseOperation.OFF_TARGET_RISK, _off_target(off_targets=[{"score": 0.25, "weight": 1.0}]), ValidationReleaseState.REVIEW, "off_target_risk_review", "weighted review threshold"), ("c13-block-edge", ValidationReleaseOperation.OFF_TARGET_RISK, _off_target(off_targets=[{"score": 0.60, "weight": 1.0}]), ValidationReleaseState.BLOCKED, "off_target_risk_high", "maximum blocking threshold"), ("c14-zero-selection", ValidationReleaseOperation.VALUE_OF_INFORMATION, _voi(budget=1.0), ValidationReleaseState.REVIEW, "", "budget below all experiment costs"), ("c14-context-edge", ValidationReleaseOperation.VALUE_OF_INFORMATION, _voi(context_key="foreign"), ValidationReleaseState.BLOCKED, "context_mismatch", "exact context boundary"))
    probes = []
    for probe_id, operation, payload, expected, issue, boundary in cases:
        result = run_validation_release_operation(operation, payload)
        passed = result.state == expected and (not issue or issue in result.issue_codes)
        body = {"probe_id": probe_id, "operation": operation.value, "boundary": boundary, "expected_state": expected.value, "observed_state": result.state.value, "passed": passed, "issue_codes": result.issue_codes}
        probes.append(ValidationReleaseThresholdProbe(**body, content_address=content_hash(body)))
    return ValidationReleaseThresholdReport(tuple(probes), all(item.passed for item in probes), content_hash(tuple(probes)))


__all__ = ["ValidationReleaseThresholdProbe", "ValidationReleaseThresholdReport", "build_validation_release_threshold_report"]
