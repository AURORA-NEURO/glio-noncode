"""Local data-governance controls for case storage and export."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping

from .errors import PolicyViolation, ValidationError


class DataSensitivity(str, Enum):
    SYNTHETIC = "synthetic"
    PUBLIC = "public"
    INTERNAL = "internal"
    CONTROLLED = "controlled"
    RESTRICTED = "restricted"


class ExportTarget(str, Enum):
    LOCAL_REVIEW = "local_review"
    PUBLIC_ARTIFACT = "public_artifact"
    COLLABORATOR = "collaborator"
    EXTERNAL_SERVICE = "external_service"


@dataclass(frozen=True, slots=True)
class RetentionRule:
    """Retention and deletion semantics for an artifact class."""

    artifact_class: str
    sensitivity: DataSensitivity
    retention_days: int | None
    allow_public_export: bool
    delete_on_project_close: bool
    reason: str

    def __post_init__(self) -> None:
        if not self.artifact_class or not self.reason:
            raise ValidationError("retention rule requires an artifact class and reason")
        if self.retention_days is not None and self.retention_days < 1:
            raise ValidationError("retention_days must be positive or None")


@dataclass(frozen=True, slots=True)
class ProjectPolicy:
    """Project-level policy applied before persistence or export."""

    project_id: str
    rules: tuple[RetentionRule, ...]
    permitted_targets: tuple[ExportTarget, ...] = (ExportTarget.LOCAL_REVIEW,)
    network_egress_allowed: bool = False
    pseudonymization_required: bool = True
    policy_version: str = "local-policy-2026.08"

    def rule_for(self, artifact_class: str) -> RetentionRule:
        for rule in self.rules:
            if rule.artifact_class == artifact_class:
                return rule
        raise ValidationError(f"no retention rule for artifact class: {artifact_class}")


@dataclass(frozen=True, slots=True)
class ExportDecision:
    """Explain whether an artifact may cross a target boundary."""

    allowed: bool
    target: ExportTarget
    artifact_class: str
    sensitivity: DataSensitivity
    reasons: tuple[str, ...]
    policy_version: str

    def to_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "target": self.target.value,
            "artifact_class": self.artifact_class,
            "sensitivity": self.sensitivity.value,
            "reasons": list(self.reasons),
            "policy_version": self.policy_version,
        }


class LocalDataController:
    """Apply pseudonymization and export checks before data leaves a project."""

    _identifier = re.compile(r"[^A-Za-z0-9_.-]+")
    _sensitive_keys = {"name", "email", "phone", "address", "mrn", "dob", "date_of_birth"}

    def __init__(self, policy: ProjectPolicy) -> None:
        self.policy = policy

    def pseudonymize(self, value: str, *, namespace: str = "subject") -> str:
        """Create a stable project-local identifier without exposing the input."""

        if not value.strip():
            raise ValidationError("identifier must not be empty")
        digest = hashlib.sha256(f"{namespace}:{self.policy.project_id}:{value}".encode("utf-8")).hexdigest()
        return f"{namespace}-{digest[:20]}"

    def sanitize_metadata(self, metadata: Mapping[str, object]) -> dict[str, object]:
        """Drop direct identifiers and normalize remaining keys for local storage."""

        sanitized: dict[str, object] = {}
        for key, value in metadata.items():
            normalized_key = self._identifier.sub("_", str(key).strip().lower()).strip("_")
            if normalized_key in self._sensitive_keys:
                continue
            sanitized[normalized_key] = value
        return sanitized

    def decide_export(self, artifact_class: str, target: ExportTarget) -> ExportDecision:
        rule = self.policy.rule_for(artifact_class)
        reasons: list[str] = []
        allowed = True
        if target not in self.policy.permitted_targets:
            allowed = False
            reasons.append("target is not permitted by the project policy")
        if target == ExportTarget.PUBLIC_ARTIFACT and not rule.allow_public_export:
            allowed = False
            reasons.append("artifact rule does not allow public export")
        if target == ExportTarget.EXTERNAL_SERVICE and not self.policy.network_egress_allowed:
            allowed = False
            reasons.append("network egress is disabled")
        if not reasons:
            reasons.append("target and artifact rule are compatible")
        return ExportDecision(allowed, target, artifact_class, rule.sensitivity, tuple(reasons), self.policy.policy_version)

    def enforce_export(self, artifact_class: str, target: ExportTarget) -> ExportDecision:
        decision = self.decide_export(artifact_class, target)
        if not decision.allowed:
            raise PolicyViolation("; ".join(decision.reasons))
        return decision

    def validate_project_metadata(self, metadata: Mapping[str, object]) -> tuple[str, ...]:
        """Report likely direct identifiers without persisting them."""

        warnings: list[str] = []
        for key in metadata:
            normalized_key = str(key).strip().lower()
            if normalized_key in self._sensitive_keys:
                warnings.append(f"sensitive metadata key requires removal: {key}")
        return tuple(warnings)


def default_local_policy(project_id: str) -> ProjectPolicy:
    """Return a conservative policy for a new local research project."""

    return ProjectPolicy(
        project_id=project_id,
        rules=(
            RetentionRule("case_manifest", DataSensitivity.CONTROLLED, None, False, False, "case inputs remain under project control"),
            RetentionRule("research_dossier", DataSensitivity.INTERNAL, 3650, False, False, "reviewable research snapshot"),
            RetentionRule("synthetic_fixture", DataSensitivity.SYNTHETIC, None, True, False, "public reproducibility fixture"),
            RetentionRule("public_schema", DataSensitivity.PUBLIC, None, True, False, "interoperability contract"),
        ),
        permitted_targets=(ExportTarget.LOCAL_REVIEW, ExportTarget.COLLABORATOR),
        network_egress_allowed=False,
    )
