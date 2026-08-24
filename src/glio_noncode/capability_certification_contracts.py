"""Contracts for live certification of the public capability catalog.

The catalog is a product ledger.  This module gives each row an independently
addressed certification result without copying private or operational metadata
into the public projection.  A certificate is useful only when its denominator
and evidence paths are explicit, so the contracts retain both row-level and
catalog-level checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .module_fabric_contracts import FabricReferenceReceipt
from .serialization import content_hash, jsonable, require_non_empty


class CapabilityCertificationState(StrEnum):
    """Disposition of one live certification run."""

    ACCEPTED = "accepted"
    REVIEW = "review"
    BLOCKED = "blocked"


class CapabilityCertificationCategory(StrEnum):
    """Stable check categories used by reports and downstream dashboards."""

    IDENTITY = "identity"
    CATALOG = "catalog"
    IMPLEMENTATION = "implementation"
    TEST_SURFACE = "test_surface"
    DOMAIN = "domain"
    PUBLIC_BOUNDARY = "public_boundary"
    RUNTIME = "runtime"


@dataclass(frozen=True, slots=True)
class CapabilityCertificationCheck:
    """One addressed observation in a row or global certification."""

    check_id: str
    capability_id: str
    category: CapabilityCertificationCategory
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CapabilityCertificate:
    """Live evidence for one catalog capability."""

    capability_id: str
    domain_id: str
    domain: str
    layer: str
    capability_order: int
    capability: str
    kind: str
    release_wave: str
    mvp_64: bool
    registry_state: str
    implementation_receipts: tuple[FabricReferenceReceipt, ...]
    test_receipts: tuple[FabricReferenceReceipt, ...]
    checks: tuple[CapabilityCertificationCheck, ...]
    state: CapabilityCertificationState
    content_address: str

    @property
    def implementation_count(self) -> int:
        return len(self.implementation_receipts)

    @property
    def test_count(self) -> int:
        return len(self.test_receipts)

    @property
    def implementation_resolved(self) -> int:
        return sum(item.state.value == "resolved" for item in self.implementation_receipts)

    @property
    def test_resolved(self) -> int:
        return sum(item.state.value == "resolved" for item in self.test_receipts)

    @property
    def failed_checks(self) -> int:
        return sum(not item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "domain_id": self.domain_id,
            "domain": self.domain,
            "layer": self.layer,
            "capability_order": self.capability_order,
            "capability": self.capability,
            "kind": self.kind,
            "release_wave": self.release_wave,
            "mvp_64": self.mvp_64,
            "registry_state": self.registry_state,
            "implementation_receipts": [item.to_dict() for item in self.implementation_receipts],
            "test_receipts": [item.to_dict() for item in self.test_receipts],
            "checks": [item.to_dict() for item in self.checks],
            "implementation_count": self.implementation_count,
            "test_count": self.test_count,
            "implementation_resolved": self.implementation_resolved,
            "test_resolved": self.test_resolved,
            "failed_checks": self.failed_checks,
            "state": self.state.value,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class CapabilityDomainSummary:
    """Conserved readiness totals for one of the sixteen catalog domains."""

    domain_id: str
    domain: str
    capability_count: int
    mvp_count: int
    accepted_count: int
    review_count: int
    blocked_count: int
    implementation_references: int
    test_references: int
    failed_checks: int
    content_address: str

    @property
    def readiness_percent(self) -> float:
        return round(100.0 * self.accepted_count / max(1, self.capability_count), 2)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"readiness_percent": self.readiness_percent}


@dataclass(frozen=True, slots=True)
class CapabilityCertificationReport:
    """Complete live certification report for the catalog."""

    report_id: str
    catalog_version: str
    catalog_address: str
    certificates: tuple[CapabilityCertificate, ...]
    domain_summaries: tuple[CapabilityDomainSummary, ...]
    checks: tuple[CapabilityCertificationCheck, ...]
    state: CapabilityCertificationState
    content_address: str

    @property
    def capability_count(self) -> int:
        return len(self.certificates)

    @property
    def passed_checks(self) -> int:
        return sum(item.passed for item in self.checks) + sum(
            item.passed for certificate in self.certificates for item in certificate.checks
        )

    @property
    def total_checks(self) -> int:
        return len(self.checks) + sum(len(item.checks) for item in self.certificates)

    @property
    def failed_checks(self) -> int:
        return self.total_checks - self.passed_checks

    @property
    def accepted(self) -> bool:
        return self.state is CapabilityCertificationState.ACCEPTED

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "catalog_version": self.catalog_version,
            "catalog_address": self.catalog_address,
            "certificates": [item.to_dict() for item in self.certificates],
            "domain_summaries": [item.to_dict() for item in self.domain_summaries],
            "checks": [item.to_dict() for item in self.checks],
            "capability_count": self.capability_count,
            "total_checks": self.total_checks,
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "state": self.state.value,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class CapabilityCertificationQualityCheck:
    """Release-quality assertion over the complete certification report."""

    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CapabilityCertificationQualityReport:
    """Quality gate that keeps cardinality and evidence denominators visible."""

    report_address: str
    checks: tuple[CapabilityCertificationQualityCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_checks(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_checks(self) -> int:
        return len(self.checks) - self.passed_checks

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_address": self.report_address,
            "checks": [item.to_dict() for item in self.checks],
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class CapabilityCertificationStage:
    """One ordered runtime stage with predecessor and output addresses."""

    stage_id: str
    ordinal: int
    state: CapabilityCertificationState
    predecessor_address: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CapabilityCertificationRuntime:
    """Ordered runtime wrapper around the live certification report."""

    run_id: str
    report: CapabilityCertificationReport
    quality: CapabilityCertificationQualityReport
    stages: tuple[CapabilityCertificationStage, ...]
    state: CapabilityCertificationState
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state is CapabilityCertificationState.ACCEPTED

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "report": self.report.to_dict(),
            "quality": self.quality.to_dict(),
            "stages": [item.to_dict() for item in self.stages],
            "stage_count": len(self.stages),
            "state": self.state.value,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def addressed(value: Any, prefix: str) -> str:
    """Return a non-empty content address with a stable semantic prefix."""

    return content_hash(jsonable(value), prefix=prefix)


def require_address(value: str, field: str = "content_address") -> str:
    """Validate an address carried across a certification boundary."""

    return require_non_empty(value, field)


__all__ = [
    "CapabilityCertificationCategory",
    "CapabilityCertificationCheck",
    "CapabilityCertificationReport",
    "CapabilityCertificationQualityCheck",
    "CapabilityCertificationQualityReport",
    "CapabilityCertificationRuntime",
    "CapabilityCertificationStage",
    "CapabilityCertificationState",
    "CapabilityCertificate",
    "CapabilityDomainSummary",
    "addressed",
    "require_address",
]
