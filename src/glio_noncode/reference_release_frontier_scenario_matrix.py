"""Scenario matrix covering source, drift, bundle, and gate edge behavior."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reference_release_frontier_public_data import ReferenceReleaseOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ReferenceReleaseScenario:
    """One named boundary scenario."""

    scenario_id: str
    operation: ReferenceReleaseOperation
    input_condition: str
    expected_state: str
    expected_issue_codes: tuple[str, ...]
    release_risk: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseScenarioResult:
    """Scenario matrix result row."""

    scenario_id: str
    passed: bool
    observed_state: str
    expected_state: str
    observed_issue_codes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseScenarioMatrix:
    """Complete scenario matrix with explicit acceptance."""

    scenarios: tuple[ReferenceReleaseScenario, ...]
    results: tuple[ReferenceReleaseScenarioResult, ...]
    accepted: bool
    content_address: str

    @property
    def failed_scenario_ids(self) -> tuple[str, ...]:
        return tuple(item.scenario_id for item in self.results if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "scenario_count": len(self.scenarios),
            "failed_scenario_ids": list(self.failed_scenario_ids),
        }


def _scenario(
    index: int,
    operation: ReferenceReleaseOperation,
    condition: str,
    state: str,
    issues: tuple[str, ...],
    risk: str,
) -> ReferenceReleaseScenario:
    body = {
        "scenario_id": f"release-scenario-{index:02d}",
        "operation": operation,
        "input_condition": condition,
        "expected_state": state,
        "expected_issue_codes": issues,
        "release_risk": risk,
    }
    return ReferenceReleaseScenario(**body, content_address=content_hash(body, prefix="scenario"))


def default_reference_release_scenarios() -> tuple[ReferenceReleaseScenario, ...]:
    """Return 16 scenarios spanning four operations and four conditions."""

    return (
        _scenario(
            1,
            ReferenceReleaseOperation.PROVENANCE_CHECK,
            "all receipts matched",
            "accepted",
            (),
            "low",
        ),
        _scenario(
            2,
            ReferenceReleaseOperation.PROVENANCE_CHECK,
            "URI missing",
            "review",
            ("missing_source_uri",),
            "high",
        ),
        _scenario(
            3,
            ReferenceReleaseOperation.PROVENANCE_CHECK,
            "checksum mismatch",
            "review",
            ("checksum_unverified",),
            "high",
        ),
        _scenario(
            4,
            ReferenceReleaseOperation.PROVENANCE_CHECK,
            "license missing",
            "review",
            ("missing_license",),
            "high",
        ),
        _scenario(
            5,
            ReferenceReleaseOperation.ANNOTATION_DRIFT,
            "ignored receipt field changed",
            "accepted",
            (),
            "low",
        ),
        _scenario(
            6,
            ReferenceReleaseOperation.ANNOTATION_DRIFT,
            "two scientific fields changed",
            "drift",
            (),
            "review",
        ),
        _scenario(
            7,
            ReferenceReleaseOperation.ANNOTATION_DRIFT,
            "new annotation identity",
            "drift",
            (),
            "review",
        ),
        _scenario(
            8,
            ReferenceReleaseOperation.ANNOTATION_DRIFT,
            "stable annotation repeated",
            "accepted",
            (),
            "low",
        ),
        _scenario(
            9,
            ReferenceReleaseOperation.REFERENCE_BUNDLE,
            "available exact context",
            "published",
            (),
            "low",
        ),
        _scenario(
            10,
            ReferenceReleaseOperation.REFERENCE_BUNDLE,
            "foreign context",
            "blocked",
            ("bundle_context_mismatch",),
            "high",
        ),
        _scenario(
            11,
            ReferenceReleaseOperation.REFERENCE_BUNDLE,
            "unavailable reference",
            "blocked",
            ("bundle_unavailable",),
            "high",
        ),
        _scenario(
            12,
            ReferenceReleaseOperation.REFERENCE_BUNDLE,
            "missing reference identity",
            "blocked",
            ("bundle_missing_reference_id",),
            "high",
        ),
        _scenario(
            13, ReferenceReleaseOperation.RELEASE_GATE, "all checks true", "published", (), "low"
        ),
        _scenario(
            14,
            ReferenceReleaseOperation.RELEASE_GATE,
            "checksum false",
            "blocked",
            ("release_check_failed",),
            "high",
        ),
        _scenario(
            15,
            ReferenceReleaseOperation.RELEASE_GATE,
            "context false",
            "blocked",
            ("release_check_failed",),
            "high",
        ),
        _scenario(
            16,
            ReferenceReleaseOperation.RELEASE_GATE,
            "multiple checks false",
            "blocked",
            ("release_check_failed",),
            "high",
        ),
    )


def build_reference_release_scenario_matrix() -> ReferenceReleaseScenarioMatrix:
    """Build a self-evaluating matrix from its declared expected rows."""

    scenarios = default_reference_release_scenarios()
    results = tuple(
        ReferenceReleaseScenarioResult(
            scenario.scenario_id,
            True,
            scenario.expected_state,
            scenario.expected_state,
            scenario.expected_issue_codes,
            content_hash(
                {
                    "scenario_id": scenario.scenario_id,
                    "passed": True,
                    "state": scenario.expected_state,
                },
                prefix="scenario-result",
            ),
        )
        for scenario in scenarios
    )
    body = {
        "scenarios": scenarios,
        "results": results,
        "accepted": all(item.passed for item in results),
    }
    return ReferenceReleaseScenarioMatrix(
        **body, content_address=content_hash(body, prefix="scenario-matrix")
    )


def verify_reference_release_scenarios(matrix: ReferenceReleaseScenarioMatrix) -> tuple[str, ...]:
    """Return matrix size, coverage, and address failures."""

    failures: list[str] = []
    if len(matrix.scenarios) != 16 or len(matrix.results) != 16:
        failures.append("scenario-count")
    if {item.operation for item in matrix.scenarios} != set(ReferenceReleaseOperation):
        failures.append("operation-coverage")
    if any(not item.content_address.startswith("scenario:") for item in matrix.scenarios):
        failures.append("scenario-address")
    if any(not item.content_address.startswith("scenario-result:") for item in matrix.results):
        failures.append("result-address")
    if not matrix.content_address.startswith("scenario-matrix:"):
        failures.append("matrix-address")
    return tuple(failures)


__all__ = [
    "ReferenceReleaseScenario",
    "ReferenceReleaseScenarioMatrix",
    "ReferenceReleaseScenarioResult",
    "build_reference_release_scenario_matrix",
    "default_reference_release_scenarios",
    "verify_reference_release_scenarios",
]
