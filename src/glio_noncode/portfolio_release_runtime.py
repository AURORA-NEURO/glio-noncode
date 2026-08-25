"""Staged runtime, quality, and replay surfaces for portfolio releases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .portfolio_release import build_portfolio_release
from .portfolio_release_contracts import (
    PortfolioReleaseBundle,
    PortfolioReleaseCheck,
    PortfolioReleaseState,
    address_check,
)
from .runtime import CaseRuntime
from .serialization import content_hash

PORTFOLIO_RELEASE_RUNTIME_VERSION = "portfolio-release-runtime-v1"
PORTFOLIO_RELEASE_RUNTIME_STAGE_IDS = (
    "portfolio-selected",
    "members-assembled",
    "artifact-closure-verified",
    "public-boundary-verified",
    "release-addressed",
)


@dataclass(frozen=True, slots=True)
class PortfolioReleaseStage:
    """One ordered stage in the release assembly transcript."""

    stage_id: str
    ordinal: int
    passed: bool
    predecessor_address: str | None
    output_address: str
    observed: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "ordinal": self.ordinal,
            "passed": self.passed,
            "predecessor_address": self.predecessor_address,
            "output_address": self.output_address,
            "observed": self.observed,
            "detail": self.detail,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class PortfolioReleaseQuality:
    """Independent quality gate over a built portfolio package."""

    checks: tuple[PortfolioReleaseCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_checks(self) -> int:
        """Return the number of passed quality checks."""

        return sum(item.passed for item in self.checks)

    @property
    def failed_checks(self) -> int:
        """Return the number of failed quality checks."""

        return len(self.checks) - self.passed_checks

    def to_dict(self) -> dict[str, Any]:
        return {
            "checks": [item.to_dict() for item in self.checks],
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class PortfolioReleaseRuntime:
    """Complete staged execution record for one portfolio release request."""

    runtime_id: str
    bundle: PortfolioReleaseBundle
    quality: PortfolioReleaseQuality
    stages: tuple[PortfolioReleaseStage, ...]
    state: PortfolioReleaseState
    accepted: bool
    content_address: str

    @property
    def stage_count(self) -> int:
        """Return the number of ordered runtime stages."""

        return len(self.stages)

    def to_dict(self, *, include_payloads: bool = False) -> dict[str, Any]:
        return {
            "runtime_version": PORTFOLIO_RELEASE_RUNTIME_VERSION,
            "runtime_id": self.runtime_id,
            "bundle": self.bundle.to_dict(include_payloads=include_payloads),
            "quality": self.quality.to_dict(),
            "stages": [item.to_dict() for item in self.stages],
            "stage_count": self.stage_count,
            "state": self.state.value,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def evaluate_portfolio_release_quality(
    bundle: PortfolioReleaseBundle,
) -> PortfolioReleaseQuality:
    """Apply package-level checks independent of source-run construction."""

    checks = (
        address_check(
            "quality-nonempty",
            bundle.member_count > 0,
            bundle.member_count,
            ">=1",
            "quality review requires at least one member",
            scope="quality",
        ),
        address_check(
            "quality-member-addresses",
            all(item.content_address.startswith("portfolio-release-member:") for item in bundle.members),
            sum(item.content_address.startswith("portfolio-release-member:") for item in bundle.members),
            bundle.member_count,
            "every member retains a stable content address",
            scope="quality",
        ),
        address_check(
            "quality-artifact-addresses",
            all(item.content_address.startswith("portfolio-release-artifact:") for item in bundle.artifacts),
            sum(item.content_address.startswith("portfolio-release-artifact:") for item in bundle.artifacts),
            bundle.artifact_count,
            "every artifact is addressed by exact bytes",
            scope="quality",
        ),
        address_check(
            "quality-artifact-identities",
            len({item.artifact_id for item in bundle.artifacts}) == bundle.artifact_count
            and len({item.relative_path for item in bundle.artifacts}) == bundle.artifact_count,
            bundle.artifact_count,
            "unique artifact ids and paths",
            "artifact identities and paths are unique",
            scope="quality",
        ),
        address_check(
            "quality-member-closure",
            all(set(item.artifact_ids).issubset({artifact.artifact_id for artifact in bundle.artifacts}) for item in bundle.members),
            bundle.member_count,
            bundle.member_count,
            "every member points only to package artifacts",
            scope="quality",
        ),
        address_check(
            "quality-state-reconciles",
            bundle.accepted == (bundle.state is PortfolioReleaseState.READY),
            bundle.state.value,
            "accepted iff ready",
            "package lifecycle state reconciles with accepted flag",
            scope="quality",
        ),
        address_check(
            "quality-gates-reconcile",
            bundle.accepted == all(item.passed for item in bundle.checks) and bool(bundle.members),
            bundle.accepted,
            "all package checks pass",
            "package accepted state reconciles with its checks",
            scope="quality",
        ),
    )
    body = {
        "checks": [item.to_dict() for item in checks],
        "accepted": all(item.passed for item in checks),
    }
    return PortfolioReleaseQuality(
        checks=checks,
        accepted=body["accepted"],
        content_address=content_hash(body, prefix="portfolio-release-quality"),
    )


def _stage(
    stage_id: str,
    ordinal: int,
    passed: bool,
    predecessor_address: str | None,
    output: Any,
    detail: str,
) -> PortfolioReleaseStage:
    """Create a content-addressed transcript stage."""

    output_address = content_hash(output, prefix=f"portfolio-release-stage-{stage_id}")
    body = {
        "stage_id": stage_id,
        "ordinal": ordinal,
        "passed": passed,
        "predecessor_address": predecessor_address,
        "output_address": output_address,
        "observed": output,
        "detail": detail,
    }
    return PortfolioReleaseStage(
        **body,
        content_address=content_hash(body, prefix="portfolio-release-stage"),
    )


def run_portfolio_release(
    runtime: CaseRuntime,
    **options: Any,
) -> PortfolioReleaseRuntime:
    """Assemble a package and record its ordered operational stages."""

    bundle = build_portfolio_release(runtime, **options)
    stages: list[PortfolioReleaseStage] = []
    predecessor: str | None = None
    stage_outputs = (
        ("portfolio-selected", {"member_count": bundle.member_count, "selection": bundle.selection}, "source portfolio selection completed"),
        ("members-assembled", {"member_count": bundle.member_count, "ready_member_count": bundle.ready_member_count}, "member release evidence was assembled"),
        ("artifact-closure-verified", {"artifact_count": bundle.artifact_count, "failed_checks": bundle.failed_check_ids}, "artifact identities and exact-byte addresses were closed"),
        ("public-boundary-verified", {"accepted": all(item.passed for item in bundle.checks if item.scope == "portfolio")}, "portfolio-level public-boundary checks were evaluated"),
        ("release-addressed", {"content_address": bundle.content_address, "state": bundle.state.value}, "final package manifest was content-addressed"),
    )
    for ordinal, (stage_id, output, detail) in enumerate(stage_outputs, start=1):
        passed = stage_id != "release-addressed" or bool(bundle.content_address)
        item = _stage(stage_id, ordinal, passed, predecessor, output, detail)
        stages.append(item)
        predecessor = item.output_address
    quality = evaluate_portfolio_release_quality(bundle)
    accepted = bundle.accepted and quality.accepted and all(item.passed for item in stages)
    state = PortfolioReleaseState.READY if accepted else PortfolioReleaseState.BLOCKED
    runtime_id = f"portfolio-runtime-{content_hash({'bundle': bundle.content_address, 'quality': quality.content_address}).split(':', 1)[1][:24]}"
    body = {
        "runtime_version": PORTFOLIO_RELEASE_RUNTIME_VERSION,
        "runtime_id": runtime_id,
        "bundle": bundle.to_dict(include_payloads=False),
        "quality": quality.to_dict(),
        "stages": [item.to_dict() for item in stages],
        "state": state.value,
        "accepted": accepted,
    }
    return PortfolioReleaseRuntime(
        runtime_id=runtime_id,
        bundle=bundle,
        quality=quality,
        stages=tuple(stages),
        state=state,
        accepted=accepted,
        content_address=content_hash(body, prefix="portfolio-release-runtime"),
    )


def replay_portfolio_release(
    runtime: CaseRuntime,
    previous: PortfolioReleaseRuntime,
) -> dict[str, Any]:
    """Rebuild a release with its original selection and compare addresses."""

    selection = dict(previous.bundle.selection)
    replay = build_portfolio_release(
        runtime,
        run_ids=selection.get("run_ids") or None,
        case_id=selection.get("case_id"),
        status=selection.get("status"),
        reviewer=selection.get("reviewer"),
        due_state=selection.get("due_state"),
        release_state=selection.get("release_state"),
        text=selection.get("text"),
        release_ready_only=bool(selection.get("release_ready_only", False)),
        include_blocked=bool(selection.get("include_blocked", True)),
        as_of=selection.get("as_of"),
        due_soon_hours=int(selection.get("due_soon_hours", 72)),
        max_runs=int(selection.get("max_runs", 25)),
    )
    body = {
        "previous_address": previous.bundle.content_address,
        "replay_address": replay.content_address,
        "same_address": previous.bundle.content_address == replay.content_address,
        "previous_runtime_id": previous.runtime_id,
    }
    return body | {"content_address": content_hash(body, prefix="portfolio-release-replay")}


__all__ = [
    "PORTFOLIO_RELEASE_RUNTIME_STAGE_IDS",
    "PORTFOLIO_RELEASE_RUNTIME_VERSION",
    "PortfolioReleaseQuality",
    "PortfolioReleaseRuntime",
    "PortfolioReleaseStage",
    "evaluate_portfolio_release_quality",
    "replay_portfolio_release",
    "run_portfolio_release",
]
