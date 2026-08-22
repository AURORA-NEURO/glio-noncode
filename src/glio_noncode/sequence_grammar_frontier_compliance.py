"""Boundary compliance audit for public aggregate sequence evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_grammar_frontier_public_data import SequenceGrammarFixture
from .sequence_grammar_frontier_runtime import SequenceGrammarRuntimeReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceGrammarBoundaryReport:
    accepted: bool
    checks: tuple[dict[str, Any], ...]
    fixture_id: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.checks:
            raise ValidationError("boundary report requires checks")
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


def audit_sequence_grammar_boundary(
    fixture: SequenceGrammarFixture, runtime: SequenceGrammarRuntimeReport
) -> SequenceGrammarBoundaryReport:
    forbidden = {"subject", "patient", "sample_id", "donor_id", "participant_id"}
    checks = (
        {
            "check_id": "aggregate",
            "passed": fixture.evidence_boundary == "public_aggregate_non_patient",
            "detail": "aggregate boundary is exact",
        },
        {
            "check_id": "sources",
            "passed": all(
                source.public_aggregate
                and not source.patient_level
                and source.uri.startswith("https://")
                for source in fixture.sources
            ),
            "detail": "sources are public HTTPS aggregate receipts",
        },
        {
            "check_id": "payload-fields",
            "passed": all(
                not forbidden.intersection(str(key).lower() for key in record.payload)
                for record in fixture.records
            ),
            "detail": "payloads exclude subject-level fields",
        },
        {
            "check_id": "runtime",
            "passed": runtime.reconciliation.fixture_id == fixture.fixture_id,
            "detail": "runtime remains bound to fixture",
        },
        {
            "check_id": "status",
            "passed": runtime.status in {"ready", "rejected"},
            "detail": "runtime status is explicit",
        },
        {
            "check_id": "limitations",
            "passed": all(
                execution.warnings or execution.adapter_state.value in {"invalid", "abstained"}
                for execution in runtime.evaluation.executions
            ),
            "detail": "operation limitations are retained",
        },
    )
    return SequenceGrammarBoundaryReport(
        all(item["passed"] for item in checks), checks, fixture.fixture_id
    )


__all__ = ["SequenceGrammarBoundaryReport", "audit_sequence_grammar_boundary"]
