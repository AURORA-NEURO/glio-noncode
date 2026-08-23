"""Controlled failure cases used to exercise release gates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .cohort_alpha_frontier_public_data import CohortAlphaFrontierFixture
from .serialization import content_hash, jsonable


class CohortAlphaFrontierFailureMode(StrEnum):
    MISSING_RECORD = "missing_record"
    DUPLICATE_RECORD = "duplicate_record"
    WRONG_CONTEXT = "wrong_context"
    STATE_DRIFT = "state_drift"
    SOURCE_GAP = "source_gap"


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierFailureCase:
    case_id: str
    mode: CohortAlphaFrontierFailureMode
    target: str
    expected_blocked: bool
    repair: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierFailureAssessment:
    case_id: str
    detected: bool
    blocked: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierFailureReport:
    cases: tuple[CohortAlphaFrontierFailureCase, ...]
    assessments: tuple[CohortAlphaFrontierFailureAssessment, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_alpha_frontier_failure_cases() -> tuple[CohortAlphaFrontierFailureCase, ...]:
    raw = (("missing-record", CohortAlphaFrontierFailureMode.MISSING_RECORD, "C09", "restore the exact fixture row"), ("duplicate-record", CohortAlphaFrontierFailureMode.DUPLICATE_RECORD, "C10", "deduplicate by record address"), ("wrong-context", CohortAlphaFrontierFailureMode.WRONG_CONTEXT, "C11", "quarantine foreign context"), ("state-drift", CohortAlphaFrontierFailureMode.STATE_DRIFT, "C12", "replay and reconcile state"), ("source-gap", CohortAlphaFrontierFailureMode.SOURCE_GAP, "GDC", "attach a source receipt"))
    return tuple(CohortAlphaFrontierFailureCase(case_id, mode, target, True, repair, content_hash({"case_id": case_id, "mode": mode, "target": target, "repair": repair}, prefix="alpha-failure-case")) for case_id, mode, target, repair in raw)


def assess_cohort_alpha_frontier_failures(fixture: CohortAlphaFrontierFixture, evaluation: CohortAlphaFrontierEvaluation, cases: tuple[CohortAlphaFrontierFailureCase, ...] | None = None) -> CohortAlphaFrontierFailureReport:
    selected = cases or default_cohort_alpha_frontier_failure_cases()
    assessments = []
    record_ids = {record.record_id for record in fixture.records}
    source_ids = {source.source_id for source in fixture.sources}
    for case in selected:
        if case.mode is CohortAlphaFrontierFailureMode.MISSING_RECORD:
            detected = len(record_ids) != len(fixture.records) or len(evaluation.rows) != len(fixture.records)
            detail = "cardinality gate" if detected else "cardinality would detect omission"
        elif case.mode is CohortAlphaFrontierFailureMode.DUPLICATE_RECORD:
            detected = len(record_ids) != len(fixture.records)
            detail = "identity gate" if detected else "identity gate is armed"
        elif case.mode is CohortAlphaFrontierFailureMode.WRONG_CONTEXT:
            detected = any(record.control_class == "foreign_context" for record in fixture.records)
            detail = "foreign-context rows are visible to quarantine" if detected else "context gate"
        elif case.mode is CohortAlphaFrontierFailureMode.STATE_DRIFT:
            detected = any(not row.accepted for row in evaluation.rows)
            detail = "reconciliation gate" if detected else "replay gate"
        else:
            detected = len(source_ids) < 6
            detail = "source registry gate" if detected else "source receipt coverage"
        assessments.append(CohortAlphaFrontierFailureAssessment(case.case_id, detected, case.expected_blocked, detail, content_hash({"case_id": case.case_id, "detected": detected, "blocked": case.expected_blocked, "detail": detail}, prefix="alpha-failure")))
    values = tuple(assessments)
    expected = {item.case_id: item.expected_blocked for item in selected}
    return CohortAlphaFrontierFailureReport(tuple(selected), values, all(item.blocked == expected[item.case_id] for item in values), content_hash(values, prefix="alpha-failure-report"))


__all__ = ["CohortAlphaFrontierFailureAssessment", "CohortAlphaFrontierFailureCase", "CohortAlphaFrontierFailureMode", "CohortAlphaFrontierFailureReport", "assess_cohort_alpha_frontier_failures", "default_cohort_alpha_frontier_failure_cases"]
