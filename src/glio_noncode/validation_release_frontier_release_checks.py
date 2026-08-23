"""Independent release-gate checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_compatibility import ValidationReleaseCompatibility
from .validation_release_frontier_integrity import ValidationReleaseIntegrityReport
from .validation_release_frontier_quality_gate import ValidationReleaseQualityReport


@dataclass(frozen=True, slots=True)
class ValidationReleaseCheckReport:
    quality_passed: bool
    integrity_passed: bool
    compatibility_passed: bool
    passed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_validation_release_checks(quality: ValidationReleaseQualityReport, integrity: ValidationReleaseIntegrityReport, compatibility: ValidationReleaseCompatibility) -> ValidationReleaseCheckReport:
    body = {"quality_passed": quality.accepted, "integrity_passed": integrity.accepted, "compatibility_passed": compatibility.compatible, "passed": quality.accepted and integrity.accepted and compatibility.compatible}
    return ValidationReleaseCheckReport(**body, content_address=content_hash(body))


__all__ = ["ValidationReleaseCheckReport", "evaluate_validation_release_checks"]
