"""Calibration readiness checks without fabricating significance estimates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable

from .cohort_beta_frontier_comparator import CohortBetaFrontierComparatorReport
from .cohort_beta_frontier_public_data import CohortBetaFrontierFixture
from .serialization import content_hash, jsonable


class CohortBetaFrontierCalibrationState(StrEnum):
    DESCRIPTIVE = "descriptive"
    READY_FOR_CALIBRATION = "ready_for_calibration"
    CALIBRATION_BLOCKED = "calibration_blocked"


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierCalibrationRequirement:
    operation: str
    requirement_id: str
    detail: str
    present: bool
    blocking: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierCalibrationReport:
    requirements: tuple[CohortBetaFrontierCalibrationRequirement, ...]
    state: CohortBetaFrontierCalibrationState
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_calibration_report(fixture: CohortBetaFrontierFixture, comparator: CohortBetaFrontierComparatorReport) -> CohortBetaFrontierCalibrationReport:
    raw = (("C05", "recurrence-null", "matched callable null distribution across independent cohorts", False, True), ("C06", "burden-null", "callable-base denominator calibration across cohorts", False, True), ("C07", "feature-null", "feature definition and matched-control calibration", False, True), ("C08", "set-null", "versioned set transport and overlap calibration", False, True), ("all", "source-version", "source version receipts are present for descriptive output", bool(comparator.receipts), False), ("all", "claim-ceiling", "no significance output is emitted by this plane", True, False))
    requirements = tuple(CohortBetaFrontierCalibrationRequirement(operation, requirement_id, detail, present, blocking, content_hash({"operation": operation, "requirement_id": requirement_id, "present": present, "blocking": blocking}, prefix="calibration")) for operation, requirement_id, detail, present, blocking in raw)
    return CohortBetaFrontierCalibrationReport(requirements, CohortBetaFrontierCalibrationState.DESCRIPTIVE, all(item.present or not item.blocking for item in requirements), content_hash({"fixture": fixture.fixture_id, "requirements": requirements}, prefix="calibration-report"))


def calibration_summary(report: CohortBetaFrontierCalibrationReport) -> dict[str, Any]:
    return {"state": report.state.value, "accepted": report.accepted, "present": sum(item.present for item in report.requirements), "blocking_missing": sum(item.blocking and not item.present for item in report.requirements)}


__all__ = ["CohortBetaFrontierCalibrationReport", "CohortBetaFrontierCalibrationRequirement", "CohortBetaFrontierCalibrationState", "build_cohort_beta_frontier_calibration_report", "calibration_summary"]
