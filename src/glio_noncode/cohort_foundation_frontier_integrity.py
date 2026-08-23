"""Content-address and duplicate checks for the foundation release."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_fixture_eval import CohortFoundationEvaluation
from .cohort_foundation_frontier_public_data import CohortFoundationFixture


@dataclass(frozen=True, slots=True)
class CohortFoundationIntegrityCheck:
    check_id: str
    passed: bool
    observed: Any
    expected: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationIntegrityReport:
    report_id: str
    checks: tuple[CohortFoundationIntegrityCheck, ...]
    accepted: bool
    content_address: str

    @property
    def failures(self) -> tuple[CohortFoundationIntegrityCheck, ...]:
        return tuple(item for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_cohort_foundation_frontier_integrity(fixture: CohortFoundationFixture, evaluation: CohortFoundationEvaluation) -> CohortFoundationIntegrityReport:
    record_ids = tuple(item.record_id for item in fixture.records)
    execution_ids = tuple(item.record_id for item in evaluation.executions)
    addresses = tuple(item.content_address for item in evaluation.executions)
    values = (
        ("fixture-record-unique", len(set(record_ids)) == len(record_ids), len(set(record_ids)), len(record_ids), "fixture IDs are unique"),
        ("execution-record-unique", len(set(execution_ids)) == len(execution_ids), len(set(execution_ids)), len(execution_ids), "execution IDs are unique"),
        ("execution-address-unique", len(set(addresses)) == len(addresses), len(set(addresses)), len(addresses), "execution addresses are unique"),
        ("address-nonempty", all(addresses), all(bool(item) for item in addresses), True, "every execution is addressed"),
        ("fixture-addressed", bool(fixture.fixture_id), fixture.fixture_id, True, "fixture identity is present"),
        ("evaluation-addressed", bool(evaluation.content_address), evaluation.content_address, True, "evaluation identity is present"),
        ("record-cardinality", len(record_ids) == len(execution_ids), len(execution_ids), len(record_ids), "fixture and execution cardinality"),
        ("context-bound", all(item.context_key in {fixture.context_key, fixture.foreign_context_key} for item in fixture.records), True, True, "records retain declared context"),
    )
    checks = tuple(CohortFoundationIntegrityCheck(check_id, passed, observed, expected, detail, content_hash((check_id, passed, observed, expected, detail))) for check_id, passed, observed, expected, detail in values)
    body = {"report_id": "cohort-foundation-frontier-integrity", "checks": checks}
    return CohortFoundationIntegrityReport(body["report_id"], checks, all(item.passed for item in checks), content_hash(body))


__all__ = ["CohortFoundationIntegrityCheck", "CohortFoundationIntegrityReport", "evaluate_cohort_foundation_frontier_integrity"]
