"""Shared report helpers for the C01-C04 baseline plane."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture, LinkGraphFoundationFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierCheck:
    check_id: str
    passed: bool
    detail: str
    evidence: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierReport:
    report_id: str
    checks: tuple[LinkGraphFoundationFrontierCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_checks(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"report_id": self.report_id, "checks": [item.to_dict() for item in self.checks], "failed_checks": self.failed_checks, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def check(check_id: str, passed: bool, detail: str, evidence: Iterable[str] = ()) -> LinkGraphFoundationFrontierCheck:
    return LinkGraphFoundationFrontierCheck(check_id, bool(passed), detail, tuple(dict.fromkeys(str(item) for item in evidence)))


def report(report_id: str, checks: Iterable[LinkGraphFoundationFrontierCheck]) -> LinkGraphFoundationFrontierReport:
    values = tuple(checks)
    return LinkGraphFoundationFrontierReport(report_id, values, bool(values) and all(item.passed for item in values))


def state_counts(evaluation: LinkGraphFoundationFrontierEvaluation) -> dict[str, int]:
    return dict(sorted(Counter(item.observed_state for item in evaluation.rows).items()))


def issue_counts(evaluation: LinkGraphFoundationFrontierEvaluation) -> dict[str, int]:
    values: Counter[str] = Counter()
    for row in evaluation.rows:
        values.update(row.observed_issue_codes)
    return dict(sorted(values.items()))


def operation_counts(fixture: LinkGraphFoundationFrontierFixture) -> dict[str, int]:
    return {operation.value: len(fixture.operation_records(operation)) for operation in LinkGraphFoundationFrontierOperation}


__all__ = ["LinkGraphFoundationFrontierCheck", "LinkGraphFoundationFrontierReport", "check", "issue_counts", "operation_counts", "report", "state_counts"]
