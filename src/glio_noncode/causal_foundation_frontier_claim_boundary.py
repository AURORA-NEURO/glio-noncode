"""Allowed-use and excluded-use checks for public aggregate release."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_foundation_frontier_bundle import CausalFoundationFrontierReleaseBundle
from .causal_foundation_frontier_release import CausalFoundationFrontierReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierClaimBoundaryCheck:
    check_id: str
    passed: bool
    phrase: str
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"check_id": self.check_id, "passed": self.passed, "phrase": self.phrase, "detail": self.detail}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierClaimBoundaryReport:
    checks: tuple[CausalFoundationFrontierClaimBoundaryCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"checks": [item.to_dict() for item in self.checks], "failed_check_ids": self.failed_check_ids, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_causal_foundation_frontier_claim_boundary(bundle: CausalFoundationFrontierReleaseBundle, release: CausalFoundationFrontierReleaseManifest) -> CausalFoundationFrontierClaimBoundaryReport:
    phrases = tuple(bundle.allowed_uses) + tuple(bundle.excluded_uses)
    checks = tuple(CausalFoundationFrontierClaimBoundaryCheck(check_id, condition, phrase, detail) for check_id, condition, phrase, detail in (
        ("allowed-uses", bool(bundle.allowed_uses), "aggregate research uses", "at least one aggregate research use is declared"),
        ("excluded-uses", bool(bundle.excluded_uses), "clinical and individual uses", "excluded uses are explicit"),
        ("patient-care-exclusion", "patient care" in phrases, "patient care", "patient care is excluded"),
        ("diagnostic-exclusion", "diagnostic determination" in phrases, "diagnostic determination", "diagnostic determination is excluded"),
        ("treatment-exclusion", "treatment selection" in phrases, "treatment selection", "treatment selection is excluded"),
        ("release-alignment", release.bundle_address == bundle.content_address, bundle.content_address, "release references the assembled bundle"),
        ("publishable-alignment", release.accepted == bundle.publishable, str(bundle.publishable), "release acceptance agrees with bundle state"),
    ))
    return CausalFoundationFrontierClaimBoundaryReport(checks, bool(checks) and all(item.passed for item in checks))


__all__ = ["CausalFoundationFrontierClaimBoundaryCheck", "CausalFoundationFrontierClaimBoundaryReport", "evaluate_causal_foundation_frontier_claim_boundary"]
