"""Operational runbook for reproducing and reviewing C13-C16 releases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ReferenceReleaseRunbookStep:
    """One ordered, reversible operational instruction."""

    sequence: int
    step_id: str
    command: str
    purpose: str
    expected_result: str
    failure_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseRunbook:
    """Complete release runbook with all required operational stages."""

    runbook_id: str
    version: str
    steps: tuple[ReferenceReleaseRunbookStep, ...]
    safety_notes: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"step_count": len(self.steps)}


def _step(
    sequence: int, step_id: str, command: str, purpose: str, expected: str, failure: str
) -> ReferenceReleaseRunbookStep:
    body = {
        "sequence": sequence,
        "step_id": step_id,
        "command": command,
        "purpose": purpose,
        "expected_result": expected,
        "failure_action": failure,
    }
    return ReferenceReleaseRunbookStep(
        **body, content_address=content_hash(body, prefix="runbook-step")
    )


def default_reference_release_runbook() -> ReferenceReleaseRunbook:
    """Return the 14-step local and hosted verification runbook."""

    steps = (
        _step(
            1,
            "inspect-refs",
            "git status --short && git log -1",
            "Confirm clean input state and exact commit.",
            "clean worktree and known commit",
            "stop and preserve user changes",
        ),
        _step(
            2,
            "load-fixture",
            "python -m glio_noncode reference-release-data-audit",
            "Load public aggregate source receipts.",
            "data audit accepted",
            "retain failed source checks",
        ),
        _step(
            3,
            "validate-contracts",
            "python -m glio_noncode reference-release-contracts",
            "Validate operation contracts.",
            "four contracts and addresses",
            "block release",
        ),
        _step(
            4,
            "validate-schema",
            "python -m glio_noncode reference-release-schema",
            "Validate input and output fields.",
            "four schemas and no missing required fields",
            "block release",
        ),
        _step(
            5,
            "evaluate-records",
            "python -m glio_noncode reference-release-evaluate",
            "Execute positives and controls.",
            "48 checks pass",
            "retain control output for review",
        ),
        _step(
            6,
            "replay",
            "python -m glio_noncode reference-release-replay",
            "Repeat evaluation deterministically.",
            "replay accepted",
            "compare addresses and halt",
        ),
        _step(
            7,
            "policy",
            "python -m glio_noncode reference-release-policy",
            "Evaluate release policy conditions.",
            "12 rules and 16 decisions",
            "route to review",
        ),
        _step(
            8,
            "lineage",
            "python -m glio_noncode reference-release-lineage",
            "Build redacted source-to-receipt graph.",
            "graph has no dangling edges",
            "retain graph failure",
        ),
        _step(
            9,
            "quality",
            "python -m glio_noncode reference-release-quality-gate",
            "Run the complete quality gate.",
            "25 conditions pass",
            "do not publish manifest",
        ),
        _step(
            10,
            "runtime",
            "python -m glio_noncode reference-release-runtime",
            "Run all nine stages.",
            "runtime accepted",
            "keep failed stage address",
        ),
        _step(
            11,
            "bundle",
            "python -m glio_noncode reference-release-bundle",
            "Render accepted receipt bundle.",
            "bundle verified",
            "discard render and inspect manifest",
        ),
        _step(
            12,
            "review",
            "python -m glio_noncode reference-release-review-queue",
            "Build review queue for controls.",
            "stable priority order",
            "retain every control row",
        ),
        _step(
            13,
            "local-suite",
            "python -m unittest discover -s tests -t .",
            "Run complete local regression suite.",
            "all tests pass",
            "repair before push",
        ),
        _step(
            14,
            "hosted-suite",
            "git push origin HEAD:main",
            "Run public repository Actions.",
            "hosted quality workflow passes",
            "inspect the hosted failure without rewriting history",
        ),
    )
    safety_notes = (
        "Use only checked-in aggregate fixtures and declared public source receipts.",
        "Do not fetch or store reference bytes as part of the deterministic fixture run.",
        "A review, drift, or blocked control remains visible in exports and queues.",
        "A failed required check prevents a ready release manifest.",
        "All generated projections must remain content addressed and raw-row free.",
    )
    body = {
        "runbook_id": "reference-release-frontier-runbook",
        "version": "2026.08.v1",
        "steps": steps,
        "safety_notes": safety_notes,
        "accepted": True,
    }
    return ReferenceReleaseRunbook(**body, content_address=content_hash(body, prefix="runbook"))


def verify_reference_release_runbook(runbook: ReferenceReleaseRunbook) -> tuple[str, ...]:
    """Return runbook completeness and order failures."""

    failures: list[str] = []
    if len(runbook.steps) != 14:
        failures.append("step-count")
    if tuple(step.sequence for step in runbook.steps) != tuple(range(1, 15)):
        failures.append("step-order")
    if any(
        not step.command or not step.expected_result or not step.failure_action
        for step in runbook.steps
    ):
        failures.append("step-detail")
    if len(runbook.safety_notes) < 5:
        failures.append("safety-notes")
    if any(not step.content_address.startswith("runbook-step:") for step in runbook.steps):
        failures.append("step-address")
    if not runbook.content_address.startswith("runbook:"):
        failures.append("runbook-address")
    return tuple(failures)


__all__ = [
    "ReferenceReleaseRunbook",
    "ReferenceReleaseRunbookStep",
    "default_reference_release_runbook",
    "verify_reference_release_runbook",
]
