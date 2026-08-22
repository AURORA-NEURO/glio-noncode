"""Independent validation orchestration over the beta evidence plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_assertions import LinkGraphBetaFrontierAssertionReport, evaluate_link_graph_beta_frontier_assertions
from .link_graph_beta_frontier_conformance import LinkGraphBetaFrontierConformanceReport, evaluate_link_graph_beta_frontier_conformance
from .link_graph_beta_frontier_field_validation import LinkGraphBetaFrontierFieldValidationReport, validate_link_graph_beta_frontier_fields
from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation, evaluate_link_graph_beta_frontier_fixture
from .link_graph_beta_frontier_invariant_catalog import LinkGraphBetaFrontierInvariantCatalogReport, evaluate_link_graph_beta_frontier_invariant_catalog
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, audit_link_graph_beta_frontier_data, default_link_graph_beta_frontier_fixture
from .link_graph_beta_frontier_traceability import LinkGraphBetaFrontierTraceabilityReport, build_link_graph_beta_frontier_traceability
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierValidationCheck:
    check_id: str
    passed: bool
    source_address: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierValidationOrchestration:
    fixture_id: str
    checks: tuple[LinkGraphBetaFrontierValidationCheck, ...]
    audit: Any
    evaluation: LinkGraphBetaFrontierEvaluation
    fields: LinkGraphBetaFrontierFieldValidationReport
    conformance: LinkGraphBetaFrontierConformanceReport
    invariants: LinkGraphBetaFrontierInvariantCatalogReport
    assertions: LinkGraphBetaFrontierAssertionReport
    traceability: LinkGraphBetaFrontierTraceabilityReport
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


def run_link_graph_beta_frontier_validation_orchestration(fixture: LinkGraphBetaFrontierFixture | None = None) -> LinkGraphBetaFrontierValidationOrchestration:
    value = fixture or default_link_graph_beta_frontier_fixture()
    audit = audit_link_graph_beta_frontier_data(value)
    evaluation = evaluate_link_graph_beta_frontier_fixture(value)
    fields = validate_link_graph_beta_frontier_fields(value)
    conformance = evaluate_link_graph_beta_frontier_conformance(value, evaluation)
    invariants = evaluate_link_graph_beta_frontier_invariant_catalog(value, evaluation)
    assertions = evaluate_link_graph_beta_frontier_assertions(value, evaluation)
    traceability = build_link_graph_beta_frontier_traceability(value, evaluation)
    checks = (LinkGraphBetaFrontierValidationCheck("audit", audit.accepted, audit.content_address, "fixture shape"), LinkGraphBetaFrontierValidationCheck("evaluation", evaluation.accepted, evaluation.content_address, "deterministic replay"), LinkGraphBetaFrontierValidationCheck("fields", fields.accepted, fields.content_address, "field presence"), LinkGraphBetaFrontierValidationCheck("conformance", conformance.accepted, conformance.content_address, "boundary rules"), LinkGraphBetaFrontierValidationCheck("invariants", invariants.accepted, invariants.content_address, "named invariants"), LinkGraphBetaFrontierValidationCheck("assertions", assertions.accepted, assertions.content_address, "explicit assertions"), LinkGraphBetaFrontierValidationCheck("traceability", traceability.accepted, traceability.content_address, "requirement coverage"))
    return LinkGraphBetaFrontierValidationOrchestration(value.fixture_id, checks, audit, evaluation, fields, conformance, invariants, assertions, traceability, all(item.passed for item in checks))


def validation_orchestration_summary(report: LinkGraphBetaFrontierValidationOrchestration) -> dict[str, Any]:
    return {"fixture_id": report.fixture_id, "check_count": len(report.checks), "passed_count": sum(item.passed for item in report.checks), "failed_checks": report.failed_checks, "accepted": report.accepted}


__all__ = ["LinkGraphBetaFrontierValidationCheck", "LinkGraphBetaFrontierValidationOrchestration", "run_link_graph_beta_frontier_validation_orchestration", "validation_orchestration_summary"]
