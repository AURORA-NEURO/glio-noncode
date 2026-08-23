"""Operational runbook for replay, review, and rollback of D03 releases."""

from __future__ import annotations

from dataclasses import dataclass

from .specimen_architecture_contracts import (
    SpecimenArchitectureCheck,
    SpecimenArchitectureCheckKind,
    addressed,
)


@dataclass(frozen=True, slots=True)
class SpecimenArchitectureRunbook:
    runbook_id: str
    steps: tuple[str, ...]
    rollback_steps: tuple[str, ...]
    escalation_rules: tuple[str, ...]
    checks: tuple[SpecimenArchitectureCheck, ...]
    content_address: str


def specimen_architecture_runbook() -> SpecimenArchitectureRunbook:
    """Return operator actions that keep publication reversible and reviewable."""

    steps = (
        "load the checked-in public aggregate fixture",
        "audit HTTPS sources, context, operation joins, and scope",
        "compile the sixteen-node dependency plan",
        "execute positives through typed specimen adapters",
        "hold context, malformed, and identity controls",
        "review the 48-item queue and verify the hash-linked ledger",
        "replay before publication and retain artifact addresses",
    )
    rollback = (
        "mark release blocked",
        "retain artifact addresses",
        "restore prior public manifest",
        "open a review item with the failing check IDs",
    )
    escalation = (
        "stop on source scope or direct identity findings",
        "stop on replay mismatch",
        "stop on any missing artifact or lineage break",
    )
    checks = (
        _check("step-depth", len(steps) == 7, len(steps), 7, "runbook covers the full path"),
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
        "runbook_id": "glio-noncode-specimen-architecture-runbook-v1",
        "steps": steps,
        "rollback_steps": rollback,
        "escalation_rules": escalation,
        "checks": checks,
    }
    return SpecimenArchitectureRunbook(
        body["runbook_id"], steps, rollback, escalation, checks, addressed(body, "specimen-runbook")
    )


def _check(
    check_id: str, passed: bool, observed: object, required: object, detail: str
) -> SpecimenArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": SpecimenArchitectureCheckKind.RELEASE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return SpecimenArchitectureCheck(
        check_id,
        SpecimenArchitectureCheckKind.RELEASE,
        passed,
        observed,
        required,
        detail,
        addressed(body, "specimen-runbook-check"),
    )


__all__ = ["SpecimenArchitectureRunbook", "specimen_architecture_runbook"]
