"""Failure probes for operation boundaries and release assumptions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseOperation, ValidationReleaseState
from .validation_release_frontier_operations import run_validation_release_operation
from .validation_release_frontier_public_data import _claim, _off_target, _package, _voi


@dataclass(frozen=True, slots=True)
class ValidationReleaseFailureProbe:
    probe_id: str
    operation: str
    expected_state: str
    observed_state: str
    passed: bool
    issue_codes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseFailureReport:
    probes: tuple[ValidationReleaseFailureProbe, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def run_validation_release_failure_injections() -> ValidationReleaseFailureReport:
    cases = (("off-target-high", ValidationReleaseOperation.OFF_TARGET_RISK, _off_target(off_targets=[{"score": 0.9, "weight": 1.0}]), ValidationReleaseState.BLOCKED, "off_target_risk_high"), ("off-target-context", ValidationReleaseOperation.OFF_TARGET_RISK, _off_target(context_key="foreign"), ValidationReleaseState.BLOCKED, "context_mismatch"), ("voi-cycle", ValidationReleaseOperation.VALUE_OF_INFORMATION, _voi(experiments=[{"experiment_id": "a", "cost": 1, "information_gain": 0.2, "risk_reduction": 0.2, "prerequisites": ["b"]}, {"experiment_id": "b", "cost": 1, "information_gain": 0.2, "risk_reduction": 0.2, "prerequisites": ["a"]}]), ValidationReleaseState.BLOCKED, "prerequisite_cycle"), ("package-empty", ValidationReleaseOperation.EXPERIMENT_PACKAGE, _package(experiments=[]), ValidationReleaseState.REJECTED, "experiments_missing"), ("claim-unknown", ValidationReleaseOperation.CLAIM_UPDATE, _claim(results=[{"claim_id": "unknown", "context_key": _claim()["context_key"], "evidence_address": "sha256:x"}]), ValidationReleaseState.REVIEW, "unknown_claim"), ("claim-foreign", ValidationReleaseOperation.CLAIM_UPDATE, _claim(results=[{**_claim()["results"][0], "context_key": "foreign"}]), ValidationReleaseState.BLOCKED, "context_mismatch"))
    probes = []
    for probe_id, operation, payload, expected, issue in cases:
        result = run_validation_release_operation(operation, payload)
        body = {"probe_id": probe_id, "operation": operation.value, "expected_state": expected.value, "observed_state": result.state.value, "passed": result.state == expected and issue in result.issue_codes, "issue_codes": result.issue_codes}
        probes.append(ValidationReleaseFailureProbe(**body, content_address=content_hash(body)))
    return ValidationReleaseFailureReport(tuple(probes), all(item.passed for item in probes), content_hash(tuple(probes)))


__all__ = ["ValidationReleaseFailureProbe", "ValidationReleaseFailureReport", "run_validation_release_failure_injections"]
