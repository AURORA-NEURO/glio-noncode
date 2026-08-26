"""Typed contracts for configurable certification quality gates."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_CERTIFICATION_QUALITY_POLICY_VERSION = "module-certification-quality-policy-v1"
MODULE_CERTIFICATION_QUALITY_POLICY_BOUNDARY = (
    "public_aggregate_module_certification_quality_policy"
)
MODULE_CERTIFICATION_QUALITY_POLICY_MAX_CHECKS = 64
MODULE_CERTIFICATION_QUALITY_POLICY_MAX_LIMIT = 512


def _text(value: Any, field: str, maximum: int = 1024) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")
    return value


def _percent(value: Any, field: str) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0.0 <= value <= 100.0:
        raise ValidationError(f"{field} must be between zero and one hundred")


def _score(value: Any, field: str) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0.0 <= value <= 1.0:
        raise ValidationError(f"{field} must be between zero and one")


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


@dataclass(frozen=True, slots=True)
class ModuleCertificationQualityPolicy:
    """Thresholds applied to a previously computed quality report."""

    minimum_evidence_coverage_percent: float
    minimum_check_pass_percent: float
    minimum_family_score: float
    require_no_blockers: bool
    require_all_modules_certified: bool
    require_ready: bool
    content_address: str

    def __post_init__(self) -> None:
        _percent(self.minimum_evidence_coverage_percent, "minimum_evidence_coverage_percent")
        _percent(self.minimum_check_pass_percent, "minimum_check_pass_percent")
        _score(self.minimum_family_score, "minimum_family_score")
        for field in (
            "require_no_blockers",
            "require_all_modules_certified",
            "require_ready",
        ):
            if not isinstance(getattr(self, field), bool):
                raise ValidationError(f"{field} must be boolean")
        _text(self.content_address, "content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleCertificationQualityPolicyCheck:
    """One threshold decision with the observed and required values."""

    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        for field in ("check_id", "detail", "content_address"):
            _text(getattr(self, field), field)
        if not isinstance(self.passed, bool):
            raise ValidationError("quality policy check passed must be boolean")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleCertificationQualityGate:
    """Result of applying a policy to a quality report."""

    quality_address: str
    policy: ModuleCertificationQualityPolicy
    checks: tuple[ModuleCertificationQualityPolicyCheck, ...]
    passed_count: int
    failed_count: int
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.quality_address, "quality_address")
        _text(self.content_address, "content_address")
        if self.passed_count < 0 or self.failed_count < 0:
            raise ValidationError("quality gate counts cannot be negative")
        if self.passed_count + self.failed_count != len(self.checks):
            raise ValidationError("quality gate check counts do not conserve checks")
        if not self.checks:
            raise ValidationError("quality gate requires checks")
        if tuple(item.check_id for item in self.checks) != tuple(
            sorted(item.check_id for item in self.checks)
        ):
            raise ValidationError("quality gate checks must be sorted")
        if len(self.checks) > MODULE_CERTIFICATION_QUALITY_POLICY_MAX_CHECKS:
            raise ValidationError("quality gate check limit exceeded")

    @property
    def check_count(self) -> int:
        return len(self.checks)

    def to_dict(self, *, include_checks: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "version": MODULE_CERTIFICATION_QUALITY_POLICY_VERSION,
            "boundary": MODULE_CERTIFICATION_QUALITY_POLICY_BOUNDARY,
            "quality_address": self.quality_address,
            "policy": self.policy.to_dict(),
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_checks:
            result["checks"] = [item.to_dict() for item in self.checks]
        return result


def address_module_certification_quality_policy(value: ModuleCertificationQualityPolicy) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return _address(body, "module-certification-quality-policy")


def address_module_certification_quality_policy_check(
    value: ModuleCertificationQualityPolicyCheck,
) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return _address(body, "module-certification-quality-policy-check")


__all__ = [
    "MODULE_CERTIFICATION_QUALITY_POLICY_BOUNDARY",
    "MODULE_CERTIFICATION_QUALITY_POLICY_MAX_CHECKS",
    "MODULE_CERTIFICATION_QUALITY_POLICY_MAX_LIMIT",
    "MODULE_CERTIFICATION_QUALITY_POLICY_VERSION",
    "ModuleCertificationQualityGate",
    "ModuleCertificationQualityPolicy",
    "ModuleCertificationQualityPolicyCheck",
    "address_module_certification_quality_policy",
    "address_module_certification_quality_policy_check",
]
