"""Operational runbook for D06 sequence aggregate releases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_architecture_contracts import (
    SequenceArchitectureCheck,
    SequenceArchitectureCheckKind,
    addressed,
)
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class SequenceArchitectureRunbook:
    steps: tuple[str, ...]
    rollback_steps: tuple[str, ...]
    escalation_steps: tuple[str, ...]
    checks: tuple[SequenceArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def sequence_architecture_runbook() -> SequenceArchitectureRunbook:
    steps = (
        "emit public fixture",
        "audit sources and context",
        "compile dependency plan",
        "execute family-backed cases",
        "route controls to review",
        "close lineage and replay",
        "publish only after quality gate",
    )
    rollback = (
        "hold release state",
        "retain fixture and failed receipt addresses",
        "discard only superseded local bundle",
        "rerun after contract correction",
    )
    escalation = (
        "source receipt mismatch -> data owner",
        "context mismatch -> boundary reviewer",
        "family result mismatch -> adapter maintainer",
    )
    checks = (
        _check(
            "runbook-steps", len(steps) == 7, len(steps), 7, "D06 runbook has ordered release steps"
        ),
        _check(
            "runbook-rollback", len(rollback) == 4, len(rollback), 4, "D06 rollback is explicit"
        ),
        _check(
            "runbook-escalation",
            len(escalation) == 3,
            len(escalation),
            3,
            "D06 escalation routes are explicit",
        ),
    )
    body = {
        "steps": steps,
        "rollback_steps": rollback,
        "escalation_steps": escalation,
        "checks": checks,
    }
    return SequenceArchitectureRunbook(
        steps=steps,
        rollback_steps=rollback,
        escalation_steps=escalation,
        checks=checks,
        accepted=all(item.passed for item in checks),
        content_address=addressed(body, "sequence-runbook"),
    )


def _check(
    check_id: str, passed: bool, observed: object, required: object, detail: str
) -> SequenceArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": SequenceArchitectureCheckKind.RELEASE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return SequenceArchitectureCheck(
        check_id=check_id,
        kind=SequenceArchitectureCheckKind.RELEASE,
        passed=passed,
        observed=observed,
        required=required,
        detail=detail,
        content_address=addressed(body, "sequence-runbook-check"),
    )


__all__ = ["SequenceArchitectureRunbook", "sequence_architecture_runbook"]
