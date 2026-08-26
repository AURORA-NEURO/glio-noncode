"""Contracts for the cross-artifact module certification release report."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_CERTIFICATION_RELEASE_VERSION = "module-certification-release-v1"
MODULE_CERTIFICATION_RELEASE_BOUNDARY = "public_aggregate_module_certification_release"
MODULE_CERTIFICATION_RELEASE_MAX_CHECKS = 64
MODULE_CERTIFICATION_RELEASE_MAX_ACTIONS = 128
MODULE_CERTIFICATION_RELEASE_MAX_LIMIT = 512
MODULE_CERTIFICATION_RELEASE_DEFAULT_LIMIT = 50


class CertificationReleasePlane(StrEnum):
    """Artifact plane reconciled by a release check."""

    MATRIX = "matrix"
    LINEAGE = "lineage"
    QUALITY = "quality"
    BOUNDARY = "boundary"


def _text(value: Any, field: str, maximum: int = 1024) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")
    return value


def _non_negative(value: Any, field: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")


def _sorted_unique(values: tuple[str, ...], field: str) -> None:
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValidationError(f"{field} contains an empty value")
    if tuple(sorted(set(values))) != values:
        raise ValidationError(f"{field} must be sorted and unique")


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


@dataclass(frozen=True, slots=True)
class ModuleCertificationReleaseCheck:
    """One independent reconciliation assertion over certification artifacts."""

    check_id: str
    plane: CertificationReleasePlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.check_id, "check_id")
        _text(self.detail, "detail")
        _text(self.content_address, "content_address")
        if not isinstance(self.passed, bool):
            raise ValidationError("release check passed must be boolean")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleCertificationReleaseReport:
    """Cross-plane release decision with conserved check results."""

    matrix_address: str
    lineage_address: str
    quality_address: str
    checks: tuple[ModuleCertificationReleaseCheck, ...]
    passed_count: int
    failed_count: int
    readiness: str
    accepted: bool
    release_eligible: bool
    recommended_actions: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        for field in (
            "matrix_address",
            "lineage_address",
            "quality_address",
            "readiness",
            "content_address",
        ):
            _text(getattr(self, field), field)
        if self.readiness not in {"ready", "warning", "blocked"}:
            raise ValidationError("release readiness is unsupported")
        for field in ("passed_count", "failed_count"):
            _non_negative(getattr(self, field), field)
        if self.passed_count + self.failed_count != len(self.checks):
            raise ValidationError("release check counts do not conserve checks")
        if tuple(item.check_id for item in self.checks) != tuple(
            sorted(item.check_id for item in self.checks)
        ):
            raise ValidationError("release checks must be sorted")
        if len(self.checks) > MODULE_CERTIFICATION_RELEASE_MAX_CHECKS:
            raise ValidationError("release check limit exceeded")
        _sorted_unique(self.recommended_actions, "recommended_actions")
        if len(self.recommended_actions) > MODULE_CERTIFICATION_RELEASE_MAX_ACTIONS:
            raise ValidationError("release action limit exceeded")

    @property
    def check_count(self) -> int:
        return len(self.checks)

    def to_dict(self, *, include_checks: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "version": MODULE_CERTIFICATION_RELEASE_VERSION,
            "boundary": MODULE_CERTIFICATION_RELEASE_BOUNDARY,
            "matrix_address": self.matrix_address,
            "lineage_address": self.lineage_address,
            "quality_address": self.quality_address,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "readiness": self.readiness,
            "accepted": self.accepted,
            "release_eligible": self.release_eligible,
            "recommended_actions": list(self.recommended_actions),
            "content_address": self.content_address,
        }
        if include_checks:
            result["checks"] = [item.to_dict() for item in self.checks]
        return result


def address_module_certification_release_check(value: ModuleCertificationReleaseCheck) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return _address(body, "module-certification-release-check")


__all__ = [
    "CertificationReleasePlane",
    "MODULE_CERTIFICATION_RELEASE_BOUNDARY",
    "MODULE_CERTIFICATION_RELEASE_DEFAULT_LIMIT",
    "MODULE_CERTIFICATION_RELEASE_MAX_ACTIONS",
    "MODULE_CERTIFICATION_RELEASE_MAX_CHECKS",
    "MODULE_CERTIFICATION_RELEASE_MAX_LIMIT",
    "MODULE_CERTIFICATION_RELEASE_VERSION",
    "ModuleCertificationReleaseCheck",
    "ModuleCertificationReleaseReport",
    "address_module_certification_release_check",
]
