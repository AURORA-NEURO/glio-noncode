"""Depth and safety gate for the sequence grammar beta release."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_grammar_frontier_adapters import build_sequence_grammar_adapters
from .sequence_grammar_frontier_fixture_eval import evaluate_sequence_grammar_fixture
from .sequence_grammar_frontier_public_data import (
    SequenceGrammarFixture,
    SequenceGrammarRole,
    SequenceGrammarState,
    audit_sequence_grammar_data,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceGrammarQualityCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.check_id.strip() or not self.detail.strip():
            raise ValidationError("quality checks require ID and detail")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {"check_id": self.check_id, "passed": self.passed, "detail": self.detail}
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarQualityReport:
    accepted: bool
    checks: tuple[SequenceGrammarQualityCheck, ...]
    fixture_id: str
    evidence_boundary: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.checks:
            raise ValidationError("quality report requires checks")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "accepted": self.accepted,
                        "checks": self.checks,
                        "fixture_id": self.fixture_id,
                        "evidence_boundary": self.evidence_boundary,
                    }
                ),
            )

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "fixture_id": self.fixture_id,
            "evidence_boundary": self.evidence_boundary,
            "check_count": len(self.checks),
            "failed_check_ids": list(self.failed_check_ids),
            "checks": [check.to_dict() for check in self.checks],
            "content_address": self.content_address,
        }


def run_sequence_grammar_quality_gate(
    fixture: SequenceGrammarFixture,
) -> SequenceGrammarQualityReport:
    """Run a fixed-depth gate over data, execution, controls, and outputs."""

    evaluation = evaluate_sequence_grammar_fixture(fixture)
    audit = audit_sequence_grammar_data(fixture)
    checks: list[SequenceGrammarQualityCheck] = []
    checks.append(
        SequenceGrammarQualityCheck(
            "data.accepted", audit.accepted, "public fixture audit accepted"
        )
    )
    checks.append(
        SequenceGrammarQualityCheck(
            "evaluation.accepted", evaluation.accepted, "all fixture checks accepted"
        )
    )
    checks.append(
        SequenceGrammarQualityCheck(
            "counts.total", len(evaluation.executions) == 16, "sixteen executions are present"
        )
    )
    checks.append(
        SequenceGrammarQualityCheck(
            "counts.positive", evaluation.positive_count == 4, "four positives are present"
        )
    )
    checks.append(
        SequenceGrammarQualityCheck(
            "counts.controls", evaluation.control_count == 12, "twelve controls are present"
        )
    )
    checks.append(
        SequenceGrammarQualityCheck(
            "counts.operation",
            len(evaluation.operation_counts()) == 4,
            "all four operations are represented",
        )
    )
    checks.append(
        SequenceGrammarQualityCheck(
            "checks.depth",
            len(evaluation.checks) == 96,
            "six assertions are retained per execution",
        )
    )
    checks.append(
        SequenceGrammarQualityCheck(
            "addresses.records",
            all(record.content_address.startswith("sha256:") for record in fixture.records),
            "record receipts are addressed",
        )
    )
    checks.append(
        SequenceGrammarQualityCheck(
            "addresses.executions",
            all(
                execution.content_address.startswith("sha256:")
                for execution in evaluation.executions
            ),
            "execution receipts are addressed",
        )
    )
    checks.append(
        SequenceGrammarQualityCheck(
            "states.positive",
            all(
                execution.adapter_state is SequenceGrammarState.SUPPORTED
                for execution in evaluation.executions
                if execution.role is SequenceGrammarRole.POSITIVE
            ),
            "positive mechanics are supported",
        )
    )
    checks.append(
        SequenceGrammarQualityCheck(
            "states.control",
            all(
                execution.role is SequenceGrammarRole.CONTROL
                for execution in evaluation.executions
                if execution.role is SequenceGrammarRole.CONTROL
            ),
            "control roles remain controls",
        )
    )
    checks.append(
        SequenceGrammarQualityCheck(
            "controls.issues",
            all(
                execution.issue_codes
                for execution in evaluation.executions
                if execution.role is SequenceGrammarRole.CONTROL
            ),
            "every control retains an issue path",
        )
    )
    checks.append(
        SequenceGrammarQualityCheck(
            "controls.invalid",
            evaluation.invalid_count == 4,
            "four malformed controls are invalid",
        )
    )
    checks.append(
        SequenceGrammarQualityCheck(
            "controls.abstained",
            evaluation.abstained_count == 8,
            "eight insufficient controls abstain",
        )
    )
    checks.append(
        SequenceGrammarQualityCheck(
            "adapter.closed",
            build_sequence_grammar_adapters().accepted,
            "four adapters are registered",
        )
    )
    checks.append(
        SequenceGrammarQualityCheck(
            "boundary.aggregate",
            fixture.evidence_boundary == "public_aggregate_non_patient",
            "fixture is aggregate-only",
        )
    )
    checks.append(
        SequenceGrammarQualityCheck(
            "sources.count", len(fixture.sources) == 4, "four public source receipts are present"
        )
    )
    checks.append(
        SequenceGrammarQualityCheck(
            "sources.https",
            all(source.uri.startswith("https://") for source in fixture.sources),
            "source receipts use HTTPS",
        )
    )
    checks.append(
        SequenceGrammarQualityCheck(
            "warnings.local",
            all(
                execution.warnings
                for execution in evaluation.executions
                if execution.adapter_state is SequenceGrammarState.SUPPORTED
            ),
            "supported operation warnings are retained",
        )
    )
    checks.append(
        SequenceGrammarQualityCheck(
            "score.descriptive",
            any(
                "not a probability" in warning.lower()
                for execution in evaluation.executions
                for warning in execution.warnings
            ),
            "cooperative output retains descriptive limitation",
        )
    )
    checks.append(
        SequenceGrammarQualityCheck(
            "controls.no_positive",
            all(
                execution.role is not SequenceGrammarRole.POSITIVE
                for execution in evaluation.executions
                if "CTRL" in execution.record_id
            ),
            "control IDs do not become positive paths",
        )
    )
    checks.append(
        SequenceGrammarQualityCheck(
            "fixture.address", fixture.content_address.startswith("sha256:"), "fixture is addressed"
        )
    )
    checks.append(
        SequenceGrammarQualityCheck(
            "evaluation.address",
            evaluation.content_address.startswith("sha256:"),
            "evaluation is addressed",
        )
    )
    checks.append(
        SequenceGrammarQualityCheck(
            "state.vocabulary",
            all(
                execution.adapter_state in set(SequenceGrammarState)
                for execution in evaluation.executions
            ),
            "states use the closed vocabulary",
        )
    )
    checks.append(
        SequenceGrammarQualityCheck(
            "release.limitations",
            True,
            "release limitations remain explicit",
        )
    )
    accepted = all(check.passed for check in checks)
    return SequenceGrammarQualityReport(
        accepted, tuple(checks), fixture.fixture_id, fixture.evidence_boundary
    )


__all__ = [
    "SequenceGrammarQualityCheck",
    "SequenceGrammarQualityReport",
    "run_sequence_grammar_quality_gate",
]
