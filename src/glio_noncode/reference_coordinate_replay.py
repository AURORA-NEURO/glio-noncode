"""Replay and drift checks for the Domain 04 coordinate fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reference_coordinate_fixture_eval import evaluate_reference_coordinate_fixture
from .reference_coordinate_public_data import (
    REFERENCE_COORDINATE_CONTEXT_KEY,
    REFERENCE_COORDINATE_FIXTURE_VERSION,
    ReferenceCoordinateFixtureCatalog,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ReferenceCoordinateReplayExpectation:
    """Release floors and exact identity values required for replay."""

    fixture_id: str
    fixture_version: str
    context_key: str
    source_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    operation_ids: tuple[str, ...]
    minimum_check_count: int
    minimum_positive_count: int
    minimum_control_count: int

    def __post_init__(self) -> None:
        require_non_empty(self.fixture_id, "fixture ID")
        require_non_empty(self.fixture_version, "fixture version")
        require_non_empty(self.context_key, "context key")
        if self.minimum_check_count < 1:
            raise ValueError("minimum check count must be positive")
        if self.minimum_positive_count < 1 or self.minimum_control_count < 1:
            raise ValueError("replay requires positive and control floors")

    @classmethod
    def for_catalog(
        cls,
        catalog: ReferenceCoordinateFixtureCatalog,
        *,
        minimum_check_count: int = 130,
    ) -> ReferenceCoordinateReplayExpectation:
        return cls(
            fixture_id=catalog.fixture_id,
            fixture_version=catalog.fixture_version,
            context_key=catalog.context_key,
            source_ids=catalog.source_ids,
            record_ids=tuple(catalog.record_ids),
            operation_ids=catalog.operation_ids,
            minimum_check_count=minimum_check_count,
            minimum_positive_count=len(catalog.positives),
            minimum_control_count=len(catalog.controls),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceCoordinateReplayCheck:
    check_id: str
    passed: bool
    observed: Any
    expected: Any
    message: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceCoordinateReplayReport:
    fixture_id: str
    state: str
    checks: tuple[ReferenceCoordinateReplayCheck, ...]
    evaluation_address: str | None
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == "accepted" and all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed": self.passed,
            "failed_check_ids": self.failed_check_ids,
        }


def replay_reference_coordinate_fixture(
    catalog: ReferenceCoordinateFixtureCatalog,
    expectation: ReferenceCoordinateReplayExpectation | None = None,
) -> ReferenceCoordinateReplayReport:
    """Replay the fixture and compare identity, floors, and operation coverage."""

    expected = expectation or ReferenceCoordinateReplayExpectation.for_catalog(catalog)
    evaluation = evaluate_reference_coordinate_fixture(catalog)
    checks: list[ReferenceCoordinateReplayCheck] = []

    def add(check_id: str, passed: bool, observed: Any, wanted: Any, message: str) -> None:
        checks.append(
            ReferenceCoordinateReplayCheck(check_id, bool(passed), observed, wanted, message)
        )

    add(
        "fixture-id",
        catalog.fixture_id == expected.fixture_id,
        catalog.fixture_id,
        expected.fixture_id,
        "fixture ID is stable",
    )
    add(
        "fixture-version",
        catalog.fixture_version == expected.fixture_version,
        catalog.fixture_version,
        expected.fixture_version,
        "fixture version is stable",
    )
    add(
        "context-key",
        catalog.context_key == expected.context_key,
        catalog.context_key,
        expected.context_key,
        "exact context is stable",
    )
    add(
        "source-set",
        catalog.source_ids == expected.source_ids,
        catalog.source_ids,
        expected.source_ids,
        "source set is stable",
    )
    add(
        "record-set",
        tuple(catalog.record_ids) == expected.record_ids,
        tuple(catalog.record_ids),
        expected.record_ids,
        "record order and identity are stable",
    )
    add(
        "operation-set",
        catalog.operation_ids == expected.operation_ids,
        catalog.operation_ids,
        expected.operation_ids,
        "operation set is stable",
    )
    add(
        "positive-floor",
        len(catalog.positives) >= expected.minimum_positive_count,
        len(catalog.positives),
        expected.minimum_positive_count,
        "positive floor is preserved",
    )
    add(
        "control-floor",
        len(catalog.controls) >= expected.minimum_control_count,
        len(catalog.controls),
        expected.minimum_control_count,
        "control floor is preserved",
    )
    add(
        "evaluation-state",
        evaluation.state == "accepted",
        evaluation.state,
        "accepted",
        "replayed evaluation is accepted",
    )
    add(
        "evaluation-check-floor",
        len(evaluation.checks) >= expected.minimum_check_count,
        len(evaluation.checks),
        expected.minimum_check_count,
        "evaluation check floor is preserved",
    )
    add(
        "evaluation-address",
        evaluation.content_address.startswith("sha256:"),
        evaluation.content_address,
        "sha256:<address>",
        "evaluation is content-addressed",
    )
    add(
        "receipt-floor",
        len(evaluation.receipts) == len(catalog.records),
        len(evaluation.receipts),
        len(catalog.records),
        "one receipt exists per record",
    )
    add(
        "positive-receipts",
        sum(receipt.role.value == "positive" for receipt in evaluation.receipts)
        == len(catalog.positives),
        sum(receipt.role.value == "positive" for receipt in evaluation.receipts),
        len(catalog.positives),
        "positive receipt count is conserved",
    )
    add(
        "control-receipts",
        sum(receipt.role.value == "control" for receipt in evaluation.receipts)
        == len(catalog.controls),
        sum(receipt.role.value == "control" for receipt in evaluation.receipts),
        len(catalog.controls),
        "control receipt count is conserved",
    )
    add(
        "all-receipt-addresses",
        all(receipt.content_address.startswith("sha256:") for receipt in evaluation.receipts),
        True,
        True,
        "all replay receipts are addressed",
    )
    add(
        "replay-context",
        all(receipt.context_key == expected.context_key for receipt in evaluation.receipts),
        True,
        True,
        "all receipts retain the replay context",
    )
    state = "accepted" if all(check.passed for check in checks) else "review"
    body = {
        "fixture_id": catalog.fixture_id,
        "state": state,
        "checks": checks,
        "evaluation_address": evaluation.content_address,
    }
    return ReferenceCoordinateReplayReport(
        catalog.fixture_id, state, tuple(checks), evaluation.content_address, content_hash(body)
    )


def default_reference_coordinate_expectation(
    catalog: ReferenceCoordinateFixtureCatalog,
) -> ReferenceCoordinateReplayExpectation:
    """Return a locked expectation for the checked-in release fixture."""

    return ReferenceCoordinateReplayExpectation(
        fixture_id=catalog.fixture_id,
        fixture_version=REFERENCE_COORDINATE_FIXTURE_VERSION,
        context_key=REFERENCE_COORDINATE_CONTEXT_KEY,
        source_ids=catalog.source_ids,
        record_ids=tuple(catalog.record_ids),
        operation_ids=catalog.operation_ids,
        minimum_check_count=130,
        minimum_positive_count=REFERENCE_COORDINATE_EXPECTED_POSITIVES,
        minimum_control_count=REFERENCE_COORDINATE_EXPECTED_CONTROLS,
    )


REFERENCE_COORDINATE_EXPECTED_POSITIVES = 4
REFERENCE_COORDINATE_EXPECTED_CONTROLS = 12


__all__ = [
    "REFERENCE_COORDINATE_EXPECTED_CONTROLS",
    "REFERENCE_COORDINATE_EXPECTED_POSITIVES",
    "ReferenceCoordinateReplayCheck",
    "ReferenceCoordinateReplayExpectation",
    "ReferenceCoordinateReplayReport",
    "default_reference_coordinate_expectation",
    "replay_reference_coordinate_fixture",
]
