"""Deterministic replay receipts for the C13-C16 operation fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reference_release_frontier_fixture_eval import (
    ReferenceReleaseEvaluation,
    evaluate_reference_release_fixture,
)
from .reference_release_frontier_public_data import (
    ReferenceReleaseFixture,
    default_reference_release_fixture,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ReferenceReleaseReplayCheck:
    """One replay equality or floor check."""

    check_id: str
    passed: bool
    observed: Any
    expected: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseReplayReceipt:
    """Replay result containing no raw operation payloads."""

    replay_id: str
    fixture_id: str
    original_address: str
    replayed_address: str
    checks: tuple[ReferenceReleaseReplayCheck, ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


def _check(
    index: int, passed: bool, observed: Any, expected: Any, detail: str
) -> ReferenceReleaseReplayCheck:
    body = {
        "check_id": f"release-replay-{index:03d}",
        "passed": passed,
        "observed": observed,
        "expected": expected,
        "detail": detail,
    }
    return ReferenceReleaseReplayCheck(
        **body, content_address=content_hash(body, prefix="replay-check")
    )


def build_reference_release_expectation(evaluation: ReferenceReleaseEvaluation) -> dict[str, Any]:
    """Extract the stable receipt tuple used for replay comparison."""

    return {
        "fixture_id": evaluation.fixture_id,
        "executions": tuple(
            (item.record_id, item.state, item.issue_codes, item.content_address)
            for item in evaluation.executions
        ),
        "checks": tuple(
            (item.check_id, item.passed, item.content_address) for item in evaluation.checks
        ),
    }


def replay_reference_release_evaluation(
    evaluation: ReferenceReleaseEvaluation,
    *,
    fixture: ReferenceReleaseFixture | None = None,
    replay_id: str = "reference-release-replay",
) -> ReferenceReleaseReplayReceipt:
    """Run the fixture again and compare every stable receipt field."""

    fixture = fixture or default_reference_release_fixture()
    require_non_empty(replay_id, "replay_id")
    replayed = evaluate_reference_release_fixture(fixture)
    original = build_reference_release_expectation(evaluation)
    repeated = build_reference_release_expectation(replayed)
    checks = (
        _check(
            1,
            original["fixture_id"] == repeated["fixture_id"],
            original["fixture_id"],
            repeated["fixture_id"],
            "fixture identity is stable",
        ),
        _check(
            2,
            original["executions"] == repeated["executions"],
            len(original["executions"]),
            len(repeated["executions"]),
            "execution receipt tuples are stable",
        ),
        _check(
            3,
            original["checks"] == repeated["checks"],
            len(original["checks"]),
            len(repeated["checks"]),
            "evaluation checks are stable",
        ),
        _check(
            4,
            evaluation.content_address == replayed.content_address,
            evaluation.content_address,
            replayed.content_address,
            "evaluation content address is stable",
        ),
        _check(
            5,
            evaluation.accepted and replayed.accepted,
            (evaluation.accepted, replayed.accepted),
            (True, True),
            "both evaluations are accepted",
        ),
        _check(
            6,
            len(evaluation.executions) == 16,
            len(evaluation.executions),
            16,
            "replay covers all records",
        ),
        _check(
            7,
            len(evaluation.checks) == 48,
            len(evaluation.checks),
            48,
            "replay covers all assertions",
        ),
        _check(
            8,
            all(item.content_address.startswith("sha256:") for item in replayed.executions),
            True,
            True,
            "replayed receipts are addressed",
        ),
        _check(
            9,
            all(item.content_address.startswith("sha256:") for item in replayed.checks),
            True,
            True,
            "replayed checks are addressed",
        ),
        _check(
            10,
            not {"payload", "records"} & set(replayed.to_dict()),
            sorted({"payload", "records"} & set(replayed.to_dict())),
            [],
            "replay report does not expose raw payloads",
        ),
        _check(
            11,
            tuple(item.record_id for item in evaluation.executions)
            == tuple(item.record_id for item in replayed.executions),
            True,
            True,
            "record order is stable",
        ),
        _check(
            12,
            tuple(item.operation for item in evaluation.executions)
            == tuple(item.operation for item in replayed.executions),
            True,
            True,
            "operation order is stable",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {
        "replay_id": replay_id,
        "fixture_id": fixture.fixture_id,
        "original_address": evaluation.content_address,
        "replayed_address": replayed.content_address,
        "checks": checks,
        "accepted": accepted,
    }
    return ReferenceReleaseReplayReceipt(
        **body, content_address=content_hash(body, prefix="release-replay")
    )


__all__ = [
    "ReferenceReleaseReplayCheck",
    "ReferenceReleaseReplayReceipt",
    "build_reference_release_expectation",
    "replay_reference_release_evaluation",
]
