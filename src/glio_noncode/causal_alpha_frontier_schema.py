"""Schema closure checks for C09-C12 fixture records and operation outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_alpha_frontier_adapters import CausalAlphaFrontierEvaluation
from .causal_alpha_frontier_contracts import CausalAlphaFrontierContractReport
from .causal_alpha_frontier_public_data import CausalAlphaFrontierFixture, CausalAlphaFrontierOperation
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierSchemaReport:
    """Field-level checks over every fixture row and result."""

    fixture_id: str
    checks: tuple[dict[str, Any], ...]
    record_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_checks(self) -> tuple[str, ...]:
        return tuple(item["check_id"] for item in self.checks if not item["passed"])

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "checks": self.checks, "failed_checks": self.failed_checks, "record_count": self.record_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def validate_causal_alpha_frontier_schema(fixture: CausalAlphaFrontierFixture, evaluation: CausalAlphaFrontierEvaluation, contracts: CausalAlphaFrontierContractReport | None = None) -> CausalAlphaFrontierSchemaReport:
    checks: list[dict[str, Any]] = []
    checks.append({"check_id": "record-count", "passed": len(fixture.records) == len(evaluation.results) == 16, "detail": "every fixture record has one result"})
    checks.append({"check_id": "record-identities", "passed": tuple(item.record_id for item in fixture.records) == tuple(item.record_id for item in evaluation.results), "detail": "record order and IDs are stable"})
    checks.append({"check_id": "operation-closure", "passed": {item.operation for item in fixture.records} == set(CausalAlphaFrontierOperation), "detail": "all four operations are represented"})
    checks.append({"check_id": "addresses", "passed": all(item.content_address.startswith("sha256:") for item in evaluation.results), "detail": "normalized result addresses exist"})
    checks.append({"check_id": "output-envelopes", "passed": all(bool(item.output) for item in evaluation.results), "detail": "every adapter returned a structured envelope"})
    checks.append({"check_id": "state-closure", "passed": all(item.observed_state.value for item in evaluation.results), "detail": "all observed states are typed"})
    checks.append({"check_id": "contract-count", "passed": contracts is None or len(contracts.contracts) == 4, "detail": "one contract per operation"})
    checks = [{**item, "content_address": content_hash(item)} for item in checks]
    return CausalAlphaFrontierSchemaReport(fixture.fixture_id, tuple(checks), len(fixture.records), all(item["passed"] for item in checks))


__all__ = ["CausalAlphaFrontierSchemaReport", "validate_causal_alpha_frontier_schema"]
