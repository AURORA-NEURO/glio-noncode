"""Boundary and secret-surface compliance checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_gamma_frontier_fixture_eval import GammaFrontierEvaluation
from .workspace_gamma_frontier_public_data import GammaFrontierFixture


@dataclass(frozen=True, slots=True)
class GammaFrontierBoundaryCheck:
    """One boundary check over fixture or serialized output."""

    check_id: str
    passed: bool
    severity: str
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierBoundaryReport:
    """Compliance report retaining blocking and advisory counts."""

    fixture_id: str
    checks: tuple[GammaFrontierBoundaryCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "blocking_failures": [
                item.check_id
                for item in self.checks
                if not item.passed and item.severity == "blocking"
            ]
        }


def _check(
    index: int, passed: bool, severity: str, observed: Any, required: Any, detail: str
) -> GammaFrontierBoundaryCheck:
    body = {
        "check_id": f"gamma-boundary-{index:03d}",
        "passed": passed,
        "severity": severity,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return GammaFrontierBoundaryCheck(**body, content_address=content_hash(body, prefix="boundary"))


def _keys(value: Any) -> tuple[str, ...]:
    return tuple(value.keys()) if isinstance(value, dict) else ()


def evaluate_gamma_frontier_boundary(
    fixture: GammaFrontierFixture, evaluation: GammaFrontierEvaluation
) -> GammaFrontierBoundaryReport:
    """Check aggregate boundary, HTTPS receipts, and absence of secret fields."""

    output_keys = tuple(
        key for execution in evaluation.executions for key in _keys(execution.output)
    )
    checks = (
        _check(
            1,
            fixture.evidence_boundary == "public_aggregate_non_patient",
            "blocking",
            fixture.evidence_boundary,
            "public_aggregate_non_patient",
            "fixture boundary is explicit",
        ),
        _check(
            2,
            all(source.uri.startswith("https://") for source in fixture.sources),
            "blocking",
            tuple(source.uri for source in fixture.sources),
            "HTTPS",
            "source receipts are HTTPS",
        ),
        _check(
            3,
            all(key not in {"signing_secret", "verify_secret"} for key in output_keys),
            "blocking",
            tuple(key for key in output_keys if key in {"signing_secret", "verify_secret"}),
            "no secrets",
            "serialized outputs do not expose signing material",
        ),
        _check(
            4,
            all(
                execution.output.get("research_use_only", True)
                for execution in evaluation.executions
            ),
            "blocking",
            True,
            True,
            "snapshot research boundary remains true",
        ),
        _check(
            5,
            all("raw" not in key.lower() for key in output_keys),
            "advisory",
            tuple(key for key in output_keys if "raw" in key.lower()),
            "no raw fields",
            "review output uses sanitized fields",
        ),
    )
    accepted = not any(not item.passed and item.severity == "blocking" for item in checks)
    body = {"fixture_id": fixture.fixture_id, "checks": checks, "accepted": accepted}
    return GammaFrontierBoundaryReport(
        **body, content_address=content_hash(body, prefix="boundary-report")
    )


__all__ = [
    "GammaFrontierBoundaryCheck",
    "GammaFrontierBoundaryReport",
    "evaluate_gamma_frontier_boundary",
]
