"""Independent validation orchestration across the foundation evidence plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_assertions import LinkGraphFoundationFrontierAssertionReport, evaluate_link_graph_foundation_frontier_assertions
from .link_graph_foundation_frontier_conformance import LinkGraphFoundationFrontierConformanceReport, evaluate_link_graph_foundation_frontier_conformance
from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation, evaluate_link_graph_foundation_frontier_fixture
from .link_graph_foundation_frontier_invariant_catalog import LinkGraphFoundationFrontierInvariantReport, evaluate_link_graph_foundation_frontier_invariants
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture, audit_link_graph_foundation_frontier_data, default_link_graph_foundation_frontier_fixture
from .link_graph_foundation_frontier_traceability import LinkGraphFoundationFrontierTraceabilityReport, build_link_graph_foundation_frontier_traceability
from .link_graph_foundation_frontier_field_validation import LinkGraphFoundationFrontierFieldValidationReport, validate_link_graph_foundation_frontier_fields
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierValidationCheck:
    check_id: str
    passed: bool
    source_address: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierValidationOrchestration:
    fixture_id: str
    checks: tuple[LinkGraphFoundationFrontierValidationCheck, ...]
    audit: Any
    evaluation: LinkGraphFoundationFrontierEvaluation
    fields: LinkGraphFoundationFrontierFieldValidationReport
    conformance: LinkGraphFoundationFrontierConformanceReport
    invariants: LinkGraphFoundationFrontierInvariantReport
    assertions: LinkGraphFoundationFrontierAssertionReport
    traceability: LinkGraphFoundationFrontierTraceabilityReport
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_checks(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "checks": [item.to_dict() for item in self.checks], "failed_checks": self.failed_checks, "audit": self.audit.to_dict(), "evaluation": self.evaluation.to_dict(), "fields": self.fields.to_dict(), "conformance": self.conformance.to_dict(), "invariants": self.invariants.to_dict(), "assertions": self.assertions.to_dict(), "traceability": self.traceability.to_dict(), "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def run_link_graph_foundation_frontier_validation_orchestration(fixture: LinkGraphFoundationFrontierFixture | None = None) -> LinkGraphFoundationFrontierValidationOrchestration:
    value = fixture or default_link_graph_foundation_frontier_fixture()
    audit = audit_link_graph_foundation_frontier_data(value)
    evaluation = evaluate_link_graph_foundation_frontier_fixture(value)
    fields = validate_link_graph_foundation_frontier_fields(value)
    conformance = evaluate_link_graph_foundation_frontier_conformance(value, evaluation)
    invariants = evaluate_link_graph_foundation_frontier_invariants(value, evaluation)
    assertions = evaluate_link_graph_foundation_frontier_assertions(value, evaluation)
    traceability = build_link_graph_foundation_frontier_traceability(value, evaluation)
    checks = (LinkGraphFoundationFrontierValidationCheck("audit", audit.accepted, audit.content_address, "fixture shape"), LinkGraphFoundationFrontierValidationCheck("evaluation", evaluation.accepted, evaluation.content_address, "deterministic replay"), LinkGraphFoundationFrontierValidationCheck("fields", fields.accepted, fields.content_address, "field presence"), LinkGraphFoundationFrontierValidationCheck("conformance", conformance.accepted, conformance.content_address, "boundary rules"), LinkGraphFoundationFrontierValidationCheck("invariants", invariants.accepted, invariants.content_address, "named invariants"), LinkGraphFoundationFrontierValidationCheck("assertions", assertions.accepted, assertions.content_address, "explicit assertions"), LinkGraphFoundationFrontierValidationCheck("traceability", traceability.accepted, traceability.content_address, "requirement coverage"))
    return LinkGraphFoundationFrontierValidationOrchestration(value.fixture_id, checks, audit, evaluation, fields, conformance, invariants, assertions, traceability, all(item.passed for item in checks))


def validation_orchestration_summary(report: LinkGraphFoundationFrontierValidationOrchestration) -> dict[str, Any]:
    return {"fixture_id": report.fixture_id, "check_count": len(report.checks), "passed_count": sum(item.passed for item in report.checks), "failed_checks": report.failed_checks, "accepted": report.accepted}


__all__ = ["LinkGraphFoundationFrontierValidationCheck", "LinkGraphFoundationFrontierValidationOrchestration", "run_link_graph_foundation_frontier_validation_orchestration", "validation_orchestration_summary"]
