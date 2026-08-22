"""Cross-record invariants for the sequence grammar frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_grammar_frontier_fixture_eval import SequenceGrammarEvaluation
from .sequence_grammar_frontier_public_data import (
    SequenceGrammarFixture,
    SequenceGrammarRole,
    SequenceGrammarState,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceGrammarInvariant:
    invariant_id: str
    title: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarInvariantReport:
    accepted: bool
    checks: tuple[dict[str, Any], ...]
    fixture_id: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.checks:
            raise ValidationError("invariant report requires checks")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "accepted": self.accepted,
                        "checks": self.checks,
                        "fixture_id": self.fixture_id,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "fixture_id": self.fixture_id,
            "check_count": len(self.checks),
            "checks": jsonable(self.checks),
            "content_address": self.content_address,
        }


def default_sequence_grammar_invariants() -> tuple[SequenceGrammarInvariant, ...]:
    return tuple(
        SequenceGrammarInvariant(f"I{index:02d}", title, detail)
        for index, (title, detail) in enumerate(
            (
                ("role conservation", "positive and control roles remain separate"),
                ("operation closure", "every record uses one declared operation"),
                ("state closure", "every execution uses one declared state"),
                ("control visibility", "controls remain in evaluation and review"),
                ("address closure", "records and results are content addressed"),
                ("source closure", "record source IDs resolve to receipts"),
                ("issue retention", "control issue codes remain visible"),
                ("context conservation", "fixture context binds every record"),
                ("count balance", "positive plus controls equals total"),
                ("no score conversion", "cooperative score remains descriptive"),
            ),
            start=1,
        )
    )


def run_sequence_grammar_invariants(
    fixture: SequenceGrammarFixture, evaluation: SequenceGrammarEvaluation
) -> SequenceGrammarInvariantReport:
    records = fixture.records
    executions = evaluation.executions
    checks = (
        {
            "check_id": "I01",
            "passed": len(executions) == len(records)
            and sum(row.role is SequenceGrammarRole.POSITIVE for row in executions)
            + sum(row.role is SequenceGrammarRole.CONTROL for row in executions)
            == len(executions),
            "detail": "roles balance",
        },
        {
            "check_id": "I02",
            "passed": {row.operation.value for row in executions}
            == {
                "motif_disruption",
                "motif_creation",
                "motif_spacing_grammar",
                "cooperative_tf_grammar",
            },
            "detail": "operations are closed",
        },
        {
            "check_id": "I03",
            "passed": all(row.adapter_state in set(SequenceGrammarState) for row in executions),
            "detail": "states are closed",
        },
        {
            "check_id": "I04",
            "passed": sum(row.role is SequenceGrammarRole.CONTROL for row in executions) == 12,
            "detail": "all twelve controls remain visible",
        },
        {
            "check_id": "I05",
            "passed": all(row.content_address.startswith("sha256:") for row in executions),
            "detail": "execution addresses are present",
        },
        {
            "check_id": "I06",
            "passed": all(
                set(record.source_ids) <= {source.source_id for source in fixture.sources}
                for record in records
            ),
            "detail": "source references resolve",
        },
        {
            "check_id": "I07",
            "passed": all(
                row.issue_codes for row in executions if row.role is SequenceGrammarRole.CONTROL
            ),
            "detail": "control issues are retained",
        },
        {
            "check_id": "I08",
            "passed": all(record.context_key == fixture.context_key for record in records),
            "detail": "context is conserved",
        },
        {
            "check_id": "I09",
            "passed": evaluation.positive_count + evaluation.control_count == len(executions),
            "detail": "counts balance",
        },
        {
            "check_id": "I10",
            "passed": any(
                "not a probability" in warning.lower()
                for row in executions
                for warning in row.warnings
            ),
            "detail": "score limitation remains explicit",
        },
    )
    return SequenceGrammarInvariantReport(
        all(item["passed"] for item in checks), checks, fixture.fixture_id
    )


__all__ = [
    "SequenceGrammarInvariant",
    "SequenceGrammarInvariantReport",
    "default_sequence_grammar_invariants",
    "run_sequence_grammar_invariants",
]
