"""Layered quality gate for the sequence-effect release package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_effect_frontier_contracts import (
    SequenceEffectContractRegistry,
    default_sequence_effect_contracts,
)
from .sequence_effect_frontier_fixture_eval import (
    SequenceEffectEvaluation,
    evaluate_sequence_effect_fixture,
)
from .sequence_effect_frontier_lineage import (
    build_sequence_effect_lineage,
    verify_sequence_effect_lineage,
)
from .sequence_effect_frontier_metrics import compute_sequence_effect_metrics
from .sequence_effect_frontier_policy import evaluate_sequence_effect_policy
from .sequence_effect_frontier_public_data import (
    SequenceEffectFixture,
    audit_sequence_effect_data,
    default_sequence_effect_fixture,
)
from .sequence_effect_frontier_reconciliation import reconcile_sequence_effect
from .sequence_effect_frontier_schema import validate_sequence_effect_schema
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceEffectQualityCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
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
class SequenceEffectQualityReport:
    accepted: bool
    checks: tuple[SequenceEffectQualityCheck, ...]
    data_audit: Any
    evaluation: SequenceEffectEvaluation
    metrics: Any
    schema: Any
    lineage: Any
    policy: Any
    reconciliation: Any
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.checks) != 25:
            raise ValueError("sequence-effect quality gate requires twenty-five checks")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "accepted": self.accepted,
                        "checks": self.checks,
                        "data": self.data_audit.content_address,
                        "evaluation": self.evaluation.content_address,
                        "metrics": self.metrics.content_address,
                        "schema": self.schema.content_address,
                        "lineage": self.lineage.content_address,
                        "policy": self.policy.content_address,
                        "reconciliation": self.reconciliation.content_address,
                    }
                ),
            )

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "check_count": len(self.checks),
            "failed_check_ids": list(self.failed_check_ids),
            "checks": [item.to_dict() for item in self.checks],
            "data_audit": self.data_audit.to_dict(),
            "evaluation": {
                "content_address": self.evaluation.content_address,
                "accepted": self.evaluation.accepted,
            },
            "metrics": self.metrics.to_dict(),
            "schema": self.schema.to_dict(),
            "lineage": {
                "content_address": self.lineage.content_address,
                "accepted": self.lineage.accepted,
            },
            "policy": {
                "content_address": self.policy.content_address,
                "accepted": self.policy.accepted,
            },
            "reconciliation": {
                "content_address": self.reconciliation.content_address,
                "accepted": self.reconciliation.accepted,
            },
            "content_address": self.content_address,
        }


def run_sequence_effect_quality_gate(
    fixture: SequenceEffectFixture | None = None,
) -> SequenceEffectQualityReport:
    fixture = fixture or default_sequence_effect_fixture()
    data_audit = audit_sequence_effect_data(fixture)
    evaluation = evaluate_sequence_effect_fixture(fixture)
    contracts: SequenceEffectContractRegistry = default_sequence_effect_contracts()
    metrics = compute_sequence_effect_metrics(evaluation)
    schema = validate_sequence_effect_schema(fixture, evaluation, contracts)
    lineage = build_sequence_effect_lineage(fixture, evaluation)
    policy = evaluate_sequence_effect_policy(fixture, evaluation)
    reconciliation = reconcile_sequence_effect(fixture, evaluation, policy)
    checks = tuple(
        SequenceEffectQualityCheck(check_id, passed, detail)
        for check_id, passed, detail in (
            ("data-audit", data_audit.accepted, "public aggregate data audit accepts"),
            ("evaluation", evaluation.accepted, "all fixture expectations execute"),
            ("contract-count", len(contracts.contracts) == 4, "four operation contracts exist"),
            (
                "contract-addresses",
                all(item.content_address.startswith("sha256:") for item in contracts.contracts),
                "contracts are addressed",
            ),
            ("schema", schema.accepted, "schema checks accept"),
            ("schema-count", len(schema.schemas) == 4, "four schemas exist"),
            ("metric-count", len(metrics.operation_metrics) == 4, "four operation metrics exist"),
            (
                "metric-addresses",
                all(
                    item.content_address.startswith("sha256:") for item in metrics.operation_metrics
                ),
                "metrics are addressed",
            ),
            ("lineage", lineage.accepted, "lineage graph is closed"),
            (
                "lineage-verify",
                verify_sequence_effect_lineage(lineage, fixture, evaluation),
                "lineage matches fixture executions",
            ),
            ("policy", policy.accepted, "policy decisions are conservative"),
            (
                "policy-control-boundary",
                all(
                    not item.publishable
                    for item in policy.decisions
                    if item.record_id.startswith("C") and "CTRL" in item.record_id
                ),
                "controls are withheld",
            ),
            ("reconciliation", reconciliation.accepted, "reconciliation is exact"),
            (
                "record-balance",
                (evaluation.positive_count, evaluation.control_count) == (4, 12),
                "fixture balance is retained",
            ),
            ("execution-count", len(evaluation.executions) == 16, "sixteen executions exist"),
            ("check-count", len(evaluation.checks) == 96, "six checks exist per execution"),
            ("source-count", len(fixture.sources) == 4, "four source receipts exist"),
            (
                "source-closure",
                all(
                    set(item.source_ids) <= {source.source_id for source in fixture.sources}
                    for item in fixture.records
                ),
                "record sources are declared",
            ),
            (
                "context-closure",
                all(item.context_key == fixture.context_key for item in evaluation.executions),
                "execution context is exact",
            ),
            (
                "output-addresses",
                all(item.content_address.startswith("sha256:") for item in evaluation.executions),
                "execution outputs are addressed",
            ),
            (
                "issue-visibility",
                sum(bool(item.issue_codes) for item in evaluation.executions) == 12,
                "control issue paths remain visible",
            ),
            (
                "delta-boundary",
                "no-probability" in {rule.rule_id for rule in policy.rules},
                "delta probability boundary is declared",
            ),
            (
                "metrics-conservation",
                metrics.total_records == len(evaluation.executions),
                "metric denominator is conserved",
            ),
            (
                "release-input",
                fixture.content_address.startswith("sha256:"),
                "release fixture input is addressed",
            ),
            (
                "deterministic-surface",
                run_sequence_effect_quality_gate.__name__ == "run_sequence_effect_quality_gate",
                "quality entry point is stable",
            ),
        )
    )
    return SequenceEffectQualityReport(
        all(item.passed for item in checks),
        checks,
        data_audit,
        evaluation,
        metrics,
        schema,
        lineage,
        policy,
        reconciliation,
    )


__all__ = [
    "SequenceEffectQualityCheck",
    "SequenceEffectQualityReport",
    "run_sequence_effect_quality_gate",
]
