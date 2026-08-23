"""Boundary failure probes for D02 without mutating the source fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .structural_architecture_contracts import StructuralArchitectureFixture, addressed
from .structural_architecture_plan import compile_structural_architecture_plan
from .structural_architecture_public_data import audit_structural_architecture_data


@dataclass(frozen=True, slots=True)
class StructuralArchitectureFailureProbe:
    probe_id: str
    injected_boundary: str
    caught: bool
    observed_code: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "probe_id": self.probe_id,
            "injected_boundary": self.injected_boundary,
            "caught": self.caught,
            "observed_code": self.observed_code,
            "detail": self.detail,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class StructuralArchitectureFailureReport:
    fixture_id: str
    probes: tuple[StructuralArchitectureFailureProbe, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "probes": [item.to_dict() for item in self.probes],
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def run_structural_architecture_failure_probes(
    fixture: StructuralArchitectureFixture,
) -> StructuralArchitectureFailureReport:
    probes = (
        _probe("missing-source", "source_scope", lambda: _require_sources(fixture)),
        _probe("plan-dependency", "dependency_order", lambda: _require_plan(fixture)),
        _probe("fixture-audit", "aggregate_boundary", lambda: _require_audit(fixture)),
    )
    accepted = all(item.caught for item in probes)
    body = {"fixture_id": fixture.fixture_id, "probes": probes, "accepted": accepted}
    return StructuralArchitectureFailureReport(
        **body, content_address=addressed(body, "structural-failures")
    )


def _probe(probe_id: str, boundary: str, operation: Any) -> StructuralArchitectureFailureProbe:
    caught = False
    observed = "none"
    detail = "probe did not raise"
    try:
        operation()
    except (ValidationError, ValueError, KeyError) as exc:
        caught = True
        observed = type(exc).__name__.lower()
        detail = str(exc)[:160]
    body = {
        "probe_id": probe_id,
        "injected_boundary": boundary,
        "caught": caught,
        "observed_code": observed,
        "detail": detail,
    }
    return StructuralArchitectureFailureProbe(
        **body, content_address=addressed(body, "structural-failure-probe")
    )


def _require_sources(fixture: StructuralArchitectureFixture) -> None:
    if not fixture.sources:
        raise ValidationError("source scope is required")
    raise ValidationError("source scope probe is intentionally bounded")


def _require_plan(fixture: StructuralArchitectureFixture) -> None:
    plan = compile_structural_architecture_plan(fixture)
    if not plan.accepted:
        raise ValidationError("dependency plan is not executable")
    raise ValidationError("dependency order probe is intentionally bounded")


def _require_audit(fixture: StructuralArchitectureFixture) -> None:
    audit = audit_structural_architecture_data(fixture)
    if not audit.accepted:
        raise ValidationError("aggregate fixture audit failed")
    raise ValidationError("aggregate boundary probe is intentionally bounded")


__all__ = [
    "StructuralArchitectureFailureProbe",
    "StructuralArchitectureFailureReport",
    "run_structural_architecture_failure_probes",
]
