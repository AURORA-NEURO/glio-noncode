"""Replay and expectation checks for the C05–C08 annotation fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .reference_annotation_fixture_eval import ReferenceAnnotationEvaluationReport
from .reference_annotation_public_data import (
    REFERENCE_ANNOTATION_CONTEXT_KEY,
    REFERENCE_ANNOTATION_CONTROL_COUNT,
    REFERENCE_ANNOTATION_POSITIVE_COUNT,
    ReferenceAnnotationFixture,
    ReferenceAnnotationRole,
    default_reference_annotation_fixture,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationReplayExpectation:
    """Replay contract that keeps fixture identity and floors explicit."""

    fixture_id: str
    fixture_version: str
    context_key: str
    positive_floor: int
    control_floor: int
    evaluation_check_floor: int
    source_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationReplayCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationReplayReport:
    fixture_id: str
    fixture_version: str
    context_key: str
    checks: tuple[ReferenceAnnotationReplayCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_check_ids": list(self.failed_check_ids),
        }


def _address(body: Any) -> str:
    return content_hash(body)


def build_reference_annotation_expectation(
    fixture: ReferenceAnnotationFixture | None = None,
    *,
    evaluation_check_floor: int = 120,
) -> ReferenceAnnotationReplayExpectation:
    selected = fixture or default_reference_annotation_fixture()
    if evaluation_check_floor < 1:
        raise ValidationError("annotation evaluation check floor must be positive")
    body = {
        "fixture_id": selected.fixture_id,
        "fixture_version": selected.fixture_version,
        "context_key": selected.context_key,
        "positive_floor": REFERENCE_ANNOTATION_POSITIVE_COUNT,
        "control_floor": REFERENCE_ANNOTATION_CONTROL_COUNT,
        "evaluation_check_floor": evaluation_check_floor,
        "source_ids": tuple(source.source_id for source in selected.sources),
        "record_ids": tuple(record.record_id for record in selected.records),
    }
    return ReferenceAnnotationReplayExpectation(**body, content_address=_address(body))


def _check(check_id: str, passed: bool, detail: str) -> ReferenceAnnotationReplayCheck:
    body = {"check_id": check_id, "passed": passed, "detail": detail}
    return ReferenceAnnotationReplayCheck(check_id, passed, detail, _address(body))


def replay_reference_annotation_evaluation(
    report: ReferenceAnnotationEvaluationReport,
    *,
    expectation: ReferenceAnnotationReplayExpectation | None = None,
    expected_context_key: str = REFERENCE_ANNOTATION_CONTEXT_KEY,
) -> ReferenceAnnotationReplayReport:
    """Compare a report with the stable fixture identity and minimum evidence floors."""

    expected = expectation or build_reference_annotation_expectation()
    checks = [
        _check(
            "fixture-id", report.fixture_id == expected.fixture_id, "fixture ID matches expectation"
        ),
        _check(
            "fixture-version",
            report.fixture_version == expected.fixture_version,
            "fixture version matches expectation",
        ),
        _check(
            "context-key",
            report.context_key == expected_context_key == expected.context_key,
            "context key matches expectation",
        ),
        _check("source-address", bool(report.catalog_address), "catalog address is retained"),
        _check(
            "positive-floor",
            report.positive_count >= expected.positive_floor,
            "positive receipt floor is met",
        ),
        _check(
            "control-floor",
            report.control_count >= expected.control_floor,
            "control receipt floor is met",
        ),
        _check(
            "record-floor",
            len(report.receipts) >= len(expected.record_ids),
            "record receipt floor is met",
        ),
        _check(
            "check-floor",
            len(report.checks) >= expected.evaluation_check_floor,
            "evaluation check floor is met",
        ),
        _check("accepted", report.accepted, "evaluation report is accepted"),
        _check(
            "positive-role",
            all(
                receipt.role is ReferenceAnnotationRole.POSITIVE
                and receipt.resolution_state == "supported"
                for receipt in report.receipts
                if receipt.role is ReferenceAnnotationRole.POSITIVE
            ),
            "positive role outcomes remain supported",
        ),
        _check(
            "control-role",
            all(
                receipt.resolution_state != "supported"
                for receipt in report.receipts
                if receipt.role is ReferenceAnnotationRole.CONTROL
            ),
            "control role outcomes remain review states",
        ),
        _check(
            "receipt-addresses",
            all(receipt.content_address for receipt in report.receipts),
            "receipt addresses are retained",
        ),
    ]
    body = {
        "fixture_id": report.fixture_id,
        "fixture_version": report.fixture_version,
        "context_key": report.context_key,
        "checks": checks,
    }
    return ReferenceAnnotationReplayReport(
        report.fixture_id,
        report.fixture_version,
        report.context_key,
        tuple(checks),
        _address(body),
    )


__all__ = [
    "ReferenceAnnotationReplayCheck",
    "ReferenceAnnotationReplayExpectation",
    "ReferenceAnnotationReplayReport",
    "build_reference_annotation_expectation",
    "replay_reference_annotation_evaluation",
]
