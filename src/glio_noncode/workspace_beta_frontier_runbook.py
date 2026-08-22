"""Executable runbook metadata for the beta frontier CI and release path."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class BetaFrontierRunbookStep:
    step_id: str
    sequence: int
    phase: str
    command: str
    expected_exit: int
    output_kind: str
    failure_action: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.step_id, "step_id")
        require_non_empty(self.phase, "phase")
        require_non_empty(self.command, "command")
        require_non_empty(self.output_kind, "output_kind")
        require_non_empty(self.failure_action, "failure_action")
        if self.sequence < 1 or self.expected_exit < 0:
            raise ValueError("beta frontier runbook values are invalid")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierRunbook:
    runbook_id: str
    version: str
    steps: tuple[BetaFrontierRunbookStep, ...]
    required_step_count: int
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.runbook_id, "runbook_id")
        require_non_empty(self.version, "version")
        if len(self.steps) != self.required_step_count:
            raise ValueError("beta frontier runbook step count does not match")

    def by_phase(self, phase: str) -> tuple[BetaFrontierRunbookStep, ...]:
        return tuple(item for item in self.steps if item.phase == phase)

    def commands(self) -> tuple[str, ...]:
        return tuple(item.command for item in self.steps)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _step(index: int, phase: str, command: str, output_kind: str, failure_action: str) -> BetaFrontierRunbookStep:
    body = {"step_id": f"runbook-step-{index:02d}", "sequence": index, "phase": phase, "command": command, "expected_exit": 0, "output_kind": output_kind, "failure_action": failure_action}
    return BetaFrontierRunbookStep(**body, content_address=content_hash(body))


def default_beta_frontier_runbook() -> BetaFrontierRunbook:
    """Return the CI order for data, projections, release, and review."""

    commands = (
        ("prepare", "python -m glio_noncode beta-frontier-data-audit", "audit", "stop and inspect fixture boundary"),
        ("prepare", "python -m glio_noncode beta-frontier-contracts", "contracts", "stop and inspect operation registry"),
        ("prepare", "python -m glio_noncode beta-frontier-schema", "schema", "stop and inspect field manifest"),
        ("execute", "python -m glio_noncode beta-frontier-evaluate", "evaluation", "stop and inspect failed row"),
        ("execute", "python -m glio_noncode beta-frontier-replay", "replay", "stop and compare addresses"),
        ("execute", "python -m glio_noncode beta-frontier-metrics", "metrics", "retain metrics for review"),
        ("execute", "python -m glio_noncode beta-frontier-lineage", "lineage", "stop and inspect graph"),
        ("policy", "python -m glio_noncode beta-frontier-policy", "policy", "hold until policy is readable"),
        ("policy", "python -m glio_noncode beta-frontier-quality-gate", "quality", "stop on blocking failure"),
        ("policy", "python -m glio_noncode beta-frontier-invariants", "invariants", "stop on invariant failure"),
        ("runtime", "python -m glio_noncode beta-frontier-runtime", "runtime", "stop and inspect stage"),
        ("runtime", "python -m glio_noncode beta-frontier-observability", "events", "retain event stream"),
        ("runtime", "python -m glio_noncode beta-frontier-artifacts", "artifacts", "stop on missing artifact"),
        ("release", "python -m glio_noncode beta-frontier-bundle", "bundle", "hold release"),
        ("release", "python -m glio_noncode beta-frontier-release", "manifest", "hold release"),
        ("review", "python -m glio_noncode beta-frontier-review-queue", "queue", "route held rows"),
        ("review", "python -m glio_noncode export-beta-frontier-review-csv", "csv", "retain stable export"),
        ("review", "python -m glio_noncode beta-frontier-depth-audit", "depth", "retain audit detail"),
        ("review", "python -m glio_noncode beta-frontier-adapters", "adapters", "inspect input paths"),
        ("review", "python -m glio_noncode beta-frontier-scenarios", "scenarios", "retain scenario matrix"),
        ("review", "python -m glio_noncode beta-frontier-thresholds", "thresholds", "retain threshold probes"),
        ("close", "python -m unittest tests.test_workspace_beta_frontier", "tests", "stop and inspect test failure"),
        ("close", "python -m unittest tests.test_workspace_beta_frontier_cli", "cli-tests", "stop and inspect CLI failure"),
        ("close", "python -m ruff check --ignore E501 src/glio_noncode/workspace_beta_frontier_*.py", "lint", "stop and fix lint"),
        ("close", "git diff --check", "diff", "stop and fix whitespace"),
    )
    steps = tuple(_step(index, phase, command, output_kind, failure_action) for index, (phase, command, output_kind, failure_action) in enumerate(commands, start=1))
    body = {"runbook_id": "workspace-beta-frontier-runbook", "version": "2026.08.d15.c05-c08.v1", "steps": steps, "required_step_count": len(steps)}
    return BetaFrontierRunbook(**body, content_address=content_hash(body))


__all__ = ["BetaFrontierRunbook", "BetaFrontierRunbookStep", "default_beta_frontier_runbook"]
