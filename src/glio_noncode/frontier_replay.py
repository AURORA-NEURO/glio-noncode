"""Deterministic replay and cross-fixture integrity for frontier evidence.

The replay layer is intentionally local. It loads one or more checked-in
frontier fixtures, runs the same evaluator used by CI, and compares the
resulting receipts against declared expectations. It catches duplicate fixture
identity, context mixing, source-set drift, insufficient check coverage, and
non-deterministic output addresses before a batch is treated as accepted.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .frontier_data_alpha import FrontierState
from .frontier_fixture_eval import FrontierFixtureEvaluator
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ReplayExpectation:
    """Acceptance requirements for one fixture replay."""

    fixture_id: str | None = None
    expected_state: str = FrontierState.ACCEPTED.value
    minimum_checks: int = 49
    context_key: str | None = None
    source_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.fixture_id is not None:
            require_non_empty(self.fixture_id, "fixture_id")
        require_non_empty(self.expected_state, "expected_state")
        if self.minimum_checks < 1:
            raise ValidationError("minimum_checks must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReplayCaseReceipt:
    """Replay result for one fixture path."""

    path: str
    fixture_id: str
    expected_state: str
    observed_state: str
    context_key: str | None
    source_ids: tuple[str, ...]
    check_count: int
    content_address: str | None
    passed: bool
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierReplayReport:
    """Cross-fixture replay report and integrity verdict."""

    case_receipts: tuple[ReplayCaseReceipt, ...]
    duplicate_fixture_ids: tuple[str, ...]
    context_keys: tuple[str, ...]
    source_ids: tuple[str, ...]
    failed_fixture_ids: tuple[str, ...]
    integrity_issues: tuple[str, ...]
    state: FrontierState
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == FrontierState.ACCEPTED and not self.integrity_issues

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["passed"] = self.passed
        result["case_count"] = len(self.case_receipts)
        return result


class FrontierReplayRunner:
    """Replay frontier fixtures and enforce cross-case boundaries."""

    def __init__(self, evaluator: FrontierFixtureEvaluator | None = None) -> None:
        self.evaluator = evaluator or FrontierFixtureEvaluator()

    def replay_file(
        self,
        path: str | Path,
        *,
        expectation: ReplayExpectation | None = None,
    ) -> ReplayCaseReceipt:
        """Replay one fixture and retain validation errors as a failed receipt."""

        fixture_path = Path(path)
        expected = expectation or ReplayExpectation()
        try:
            report = self.evaluator.evaluate_file(fixture_path)
        except (OSError, TypeError, ValueError, ValidationError) as exc:
            return ReplayCaseReceipt(
                str(fixture_path),
                expected.fixture_id or fixture_path.stem,
                expected.expected_state,
                "error",
                None,
                (),
                0,
                None,
                False,
                str(exc),
            )
        observed_state = report.state.value
        issues: list[str] = []
        if expected.fixture_id is not None and expected.fixture_id != report.fixture_id:
            issues.append("fixture_id_mismatch")
        if expected.context_key is not None and expected.context_key != report.context_key:
            issues.append("context_key_mismatch")
        if expected.source_ids and tuple(expected.source_ids) != tuple(report.source_ids):
            issues.append("source_set_mismatch")
        if len(report.checks) < expected.minimum_checks:
            issues.append("insufficient_checks")
        if observed_state != expected.expected_state:
            issues.append("state_mismatch")
        if not report.passed:
            issues.append("fixture_failed")
        return ReplayCaseReceipt(
            str(fixture_path),
            report.fixture_id,
            expected.expected_state,
            observed_state,
            report.context_key,
            report.source_ids,
            len(report.checks),
            report.content_address,
            not issues,
            ";".join(issues) if issues else None,
        )

    def replay(
        self,
        paths: Iterable[str | Path],
        *,
        expectations: Mapping[str, ReplayExpectation] | None = None,
        required_context_key: str | None = None,
        require_same_context: bool = True,
    ) -> FrontierReplayReport:
        """Replay a batch and validate identity, context, and source integrity."""

        path_list = tuple(Path(path) for path in paths)
        if not path_list:
            raise ValidationError("at least one frontier fixture path is required")
        expected_map = expectations or {}
        receipts = tuple(
            self.replay_file(
                path,
                expectation=expected_map.get(str(path), expected_map.get(path.name)),
            )
            for path in path_list
        )
        fixture_counts = Counter(receipt.fixture_id for receipt in receipts)
        duplicates = tuple(
            sorted(identifier for identifier, count in fixture_counts.items() if count > 1)
        )
        contexts = tuple(
            sorted({receipt.context_key for receipt in receipts if receipt.context_key})
        )
        sources = tuple(sorted({source for receipt in receipts for source in receipt.source_ids}))
        failed = tuple(sorted(receipt.fixture_id for receipt in receipts if not receipt.passed))
        issues: list[str] = []
        if duplicates:
            issues.extend(f"duplicate_fixture_id:{identifier}" for identifier in duplicates)
        if require_same_context and len(contexts) > 1:
            issues.append("mixed_context_keys")
        if required_context_key is not None and required_context_key not in contexts:
            issues.append("required_context_missing")
        if failed:
            issues.extend(f"failed_fixture:{identifier}" for identifier in failed)
        address_payload = {
            "receipts": receipts,
            "duplicates": duplicates,
            "contexts": contexts,
            "sources": sources,
            "failed": failed,
            "issues": issues,
        }
        state = FrontierState.ACCEPTED if not issues else FrontierState.REVIEW
        return FrontierReplayReport(
            receipts,
            duplicates,
            contexts,
            sources,
            failed,
            tuple(issues),
            state,
            content_hash(address_payload),
        )


def replay_frontier_fixtures(
    paths: Sequence[str | Path],
    *,
    required_context_key: str | None = None,
) -> FrontierReplayReport:
    """Convenience entry point for local scripts and the CLI."""

    return FrontierReplayRunner().replay(paths, required_context_key=required_context_key)


__all__ = [
    "FrontierReplayReport",
    "FrontierReplayRunner",
    "ReplayCaseReceipt",
    "ReplayExpectation",
    "replay_frontier_fixtures",
]
