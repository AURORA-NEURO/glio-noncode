"""Executable release runbook for the C05-C08 frontier surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_beta_frontier_bundle import CausalBetaFrontierReleaseBundle
from .causal_beta_frontier_claim_boundary import CausalBetaFrontierClaimBoundaryReport
from .causal_beta_frontier_release import CausalBetaFrontierReleaseManifest
from .causal_beta_frontier_assurance import CausalBetaFrontierAssurance
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierRunbookStep:
    step_id: str
    sequence: int
    command: str
    purpose: str
    required_output: str
    blocking: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"step_id": self.step_id, "sequence": self.sequence, "command": self.command, "purpose": self.purpose, "required_output": self.required_output, "blocking": self.blocking}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierRunbook:
    runbook_id: str
    fixture_id: str
    release_id: str
    stage_count: int
    steps: tuple[CausalBetaFrontierRunbookStep, ...]
    release_state: str
    boundary: str
    required_addresses: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def commands(self) -> tuple[str, ...]:
        return tuple(item.command for item in self.steps)

    @property
    def blocking_steps(self) -> tuple[CausalBetaFrontierRunbookStep, ...]:
        return tuple(item for item in self.steps if item.blocking)

    def step(self, step_id: str) -> CausalBetaFrontierRunbookStep:
        return next(item for item in self.steps if item.step_id == step_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"runbook_id": self.runbook_id, "fixture_id": self.fixture_id, "release_id": self.release_id, "stage_count": self.stage_count, "steps": [item.to_dict() for item in self.steps], "release_state": self.release_state, "boundary": self.boundary, "required_addresses": self.required_addresses, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value

    def to_markdown(self) -> str:
        lines = [f"# {self.runbook_id}", "", f"Fixture: `{self.fixture_id}`", f"Release: `{self.release_id}`", f"Stages: `{self.stage_count}`", "", "| Step | Command | Required output | Blocking |", "| --- | --- | --- | --- |"]
        for item in self.steps:
            lines.append(f"| {item.sequence}. {item.step_id} | `{item.command}` | {item.required_output} | {item.blocking} |")
        return "\n".join(lines) + "\n"


def _steps() -> tuple[CausalBetaFrontierRunbookStep, ...]:
    values = (
        ("audit", "causal-beta-frontier-data-audit", "validate public sources and controls", "data audit accepted", True),
        ("evaluate", "causal-beta-frontier-evaluate", "replay all four operations", "16 rows match", True),
        ("quality", "causal-beta-frontier-quality-gate", "apply blocking and review checks", "quality gate accepted", True),
        ("runtime", "causal-beta-frontier-runtime", "execute ordered release stages", "runtime accepted", True),
        ("integrity", "causal-beta-frontier-integrity", "verify graph and address closure", "integrity accepted", True),
        ("operational", "causal-beta-frontier-operational", "project bounded row actions", "4 allowed cells", True),
        ("boundary", "causal-beta-frontier-boundary", "enforce use boundaries", "boundary accepted", True),
        ("release", "causal-beta-frontier-release", "build release manifest", "release state ready", True),
        ("review-csv", "export-causal-beta-frontier-review-csv", "export review rows", "17 CSV lines", False),
        ("review-markdown", "export-causal-beta-frontier-review-markdown", "export review table", "Markdown table", False),
        ("exports", "export-causal-beta-frontier-json", "export release payloads", "6 envelopes", False),
        ("assurance", "causal-beta-frontier-assurance", "emit final assurance", "assurance accepted", True),
    )
    return tuple(CausalBetaFrontierRunbookStep(step_id, sequence, command, purpose, required_output, blocking) for sequence, (step_id, command, purpose, required_output, blocking) in enumerate(values, 1))


def build_causal_beta_frontier_runbook(runbook_id: str, fixture_id: str, stage_count: int, release: CausalBetaFrontierReleaseManifest, bundle: CausalBetaFrontierReleaseBundle, boundary: CausalBetaFrontierClaimBoundaryReport, assurance: CausalBetaFrontierAssurance) -> CausalBetaFrontierRunbook:
    steps = _steps()
    addresses = (release.content_address, bundle.content_address, boundary.content_address, assurance.content_address)
    accepted = bool(stage_count >= 1 and steps and release.accepted and bundle.publishable and boundary.accepted and assurance.accepted and all(addresses) and len({item.sequence for item in steps}) == len(steps))
    return CausalBetaFrontierRunbook(runbook_id + ":runbook", fixture_id, release.release_id, stage_count, steps, release.state.value, boundary.boundary, addresses, accepted)


def runbook_is_executable(runbook: CausalBetaFrontierRunbook) -> bool:
    return bool(runbook.accepted and runbook.steps and tuple(item.sequence for item in runbook.steps) == tuple(range(1, len(runbook.steps) + 1)) and all(item.command.startswith(("causal-beta-frontier-", "export-causal-beta-frontier-")) for item in runbook.steps))


__all__ = ["CausalBetaFrontierRunbook", "CausalBetaFrontierRunbookStep", "build_causal_beta_frontier_runbook", "runbook_is_executable"]
