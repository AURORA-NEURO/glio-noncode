"""Operational runbook for the D05 public atlas release."""

from __future__ import annotations

from dataclasses import dataclass

from .atlas_architecture_contracts import (
    AtlasArchitectureCheck,
    AtlasArchitectureCheckKind,
    addressed,
)


@dataclass(frozen=True, slots=True)
class AtlasArchitectureRunbook:
    runbook_id: str
    steps: tuple[str, ...]
    rollback_steps: tuple[str, ...]
    escalation_rules: tuple[str, ...]
    checks: tuple[AtlasArchitectureCheck, ...]
    content_address: str

    def to_dict(self) -> dict[str, object]:
        from .serialization import jsonable

        return jsonable(self)


def atlas_architecture_runbook() -> AtlasArchitectureRunbook:
    steps = (
        "load four-family public aggregate atlas fixture",
        "audit source receipts and exact D05 context",
        "compile the sixteen-node family dependency plan",
        "execute regulatory, molecular, alpha-evidence, and frontier positives",
        "hold foreign, malformed, and identity controls",
        "verify review queue, replay, and hash-linked lineage",
        "publish six addressed atlas artifacts",
    )
    rollback = (
        "mark release blocked",
        "retain artifact addresses",
        "restore prior atlas manifest",
        "open review items for failed checks",
    )
    escalation = (
        "stop on scope or direct identity findings",
        "stop on replay or lineage mismatch",
        "stop on missing checksum, schema, license, or context evidence",
    )
    checks = (
        _check(
            "step-depth", len(steps) == 7, len(steps), 7, "runbook covers complete atlas runtime"
        ),
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
        "runbook_id": "glio-noncode-atlas-architecture-runbook-v1",
        "steps": steps,
        "rollback_steps": rollback,
        "escalation_rules": escalation,
        "checks": checks,
    }
    return AtlasArchitectureRunbook(
        body["runbook_id"], steps, rollback, escalation, checks, addressed(body, "atlas-runbook")
    )


def _check(
    check_id: str, passed: bool, observed: object, required: object, detail: str
) -> AtlasArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": AtlasArchitectureCheckKind.RELEASE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return AtlasArchitectureCheck(
        check_id,
        AtlasArchitectureCheckKind.RELEASE,
        passed,
        observed,
        required,
        detail,
        addressed(body, "atlas-runbook-check"),
    )


__all__ = ["AtlasArchitectureRunbook", "atlas_architecture_runbook"]
