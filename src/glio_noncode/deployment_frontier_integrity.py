"""Nested content-address integrity checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierEvaluation, DeploymentFrontierFixture
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierIntegrityCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierIntegrityReport:
    checks: tuple[DeploymentFrontierIntegrityCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_deployment_frontier_integrity(fixture: DeploymentFrontierFixture, evaluation: DeploymentFrontierEvaluation) -> DeploymentFrontierIntegrityReport:
    values = (
        ("fixture-address", fixture.content_address == deployment_address({"fixture_id": fixture.fixture_id, "fixture_version": fixture.fixture_version, "context_key": fixture.context_key, "evidence_boundary": fixture.evidence_boundary, "sources": fixture.sources, "records": fixture.records}), "fixture address recomputes"),
        ("source-addresses", all(item.content_address.startswith("sha256:") for item in fixture.sources), "source addresses exist"),
        ("record-addresses", all(item.content_address.startswith("sha256:") for item in fixture.records), "record addresses exist"),
        ("execution-addresses", all(item.content_address.startswith("sha256:") for item in evaluation.executions), "execution addresses exist"),
        ("check-addresses", all(item.content_address.startswith("sha256:") for item in evaluation.checks), "check addresses exist"),
    )
    checks = []
    for check_id, passed, detail in values:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(DeploymentFrontierIntegrityCheck(**body, content_address=deployment_address(body)))
    return DeploymentFrontierIntegrityReport(tuple(checks), all(item.passed for item in checks), deployment_address(tuple(checks)))


__all__ = ["DeploymentFrontierIntegrityCheck", "DeploymentFrontierIntegrityReport", "evaluate_deployment_frontier_integrity"]
