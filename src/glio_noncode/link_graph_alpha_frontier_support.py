"""Shared deterministic helpers for the Domain 10 link assurance plane."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .link_graph_alpha_frontier_public_data import (
    LinkGraphAlphaFrontierFixture,
    LinkGraphAlphaFrontierOperation,
    LinkGraphAlphaFrontierRecord,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierCheck:
    """One named assertion with an inspectable reason and scope."""

    check_id: str
    passed: bool
    scope: str
    detail: str
    evidence: tuple[str, ...] = ()
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierReport:
    """Reusable report envelope for assurance submodules."""

    report_id: str
    checks: tuple[LinkGraphAlphaFrontierCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_checks(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "report_id": self.report_id,
            "checks": [item.to_dict() for item in self.checks],
            "failed_checks": self.failed_checks,
            "accepted": self.accepted,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


def records_for(
    fixture: LinkGraphAlphaFrontierFixture,
    operation: LinkGraphAlphaFrontierOperation | str | None = None,
) -> tuple[LinkGraphAlphaFrontierRecord, ...]:
    if operation is None:
        return fixture.records
    return fixture.operation_records(operation)


def result_state_counts(evaluation: LinkGraphAlphaFrontierEvaluation) -> dict[str, int]:
    return dict(sorted(Counter(item.observed_state for item in evaluation.rows).items()))


def expected_state_counts(fixture: LinkGraphAlphaFrontierFixture) -> dict[str, int]:
    return dict(sorted(Counter(item.expected_state for item in fixture.records).items()))


def operation_counts(fixture: LinkGraphAlphaFrontierFixture) -> dict[str, int]:
    return {
        operation.value: len(fixture.operation_records(operation))
        for operation in LinkGraphAlphaFrontierOperation
    }


def issue_counts(evaluation: LinkGraphAlphaFrontierEvaluation) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in evaluation.rows:
        counts.update(row.observed_issue_codes)
    return dict(sorted(counts.items()))


def issue_set(evaluation: LinkGraphAlphaFrontierEvaluation) -> frozenset[str]:
    return frozenset(code for row in evaluation.rows for code in row.observed_issue_codes)


def record_hashes(records: Iterable[LinkGraphAlphaFrontierRecord]) -> tuple[str, ...]:
    return tuple(sorted(item.content_address for item in records))


def as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def check(
    check_id: str,
    passed: bool,
    detail: str,
    *,
    scope: str = "fixture",
    evidence: Iterable[str] = (),
    severity: str = "error",
) -> LinkGraphAlphaFrontierCheck:
    return LinkGraphAlphaFrontierCheck(
        check_id,
        bool(passed),
        scope,
        detail,
        tuple(dict.fromkeys(str(item) for item in evidence)),
        severity,
    )


def report(
    report_id: str,
    checks: Iterable[LinkGraphAlphaFrontierCheck],
) -> LinkGraphAlphaFrontierReport:
    values = tuple(checks)
    return LinkGraphAlphaFrontierReport(report_id, values, all(item.passed for item in values))


__all__ = [
    "LinkGraphAlphaFrontierCheck",
    "LinkGraphAlphaFrontierReport",
    "as_mapping",
    "check",
    "expected_state_counts",
    "issue_counts",
    "issue_set",
    "operation_counts",
    "record_hashes",
    "records_for",
    "report",
    "result_state_counts",
]
