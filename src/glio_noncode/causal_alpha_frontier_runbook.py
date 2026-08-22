"""Executable release runbook for the C09-C12 frontier surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_alpha_frontier_assurance import CausalAlphaFrontierAssurance
from .causal_alpha_frontier_bundle import CausalAlphaFrontierReleaseBundle
from .causal_alpha_frontier_claim_boundary import CausalAlphaFrontierClaimBoundaryReport
from .causal_alpha_frontier_release import CausalAlphaFrontierReleaseManifest
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierRunbookStep:
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
class CausalAlphaFrontierRunbook:
    runbook_id: str
    fixture_id: str
    release_id: str
    stage_count: int
    steps: tuple[CausalAlphaFrontierRunbookStep, ...]
    release_state: str
    boundary: str
    required_addresses: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def blocking_steps(self) -> tuple[CausalAlphaFrontierRunbookStep, ...]:
        return tuple(item for item in self.steps if item.blocking)

    @property
    def commands(self) -> tuple[str, ...]:
        return tuple(item.command for item in self.steps)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"runbook_id": self.runbook_id, "fixture_id": self.fixture_id, "release_id": self.release_id, "stage_count": self.stage_count, "steps": [item.to_dict() for item in self.steps], "release_state": self.release_state, "boundary": self.boundary, "required_addresses": self.required_addresses, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value

    def to_markdown(self) -> str:
        lines = [f"# {self.runbook_id}", "", f"Fixture: `{self.fixture_id}`", f"Release: `{self.release_id}`", f"Stages: `{self.stage_count}`", "", "| Step | Command | Required output | Blocking |", "| --- | --- | --- | --- |"]
        lines.extend(f"| {item.sequence}. {item.step_id} | `{item.command}` | {item.required_output} | {item.blocking} |" for item in self.steps)
        return "\n".join(lines) + "\n"


def _steps() -> tuple[CausalAlphaFrontierRunbookStep, ...]:
    values = (
        ("audit", "causal-alpha-frontier-data-audit", "validate sources and controls", "data audit accepted", True),
        ("evaluate", "causal-alpha-frontier-evaluate", "replay four alpha operations", "16 rows match", True),
        ("quality", "causal-alpha-frontier-quality-gate", "apply release checks", "quality gate accepted", True),
        ("runtime", "causal-alpha-frontier-runtime", "execute ordered stages", "runtime accepted", True),
        ("integrity", "causal-alpha-frontier-integrity", "verify address closure", "integrity accepted", True),
        ("operational", "causal-alpha-frontier-operational", "project bounded actions", "4 quarantines", True),
        ("boundary", "causal-alpha-frontier-boundary", "enforce claim limits", "boundary accepted", True),
        ("release", "causal-alpha-frontier-release", "build release manifest", "release ready", True),
        ("review-csv", "export-causal-alpha-frontier-review-csv", "export review rows", "16 CSV rows", False),
        ("review-markdown", "export-causal-alpha-frontier-review-markdown", "export review table", "Markdown table", False),
        ("exports", "export-causal-alpha-frontier-json", "export release envelopes", "9 envelopes", False),
        ("assurance", "causal-alpha-frontier-assurance", "emit final assurance", "assurance accepted", True),
    )
    return tuple(CausalAlphaFrontierRunbookStep(step_id, sequence, command, purpose, required_output, blocking) for sequence, (step_id, command, purpose, required_output, blocking) in enumerate(values, 1))


def build_causal_alpha_frontier_runbook(runbook_id: str, fixture_id: str, stage_count: int, release: CausalAlphaFrontierReleaseManifest, bundle: CausalAlphaFrontierReleaseBundle, boundary: CausalAlphaFrontierClaimBoundaryReport, assurance: CausalAlphaFrontierAssurance) -> CausalAlphaFrontierRunbook:
    steps = _steps()
    addresses = (release.content_address, bundle.content_address, boundary.content_address, assurance.content_address)
    accepted = bool(stage_count >= 1 and release.accepted and bundle.publishable and boundary.accepted and assurance.accepted and all(addresses) and tuple(item.sequence for item in steps) == tuple(range(1, len(steps) + 1)))
    return CausalAlphaFrontierRunbook(runbook_id + ":runbook", fixture_id, release.release_id, stage_count, steps, release.state.value, boundary.boundary, addresses, accepted)


def runbook_is_executable(runbook: CausalAlphaFrontierRunbook) -> bool:
    return bool(runbook.accepted and runbook.steps and all(item.command.startswith(("causal-alpha-frontier-", "export-causal-alpha-frontier-")) for item in runbook.steps))


__all__ = ["CausalAlphaFrontierRunbook", "CausalAlphaFrontierRunbookStep", "build_causal_alpha_frontier_runbook", "runbook_is_executable"]
