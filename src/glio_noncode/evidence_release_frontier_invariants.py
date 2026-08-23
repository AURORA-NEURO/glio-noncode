"""Executable invariants for content addresses, roles, and control behavior."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseInvariantReport:
    checks: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_evidence_release_invariants(fixture: Any, evaluation: Any) -> EvidenceReleaseInvariantReport:
    record_ids = tuple(record.record_id for record in fixture.records)
    execution_ids = tuple(row.record_id for row in evaluation.executions)
    checks = (
        {"invariant": "record-identity-unique", "passed": len(record_ids) == len(set(record_ids))},
        {"invariant": "execution-identity-closed", "passed": set(record_ids) == set(execution_ids)},
        {"invariant": "source-addresses", "passed": all(source.content_address.startswith("sha256:") for source in fixture.sources)},
        {"invariant": "record-addresses", "passed": all(record.content_address.startswith("sha256:") for record in fixture.records)},
        {"invariant": "execution-addresses", "passed": all(row.content_address.startswith("sha256:") for row in evaluation.executions)},
        {"invariant": "positive-roles", "passed": all(record.role.value == "positive" for record in fixture.positive_records)},
        {"invariant": "control-roles", "passed": all(record.role.value == "control" for record in fixture.control_records)},
        {"invariant": "control-reasons", "passed": all(record.expected_issue_codes for record in fixture.control_records)},
        {"invariant": "positive-clean", "passed": all(not record.expected_issue_codes for record in fixture.positive_records)},
        {"invariant": "evaluation-accepted", "passed": evaluation.accepted},
    )
    body = {"checks": checks, "accepted": all(item["passed"] for item in checks)}
    return EvidenceReleaseInvariantReport(**body, content_address=content_hash(body))


def assert_evidence_release_invariants(fixture: Any, evaluation: Any) -> None:
    report = evaluate_evidence_release_invariants(fixture, evaluation)
    if not report.accepted:
        failed = tuple(item["invariant"] for item in report.checks if not item["passed"])
        raise AssertionError(f"evidence-release invariants failed: {failed}")


__all__ = ["EvidenceReleaseInvariantReport", "assert_evidence_release_invariants", "evaluate_evidence_release_invariants"]
