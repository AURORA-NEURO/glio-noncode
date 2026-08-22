"""Cross-plane diagnostic findings for the C09-C12 release surface.

The primitive operations each have their own tests, but release confidence
also depends on the joins between them. This module checks those joins:
fixture row identity, state reconciliation, control-class completeness,
trace address continuity, projection cardinality, and foreign-context
quarantine. Findings are explicit and content-addressed so a failed join is
actionable rather than hidden inside one large boolean.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .causal_alpha_frontier_controls import CausalAlphaFrontierControlCoverage
from .causal_alpha_frontier_fixture_eval import CausalAlphaFrontierFixtureEvaluation
from .causal_alpha_frontier_projections import CausalAlphaFrontierProjectionReport
from .causal_alpha_frontier_public_data import CausalAlphaFrontierFixture
from .causal_alpha_frontier_traces import CausalAlphaFrontierTraceLedger
from .serialization import content_hash


class CausalAlphaFrontierDiagnosticSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierDiagnosticFinding:
    finding_id: str
    severity: CausalAlphaFrontierDiagnosticSeverity
    check_id: str
    message: str
    observed: Any
    expected: Any
    evidence_addresses: tuple[str, ...]
    remediation: str
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"finding_id": self.finding_id, "severity": self.severity, "check_id": self.check_id, "message": self.message, "observed": self.observed, "expected": self.expected, "evidence_addresses": self.evidence_addresses, "remediation": self.remediation, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierDiagnosticReport:
    fixture_id: str
    findings: tuple[CausalAlphaFrontierDiagnosticFinding, ...]
    error_count: int
    warning_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_checks(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.findings if not item.accepted)

    @property
    def errors(self) -> tuple[CausalAlphaFrontierDiagnosticFinding, ...]:
        return tuple(item for item in self.findings if item.severity is CausalAlphaFrontierDiagnosticSeverity.ERROR and not item.accepted)

    @property
    def warnings(self) -> tuple[CausalAlphaFrontierDiagnosticFinding, ...]:
        return tuple(item for item in self.findings if item.severity is CausalAlphaFrontierDiagnosticSeverity.WARNING and not item.accepted)

    def for_check(self, check_id: str) -> CausalAlphaFrontierDiagnosticFinding:
        return next(item for item in self.findings if item.check_id == check_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "findings": [item.to_dict() for item in self.findings], "error_count": self.error_count, "warning_count": self.warning_count, "failed_checks": self.failed_checks, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _finding(check_id: str, passed: bool, observed: Any, expected: Any, addresses: tuple[str, ...], message: str, remediation: str, *, severity: CausalAlphaFrontierDiagnosticSeverity = CausalAlphaFrontierDiagnosticSeverity.ERROR) -> CausalAlphaFrontierDiagnosticFinding:
    return CausalAlphaFrontierDiagnosticFinding(f"diagnostic:{check_id}", severity, check_id, message, observed, expected, addresses, remediation, passed)


def build_causal_alpha_frontier_diagnostics(fixture: CausalAlphaFrontierFixture, evaluation: CausalAlphaFrontierFixtureEvaluation, controls: CausalAlphaFrontierControlCoverage, traces: CausalAlphaFrontierTraceLedger, projections: CausalAlphaFrontierProjectionReport) -> CausalAlphaFrontierDiagnosticReport:
    record_ids = tuple(item.record_id for item in fixture.records)
    result_ids = tuple(item.record_id for item in evaluation.evaluation.results)
    findings = (
        _finding("row-identity", record_ids == result_ids, result_ids, record_ids, (fixture.content_address, evaluation.content_address), "fixture and evaluation row identities are aligned", "replay the fixture and inspect missing result rows"),
        _finding("evaluation-accepted", evaluation.accepted, evaluation.accepted, True, (evaluation.content_address,), "all expected bounded states reconcile", "inspect the mismatched result envelopes"),
        _finding("control-classes", controls.accepted and not controls.missing_classes, controls.present_classes, controls.required_classes, (controls.content_address,), "required control classes are represented", "add a missing control case before release"),
        _finding("control-review-retention", all(item.retained_in_review or item.control_class.value == "positive" for item in controls.rows), sum(item.retained_in_review for item in controls.rows), 12, (controls.content_address,), "non-positive controls remain review-visible", "route any non-positive row into the review queue"),
        _finding("trace-cardinality", traces.accepted and len(traces.traces) == len(fixture.records), len(traces.traces), len(fixture.records), (traces.content_address,), "one accepted transformation trace exists per row", "rebuild missing row traces"),
        _finding("trace-continuity", all(len(item.steps) == 3 and item.steps[1].input_addresses == (item.steps[0].output_address,) and item.steps[2].input_addresses == (item.steps[1].output_address,) for item in traces.traces), "three steps with linked addresses", "three linked steps per row", (traces.content_address,), "trace inputs link prior outputs", "inspect the trace with a broken address edge"),
        _finding("projection-dimensions", projections.accepted and len(projections.dimensions) == 6, projections.dimensions, ("context", "control_class", "disposition", "operation", "role", "state"), (projections.content_address,), "facets cover all release dimensions", "rebuild projections from normalized results"),
        _finding("foreign-quarantine", len(projections.facet("context", "foreign").record_ids) == 4, len(projections.facet("context", "foreign").record_ids), 4, (projections.content_address,), "all foreign rows remain visible as one facet", "do not transport foreign-context rows"),
    )
    return CausalAlphaFrontierDiagnosticReport(fixture.fixture_id, findings, sum(item.severity is CausalAlphaFrontierDiagnosticSeverity.ERROR and not item.accepted for item in findings), sum(item.severity is CausalAlphaFrontierDiagnosticSeverity.WARNING and not item.accepted for item in findings), all(item.accepted for item in findings))


__all__ = ["CausalAlphaFrontierDiagnosticFinding", "CausalAlphaFrontierDiagnosticReport", "CausalAlphaFrontierDiagnosticSeverity", "build_causal_alpha_frontier_diagnostics"]
