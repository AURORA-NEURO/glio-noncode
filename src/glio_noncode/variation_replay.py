"""Batch replay and identity integrity for Domain 01 variation fixtures."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .variation_fixture_eval import VariationFixtureEvaluationReport, VariationFixtureEvaluator
from .variation_public_data import VariationDataState


@dataclass(frozen=True, slots=True)
class VariationReplayExpectation:
    """Expected identity and evidence floor for one replayed fixture."""

    fixture_id: str | None = None
    context_key: str | None = None
    source_ids: tuple[str, ...] = ()
    expected_state: str = VariationDataState.ACCEPTED.value
    minimum_checks: int = 29

    def __post_init__(self) -> None:
        if self.fixture_id is not None:
            require_non_empty(self.fixture_id, "fixture_id")
        if self.context_key is not None:
            require_non_empty(self.context_key, "context_key")
        if self.expected_state not in {state.value for state in VariationDataState}:
            raise ValidationError("variation replay expected_state is invalid")
        if self.minimum_checks < 1:
            raise ValidationError("variation replay minimum_checks must be positive")


@dataclass(frozen=True, slots=True)
class VariationReplayCaseReceipt:
    """One fixture replay result retained even when evaluation fails."""

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
class VariationReplayReport:
    """Cross-fixture replay and integrity verdict."""

    case_receipts: tuple[VariationReplayCaseReceipt, ...]
    duplicate_fixture_ids: tuple[str, ...]
    context_keys: tuple[str, ...]
    source_ids: tuple[str, ...]
    failed_fixture_ids: tuple[str, ...]
    integrity_issues: tuple[str, ...]
    state: VariationDataState
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == VariationDataState.ACCEPTED and not self.integrity_issues

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["passed"] = self.passed
        result["case_count"] = len(self.case_receipts)
        return result


class VariationReplayRunner:
    """Replay one or more variation fixtures with exact identity controls."""

    def __init__(self, evaluator: VariationFixtureEvaluator | None = None) -> None:
        self.evaluator = evaluator or VariationFixtureEvaluator()

    def replay_file(
        self,
        path: str | Path,
        *,
        expectation: VariationReplayExpectation | None = None,
    ) -> VariationReplayCaseReceipt:
        fixture_path = Path(path)
        expected = expectation or VariationReplayExpectation()
        try:
            report = self.evaluator.evaluate_file(fixture_path)
        except (OSError, TypeError, ValueError, ValidationError) as exc:
            return VariationReplayCaseReceipt(
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
        return self._receipt(fixture_path, report, expected)

    @staticmethod
    def _receipt(
        fixture_path: Path,
        report: VariationFixtureEvaluationReport,
        expected: VariationReplayExpectation,
    ) -> VariationReplayCaseReceipt:
        issues: list[str] = []
        observed_state = report.state.value
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
        return VariationReplayCaseReceipt(
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
        expectations: Mapping[str, VariationReplayExpectation] | None = None,
        required_context_key: str | None = None,
        require_same_context: bool = True,
    ) -> VariationReplayReport:
        path_list = tuple(Path(path) for path in paths)
        if not path_list:
            raise ValidationError("at least one variation fixture path is required")
        expected_map = expectations or {}
        receipts = tuple(
            self.replay_file(
                path,
                expectation=expected_map.get(str(path), expected_map.get(path.name)),
            )
            for path in path_list
        )
        counts = Counter(receipt.fixture_id for receipt in receipts)
        duplicates = tuple(sorted(identifier for identifier, count in counts.items() if count > 1))
        contexts = tuple(
            sorted({receipt.context_key for receipt in receipts if receipt.context_key})
        )
        sources = tuple(sorted({source for receipt in receipts for source in receipt.source_ids}))
        failed = tuple(sorted(receipt.fixture_id for receipt in receipts if not receipt.passed))
        issues: list[str] = []
        issues.extend(f"duplicate_fixture_id:{item}" for item in duplicates)
        if require_same_context and len(contexts) > 1:
            issues.append("mixed_context_keys")
        if required_context_key is not None and required_context_key not in contexts:
            issues.append("required_context_missing")
        issues.extend(f"failed_fixture:{item}" for item in failed)
        state = VariationDataState.ACCEPTED if not issues else VariationDataState.REVIEW
        body = {
            "case_receipts": receipts,
            "duplicate_fixture_ids": duplicates,
            "context_keys": contexts,
            "source_ids": sources,
            "failed_fixture_ids": failed,
            "integrity_issues": issues,
            "state": state,
        }
        return VariationReplayReport(
            receipts,
            duplicates,
            contexts,
            sources,
            failed,
            tuple(issues),
            state,
            content_hash(body),
        )


def replay_variation_fixtures(
    paths: Iterable[str | Path],
    *,
    required_context_key: str | None = None,
) -> VariationReplayReport:
    """Convenience function for cross-fixture variation replay."""

    return VariationReplayRunner().replay(paths, required_context_key=required_context_key)


__all__ = [
    "VariationReplayCaseReceipt",
    "VariationReplayExpectation",
    "VariationReplayReport",
    "VariationReplayRunner",
    "replay_variation_fixtures",
]
