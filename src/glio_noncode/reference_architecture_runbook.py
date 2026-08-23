"""Operational runbook for D04 reference release composition."""

from __future__ import annotations

from dataclasses import dataclass

from .reference_architecture_contracts import (
    ReferenceArchitectureCheck,
    ReferenceArchitectureCheckKind,
    addressed,
)


@dataclass(frozen=True, slots=True)
class ReferenceArchitectureRunbook:
    runbook_id: str
    steps: tuple[str, ...]
    rollback_steps: tuple[str, ...]
    escalation_rules: tuple[str, ...]
    checks: tuple[ReferenceArchitectureCheck, ...]
    content_address: str


def reference_architecture_runbook() -> ReferenceArchitectureRunbook:
    steps = (
        "load public aggregate reference fixture",
        "audit source receipts and exact reference context",
        "compile the 16-node dependency plan",
        "execute positive coordinate, annotation, governance, and release adapters",
        "hold context, malformed, and identity controls",
        "verify review queue and hash-linked lineage",
        "replay and publish six addressed artifacts",
    )
    rollback = (
        "mark release blocked",
        "retain artifact addresses",
        "restore prior public manifest",
        "open review items for failing check IDs",
    )
    escalation = (
        "stop on scope or direct identity findings",
        "stop on replay or lineage mismatch",
        "stop on missing checksum, schema, license, or context evidence",
    )
    checks = (
        _check("step-depth", len(steps) == 7, len(steps), 7, "runbook covers the full runtime"),
        _check("rollback-depth", len(rollback) == 4, len(rollback), 4, "rollback is explicit"),
        _check(
            "escalation-depth",
            len(escalation) == 3,
            len(escalation),
            3,
            "release blockers are named",
        ),
    )
    body = {
        "runbook_id": "glio-noncode-reference-architecture-runbook-v1",
        "steps": steps,
        "rollback_steps": rollback,
        "escalation_rules": escalation,
        "checks": checks,
    }
    return ReferenceArchitectureRunbook(
        body["runbook_id"],
        steps,
        rollback,
        escalation,
        checks,
        addressed(body, "reference-runbook"),
    )


def _check(
    check_id: str, passed: bool, observed: object, required: object, detail: str
) -> ReferenceArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": ReferenceArchitectureCheckKind.RELEASE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ReferenceArchitectureCheck(
        check_id,
        ReferenceArchitectureCheckKind.RELEASE,
        passed,
        observed,
        required,
        detail,
        addressed(body, "reference-runbook-check"),
    )


__all__ = ["ReferenceArchitectureRunbook", "reference_architecture_runbook"]
